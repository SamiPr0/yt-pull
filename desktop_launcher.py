"""Entry point for the packaged desktop build (see BUILD.md).

Runs the FastAPI app (`app.main`) on localhost, then shows it in a native
window (pywebview / the Edge WebView2 runtime). Bundles its own ffmpeg so
nothing needs to be installed by the person running the .exe.

Before starting it pulls the latest **static** UI (HTML/CSS/JS) from GitHub
Pages into a local cache and points the server at it, so a frontend change
is a `git push` and reaches every installed exe on its next launch with no
rebuild. Only static assets are fetched — never Python — so a repo
compromise can't run code on users' machines; the worst case is a tampered
page, confined to the webview. If Pages is unreachable the server falls back
to the copy of the UI frozen into this exe.

The exe is built windowed (no console); status/errors go to
%LOCALAPPDATA%\\yt-pull\\log.txt, and fatal problems also raise a message box.
Backend changes (anything under `app/*.py`) still need a new exe release.
"""
from __future__ import annotations

import ctypes
import os
import secrets
import shutil
import sys
import threading
import time
import urllib.request

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

WEBVIEW2_HELP = (
    "yt-pull needs the Microsoft Edge WebView2 runtime, which doesn't seem "
    "to be installed on this PC.\n\n"
    "It's a free, small download from Microsoft:\n"
    "https://developer.microsoft.com/microsoft-edge/webview2/\n\n"
    "Install it (the \"Evergreen Standalone Installer\"), then start yt-pull "
    "again."
)


def _app_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = os.path.join(base, "yt-pull")
    os.makedirs(path, exist_ok=True)
    return path


def _redirect_output_to_logfile() -> None:
    """Windowed builds have no console; without this, anything writing to
    stdout/stderr (uvicorn, tracebacks) would crash on a None stream."""
    try:
        f = open(os.path.join(_app_dir(), "log.txt"), "w", encoding="utf-8", buffering=1)
        sys.stdout = f
        sys.stderr = f
    except Exception:
        pass


def _error_box(message: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(0, message, "yt-pull", 0x10)  # MB_ICONERROR
    except Exception:
        print(message)


def _resource_dir() -> str:
    """Directory PyInstaller extracts bundled files into at runtime,
    or the project root when running unfrozen (`python desktop_launcher.py`)."""
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def _prepend_bundled_ffmpeg_to_path() -> None:
    ffmpeg_dir = _resource_dir()
    if os.path.isfile(os.path.join(ffmpeg_dir, "ffmpeg.exe")):
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")


def _ui_cache_dir() -> str:
    path = os.path.join(_app_dir(), "ui_cache")
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


def _wait_for_local_server(url: str) -> bool:
    for _ in range(150):  # ~30s
        try:
            urllib.request.urlopen(url + "/api/health", timeout=0.5)
            return True
        except Exception:
            time.sleep(0.2)
    return False


def main() -> None:
    _redirect_output_to_logfile()
    _prepend_bundled_ffmpeg_to_path()
    os.environ["YTPULL_UI_DIR"] = _sync_ui_from_pages()
    os.environ["YTPULL_TOKEN"] = secrets.token_urlsafe(24)

    port = 8000
    url = f"http://127.0.0.1:{port}"
    print("yt-pull starting...")

    import uvicorn

    from app.main import app

    threading.Thread(
        target=lambda: uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning"),
        daemon=True,
    ).start()

    if not _wait_for_local_server(url):
        _error_box(
            "yt-pull couldn't start its local server.\n\n"
            f"See {os.path.join(_app_dir(), 'log.txt')} for details."
        )
        return

    try:
        import webview

        webview.create_window("yt-pull", url, width=1180, height=860, min_size=(900, 640))
        webview.start()  # blocks until the window is closed
    except Exception as exc:  # noqa: BLE001
        print(f"webview failed: {exc!r}")
        _error_box(WEBVIEW2_HELP)
        os._exit(1)

    # The window is closed. Hard-exit rather than returning: the uvicorn
    # thread and the hosted .NET/WebView2 runtime can otherwise keep the
    # process alive. Orphaned temp dirs (if a download was mid-flight) are
    # swept on the next launch.
    os._exit(0)


if __name__ == "__main__":
    main()
