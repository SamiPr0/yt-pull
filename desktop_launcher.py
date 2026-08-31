"""Entry point for the packaged desktop build (see BUILD.md).

Starts the FastAPI app (`app.main`) on localhost only, then opens the user's
browser to the UI. Bundles its own ffmpeg so nothing needs to be installed
by the person running the .exe.

The UI (HTML/CSS/JS) is NOT the exe's job: it's hosted on GitHub Pages and
opened from there, so a frontend change is a `git push` and reaches every
already-distributed exe with no rebuild. The exe only ships the API — the
part that talks to YouTube from the user's own connection — and that API is
frozen at build time: nothing is ever fetched and executed at runtime, so a
compromised repo can't push code onto users' machines. A backend change does
need a new exe release.

If GitHub Pages is unreachable, we fall back to the copy of the UI frozen
into this exe and served from the local server itself.
"""
from __future__ import annotations

import os
import secrets
import sys
import threading
import time
import urllib.request
import webbrowser

PAGES_URL = "https://samipr0.github.io/yt-pull/app/"


def _resource_dir() -> str:
    """Directory PyInstaller extracts bundled files into at runtime,
    or the project root when running unfrozen (`python desktop_launcher.py`)."""
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def _prepend_bundled_ffmpeg_to_path() -> None:
    ffmpeg_dir = _resource_dir()
    if os.path.isfile(os.path.join(ffmpeg_dir, "ffmpeg.exe")):
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")


def _wait_for_local_server(base_url: str) -> None:
    for _ in range(100):  # ~20s max
        try:
            urllib.request.urlopen(base_url + "/api/health", timeout=0.5)
            return
        except Exception:
            time.sleep(0.2)


def _pick_ui_url(local_url: str) -> str:
    """Prefer the GitHub Pages UI; fall back to the frozen copy served by the
    local server if Pages can't be reached (offline, outage, blocked)."""
    try:
        urllib.request.urlopen(PAGES_URL, timeout=3)
        return PAGES_URL
    except Exception:
        return local_url


def _open_browser_when_ready(local_url: str, token: str) -> None:
    _wait_for_local_server(local_url)
    url = _pick_ui_url(local_url)
    # The Pages UI can only receive the launch token through the URL fragment
    # (the local fallback gets it injected server-side, so it doesn't need it
    # here — but appending it is harmless).
    webbrowser.open(f"{url}#t={token}")


def main() -> None:
    _prepend_bundled_ffmpeg_to_path()
    token = secrets.token_urlsafe(24)
    os.environ["YTPULL_TOKEN"] = token

    port = 8000
    local_url = f"http://127.0.0.1:{port}"

    print("yt-pull is starting...")
    print("Keep this window open while you use the app - close it to stop.")
    print(f"  App:                    {PAGES_URL}")
    print(f"  Offline / fallback UI:  {local_url}")

    threading.Thread(
        target=_open_browser_when_ready, args=(local_url, token), daemon=True
    ).start()

    import uvicorn

    from app.main import app

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
