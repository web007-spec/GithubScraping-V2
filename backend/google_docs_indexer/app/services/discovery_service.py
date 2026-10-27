"""Discovery orchestration service."""

from pathlib import Path

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings, get_settings
from app.crawler.discovery import DiscoveryService, UrlListDiscoverySource
from app.database.repositories.document_repository import DocumentRepository


async def run_discovery(
    session: AsyncSession,
    settings: Settings | None = None,
    url_file: str | None = None,
) -> int:
    """
    Discover URLs and persist new documents.

    Returns count of newly discovered documents.
    """
    settings = settings or get_settings()
    file_path = Path(url_file) if url_file else settings.discovered_urls_file

    sources = [UrlListDiscoverySource(file_path)]
    discovery = DiscoveryService(sources)
    repo = DocumentRepository(session)

    discovered = await discovery.discover_urls()
    new_count = 0

    for google_doc_id, url in discovered:
        existing = await repo.get_by_google_doc_id(google_doc_id)
        if existing:
            if existing.url != url:
                logger.debug("Doc {} already exists with URL {}", google_doc_id, existing.url)
            continue

        existing_url = await repo.get_by_url(url)
        if existing_url:
            continue

        await repo.create_discovered(google_doc_id, url)
        new_count += 1

    await session.commit()
    logger.info("Registered {} new documents ({} total candidates)", new_count, len(discovered))
    return new_count
