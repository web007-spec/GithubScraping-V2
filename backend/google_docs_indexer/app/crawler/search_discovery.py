"""Web search discovery for public Google Docs URLs."""

from app.config.settings import Settings, get_settings
from app.crawler.discovery import DiscoverySource
from app.crawler.search_backends import search_all_backends
from loguru import logger


class WebSearchDiscoverySource(DiscoverySource):
    """Discover Google Docs by searching the web."""

    def __init__(
        self,
        query: str,
        max_results: int = 20,
        settings: Settings | None = None,
    ) -> None:
        self._user_query = query.strip()
        self._max_results = max_results
        self._settings = settings or get_settings()
        self._search_query = (
            self._user_query
            if "site:docs.google.com" in self._user_query
            else f"site:docs.google.com/document {self._user_query}"
        )

    @property
    def search_query(self) -> str:
        return self._search_query

    async def discover(self) -> list[str]:
        results = await search_all_backends(
            self._search_query,
            self._max_results,
            self._settings,
        )
        logger.info(
            "Web search discovered {} Google Docs URLs for '{}'",
            len(results),
            self._user_query,
        )
        return results
