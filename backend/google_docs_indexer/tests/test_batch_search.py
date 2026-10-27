"""Tests for batch search service."""

import pytest

from app.services.batch_search_service import BatchSearchService


def test_load_queries(tmp_path):
    qfile = tmp_path / "queries.txt"
    qfile.write_text("# comment\nresume\nbusiness plan\n\n# another\n", encoding="utf-8")
    queries = BatchSearchService.load_queries(qfile)
    assert queries == ["resume", "business plan"]


def test_generate_queries():
    queries = BatchSearchService.generate_queries(["resume"], ["template", "example"])
    assert "resume" in queries
    assert "resume template" in queries
    assert "resume example" in queries


def test_load_existing_ids(tmp_path):
    url_file = tmp_path / "urls.txt"
    url_file.write_text(
        "https://docs.google.com/document/d/abc123/edit\n"
        "https://docs.google.com/document/d/def456/edit\n",
        encoding="utf-8",
    )
    ids = BatchSearchService._load_existing_ids(url_file)
    assert ids == {"abc123", "def456"}
