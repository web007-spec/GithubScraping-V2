"""Async token-bucket rate limiter."""

import asyncio
import time


class RateLimiter:
    """Simple async rate limiter (requests per second)."""

    def __init__(self, rate: float) -> None:
        self._rate = max(rate, 0.1)
        self._interval = 1.0 / self._rate
        self._lock = asyncio.Lock()
        self._last_request = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self._interval - (now - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()
