"""Tests for accurate MongoDB candidate retrieval."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from outreach_db.text_search import format_text_search, merge_text_rows  # noqa: E402


def test_format_text_search_uses_phrase_for_multi_word() -> None:
    assert format_text_search("business plan") == '"business plan"'


def test_stopword_only_query_rejected() -> None:
    from outreach_db.text_search import is_searchable_query

    assert is_searchable_query("in") is False
    assert is_searchable_query("the plan") is True


def test_merge_text_rows_dedupes_by_id() -> None:
    rows = merge_text_rows(
        [{"google_doc_id": "a", "title": "A"}],
        [{"google_doc_id": "a", "title": "A2"}, {"google_doc_id": "b", "title": "B"}],
        limit=10,
        id_field="google_doc_id",
    )
    assert [r["google_doc_id"] for r in rows] == ["a", "b"]
