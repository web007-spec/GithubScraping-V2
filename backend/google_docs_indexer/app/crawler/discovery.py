"""Discovery module for Google Docs URLs."""

from abc import ABC, abstractmethod
from pathlib import Path

from loguru import logger

from app.utils.url_utils import extract_google_doc_id, is_google_docs_url, normalize_google_docs_url


class DiscoverySource(ABC):
    """Abstract source of candidate Google Docs URLs."""

    @abstractmethod
    async def discover(self) -> list[str]:
        """Return raw candidate URLs."""


class UrlListDiscoverySource(DiscoverySource):
    """Load URLs from a text file (one URL per line)."""

    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path

    async def discover(self) -> list[str]:
        if not self._file_path.exists():
            logger.warning("URL list file not found: {}", self._file_path)
            return []

        urls: list[str] = []
        content = self._file_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            urls.append(line)
        logger.info("Loaded {} URLs from {}", len(urls), self._file_path)
        return urls


class InMemoryDiscoverySource(DiscoverySource):
    """Discovery from an in-memory list of URLs."""

    def __init__(self, urls: list[str]) -> None:
        self._urls = urls

    async def discover(self) -> list[str]:
        return list(self._urls)


class SearchApiDiscoverySource(DiscoverySource):
    """
    Placeholder for search API integration.

    Accepts pre-fetched search results; does not call external APIs directly
    unless configured with result payloads.
    """

    def __init__(self, results: list[str] | None = None) -> None:
        self._results = results or []

    async def discover(self) -> list[str]:
        return list(self._results)


class DiscoveryService:
    """Normalize and deduplicate discovered URLs."""

    def __init__(self, sources: list[DiscoverySource]) -> None:
        self._sources = sources

    async def discover_urls(self) -> list[tuple[str, str]]:
        """
        Discover and normalize URLs.

        Returns list of (google_doc_id, normalized_url) tuples, deduplicated.
        """
        seen_ids: set[str] = set()
        seen_urls: set[str] = set()
        results: list[tuple[str, str]] = []

        for source in self._sources:
            raw_urls = await source.discover()
            for raw in raw_urls:
                if not is_google_docs_url(raw):
                    logger.debug("Skipping non-Google-Docs URL: {}", raw)
                    continue

                normalized = normalize_google_docs_url(raw)
                if not normalized:
                    continue

                doc_id = extract_google_doc_id(normalized)
                if not doc_id:
                    continue

                if doc_id in seen_ids or normalized in seen_urls:
                    logger.debug("Skipping duplicate URL: {}", normalized)
                    continue

                seen_ids.add(doc_id)
                seen_urls.add(normalized)
                results.append((doc_id, normalized))

        logger.info("Discovered {} unique public candidate URLs", len(results))
        return results
