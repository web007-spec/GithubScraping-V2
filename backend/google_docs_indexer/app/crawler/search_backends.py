"""Search backend implementations for discovering Google Docs URLs."""

import asyncio
import re
from abc import ABC, abstractmethod
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from bs4 import BeautifulSoup
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config.settings import Settings, get_settings
from app.utils.rate_limiter import RateLimiter
from app.utils.url_utils import extract_google_doc_id, is_google_docs_url

GOOGLE_DOC_URL_RE = re.compile(
    r"https?://docs\.google\.com/document/d/[a-zA-Z0-9_-]+(?:/[^\s\"'<>]*)?"
)


class SearchBackend(ABC):
    """Abstract web search backend."""

    name: str = "base"

    @abstractmethod
    async def search(self, query: str, max_results: int) -> list[str]:
        """Return candidate URLs from search results."""


def _filter_google_doc_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for url in urls:
        if not is_google_docs_url(url):
            continue
        doc_id = extract_google_doc_id(url)
        if not doc_id or doc_id in seen:
            continue
        seen.add(doc_id)
        results.append(f"https://docs.google.com/document/d/{doc_id}/edit")
    return results


class DdgsSearchBackend(SearchBackend):
    """Primary backend using the ddgs Python package (reliable)."""

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
        return _filter_google_doc_urls(urls)

    async def search(self, query: str, max_results: int) -> list[str]:
        try:
            urls = await asyncio.to_thread(self._search_sync, query, max_results)
            logger.info("DDGS returned {} URLs for: {}", len(urls), query[:60])
            return urls[:max_results]
        except Exception as exc:
            logger.warning("DDGS search failed for '{}': {}", query[:40], exc)
            return []


class DuckDuckGoHtmlSearchBackend(SearchBackend):
    """Fallback: scrape DuckDuckGo HTML results."""

    name = "ddg-html"
    SEARCH_URL = "https://html.duckduckgo.com/html/"
    RESULTS_PER_PAGE = 30

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._rate_limiter = RateLimiter(max(self._settings.rate_limit / 2, 0.5))

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8), reraise=True)
    async def _fetch_page(self, client: httpx.AsyncClient, query: str, offset: int = 0) -> str:
        await self._rate_limiter.acquire()
        data = {"q": query, "b": "", "kl": "us-en"}
        if offset > 0:
            data["s"] = str(offset)
            data["next"] = "1"
        response = await client.post(self.SEARCH_URL, data=data)
        response.raise_for_status()
        return response.text

    async def search(self, query: str, max_results: int) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        offset = 0

        async with httpx.AsyncClient(
            timeout=self._settings.download_timeout,
            headers={"User-Agent": self._settings.user_agent, "Accept": "text/html"},
            follow_redirects=True,
        ) as client:
            while len(urls) < max_results:
                html = await self._fetch_page(client, query, offset=offset)
                page_urls = _extract_urls_from_html(html)
                if not page_urls:
                    break
                for url in page_urls:
                    doc_id = extract_google_doc_id(url)
                    if doc_id and doc_id not in seen:
                        seen.add(doc_id)
                        urls.append(url)
                    if len(urls) >= max_results:
                        break
                offset += self.RESULTS_PER_PAGE
                if offset > max_results * 3:
                    break

        logger.info("DDG HTML returned {} URLs", len(urls))
        return urls[:max_results]


class GoogleCseSearchBackend(SearchBackend):
    """Google Custom Search JSON API (up to 100 results per query)."""

    name = "google-cse"
    API_URL = "https://www.googleapis.com/customsearch/v1"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._rate_limiter = RateLimiter(max(self._settings.rate_limit / 2, 0.5))

    async def search(self, query: str, max_results: int) -> list[str]:
        if not self._settings.google_cse_api_key or not self._settings.google_cse_id:
            return []

        urls: list[str] = []
        start = 1

        async with httpx.AsyncClient(timeout=self._settings.download_timeout) as client:
            while len(urls) < max_results and start <= 91:
                await self._rate_limiter.acquire()
                params = {
                    "key": self._settings.google_cse_api_key,
                    "cx": self._settings.google_cse_id,
                    "q": query,
                    "start": start,
                    "num": min(10, max_results - len(urls)),
                }
                response = await client.get(self.API_URL, params=params)
                response.raise_for_status()
                items = response.json().get("items", [])
                if not items:
                    break
                for item in items:
                    link = item.get("link", "")
                    if is_google_docs_url(link):
                        urls.append(link)
                start += 10

        return _filter_google_doc_urls(urls)[:max_results]


