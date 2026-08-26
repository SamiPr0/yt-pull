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
  --add-data "app/static;app/static" \
  --add-data "<path-to-ffmpeg.exe>;." \
  desktop_launcher.py
```

The result is `dist/yt-pull.exe` (~100-150 MB — Python, yt-dlp, and ffmpeg all bundled in). `build/` and `dist/` are gitignored; rebuild locally rather than committing the binary.

## Handing it to someone non-technical

- Send them just `dist/yt-pull.exe` (a file-sharing link, not email — it's too big to attach).
- Double-clicking it opens a console window (status/log) and their browser to the app, same UI as [yt-pull.onrender.com](https://yt-pull.onrender.com/).
- Windows SmartScreen will likely warn "unknown publisher" on first run (the exe isn't code-signed) — click **More info → Run anyway**. Not a sign of anything wrong, just what happens for any unsigned indie executable.
- Antivirus may occasionally flag PyInstaller-built exes as a false positive (malware also uses PyInstaller) — expected, not a real detection.
- Closing the console window stops the server.
