"""Tests for DB-native crawl service."""

from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx

from app.services.csv_crawl_service import CsvCrawlService
from app.utils.csv_writer import CsvRow

SAMPLE_HTML = """
<html><head><title>Test Doc</title></head>
<body><h1>Hello</h1><p>World content here.</p>
<a href="https://example.com">link</a></body></html>
"""


@pytest.mark.asyncio
@respx.mock
async def test_csv_crawl_persists_parsed_doc(tmp_path: Path):
    url_file = tmp_path / "urls.txt"
    url_file.write_text(
        "https://docs.google.com/document/d/testdoc123/edit\n",
        encoding="utf-8",
    )
    export_url = "https://docs.google.com/document/d/testdoc123/export?format=html"
    respx.get(export_url).mock(return_value=httpx.Response(200, text=SAMPLE_HTML))

    saved: list[CsvRow] = []

    def capture(row: CsvRow) -> None:
        saved.append(row)

    with (
        patch("app.services.csv_crawl_service.require_db_storage"),
        patch("app.services.csv_crawl_service.persist_row", side_effect=capture),
        patch("app.services.csv_crawl_service.load_resume_state", return_value=([], set(), set())),
    ):
        service = CsvCrawlService()
        stats = await service.crawl_from_file(url_file)

    assert stats.parsed >= 1
    assert any(row.status == "parsed" and row.google_doc_id == "testdoc123" for row in saved)


@pytest.mark.asyncio
@respx.mock
async def test_csv_crawl_failed_doc(tmp_path: Path):
    url_file = tmp_path / "urls.txt"
    url_file.write_text(
        "https://docs.google.com/document/d/private456/edit\n",
        encoding="utf-8",
    )
    export_url = "https://docs.google.com/document/d/private456/export?format=html"
    respx.get(export_url).mock(return_value=httpx.Response(403, text="Forbidden"))

    saved: list[CsvRow] = []

    with (
        patch("app.services.csv_crawl_service.require_db_storage"),
        patch("app.services.csv_crawl_service.persist_row", side_effect=lambda row: saved.append(row)),
        patch("app.services.csv_crawl_service.load_resume_state", return_value=([], set(), set())),
    ):
        service = CsvCrawlService()
        stats = await service.crawl_from_file(url_file)

    assert stats.failed >= 1
    assert any(row.status == "failed" for row in saved)


@pytest.mark.asyncio
@respx.mock
async def test_csv_crawl_duplicate_detection(tmp_path: Path):
    url_file = tmp_path / "urls.txt"
    url_file.write_text(
        "https://docs.google.com/document/d/doc1/edit\n"
        "https://docs.google.com/document/d/doc2/edit\n",
        encoding="utf-8",
    )
    respx.get("https://docs.google.com/document/d/doc1/export?format=html").mock(
        return_value=httpx.Response(200, text=SAMPLE_HTML)
    )
    respx.get("https://docs.google.com/document/d/doc2/export?format=html").mock(
        return_value=httpx.Response(200, text=SAMPLE_HTML)
    )

    saved: list[CsvRow] = []

    with (
        patch("app.services.csv_crawl_service.require_db_storage"),
        patch("app.services.csv_crawl_service.persist_row", side_effect=lambda row: saved.append(row)),
        patch("app.services.csv_crawl_service.load_resume_state", return_value=([], set(), set())),
    ):
        service = CsvCrawlService()
        stats = await service.crawl_from_file(url_file)

    assert stats.crawled >= 2
    statuses = {row.status for row in saved}
    assert "parsed" in statuses
    assert "duplicate" in statuses or stats.duplicate >= 1
