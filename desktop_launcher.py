"""Entry point for the packaged desktop build (see BUILD.md).

Starts the FastAPI app (`app.main`) on localhost only, then opens the user's
browser to it. Bundles its own ffmpeg so nothing needs to be installed by
the person running the .exe.

Before starting, it pulls the latest **static** UI (HTML/CSS/JS) from GitHub
Pages into a local cache and points the server at it, so a frontend change
is a `git push` and reaches every installed exe on its next launch with no
rebuild. Only static assets are fetched — never Python — so there is no way
for a repo compromise to run code on users' machines; the worst case is a
tampered page, which is confined to the browser sandbox. If Pages is
unreachable the server falls back to the copy of the UI frozen into this exe.

Backend changes (anything under `app/*.py`) still need a new exe release.
"""
from __future__ import annotations

import os
import secrets
import shutil
import sys
import threading
import time
import urllib.request
import webbrowser

PAGES_UI_BASE = "https://samipr0.github.io/yt-pull/app/"

UI_FILES = [
    "index.html",
    "app.js",
    "style.css",
    "i18n.js",
    "favicon.svg",
    "favicon.ico",
    "og-image.png",
]


def _resource_dir() -> str:
    """Directory PyInstaller extracts bundled files into at runtime,
    or the project root when running unfrozen (`python desktop_launcher.py`)."""
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def _prepend_bundled_ffmpeg_to_path() -> None:
    ffmpeg_dir = _resource_dir()
    if os.path.isfile(os.path.join(ffmpeg_dir, "ffmpeg.exe")):
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")


def _ui_cache_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = os.path.join(base, "yt-pull", "ui_cache")
    os.makedirs(path, exist_ok=True)
    return path


def _fetch(name: str, timeout: float) -> bytes:
    with urllib.request.urlopen(PAGES_UI_BASE + name, timeout=timeout) as resp:
        return resp.read()


def _sync_ui_from_pages() -> str:
    """Refresh the local UI cache from GitHub Pages (static files only).

    Any file that can't be fetched keeps its previous cached copy, or falls
    back to the one frozen into this exe. Always returns a usable directory.
    A failed first fetch is taken as "offline" — fall straight back to the
    frozen copy instead of timing out on every file.
    """
    cache = _ui_cache_dir()
    frozen = os.path.join(_resource_dir(), "app", "static")

    def use_frozen(name: str) -> None:
        dest = os.path.join(cache, name)
        if not os.path.isfile(dest):
            src = os.path.join(frozen, name)
            if os.path.isfile(src):
                shutil.copyfile(src, dest)

    try:
        first = _fetch(UI_FILES[0], 2.0)
    except Exception:
        for name in UI_FILES:
            use_frozen(name)
        return cache

    with open(os.path.join(cache, UI_FILES[0]), "wb") as f:
        f.write(first)
    for name in UI_FILES[1:]:
        try:
            data = _fetch(name, 2.0)
            with open(os.path.join(cache, name), "wb") as f:
                f.write(data)
        except Exception:
            use_frozen(name)
    return cache


def _open_browser_when_ready(url: str) -> None:
    for _ in range(100):  # ~20s max
        try:
            urllib.request.urlopen(url + "/api/health", timeout=0.5)
            break
        except Exception:
            time.sleep(0.2)
    webbrowser.open(url)


def main() -> None:
    _prepend_bundled_ffmpeg_to_path()
    os.environ["YTPULL_UI_DIR"] = _sync_ui_from_pages()
    os.environ["YTPULL_TOKEN"] = secrets.token_urlsafe(24)

    port = 8000
    url = f"http://127.0.0.1:{port}"

    print("yt-pull is starting...")
    print("Keep this window open while you use the app - close it to stop.")
    print(f"If your browser doesn't open automatically, go to: {url}")

    threading.Thread(target=_open_browser_when_ready, args=(url,), daemon=True).start()

    import uvicorn

    from app.main import app

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
