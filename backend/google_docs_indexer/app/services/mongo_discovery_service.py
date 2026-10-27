"""MongoDB discovery — register URLs from a file without crawling."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from app.config.settings import Settings, get_settings
from app.crawler.discovery import DiscoveryService, UrlListDiscoverySource
from app.services.document_store import is_db_storage_enabled, register_discovered_many, require_db_storage


async def run_discovery_db(
    settings: Settings | None = None,
    url_file: str | Path | None = None,
) -> tuple[int, int]:
    """
    Load URLs from a file and register them in the database.

    Returns (newly_registered, total_candidates).
    """
    require_db_storage()
    settings = settings or get_settings()
    file_path = Path(url_file) if url_file else settings.discovered_urls_file

    sources = [UrlListDiscoverySource(file_path)]
    discovery = DiscoveryService(sources)
    discovered = await discovery.discover_urls()
    registered = register_discovered_many(discovered)
    logger.info(
        "Loaded {} URLs from {}, registered {} in database",
        len(discovered),
        file_path,
        registered,
    )
    return registered, len(discovered)


def db_discovery_available() -> bool:
    return is_db_storage_enabled()
