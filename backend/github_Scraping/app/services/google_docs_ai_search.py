"""LLM relevance ranking for Google Docs search — OpenAI-first, token-efficient."""

from __future__ import annotations

import logging
from typing import Any

from app.services.ai_search_core import (
    DOCS_RANKING_SYSTEM,
    ai_search_available,
    call_ranking_llm,
    compact_doc_for_llm,
    merge_ranked_hits,
    openai_search_configured,
    parse_doc_llm_hit,
    resolve_search_provider,
    search_settings,
    should_skip_llm,
    trim_for_llm,
)
from outreach_db.text_search import is_searchable_query
from app.services.google_docs import _build_snippet, fetch_candidates_for_ranking
from app.services.search_ranking import filter_relevant_hits, rank_documents

log = logging.getLogger(__name__)

PREFILTER_LIMIT = 80
LOCAL_THRESHOLD = 55


def search_documents_ai(
    *,
    q: str,
    limit: int = 24,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int | None, dict[str, Any]]:
    """
    Database pre-filter → local exact ranking → optional OpenAI re-rank (top N only).
    """
    needle = q.strip()
    if not needle or not is_searchable_query(needle):
        return [], 0, {"mode": "keyword", "ai_available": ai_search_available()}

    limit = max(1, min(limit, 50))
    offset = max(0, offset)

    candidates = fetch_candidates_for_ranking(needle, limit=PREFILTER_LIMIT)
    if not candidates:
        return [], 0, {"mode": "ranked", "ai_available": ai_search_available(), "candidates": 0}

    by_id = {str(r.get("google_doc_id") or r.get("id")): r for r in candidates}
    local_ranked = rank_documents(needle, candidates, threshold=LOCAL_THRESHOLD)
    local_hits = [
        {
            "id": str(item["row"].get("google_doc_id") or item["row"].get("id")),
            "score": item["score"],
            "reason": item["reason"],
        }
        for item in local_ranked
    ]

    mode = "ranked"
    ai_error: str | None = None
    provider_used: str | None = None
    llm_candidates_sent = 0
    merged = local_hits

    if ai_search_available() and local_hits and not should_skip_llm(local_hits):
        top_local = trim_for_llm(local_hits)
        compact = []
        for hit in top_local:
            row = by_id.get(hit["id"])
            if row:
                compact.append(compact_doc_for_llm(row, local_score=int(hit["score"])))
        llm_candidates_sent = len(compact)
        llm_hits, provider_used, ai_error = call_ranking_llm(
            needle,
            compact,
            system_prompt=DOCS_RANKING_SYSTEM,
            parse_hit=parse_doc_llm_hit,
        )
        if llm_hits:
            merged = merge_ranked_hits(local_hits, llm_hits)
            mode = "ai"
    elif should_skip_llm(local_hits):
        log.info("Skipping OpenAI for docs search %r — high-confidence local match", needle[:60])

    min_score = search_settings()["min_result_score"]
    merged = filter_relevant_hits(merged, min_score=min_score)

    results: list[dict[str, Any]] = []
    for hit in merged:
        row = by_id.get(hit["id"])
        if not row:
            continue
        enriched = dict(row)
        enriched["relevance_score"] = int(hit["score"])
        enriched["ranking_reason"] = str(hit.get("reason") or "")
        enriched["snippet"] = enriched["ranking_reason"] or _build_snippet(row, needle)
        results.append(enriched)

    total = len(results)
    page = results[offset : offset + limit]
    meta: dict[str, Any] = {
        "mode": mode,
        "ai_available": ai_search_available(),
        "openai_configured": openai_search_configured(),
        "ai_provider": provider_used or resolve_search_provider(),
        "candidates": len(candidates),
        "llm_candidates": llm_candidates_sent,
        "ranked": total,
        "score_threshold": LOCAL_THRESHOLD,
        "min_result_score": min_score,
    }
    if ai_error and mode != "ai":
        meta["ai_error"] = ai_error
    return page, total, meta
