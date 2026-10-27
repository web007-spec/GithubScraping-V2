"""Async HTTP client with rate limiting and retries."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from app.settings import Settings


class RateLimitedSession:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._sem = asyncio.Semaphore(max(1, settings.max_concurrent_requests))
        self._delay = max(0.0, settings.request_delay_sec)
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> RateLimitedSession:
        timeout = aiohttp.ClientTimeout(total=120, connect=30)
        headers = {"User-Agent": self._settings.user_agent}
        self._session = aiohttp.ClientSession(timeout=timeout, headers=headers)
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._session:
            await self._session.close()

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise RuntimeError("Session not started")
        return self._session

    async def get_text(self, url: str) -> tuple[int, str]:
        return await self._request("GET", url, expect="text")

    async def get_bytes(self, url: str, *, max_bytes: int | None = None) -> tuple[int, bytes]:
        status, payload = await self._request("GET", url, expect="bytes", max_bytes=max_bytes)
        return status, payload  # type: ignore[return-value]

    async def head(self, url: str) -> int:
        status, _ = await self._request("HEAD", url, expect="none")
        return status

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=0.5, min=0.5, max=8))
    async def _request(
        self,
        method: str,
        url: str,
        *,
        expect: str,
        max_bytes: int | None = None,
    ) -> tuple[int, str | bytes | None]:
        async with self._sem:
            if self._delay:
                await asyncio.sleep(self._delay)
            assert self._session is not None
            async with self._session.request(method, url, allow_redirects=True) as resp:
                status = resp.status
                if expect == "none":
                    return status, None
                if expect == "text":
                    return status, await resp.text(errors="replace")
                data = bytearray()
                async for chunk in resp.content.iter_chunked(65536):
                    data.extend(chunk)
                    if max_bytes and len(data) > max_bytes:
                        raise ValueError(f"File exceeds max size ({max_bytes} bytes)")
                return status, bytes(data)
