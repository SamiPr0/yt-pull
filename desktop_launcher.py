"""Entry point for the packaged desktop build (see BUILD.md).

Starts the same FastAPI app used for the web version, on localhost only,
and opens the user's default browser to it. Bundles its own ffmpeg so
nothing needs to be installed by the person running the .exe.
"""
from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser


def _resource_dir() -> str:
    """Directory PyInstaller extracts bundled files into at runtime,
    or the project root when running unfrozen (`python desktop_launcher.py`)."""
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def _prepend_bundled_ffmpeg_to_path() -> None:
    ffmpeg_dir = _resource_dir()
    if os.path.isfile(os.path.join(ffmpeg_dir, "ffmpeg.exe")):
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")


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

    port = 8000
    url = f"http://127.0.0.1:{port}"

    print("yt-pull demarre...")
    print(f"Si le navigateur ne s'ouvre pas tout seul, va sur : {url}")
    print("Pour arreter le programme, ferme simplement cette fenetre.")

    threading.Thread(target=_open_browser_when_ready, args=(url,), daemon=True).start()

    import uvicorn

    from app.main import app

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
