"""Copy the frontend from app/static/ into docs/ for GitHub Pages.

Run this after any frontend change, then commit + push docs/ — the change
is live for every desktop user on their next launch, with no exe rebuild.

  python sync_docs.py

docs/            -> the landing page (advertises + links the .exe download);
                    hand-maintained, this script only refreshes its assets
docs/app/        -> the actual app UI, opened by the desktop exe from
                    https://<user>.github.io/yt-pull/app/ ; fully generated here

app/static/ stays the source of truth (it's what the exe freezes as an
offline fallback). This script just mirrors it.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "app" / "static"
DOCS = ROOT / "docs"
DOCS_APP = DOCS / "app"

# Where GitHub Pages serves docs/app/ from. Used to make the link-preview
# meta tags absolute (social scrapers don't resolve relative image URLs).
APP_PAGES_URL = "https://samipr0.github.io/yt-pull/app/"

# Assets the app page needs, copied verbatim (none reference absolute paths).
APP_ASSETS = ["app.js", "style.css", "i18n.js", "favicon.svg", "favicon.ico", "og-image.png"]
# Assets the landing page needs (subset, same files).
LANDING_ASSETS = ["style.css", "i18n.js", "favicon.svg", "og-image.png"]


def _for_pages(html: str) -> str:
    """Adapt app/static/index.html for GitHub Pages:
    - root-absolute paths ("/style.css") resolve wrong under /yt-pull/, so
      make them relative;
    - og:image / twitter:image must be absolute URLs for link previews.
    """
    html = re.sub(r'(href|src)="/(?!/)', r'\1="', html)
    html = html.replace(
        'content="og-image.png"', f'content="{APP_PAGES_URL}og-image.png"'
    )
    html = html.replace(
        '<meta property="og:type" content="website" />',
        '<meta property="og:type" content="website" />\n'
        f'<meta property="og:url" content="{APP_PAGES_URL}" />',
        1,
    )
    return html


def main() -> None:
    DOCS_APP.mkdir(parents=True, exist_ok=True)

    for name in APP_ASSETS:
        shutil.copyfile(STATIC / name, DOCS_APP / name)
    for name in LANDING_ASSETS:
        shutil.copyfile(STATIC / name, DOCS / name)

    (DOCS_APP / "index.html").write_text(
        _for_pages((STATIC / "index.html").read_text(encoding="utf-8")),
        encoding="utf-8",
    )

    print("Synced app/static/ -> docs/app/ (and refreshed docs/ assets)")
    print("Next: git add docs && git commit && git push")


if __name__ == "__main__":
    main()
