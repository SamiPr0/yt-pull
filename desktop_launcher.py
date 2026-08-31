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
import json
import os
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import quote

import webview


PAGES_UI_BASE = os.environ.get("YTPULL_UI_BASE") or "https://samipr0.github.io/yt-pull/app/"

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


_SINGLE_INSTANCE_HANDLE = None


def _is_only_instance() -> bool:
    """Race-free single-instance guard via a named mutex. A second launch
    would just fail to bind port 8000 and confuse things. The handle is kept
    for the process lifetime; Windows frees it automatically on exit/crash."""
    global _SINGLE_INSTANCE_HANDLE
    try:
        kernel32 = ctypes.windll.kernel32
        _SINGLE_INSTANCE_HANDLE = kernel32.CreateMutexW(None, False, "Local\\yt-pull-singleton")
        return kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS
    except Exception:
        return True  # never let the guard itself block startup


class _Cancelled(Exception):
    pass


def _clipboard_text() -> str:
    """Read the Windows clipboard as text. Done here rather than in JS
    because WebView2 gates navigator.clipboard.readText() behind a
    permission prompt this app doesn't wire up."""
    CF_UNICODETEXT = 13
    u, k = ctypes.windll.user32, ctypes.windll.kernel32
    u.GetClipboardData.restype = ctypes.c_void_p
    k.GlobalLock.restype = ctypes.c_void_p
    k.GlobalLock.argtypes = [ctypes.c_void_p]
    k.GlobalUnlock.argtypes = [ctypes.c_void_p]
    if not u.OpenClipboard(0):
        return ""
    try:
        if not u.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return ""
        handle = u.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        ptr = k.GlobalLock(handle)
        if not ptr:
            return ""
        try:
            return ctypes.wstring_at(ptr)
        finally:
            k.GlobalUnlock(handle)
    except Exception:
        return ""
    finally:
        u.CloseClipboard()


class _Api:
    """Exposed to the page as ``window.pywebview.api``. WebView2 silently
    drops blob / ``<a download>`` saves, so the desktop UI hands the download
    here instead: a native Save (or folder) dialog, then the mp4 is streamed
    from the local API straight to that path, with progress pushed back to
    ``window.__ytpullProgress``."""

    def __init__(self, base_url: str, token: str) -> None:
        self._base = base_url
        self._token = token
        self.window: object | None = None
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def clipboard(self) -> str:
        return _clipboard_text()

    def pick_folder(self):
        picked = self.window.create_file_dialog(webview.FOLDER_DIALOG)
        return picked[0] if picked else None

    def reveal(self, path: str) -> None:
        """Open the folder the file is in, with the file selected. `explorer
        /select` only parses correctly when passed as one raw command string
        (a quoted argv element breaks it); fall back to just opening the
        folder."""
        path = os.path.normpath(path)
        try:
            subprocess.run(f'explorer /select,"{path}"', check=False)
        except Exception:
            try:
                os.startfile(os.path.dirname(path) or ".")  # noqa: S606
            except Exception:
                pass

    def download(
        self,
        video_url: str,
        quality: str,
        lang: str,
        suggested_name: str,
        folder: str | None = None,
    ) -> dict:
        """`folder` set → save straight into it (batch); otherwise a Save As
        dialog. Returns {"path": ...} | {"cancelled": True} | {"error": ...}."""
        self._cancel = False
        if folder:
            dest = os.path.join(folder, suggested_name)
        else:
            picked = self.window.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename=suggested_name or "video.mp4",
                file_types=("MP4 video (*.mp4)", "All files (*.*)"),
            )
            if not picked:
                return {"cancelled": True}
            dest = picked if isinstance(picked, str) else picked[0]

        api_url = (
            f"{self._base}/api/download?url={quote(video_url, safe='')}"
            f"&quality={quote(quality or 'best')}&lang={quote(lang or 'en')}"
        )
        req = urllib.request.Request(api_url, headers={"X-YTPull-Token": self._token})
        try:
            with urllib.request.urlopen(req) as resp, open(dest, "wb") as out:
                total = int(resp.headers.get("Content-Length") or 0)
                got = 0
                while True:
                    if self._cancel:
                        raise _Cancelled
                    chunk = resp.read(262144)
                    if not chunk:
                        break
                    out.write(chunk)
                    got += len(chunk)
                    self._progress(got, total)
        except _Cancelled:
            self._discard(dest)
            return {"cancelled": True}
        except urllib.error.HTTPError as exc:
            self._discard(dest)
            try:
                return {"error": json.loads(exc.read()).get("detail") or f"HTTP {exc.code}"}
            except Exception:
                return {"error": f"HTTP {exc.code}"}
        except Exception as exc:  # noqa: BLE001
            self._discard(dest)
            return {"error": str(exc)}
        return {"path": dest}

    def _progress(self, got: int, total: int) -> None:
        try:
            self.window.evaluate_js(
                f"window.__ytpullProgress && window.__ytpullProgress({got},{total})"
            )
        except Exception:
            pass

    @staticmethod
    def _discard(path: str) -> None:
        try:
            os.remove(path)
        except OSError:
            pass


def main() -> None:
    # Before anything else, and before touching the shared log file.
    if not _is_only_instance():
        _error_box("yt-pull is already running.\n\nCheck for its window (or the taskbar).")
        os._exit(0)

    _redirect_output_to_logfile()
    print("yt-pull starting...")
    _prepend_bundled_ffmpeg_to_path()
    os.environ["YTPULL_UI_DIR"] = _sync_ui_from_pages()

    port = 8000
    url = f"http://127.0.0.1:{port}"
    token = secrets.token_urlsafe(24)
    os.environ["YTPULL_TOKEN"] = token

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

    api = _Api(url, token)
    try:
        window = webview.create_window(
            "yt-pull", url, js_api=api, width=1180, height=860, min_size=(900, 640)
        )
        api.window = window
        # storage_path pins the WebView2 user-data folder to one fixed
        # location instead of a fresh %TEMP%\tmp*/EBWebView per launch that
        # our os._exit() then leaves behind. private_mode stays default.
        webview.start(storage_path=os.path.join(_app_dir(), "webview"))  # blocks until closed
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
