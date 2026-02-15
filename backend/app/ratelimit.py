"""Per-IP sliding-window limiter for the endpoints that cost real work.

In-process and therefore per-replica. Fine for a single container; put a real
limiter in front of it (nginx, Cloudflare) if you scale out.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings

# Reads and event streams are cheap; only guard the expensive verbs.
GUARDED_PREFIXES = ("/api/info",)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _should_guard(self, request: Request) -> bool:
        path = request.url.path
        if path.startswith(GUARDED_PREFIXES):
            return True
        # Job creation, but not status polling or file fetches.
        return request.method == "POST" and path.rstrip("/") == "/api/jobs"

    async def dispatch(self, request: Request, call_next):
        if not self._should_guard(request):
            return await call_next(request)

        client = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if not client:
            client = request.client.host if request.client else "unknown"

        now = time.monotonic()
        window = settings.rate_limit_window_seconds
        bucket = self._hits[client]
        while bucket and now - bucket[0] > window:
            bucket.popleft()

        if len(bucket) >= settings.rate_limit_requests:
            retry_after = int(window - (now - bucket[0])) + 1
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down."},
                headers={"Retry-After": str(retry_after)},
            )

        bucket.append(now)
        if len(self._hits) > 10_000:  # keep the map from growing without bound
            for key in [k for k, v in self._hits.items() if not v]:
                self._hits.pop(key, None)
        return await call_next(request)
