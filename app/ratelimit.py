"""Minimal in-memory per-IP rate limiter — no extra dependency, no external
service. Good enough to blunt casual spam/abuse of a single-instance
deployment; state resets on restart and isn't shared across instances."""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.i18n import t

_hits: dict[str, deque[float]] = defaultdict(deque)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce(
    request: Request,
    bucket: str,
    max_requests: int,
    window_seconds: int,
    lang: str | None = None,
) -> None:
    key = f"{bucket}:{client_ip(request)}"
    now = time.monotonic()
    hits = _hits[key]

    while hits and hits[0] <= now - window_seconds:
        hits.popleft()

    if len(hits) >= max_requests:
        raise HTTPException(status_code=429, detail=t("rate_limited", lang))

    hits.append(now)
