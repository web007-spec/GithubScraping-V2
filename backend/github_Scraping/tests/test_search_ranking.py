"""Tests for local search ranking."""

from app.services.search_ranking import filter_relevant_hits, rank_documents, score_document


def test_title_exact_match_scores_highest() -> None:
    score, reason = score_document(
        "business plan",
        {"title": "Business Plan", "excerpt": "other", "headings": "", "clean_text": ""},
    )
    assert score >= 90
    assert "title" in reason.lower()


def test_rank_documents_filters_weak_matches() -> None:
    rows = [
        {"google_doc_id": "a", "title": "Business Plan Template"},
        {"google_doc_id": "b", "title": "Unrelated Notes", "excerpt": "cats and dogs"},
    ]
    ranked = rank_documents("business plan", rows, threshold=55)
    ids = [str(item["row"]["google_doc_id"]) for item in ranked]
    assert ids[0] == "a"
    assert "b" not in ids


def test_filter_relevant_hits_drops_noise() -> None:
    hits = [{"id": "a", "score": 90}, {"id": "b", "score": 42}]
    kept = filter_relevant_hits(hits, min_score=65)
    assert [h["id"] for h in kept] == ["a"]
