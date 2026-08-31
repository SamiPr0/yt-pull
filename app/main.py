import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask

from app import downloader, ratelimit
from app.i18n import t
from app.models import ResolveRequest

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# The desktop build refreshes the UI from GitHub Pages into a local cache and
# points us at it via YTPULL_UI_DIR; otherwise (dev, or the frozen fallback)
# we serve the copy bundled next to this file. Either way it's served from
# 127.0.0.1, same-origin with the API.
UI_DIR = Path(os.environ["YTPULL_UI_DIR"]) if os.environ.get("YTPULL_UI_DIR") else STATIC_DIR

# Per-launch secret the desktop launcher generates and injects into the page
# it serves. Every call to a work endpoint must echo it back in the
# X-YTPull-Token header. Together with the loopback-origin check below this
# stops another site (or another local process' web page) driving a running
# server: the origin check blocks ordinary cross-site fetches, and the token
# blocks the header-less `no-cors` variety. Unset for a plain `uvicorn` dev
# run — then only the origin check applies.
EXPECTED_TOKEN = os.environ.get("YTPULL_TOKEN") or None

app = FastAPI(title="yt-pull", docs_url="/api/docs")


def _guard(request: Request, lang: str | None = None) -> None:
    """Gate the work endpoints. A browser call carries an Origin (or at least
    a Referer); it must be a loopback address. A non-browser client (curl)
    carries neither and, if no token is configured, is left alone — it's the
    user's own machine."""
    origin = request.headers.get("origin") or request.headers.get("referer")
    if origin is not None and urlsplit(origin).hostname not in ("127.0.0.1", "localhost"):
        raise HTTPException(status_code=403, detail=t("cross_origin", lang))
    if EXPECTED_TOKEN and request.headers.get("x-ytpull-token") != EXPECTED_TOKEN:
        raise HTTPException(status_code=403, detail=t("cross_origin", lang))


@app.on_event("startup")
def _startup() -> None:
    downloader.cleanup_orphaned_temp_dirs()


@app.post("/api/resolve")
def resolve(payload: ResolveRequest, request: Request):
    """Expand one or more links (video / playlist / mixed batch) into a
    flat list of downloadable items with their available qualities."""
    lang = payload.lang
    _guard(request, lang)
    ratelimit.enforce(request, "resolve", max_requests=20, window_seconds=60, lang=lang)

    urls = [u for u in payload.urls if u and u.strip()]
    if not urls:
        raise HTTPException(status_code=400, detail=t("no_link", lang))
    if len(urls) > 25:
        raise HTTPException(status_code=400, detail=t("too_many_links", lang))
    return {"items": downloader.resolve(urls, lang)}


@app.get("/api/download")
def download(
    request: Request,
    url: str = Query(..., description="YouTube video link"),
    quality: str | None = Query(None, description="e.g. 1080p, 720p, best"),
    lang: str | None = Query(None, description="UI language for error messages, e.g. en, fr"),
):
    """Stream a single mp4 straight to the client. The temp file used to
    build it is deleted immediately after the response finishes sending —
    nothing is kept on the server afterwards."""
    _guard(request, lang)
    ratelimit.enforce(request, "download", max_requests=10, window_seconds=60, lang=lang)

    try:
        filepath, filename, tmpdir = downloader.download_to_temp(url, quality, lang)
    except downloader.InvalidUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=t("download_failed", lang, error=exc)) from exc

    return FileResponse(
        path=filepath,
        media_type="video/mp4",
        filename=filename,
        background=BackgroundTask(downloader.cleanup, tmpdir),
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    # Explicit route for the bare "/": StaticFiles(html=True) at "/" doesn't
    # reliably resolve it, and this is also where the launch token gets
    # injected into the page.
    html = (UI_DIR / "index.html").read_text(encoding="utf-8")
    if EXPECTED_TOKEN:
        tag = f"<script>window.__YTPULL_TOKEN__ = {json.dumps(EXPECTED_TOKEN)};</script>"
        html = html.replace("</head>", tag + "</head>", 1)
    return HTMLResponse(html)


# Serve the frontend's other assets (style.css, app.js, ...) last so /api/*
# and the explicit "/" route above take priority.
app.mount("/", StaticFiles(directory=UI_DIR), name="static")
