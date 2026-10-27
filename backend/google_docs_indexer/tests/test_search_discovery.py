"""Tests for web search discovery."""

import pytest
import respx
import httpx

from app.crawler.search_backends import _extract_urls_from_html, search_all_backends
from app.crawler.search_discovery import WebSearchDiscoverySource


SAMPLE_DDG_HTML = """
<html><body>
<a class="result__a" href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fdocs.google.com%2Fdocument%2Fd%2Fabc123XYZ%2Fedit">
Sample Doc Title
</a>
<a class="result__a" href="https://docs.google.com/document/d/def456/edit">Direct link</a>
</body></html>
"""


def test_extract_urls_from_ddg_html():
    urls = _extract_urls_from_html(SAMPLE_DDG_HTML)
    assert len(urls) == 2
    ids = {u.split("/d/")[1].split("/")[0] for u in urls}
    assert ids == {"abc123XYZ", "def456"}


@pytest.mark.asyncio
async def test_web_search_discovery_source_with_ddgs(monkeypatch):
    async def mock_search(query, max_results, settings=None):
        return [
            "https://docs.google.com/document/d/abc123/edit",
            "https://docs.google.com/document/d/def456/edit",
        ]

    monkeypatch.setattr(
        "app.crawler.search_discovery.search_all_backends",
        mock_search,
    )
    source = WebSearchDiscoverySource("resume template", max_results=10)
    urls = await source.discover()
    assert len(urls) == 2
