"""Tests for Drive discovery helpers."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BACKEND))

from app.crawler.search_backends import _filter_drive_urls, _normalize_search_query
from app.services.query_builder import merge_query_sources, queries_for_categories
from app.utils.drive_ids import is_valid_drive_id


def test_is_valid_drive_id_rejects_junk():
    assert is_valid_drive_id("0B7jrEyvkmdl3WjhTREFMOGFGYWc")
    assert not is_valid_drive_id("x220B451Yjwt_acQWEpWVXZmbEFKbFU")
    assert not is_valid_drive_id("_gd")
    assert not is_valid_drive_id("u003d0-o7RWK0YRnwAtQMO7MuX9WQ")


def test_normalize_search_query_includes_docs():
    q = _normalize_search_query("resume template")
    assert "docs.google.com" in q


def test_filter_drive_urls_dedupes():
    urls = [
        "https://drive.google.com/drive/folders/abc123456789012345678901",
        "https://drive.google.com/drive/folders/abc123456789012345678901",
    ]
    assert len(_filter_drive_urls(urls)) == 1


def test_queries_for_categories_includes_labels():
    queries = queries_for_categories(["templates", "resumes"])
    assert any("resume" in q.lower() for q in queries)


def test_merge_query_sources_prefers_categories(tmp_path: Path):
    qfile = tmp_path / "queries.txt"
    qfile.write_text("public dataset folder\n", encoding="utf-8")
    merged = merge_query_sources(categories=["research_papers"], queries_file=qfile)
    assert "public dataset folder" not in merged
    assert len(merged) >= 2
