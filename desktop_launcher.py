"""Entry point for the packaged desktop build (see BUILD.md).

Starts the same FastAPI app used for the web version, on localhost only,
and opens the user's default browser to it. Bundles its own ffmpeg so
nothing needs to be installed by the person running the .exe.

Before starting, it also tries to pull the latest app/ source + static
assets straight from GitHub into a local cache and import from there
instead of the copy frozen into the exe at build time. That means a
plain code change (no new dependency, no new bundled binary) reaches
every already-distributed .exe on its next launch, with no rebuild.
If GitHub isn't reachable, it silently falls back to the version baked
into this exe — see _sync_app_from_github().

Trade-off worth knowing: this means a push to `main` on GitHub takes
effect for everyone immediately, not just on the next intentional
release — there's no staging step. Fine for a small personal tool with
one maintainer; would need a dedicated stable branch/tag for anything
bigger.
"""
from __future__ import annotations

import os
import shutil
import sys
import threading
import time
import webbrowser

GITHUB_RAW_BASE = "https://raw.githubusercontent.com/SamiPr0/yt-pull/main/"

APP_PY_FILES = [
    "app/__init__.py",
    "app/main.py",
    "app/downloader.py",
    "app/models.py",
    "app/i18n.py",
    "app/ratelimit.py",
]

APP_STATIC_FILES = [
    "app/static/index.html",
    "app/static/landing.html",
    "app/static/style.css",
    "app/static/app.js",
    "app/static/i18n.js",
    "app/static/favicon.svg",
    "app/static/favicon.ico",
    "app/static/og-image.png",
]


def _resource_dir() -> str:
    """Directory PyInstaller extracts bundled files into at runtime,
    or the project root when running unfrozen (`python desktop_launcher.py`)."""
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def _prepend_bundled_ffmpeg_to_path() -> None:
    ffmpeg_dir = _resource_dir()
    if os.path.isfile(os.path.join(ffmpeg_dir, "ffmpeg.exe")):
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")


def _cache_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = os.path.join(base, "yt-pull", "app_cache")
    os.makedirs(path, exist_ok=True)
    return path


def _fetch(rel_path: str, timeout: float) -> bytes:
    import urllib.request

    with urllib.request.urlopen(GITHUB_RAW_BASE + rel_path, timeout=timeout) as resp:
        return resp.read()


def _sync_app_from_github(per_file_timeout: float = 1.5) -> str | None:
    """Best-effort refresh of app/ from GitHub into a local cache.

    Returns the cache dir to import from if it ends up with a complete,
    usable set of .py files (freshly fetched or left over from an earlier
    successful run) — otherwise None, meaning "use the version frozen
    into this exe, don't touch sys.path". Never lets a network hiccup
    turn into a broken app: any single file that fails to fetch just
    keeps whatever was already cached from last time.
    """
    cache = _cache_dir()

    # Quick probe: if GitHub isn't reachable at all, don't wait through a
    # timeout for every single file — bail immediately and use the build
    # frozen into this exe.
    try:
        main_py = _fetch("app/main.py", per_file_timeout)
    except Exception:
        return cache if os.path.isfile(os.path.join(cache, "app", "main.py")) else None

    os.makedirs(os.path.join(cache, "app"), exist_ok=True)
    with open(os.path.join(cache, "app", "main.py"), "wb") as f:
        f.write(main_py)

    for rel in APP_PY_FILES:
        if rel == "app/main.py":
            continue
        dest = os.path.join(cache, *rel.split("/"))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        try:
            data = _fetch(rel, per_file_timeout)
            with open(dest, "wb") as f:
                f.write(data)
        except Exception:
            if not os.path.isfile(dest):
                return None  # incomplete cache and no fallback for this module — use the frozen build

    for rel in APP_STATIC_FILES:
        dest = os.path.join(cache, *rel.split("/"))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        try:
            data = _fetch(rel, per_file_timeout)
            with open(dest, "wb") as f:
                f.write(data)
        except Exception:
            if not os.path.isfile(dest):
                bundled = os.path.join(_resource_dir(), *rel.split("/"))
                if os.path.isfile(bundled):
                    shutil.copyfile(bundled, dest)

    return cache


def _open_browser_when_ready(url: str) -> None:
    import urllib.request

    for _ in range(100):  # ~20s max
        try:
            urllib.request.urlopen(url + "/api/health", timeout=0.5)
            break
        except Exception:
            time.sleep(0.2)
    webbrowser.open(url)


def main() -> None:
    _prepend_bundled_ffmpeg_to_path()
    os.environ["YTPULL_DESKTOP"] = "1"

    port = 8000
    url = f"http://127.0.0.1:{port}"

    print("yt-pull is starting...")

    cache_dir = _sync_app_from_github()
    if cache_dir:
        sys.path.insert(0, cache_dir)
        print("Loaded the latest app version from GitHub.")
    else:
        print("Couldn't reach GitHub - using the version built into this file.")

    print(f"If your browser doesn't open automatically, go to: {url}")
    print("To stop the program, just close this window.")

    threading.Thread(target=_open_browser_when_ready, args=(url,), daemon=True).start()

    import uvicorn

    from app.main import app

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
