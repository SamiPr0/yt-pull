# Building the desktop version

Packages the app into a single `yt-pull.exe` that runs on any Windows PC with no Python, ffmpeg, or install step — double-click it, the browser opens to the same interface as the web version.

Why this exists: YouTube blocks datacenter IPs (Render, AWS, etc.) far more aggressively than home connections. Running on the end user's own machine sidesteps that entirely.

## Build it

```bash
pip install -r requirements-desktop.txt
```

Download a static Windows `ffmpeg.exe` (e.g. from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) or reuse one already installed on your machine), then:

```bash
pyinstaller --onefile --name yt-pull --console \
  --icon "app/static/favicon.ico" \
  --add-data "app/static;app/static" \
  --add-data "<path-to-ffmpeg.exe>;." \
  desktop_launcher.py
```

The result is `dist/yt-pull.exe` (~100-150 MB — Python, yt-dlp, and ffmpeg all bundled in). `build/` and `dist/` are gitignored; rebuild locally rather than committing the binary — it's also too big for a normal git push (GitHub's 100MB limit).

## Distributing it

The exe is too large to commit to the repo, so it's published as a **GitHub Release** asset instead (Releases allow up to 2GB, no size issue) — this requires the repo to be public, since a private repo's Releases are just as access-restricted as its code:

1. On GitHub → **Releases** → **Create a new release**.
2. Tag it (e.g. `v1.0`), give it a title, and **drag `dist/yt-pull.exe` into the assets area** — keep the filename exactly `yt-pull.exe`.
3. Publish. The landing page's download button already points at `https://github.com/<owner>/<repo>/releases/latest/download/yt-pull.exe`, which always resolves to whatever the latest release's asset is — no code change needed for future releases as long as the asset keeps that filename.

## Handing it to someone non-technical

- Point them at the site's download button, or send them `dist/yt-pull.exe` directly (a file-sharing link, not email — it's too big to attach).
- Double-clicking it opens a console window (status/log) and their browser to the full app.
- Windows SmartScreen will likely warn "unknown publisher" on first run (the exe isn't code-signed) — click **More info → Run anyway**. Not a sign of anything wrong, just what happens for any unsigned indie executable.
- Antivirus may occasionally flag PyInstaller-built exes as a false positive (malware also uses PyInstaller) — expected, not a real detection.
- Closing the console window stops the server.
