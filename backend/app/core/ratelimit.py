"""Simple in-process sliding-window rate limiter.

Adequate for a single-instance deployment. For multi-instance deployments,
swap the backing store for Redis (the interface is intentionally small).
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.config import settings


class SlidingWindowLimiter:
    def __init__(self, max_per_minute: int) -> None:
        self.max = max_per_minute
        self.window = 60.0
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            dq = self._hits[key]
            while dq and dq[0] <= now - self.window:
                dq.popleft()
            if len(dq) >= self.max:
                return False
            dq.append(now)
            return True


_limiter = SlidingWindowLimiter(settings.rate_limit_per_minute)


def rate_limit(request: Request) -> None:
    """FastAPI dependency enforcing a per-client rate limit."""
    client = request.client.host if request.client else "unknown"
    key = f"{client}:{request.url.path}"
    if not _limiter.check(key):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again shortly.")
