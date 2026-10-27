"""Tests for OpenAI-first search core helpers."""

from app.services.ai_search_core import should_skip_llm, trim_for_llm


def test_skip_llm_on_exact_local_match() -> None:
    hits = [{"id": "x", "score": 98, "reason": "Exact match in title"}]
    assert should_skip_llm(hits) is True


def test_trim_for_llm_limits_candidates() -> None:
    hits = [{"id": str(i), "score": i} for i in range(30)]
    trimmed = trim_for_llm(hits)
    assert len(trimmed) <= 14
    assert trimmed[0]["score"] == 29
