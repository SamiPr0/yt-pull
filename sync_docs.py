"""Copy the frontend from app/static/ into docs/ for GitHub Pages.

Run this after any frontend change, then commit + push docs/ — the change
is live for every desktop user on their next launch, with no exe rebuild.

  python sync_docs.py

docs/            -> the landing page (advertises + links the .exe download);
                    hand-maintained, this script only refreshes its assets
docs/app/        -> the actual app UI, opened by the desktop exe from
                    https://<user>.github.io/yt-pull/app/ ; fully generated here

app/static/ stays the source of truth (it's what the exe freezes as an
offline fallback, and what Render serves). This script just mirrors it.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "app" / "static"
DOCS = ROOT / "docs"
DOCS_APP = DOCS / "app"

# Assets the app page needs, copied verbatim (none reference absolute paths).
APP_ASSETS = ["app.js", "style.css", "i18n.js", "favicon.svg", "favicon.ico", "og-image.png"]
# Assets the landing page needs (subset, same files).
LANDING_ASSETS = ["style.css", "i18n.js", "favicon.svg", "og-image.png"]


def _for_pages(html: str) -> str:
    """GitHub Pages serves this repo under /yt-pull/..., so root-absolute
    paths ("/style.css") resolve wrong. Make them relative."""
    return re.sub(r'(href|src)="/(?!/)', r'\1="', html)


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
