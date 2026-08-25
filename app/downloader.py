"""Thin wrapper around yt-dlp: resolve link(s) to metadata, then pull one
video into an ephemeral temp directory on demand. Nothing here ever writes
outside of a per-request temp directory, and every temp directory is removed
as soon as it has been streamed to the client (see main.py).
"""
from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from yt_dlp import YoutubeDL

ALLOWED_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}

DEFAULT_QUALITY_LADDER = ["2160p", "1440p", "1080p", "720p", "480p", "360p"]


class InvalidUrlError(ValueError):
    pass


def assert_youtube_url(url: str) -> None:
    try:
        host = urlparse(url).hostname or ""
    except ValueError as exc:
        raise InvalidUrlError(f"URL invalide : {url}") from exc
    if host.lower() not in ALLOWED_HOSTS:
        raise InvalidUrlError(f"Seuls les liens YouTube sont acceptés : {url}")


def _thumbnail_of(entry: dict) -> str | None:
    if entry.get("thumbnail"):
        return entry["thumbnail"]
    thumbs = entry.get("thumbnails") or []
    return thumbs[-1]["url"] if thumbs else None


def resolve(urls: list[str]) -> list[dict]:
    """Expand a mix of single-video / playlist / batch links into a flat
    list of individually-downloadable video items. Never touches disk."""
    items: list[dict] = []

    for raw in urls:
        url = (raw or "").strip()
        if not url:
            continue

        try:
            assert_youtube_url(url)
        except InvalidUrlError as exc:
            items.append({"url": url, "error": str(exc)})
            continue

        try:
            with YoutubeDL(
                {"quiet": True, "no_warnings": True, "extract_flat": "in_playlist", "skip_download": True}
            ) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as exc:  # noqa: BLE001 - surface any extraction failure to the UI
            items.append({"url": url, "error": f"Impossible d'analyser ce lien : {exc}"})
            continue

        if info is None:
            items.append({"url": url, "error": "Aucune information trouvée pour ce lien."})
            continue

        if info.get("_type") == "playlist" or info.get("entries"):
            playlist_title = info.get("title") or "Playlist"
            for entry in info.get("entries") or []:
                if not entry:
                    continue
                video_id = entry.get("id")
                video_url = entry.get("url") or entry.get("webpage_url") or (
                    f"https://www.youtube.com/watch?v={video_id}" if video_id else None
                )
                if not video_url:
                    continue
                items.append(
                    {
                        "url": video_url,
                        "title": entry.get("title") or "Sans titre",
                        "thumbnail": _thumbnail_of(entry),
                        "duration": entry.get("duration"),
                        "uploader": entry.get("uploader") or entry.get("channel"),
                        "source_playlist": playlist_title,
                        "qualities": DEFAULT_QUALITY_LADDER,
                    }
                )
        else:
            try:
                with YoutubeDL(
                    {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True}
                ) as ydl2:
                    full = ydl2.extract_info(url, download=False) or info
            except Exception:  # noqa: BLE001 - fall back to the flat info we already have
                full = info

            heights = sorted(
                {
                    f.get("height")
                    for f in (full.get("formats") or [])
                    if f.get("height") and f.get("vcodec") not in (None, "none")
                },
                reverse=True,
            )
            qualities = [f"{h}p" for h in heights] or DEFAULT_QUALITY_LADDER

            items.append(
                {
                    "url": full.get("webpage_url") or url,
                    "title": full.get("title") or "Sans titre",
                    "thumbnail": _thumbnail_of(full),
                    "duration": full.get("duration"),
                    "uploader": full.get("uploader") or full.get("channel"),
                    "source_playlist": None,
                    "qualities": qualities,
                }
            )

    return items


def _format_selector(quality: str | None) -> str:
    if not quality or quality == "best":
        return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    match = re.match(r"(\d+)", quality)
    if not match:
        return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    height = match.group(1)
    return (
        f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]"
        f"/best[height<={height}][ext=mp4]/best[height<={height}]/best"
    )


def download_to_temp(url: str, quality: str | None) -> tuple[str, str, str]:
    """Download exactly one video into a fresh temp directory.

    Returns (filepath, filename, tmpdir). The caller MUST remove `tmpdir`
    once the response has been sent (see main.py's BackgroundTask).
    """
    assert_youtube_url(url)

    tmpdir = tempfile.mkdtemp(prefix="ytpull_")
    ydl_opts = {
        "format": _format_selector(quality),
        "outtmpl": str(Path(tmpdir) / "%(title).150B.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "windowsfilenames": True,
        "retries": 3,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)

        produced = sorted(Path(tmpdir).glob("*.mp4"))
        if not produced:
            produced = [p for p in Path(tmpdir).iterdir() if p.is_file()]
        if not produced:
            raise RuntimeError("Le téléchargement n'a produit aucun fichier.")

        filepath = produced[0]
        return str(filepath), filepath.name, tmpdir
    except Exception:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise


def cleanup(tmpdir: str) -> None:
    shutil.rmtree(tmpdir, ignore_errors=True)
