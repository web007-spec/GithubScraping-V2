"""Downloader tests with HTTP mocking."""

import pytest
import httpx
import respx

from app.downloader.document_downloader import DocumentDownloader, _looks_like_login_page


@pytest.mark.asyncio
@respx.mock
async def test_download_success():
    doc_id = "test123"
    url = f"https://docs.google.com/document/d/{doc_id}/export?format=html"
    respx.get(url).mock(return_value=httpx.Response(200, text="<html><body>Public doc</body></html>"))

    async with DocumentDownloader() as dl:
        result = await dl.download(doc_id, fmt="html")

    assert result.error is None
    assert result.status_code == 200
    assert "Public doc" in str(result.content)


@pytest.mark.asyncio
@respx.mock
async def test_download_forbidden():
    doc_id = "private123"
    url = f"https://docs.google.com/document/d/{doc_id}/export?format=html"
    respx.get(url).mock(return_value=httpx.Response(403, text="Forbidden"))

    async with DocumentDownloader() as dl:
        result = await dl.download(doc_id, fmt="html")

    assert result.content is None
    assert "not publicly accessible" in (result.error or "").lower()


def test_login_page_detection():
    html = '<html><body>accounts.google.com ServiceLogin</body></html>'
    assert _looks_like_login_page(html) is True
    assert _looks_like_login_page("<html><body>Public content</body></html>") is False
