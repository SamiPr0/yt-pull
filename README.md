# yt-pull

Free YouTube downloader — paste a link, pick a quality, get an MP4. Works with single videos, full playlists, or a batch of links at once.

**Live: [yt-pull.onrender.com](https://yt-pull.onrender.com/)** *(free Render tier — may take ~30-50s to wake up if idle)*

## Features

- Single video, playlist, or a batch of links (one per line)
- Per-video quality picker, 2160p → 360p or best available
- Checkboxes to pick exactly which videos to download from a batch
- Live progress bar with ETA, cancel button, auto-cancel on page leave
- Nothing stored server-side — files stream through a temp folder deleted right after
- Per-IP rate limiting, no external dependency
- English/French UI, including API error messages — add a language by editing `app/static/i18n.js` and `app/i18n.py`

## Run it

```bash
docker compose up --build
```

Or without Docker (needs Python 3.11+ and [ffmpeg](https://ffmpeg.org/download.html) on your `PATH`):

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000).

## API

| Method | Route | Description |
|---|---|---|
| `POST` | `/api/resolve` | `{"urls": [...]}` → resolved video metadata (title, thumbnail, duration, available qualities). |
| `GET` | `/api/download?url=...&quality=1080p` | Streams a single `.mp4`. |
| `GET` | `/api/health` | Healthcheck. |

Rate limits: 20/min on `/api/resolve`, 10/min on `/api/download` — `429` past that.

## Disclaimer

Built on [`yt-dlp`](https://github.com/yt-dlp/yt-dlp), for personal/educational use. Respect YouTube's terms and the copyright of what you download.

## License

MIT — see [LICENSE](LICENSE).
