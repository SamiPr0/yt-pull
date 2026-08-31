import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask

from app import downloader, ratelimit
from app.i18n import t
from app.models import ResolveRequest

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# The desktop build serves its UI from GitHub Pages, which then calls this
# API back on 127.0.0.1. So browser calls to the work endpoints legitimately
# come from the Pages origin (or, as a fallback, the loopback server's own
# origin). Override the Pages origin with YTPULL_PAGES_ORIGIN if you fork.
PAGES_ORIGIN = os.environ.get("YTPULL_PAGES_ORIGIN", "https://samipr0.github.io")
ALLOWED_ORIGINS = {
    PAGES_ORIGIN,
    "http://127.0.0.1:8000",
    "http://localhost:8000",
}

# Per-launch secret the desktop launcher generates and hands to the UI (via a
# URL fragment for the Pages build, or injected into the HTML for the frozen
# fallback). Every call to a work endpoint must echo it back. This is what
# actually stops another site driving a running local server: the Origin/
# Referer check below is a cheap first filter but a determined attacker can
# suppress both headers, whereas they cannot read this token. Unset when you
# just run `uvicorn` locally — then only the Origin filter applies.
EXPECTED_TOKEN = os.environ.get("YTPULL_TOKEN") or None

app = FastAPI(title="yt-pull", docs_url="/api/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(ALLOWED_ORIGINS),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-YTPull-Token"],
    expose_headers=["Content-Disposition"],
)


def _guard(request: Request, lang: str | None = None) -> None:
    """Gate the work endpoints: reject browser calls from an untrusted site
    (Origin/Referer filter) and, when a launch token is configured, require
    it. A non-browser client (curl) sends no Origin/Referer and, if no token
    is configured, is left alone — it's the user's own loopback server."""
    origin = request.headers.get("origin")
    if origin is None:
        referer = request.headers.get("referer")
        if referer:
            parts = urlsplit(referer)
            origin = f"{parts.scheme}://{parts.netloc}"
    if origin is not None and origin not in ALLOWED_ORIGINS:
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
    # Serve the app UI. The desktop build normally opens the GitHub Pages
    # copy and only falls back here (offline / Pages outage); a local
    # `uvicorn` dev run hits this directly. Explicit route because
    # StaticFiles(html=True) at "/" doesn't reliably resolve the bare "/".
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    if EXPECTED_TOKEN:
        # Hand this fallback UI the same launch token the Pages UI gets via
        # its URL fragment, so a plain visit to 127.0.0.1:8000 works without
        # the token in the address bar.
        tag = f"<script>window.__YTPULL_TOKEN__ = {json.dumps(EXPECTED_TOKEN)};</script>"
        html = html.replace("</head>", tag + "</head>", 1)
    return HTMLResponse(html)


# Serve the frontend's other assets (style.css, app.js, ...) last so /api/*
# and the explicit "/" route above take priority.
app.mount("/", StaticFiles(directory=STATIC_DIR), name="static")