class BingSearchBackend(SearchBackend):
    """Bing Web Search API v7 (optional, high volume)."""

    name = "bing"
    API_URL = "https://api.bing.microsoft.com/v7.0/search"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._rate_limiter = RateLimiter(max(self._settings.rate_limit / 2, 0.5))

    async def search(self, query: str, max_results: int) -> list[str]:
        if not self._settings.bing_search_api_key:
            return []

        urls: list[str] = []
        offset = 0

        async with httpx.AsyncClient(timeout=self._settings.download_timeout) as client:
            while len(urls) < max_results and offset < 1000:
                await self._rate_limiter.acquire()
                response = await client.get(
                    self.API_URL,
                    headers={"Ocp-Apim-Subscription-Key": self._settings.bing_search_api_key},
                    params={"q": query, "count": min(50, max_results - len(urls)), "offset": offset},
                )
                response.raise_for_status()
                data = response.json()
                items = data.get("webPages", {}).get("value", [])
                if not items:
                    break
                for item in items:
                    link = item.get("url", "")
                    if is_google_docs_url(link):
                        urls.append(link)
                offset += 50

        return _filter_google_doc_urls(urls)[:max_results]


def build_backends(settings: Settings | None = None) -> list[SearchBackend]:
    """Return configured search backends in priority order."""
    settings = settings or get_settings()
    backends: list[SearchBackend] = []

    if settings.google_cse_api_key and settings.google_cse_id:
        backends.append(GoogleCseSearchBackend(settings))
    if settings.bing_search_api_key:
        backends.append(BingSearchBackend(settings))
    backends.append(DdgsSearchBackend(settings))
    backends.append(DuckDuckGoHtmlSearchBackend(settings))
    return backends


async def search_all_backends(
    query: str,
    max_results: int,
    settings: Settings | None = None,
) -> list[str]:
    """Try all backends until enough unique URLs are collected."""
    settings = settings or get_settings()
    normalized_query = query.strip()
    if normalized_query and "site:docs.google.com" not in normalized_query:
        normalized_query = f"site:docs.google.com/document {normalized_query}"
    seen: set[str] = set()
    results: list[str] = []

    for backend in build_backends(settings):
        if len(results) >= max_results:
            break
        try:
            found = await backend.search(normalized_query, max_results - len(results))
        except Exception as exc:
            logger.warning("{} failed: {}", backend.name, exc)
            continue

        for url in found:
            doc_id = extract_google_doc_id(url)
            if doc_id and doc_id not in seen:
                seen.add(doc_id)
                results.append(url)
            if len(results) >= max_results:
                break

        if results:
            logger.info(
                "Backend {} contributed; total {} URLs for query",
                backend.name,
                len(results),
            )

    return results


def _extract_urls_from_html(html: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()

    for match in GOOGLE_DOC_URL_RE.findall(html):
        url = _normalize_result_url(match)
        doc_id = extract_google_doc_id(url)
        if doc_id and doc_id not in seen:
            seen.add(doc_id)
            urls.append(url)

    soup = BeautifulSoup(html, "html.parser")
    for anchor in soup.find_all("a", href=True):
        resolved = _resolve_search_href(anchor["href"])
        if not resolved:
            continue
        doc_id = extract_google_doc_id(resolved)
        if doc_id and doc_id not in seen:
            seen.add(doc_id)
            urls.append(resolved)
    return urls


def _resolve_search_href(href: str) -> str | None:
    if href.startswith("//"):
        href = "https:" + href
    if "duckduckgo.com/l/" in href:
        uddg = parse_qs(urlparse(href).query).get("uddg", [])
        if uddg:
            return unquote(uddg[0])
    if is_google_docs_url(href):
        return href
    return None


def _normalize_result_url(url: str) -> str:
    doc_id = extract_google_doc_id(url)
    if doc_id:
        return f"https://docs.google.com/document/d/{doc_id}/edit"
    return url
