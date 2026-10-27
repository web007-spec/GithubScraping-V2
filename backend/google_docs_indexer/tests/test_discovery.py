"""Discovery module tests."""

import pytest
from pathlib import Path

from app.crawler.discovery import (
    DiscoveryService,
    InMemoryDiscoverySource,
    UrlListDiscoverySource,
)


@pytest.mark.asyncio
async def test_in_memory_discovery_deduplicates():
    urls = [
        "https://docs.google.com/document/d/abc123/edit",
        "https://docs.google.com/document/d/abc123/view",
        "https://docs.google.com/document/d/xyz789/edit",
    ]
    service = DiscoveryService([InMemoryDiscoverySource(urls)])
    results = await service.discover_urls()
    assert len(results) == 2
    ids = {r[0] for r in results}
    assert ids == {"abc123", "xyz789"}


@pytest.mark.asyncio
async def test_url_list_discovery(tmp_path: Path):
    url_file = tmp_path / "urls.txt"
    url_file.write_text(
        "# comment\nhttps://docs.google.com/document/d/doc1/edit\n\n"
        "https://docs.google.com/document/d/doc2/edit\n",
        encoding="utf-8",
    )
    service = DiscoveryService([UrlListDiscoverySource(url_file)])
    results = await service.discover_urls()
    assert len(results) == 2
