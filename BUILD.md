# Building the desktop version

Packages the app into a single `yt-pull.exe` that runs on any Windows PC with no Python, ffmpeg, or install step — double-click it, the browser opens to the app.

Why this exists: YouTube blocks datacenter IPs (Render, AWS, etc.) far more aggressively than home connections. Running on the end user's own machine sidesteps that entirely.

## How the split works

The exe runs the FastAPI app on `127.0.0.1:8000` and opens the browser there. On startup it pulls the **static UI** (`index.html`, `app.js`, `style.css`, `i18n.js`, favicons) from GitHub Pages (`https://<owner>.github.io/yt-pull/app/`) into `%LOCALAPPDATA%\yt-pull\ui_cache` and serves it from that local server — the browser only ever talks to localhost.

- **Frontend change** (HTML/CSS/JS, i18n, copy): run `python sync_docs.py`, commit `docs/`, push. Live for every already-distributed exe on its next launch — **no rebuild**.
- **Backend change** (`app/*.py`): rebuild the exe and cut a new Release. Rare — the API surface is small and stable.
- Only static files are ever fetched at runtime, never Python, so a repo compromise can't run code on users' machines. A tampered page is confined to the browser sandbox.
- The launcher generates a per-run secret token and `app.main` injects it into the page it serves; the API rejects any call to `/api/resolve` or `/api/download` whose `Origin`/`Referer` isn't loopback or that doesn't echo the token back — so another site (or another local app's page) can't drive a running server.
- If GitHub Pages is unreachable, the exe serves the copy of the UI frozen into it (`--add-data "app/static;app/static"`). Keep `sync_docs.py` runs and exe rebuilds roughly in step so that fallback isn't stale.

`app/static/` is the source of truth; `sync_docs.py` mirrors it into `docs/` (landing page assets) and `docs/app/` (the full app UI, generated).

## Build it

```bash
pip install -r requirements-desktop.txt
```

Download a static Windows `ffmpeg.exe` (e.g. from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) or reuse one already installed on your machine), then:

```bash
pyinstaller --onefile --name yt-pull --console --noupx \
  --icon "app/static/favicon.ico" \
  --version-file "version_info.txt" \
  --exclude-module watchfiles --exclude-module httptools --exclude-module websockets \
  --add-data "app/static;app/static" \
  --add-data "<path-to-ffmpeg.exe>;." \
  desktop_launcher.py
```

(A generated `yt-pull.spec` with these settings baked in is gitignored; `pyinstaller yt-pull.spec` reuses it — regenerate it with the command above if you change the flags.)

The result is `dist/yt-pull.exe` (~120-170 MB — Python, yt-dlp, and ffmpeg all bundled in). `build/` and `dist/` are gitignored; rebuild locally rather than committing the binary — it's also too big for a normal git push (GitHub's 100MB limit).

Notes on the flags:
- `--noupx`, `--version-file`, and the `--exclude-module` set are there to keep antivirus false positives (and size) down — see below. Don't drop them without reading that section.
- `--add-data "app/static;app/static"` is the offline fallback UI. Run `python sync_docs.py` before building so it matches what's on Pages.

## GitHub Pages setup (one time)

Repo **Settings → Pages → Deploy from a branch → `main` / `/docs`**. This serves:

- `https://<owner>.github.io/yt-pull/` — the landing page (`docs/index.html`)
- `https://<owner>.github.io/yt-pull/app/` — the app UI the exe fetches (`docs/app/`)

If your GitHub username isn't `SamiPr0`, update `PAGES_UI_BASE` in [`desktop_launcher.py`](desktop_launcher.py).

## Distributing it

The exe is too large to commit to the repo, so it's published as a **GitHub Release** asset instead (Releases allow up to 2GB, no size issue) — this requires the repo to be public, since a private repo's Releases are just as access-restricted as its code:

1. On GitHub → **Releases** → **Create a new release**.
2. Tag it (e.g. `v1.0`), give it a title, and **drag `dist/yt-pull.exe` into the assets area** — keep the filename exactly `yt-pull.exe`.
3. Publish. The landing page's download button already points at `https://github.com/<owner>/<repo>/releases/latest/download/yt-pull.exe`, which always resolves to whatever the latest release's asset is — no code change needed for future releases as long as the asset keeps that filename.

You only need a new Release for **backend** changes. Frontend changes ship through `sync_docs.py` + a push to `docs/`.

## Handing it to someone non-technical

- Point them at the site's download button, or send them `dist/yt-pull.exe` directly (a file-sharing link, not email — it's too big to attach).
- Double-clicking it opens a console window (status/log) and their browser to the full app. The address bar shows a `github.io` URL — that's the UI; the download work still happens on their PC. Needs an internet connection (as any YouTube download would).
- Windows SmartScreen will likely warn "unknown publisher" on first run (the exe isn't code-signed) — click **More info → Run anyway**. Not a sign of anything wrong, just what happens for any unsigned indie executable.
- Closing the console window stops the server.

## Antivirus false positives

A `--onefile` PyInstaller exe that isn't code-signed gets flagged by Windows Defender / SmartScreen / Chrome ("Virus detected", often named `Trojan:Win32/Wacatac.B!ml` or `Wacapew.C!ml`) fairly often. It's a heuristic/ML match on the shape of the binary — a bundle that unpacks itself to `%TEMP%` and runs its contents — not an analysis of what the code does. Nothing here is actually malicious.

Mitigations already applied in the build command / spec:

- **No UPX packing** (`--noupx`, `upx=False`). UPX is a top false-positive trigger.
- **Real version metadata** (`--version-file version_info.txt`). Bump the version numbers in that file each release.
- **`--exclude-module watchfiles httptools websockets`** — uvicorn's "standard" extras, unused by the launcher. `requirements.txt` also pins plain `uvicorn`, but the exclude is what matters on a machine that once installed `uvicorn[standard]` (PyInstaller bundles from the environment). `watchfiles` in particular ships a Rust binary that worsens heuristics.

If detections still happen:

1. **Submit the exe to Microsoft** as a false positive: <https://www.microsoft.com/en-us/wdsi/filesubmission> → "Software developer". Usually cleared within ~24-48h — but only for that exact build, so re-submit after each release (or sign it, below).
2. **Upload to [VirusTotal](https://www.virustotal.com/)** and link the result from the release notes / landing page, so users can see it's a couple of ML engines out of ~70, not a real detection.
3. **Code-sign the exe** — the durable fix, also kills the "unknown publisher" SmartScreen warning:
   - [SignPath.io Foundation](https://signpath.io) — free Authenticode signing for open-source projects.
   - Azure Trusted Signing — ~$10/mo, needs a verified identity.
   - A bought EV certificate (~€300-600/yr, hardware token) — instant SmartScreen trust, no reputation warm-up.
4. If it's still bad, switch to `--onedir` (a folder, not one self-extracting file) wrapped in an [Inno Setup](https://jrsoftware.org/isinfo.php) installer — installers carry more SmartScreen reputation than a loose exe.
