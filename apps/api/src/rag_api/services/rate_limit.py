"""In-memory sliding-window rate limiter (F12: 30/min site key; F11: 60/min API key)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from uuid import UUID


class SlidingWindowRateLimiter:
    def __init__(self, *, limit: int, window_s: float = 60.0) -> None:
        self.limit = limit
        self.window_s = window_s
        self._lock = threading.Lock()
        self._hits: dict[UUID, deque[float]] = defaultdict(deque)

    def allow(self, key_id: UUID) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_s
        with self._lock:
            q = self._hits[key_id]
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


# Module singletons for process-local limiting (tests can call .reset()).
widget_site_key_limiter = SlidingWindowRateLimiter(limit=30, window_s=60.0)
api_key_limiter = SlidingWindowRateLimiter(limit=60, window_s=60.0)
