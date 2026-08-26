from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask

from app import downloader, ratelimit
from app.models import ResolveRequest

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="yt-pull", docs_url="/api/docs")


@app.post("/api/resolve")
def resolve(payload: ResolveRequest, request: Request):
    """Expand one or more links (video / playlist / mixed batch) into a
    flat list of downloadable items with their available qualities."""
    ratelimit.enforce(request, "resolve", max_requests=20, window_seconds=60)

    urls = [u for u in payload.urls if u and u.strip()]
    if not urls:
        raise HTTPException(status_code=400, detail="No link provided.")
    if len(urls) > 25:
        raise HTTPException(status_code=400, detail="Maximum 25 links at once.")
    return {"items": downloader.resolve(urls)}


@app.get("/api/download")
def download(
    request: Request,
    url: str = Query(..., description="YouTube video link"),
    quality: str | None = Query(None, description="e.g. 1080p, 720p, best"),
):
    """Stream a single mp4 straight to the client. The temp file used to
    build it is deleted immediately after the response finishes sending —
    nothing is kept on the server afterwards."""
    ratelimit.enforce(request, "download", max_requests=10, window_seconds=60)

    try:
        filepath, filename, tmpdir = downloader.download_to_temp(url, quality)
    except downloader.InvalidUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Download failed: {exc}") from exc

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
    # Explicit route for the bare root: StaticFiles(html=True) mounted at "/"
    # fails to resolve the index on some Starlette versions when the request
    # path is exactly "/", so serve it directly instead of relying on that.
    return FileResponse(STATIC_DIR / "index.html")


# Serve the frontend's other assets (style.css, app.js, ...) last so /api/*
# and the explicit "/" route above take priority.
app.mount("/", StaticFiles(directory=STATIC_DIR), name="static")
