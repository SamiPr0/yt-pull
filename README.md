# yt-pull

Free YouTube downloader — paste a link, pick a quality, get an MP4. Single videos, full playlists, or a batch of links at once.

**[Download for Windows](https://github.com/SamiPr0/yt-pull/releases/latest/download/yt-pull.exe)**  ·  **[Web page](https://samipr0.github.io/yt-pull/)**

The download always runs on your own machine — YouTube blocks datacenter IPs hard, home connections barely at all. The Windows app is a single file: double-click it, your browser opens, done. No install, no Python, no ffmpeg to set up. Build/release details in [BUILD.md](BUILD.md).

## Features

- Single video, playlist, or a batch of links (one per line)
- Per-video quality picker, 2160p → 360p or best available
- Checkboxes to pick exactly which videos to download from a batch
- Live progress bar with ETA, cancel button, auto-cancel on page leave
- Nothing is stored: each download streams through a temp folder deleted right after
- Per-IP rate limiting, no external dependency
- English/French UI, including API error messages — add a language by editing `app/static/i18n.js` and `app/i18n.py`

## How it's put together

There is no server to run. Two pieces:

- **UI** — static HTML/CSS/JS in `docs/`, hosted on **GitHub Pages**: the landing page at `/`, the app at `/app/`.
- **The work** — `app/` is a small FastAPI app (resolve links, download, mux with ffmpeg). It ships frozen inside `yt-pull.exe` and listens on `127.0.0.1` only. The GitHub Pages app calls that local API back; the browser is just the window.

A frontend change is a `git push` (run `python sync_docs.py` first) and reaches every installed exe on its next launch — **no rebuild**. Only a backend change needs a new exe release. See [BUILD.md](BUILD.md).

## Run the API locally (development)

Needs Python 3.11+ and [ffmpeg](https://ffmpeg.org/download.html) on your `PATH`.

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000) — you get the app UI served straight from the API, the same setup as the desktop build's offline fallback.

## API

| Method | Route | Description |
|---|---|---|
| `POST` | `/api/resolve` | `{"urls": [...]}` → resolved video metadata (title, thumbnail, duration, available qualities). |
| `GET` | `/api/download?url=...&quality=1080p` | Streams a single `.mp4`. |
| `GET` | `/api/health` | Healthcheck. |

Rate limits: 20/min on `/api/resolve`, 10/min on `/api/download` — `429` past that. The desktop build also requires an `Origin` from the app plus a per-launch `X-YTPull-Token` header (the UI sends it automatically); a plain local `uvicorn` run has no token and skips that check.

## Disclaimer

Built on [`yt-dlp`](https://github.com/yt-dlp/yt-dlp), for personal/educational use. Respect YouTube's terms and the copyright of what you download.

## License

MIT — see [LICENSE](LICENSE).
