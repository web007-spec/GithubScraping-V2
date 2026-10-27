"""Async document downloader."""

import time
from dataclasses import dataclass

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config.settings import Settings, get_settings
from app.utils.rate_limiter import RateLimiter
from app.utils.url_utils import build_export_url


@dataclass
class DownloadResult:
    """Result of a document download attempt."""

    url: str
    content: str | bytes | None
    content_type: str | None
    status_code: int | None
    error: str | None
    elapsed_ms: int
    format: str


class DocumentDownloader:
    """Download public Google Docs via export endpoints."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._rate_limiter = RateLimiter(self._settings.rate_limit)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "DocumentDownloader":
        limits = httpx.Limits(max_connections=100, max_keepalive_connections=50)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._settings.download_timeout),
            headers={"User-Agent": self._settings.user_agent},
            follow_redirects=True,
            limits=limits,
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _fetch(self, url: str) -> httpx.Response:
        await self._rate_limiter.acquire()
        assert self._client is not None
        response = await self._client.get(url)
        return response

    async def download_page(self, doc_id: str, suffix: str = "mobilebasic") -> DownloadResult:
        """Download a document view page (mobilebasic/edit) for metadata extraction."""
        url = f"https://docs.google.com/document/d/{doc_id}/{suffix}"
        start = time.perf_counter()
        try:
            response = await self._fetch(url)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            if response.status_code != 200:
                return DownloadResult(
                    url=url,
                    content=None,
                    content_type=response.headers.get("content-type"),
                    status_code=response.status_code,
                    error=f"HTTP {response.status_code}",
                    elapsed_ms=elapsed_ms,
                    format=suffix,
                )
            return DownloadResult(
                url=url,
                content=response.text,
                content_type=response.headers.get("content-type"),
                status_code=response.status_code,
                error=None,
                elapsed_ms=elapsed_ms,
                format=suffix,
            )
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return DownloadResult(
                url=url,
                content=None,
                content_type=None,
                status_code=None,
                error=str(exc),
                elapsed_ms=elapsed_ms,
                format=suffix,
            )

    async def download(
        self,
        doc_id: str,
        fmt: str = "html",
    ) -> DownloadResult:
        """Download document content in the given format."""
        url = build_export_url(doc_id, fmt)
        start = time.perf_counter()

        try:
            response = await self._fetch(url)
            elapsed_ms = int((time.perf_counter() - start) * 1000)

            if response.status_code == 401 or response.status_code == 403:
                return DownloadResult(
                    url=url,
                    content=None,
                    content_type=response.headers.get("content-type"),
                    status_code=response.status_code,
                    error="Document is not publicly accessible",
                    elapsed_ms=elapsed_ms,
                    format=fmt,
                )

            if response.status_code != 200:
                return DownloadResult(
                    url=url,
                    content=None,
                    content_type=response.headers.get("content-type"),
                    status_code=response.status_code,
                    error=f"HTTP {response.status_code}",
                    elapsed_ms=elapsed_ms,
                    format=fmt,
                )

            content_type = response.headers.get("content-type", "")
            if "pdf" in fmt or "pdf" in content_type:
                content: str | bytes = response.content
            else:
                content = response.text

            if isinstance(content, str) and _looks_like_login_page(content):
                return DownloadResult(
                    url=url,
                    content=None,
                    content_type=content_type,
                    status_code=response.status_code,
                    error="Authentication required - document is not public",
                    elapsed_ms=elapsed_ms,
                    format=fmt,
                )

            return DownloadResult(
                url=url,
                content=content,
                content_type=content_type,
                status_code=response.status_code,
                error=None,
                elapsed_ms=elapsed_ms,
                format=fmt,
            )

        except httpx.TimeoutException:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            logger.warning("Timeout downloading {}", url)
            return DownloadResult(
                url=url,
                content=None,
                content_type=None,
                status_code=None,
                error="Timeout",
                elapsed_ms=elapsed_ms,
                format=fmt,
            )
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            logger.exception("Error downloading {}: {}", url, exc)
            return DownloadResult(
                url=url,
                content=None,
                content_type=None,
                status_code=None,
                error=str(exc),
                elapsed_ms=elapsed_ms,
                format=fmt,
            )


def _looks_like_login_page(content: str) -> bool:
    """Detect Google login/permission pages in HTML responses."""
    markers = (
        "accounts.google.com",
        "ServiceLogin",
        "Sign in",
        "You need permission",
        "Request access",
    )
    lower = content[:5000].lower()
    return any(m.lower() in lower for m in markers)
