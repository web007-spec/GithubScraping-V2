"""Web search backends for discovering public Google Drive URLs."""

from __future__ import annotations

import asyncio
import re
from abc import ABC, abstractmethod
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from app.settings import Settings, get_settings
from app.utils.drive_ids import filter_valid_resources, is_valid_drive_id
from app.utils.drive_urls import extract_resource
from app.utils.rate_limiter import RateLimiter

DRIVE_URL_RE = re.compile(
    r"https?://(?:drive\.google\.com|docs\.google\.com)/[^\s\"'<>]+",
    re.IGNORECASE,
)


class SearchBackend(ABC):
    name: str = "base"

    @abstractmethod
    async def search(self, query: str, max_results: int) -> list[str]:
        """Return candidate Drive URLs from search results."""


def _filter_drive_urls(urls: list[str]) -> list[str]:
    return filter_valid_resources(urls)


def _normalize_search_query(query: str) -> str:
    raw = query.strip()
    if not raw:
        return raw
    lower = raw.lower()
    if any(token in lower for token in ("site:drive.google.com", "site:docs.google.com")):
        return raw
    # Prefer publicly exportable Google Docs + Drive files/folders.
    return f"(site:docs.google.com/document OR site:docs.google.com/spreadsheets OR site:drive.google.com) {raw}"


class DdgsSearchBackend(SearchBackend):
    name = "ddgs"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def _search_sync(self, query: str, max_results: int) -> list[str]:
        from ddgs import DDGS

        urls: list[str] = []
        with DDGS() as ddgs:
            for region in ("us-en", "wt-wt", None):
                try:
                    kwargs: dict = {"max_results": max_results}
                    if region:
                        kwargs["region"] = region
                    results = ddgs.text(query, **kwargs)
                    for item in results:
                        href = item.get("href") or item.get("link") or ""
                        if href:
                            urls.append(href)
                    if urls:
                        break
                except Exception as exc:
                    logger.debug("DDGS region {} failed: {}", region, exc)
        return _filter_drive_urls(urls)

    async def search(self, query: str, max_results: int) -> list[str]:
        try:
            urls = await asyncio.to_thread(self._search_sync, query, max_results)
            logger.info("DDGS returned {} Drive URLs for: {}", len(urls), query[:60])
            return urls[:max_results]
        except Exception as exc:
            logger.warning("DDGS search failed: {}", exc)
            return []


class HtmlSearchBackend(SearchBackend):
    """Fallback HTML scrape of DuckDuckGo lite results."""

    name = "html"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._limiter = RateLimiter(0.5)

    async def search(self, query: str, max_results: int) -> list[str]:
        await self._limiter.acquire()
        from urllib.parse import quote

        url = f"https://lite.duckduckgo.com/lite/?q={quote(query)}"
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": self._settings.user_agent},
                )
                response.raise_for_status()
                return _extract_urls_from_html(response.text)[:max_results]
        except Exception as exc:
            logger.warning("HTML search failed: {}", exc)
            return []


def get_search_backends(settings: Settings | None = None) -> list[SearchBackend]:
    settings = settings or get_settings()
    return [DdgsSearchBackend(settings), HtmlSearchBackend(settings)]


async def search_all_backends(
    query: str,
    max_results: int,
    settings: Settings | None = None,
) -> list[str]:
    settings = settings or get_settings()
    normalized = _normalize_search_query(query)
    seen: set[str] = set()
    results: list[str] = []

    for backend in get_search_backends(settings):
        try:
            found = await backend.search(normalized, max_results)
        except Exception as exc:
            logger.warning("{} failed: {}", backend.name, exc)
            continue

        for url in found:
            resource = extract_resource(url)
            if not resource or resource.resource_id in seen:
                continue
            seen.add(resource.resource_id)
            results.append(resource.url)
            if len(results) >= max_results:
                break

        if results:
            logger.info("Backend {} contributed; total {} URLs", backend.name, len(results))

    return results


def _extract_urls_from_html(html: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()

    for match in DRIVE_URL_RE.findall(html):
        resource = extract_resource(match)
        if resource and resource.resource_id not in seen:
            seen.add(resource.resource_id)
            urls.append(resource.url)

    soup = BeautifulSoup(html, "html.parser")
    for anchor in soup.find_all("a", href=True):
        resolved = _resolve_search_href(anchor["href"])
        if not resolved:
            continue
        resource = extract_resource(resolved)
        if resource and resource.resource_id not in seen:
            seen.add(resource.resource_id)
            urls.append(resource.url)
    return urls


def _resolve_search_href(href: str) -> str | None:
    if href.startswith("//"):
        href = "https:" + href
    if "duckduckgo.com/l/" in href:
        uddg = parse_qs(urlparse(href).query).get("uddg", [])
        if uddg:
            return unquote(uddg[0])
    if extract_resource(href):
        return href
    return None
