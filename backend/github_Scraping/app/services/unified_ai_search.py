"""Unified AI search — GitHub users + Google Docs, OpenAI-first, minimal API usage."""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

from app.services.ai_search_core import (
    UNIFIED_RANKING_SYSTEM,
    ai_search_available,
    call_ranking_llm,
    compact_doc_for_llm,
    compact_user_for_llm,
    merge_ranked_hits,
    openai_search_configured,
    parse_unified_llm_hit,
    resolve_search_provider,
    search_settings,
    should_skip_llm,
    trim_for_llm,
)
from outreach_db.text_search import is_searchable_query
from app.services.database import use_mongodb
from app.services.google_docs import _build_snippet, fetch_candidates_for_ranking
from app.services.search_ranking import (
    filter_relevant_hits,
    rank_documents,
    rank_users,
)
from app.services.supabase_client import table_execute

log = logging.getLogger(__name__)

DOC_PREFILTER = 60
USER_PREFILTER = 60
LOCAL_THRESHOLD = 55

_RESULT_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_MAX_RESULT_CACHE = 64


def _result_cache_key(q: str) -> str:
    return hashlib.sha256(q.strip().lower().encode()).hexdigest()


def _result_cache_get(key: str) -> list[dict[str, Any]] | None:
    row = _RESULT_CACHE.get(key)
    if not row:
        return None
    ts, items = row
    if time.time() - ts > search_settings()["cache_ttl_sec"]:
        _RESULT_CACHE.pop(key, None)
        return None
    return items


def _result_cache_set(key: str, items: list[dict[str, Any]]) -> None:
    if len(_RESULT_CACHE) >= _MAX_RESULT_CACHE:
        oldest = min(_RESULT_CACHE.items(), key=lambda item: item[1][0])[0]
        _RESULT_CACHE.pop(oldest, None)
    _RESULT_CACHE[key] = (time.time(), items)


def _compact_doc(row: dict[str, Any]) -> dict[str, Any]:
    return compact_doc_for_llm(row)


def _compact_user(row: dict[str, Any]) -> dict[str, Any]:
    return compact_user_for_llm(row)


def _fetch_user_candidates_mongo(q: str, *, limit: int) -> list[dict[str, Any]]:
    from outreach_db.github_users_search import fetch_candidates_for_ranking as fetch_users

    return fetch_users(q, limit=max(1, min(limit, 80)))


def fetch_user_candidates(q: str, *, limit: int = USER_PREFILTER) -> list[dict[str, Any]]:
    needle = q.strip()
    if not needle:
        return []
    if use_mongodb():
        return _fetch_user_candidates_mongo(needle, limit=limit)

    safe = needle.replace(",", " ").replace("%", "")
    pattern = (
        f"login.ilike.%{safe}%,name.ilike.%{safe}%,bio.ilike.%{safe}%,"
        f"location.ilike.%{safe}%,email.ilike.%{safe}%,company.ilike.%{safe}%"
    )
    try:
        result = table_execute(
            lambda sb: sb.table("github_users")
            .select("id,login,name,bio,location,country,email,company,followers,avatar_url")
            .or_(pattern)
            .order("followers", desc=True)
            .limit(max(1, min(limit, 60)))
        )
        return result.data or []
    except Exception as exc:
        log.warning("User candidate fetch failed: %s", exc)
        return []


def _local_unified_rank(
    query: str,
    user_candidates: list[dict[str, Any]],
    doc_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for item in rank_users(query, user_candidates, threshold=LOCAL_THRESHOLD):
        row = item["row"]
        login = str(row.get("login") or row.get("id") or "")
        if login:
            hits.append({"type": "user", "id": login, "score": item["score"], "reason": item["reason"]})
    for item in rank_documents(query, doc_candidates, threshold=LOCAL_THRESHOLD):
        row = item["row"]
        doc_id = str(row.get("google_doc_id") or row.get("id") or "")
        if doc_id:
            hits.append({"type": "doc", "id": doc_id, "score": item["score"], "reason": item["reason"]})
    hits.sort(key=lambda item: item["score"], reverse=True)
    return hits


def _build_items_from_hits(
    ranked: list[dict[str, Any]],
    users_by_login: dict[str, dict[str, Any]],
    docs_by_id: dict[str, dict[str, Any]],
    needle: str,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for hit in ranked:
        if hit["type"] == "user":
            row = users_by_login.get(hit["id"])
            if not row:
                continue
            items.append(
                {
                    "type": "user",
                    "id": hit["id"],
                    "login": row.get("login"),
                    "name": row.get("name"),
                    "bio": row.get("bio"),
                    "location": row.get("location") or row.get("country"),
                    "followers": row.get("followers"),
                    "avatar_url": row.get("avatar_url"),
                    "relevance_score": hit["score"],
                    "ranking_reason": hit["reason"],
                    "snippet": hit["reason"] or row.get("bio"),
                }
            )
        else:
            row = docs_by_id.get(hit["id"])
            if not row:
                continue
            enriched = dict(row)
            enriched["type"] = "doc"
            enriched["id"] = hit["id"]
            enriched["relevance_score"] = hit["score"]
            enriched["ranking_reason"] = hit["reason"]
            enriched["snippet"] = hit["reason"] or _build_snippet(row, needle)
            items.append(enriched)
    return items


def unified_ai_search(
    *,
    q: str,
    limit: int = 24,
    offset: int = 0,
) -> dict[str, Any]:
    needle = q.strip()
    limit = max(1, min(limit, 40))
    offset = max(0, offset)
    if not needle or not is_searchable_query(needle):
        return {"items": [], "total": 0, "query": needle, "mode": "keyword", "ai_available": ai_search_available()}

    cache_key = _result_cache_key(needle)
    cached_items = _result_cache_get(cache_key)
    if cached_items is not None:
        total = len(cached_items)
        return {
            "items": cached_items[offset : offset + limit],
            "total": total,
            "query": needle,
            "mode": "ai" if openai_search_configured() else "ranked",
            "ai_available": ai_search_available(),
            "cached": True,
            "page": offset // limit + 1,
            "page_size": limit,
        }

    doc_candidates = fetch_candidates_for_ranking(needle, limit=DOC_PREFILTER)
    user_candidates = fetch_user_candidates(needle, limit=USER_PREFILTER)

    if not doc_candidates and not user_candidates:
        return {
            "items": [],
            "total": 0,
            "query": needle,
            "mode": "ranked",
            "ai_available": ai_search_available(),
            "candidates": 0,
            "page": offset // limit + 1,
            "page_size": limit,
        }

    users_by_login = {str(r.get("login") or ""): r for r in user_candidates}
    docs_by_id = {str(r.get("google_doc_id") or r.get("id") or ""): r for r in doc_candidates}

    local_ranked = _local_unified_rank(needle, user_candidates, doc_candidates)
    ranked = local_ranked
    mode = "ranked"
    ai_error: str | None = None
    provider_used: str | None = None
    llm_candidates_sent = 0

    if ai_search_available() and local_ranked and not should_skip_llm(local_ranked):
        top_local = trim_for_llm(local_ranked)
        compact: list[dict[str, Any]] = []
        for hit in top_local:
            if hit["type"] == "user":
                row = users_by_login.get(hit["id"])
                if row:
                    compact.append(compact_user_for_llm(row, local_score=int(hit["score"])))
            else:
                row = docs_by_id.get(hit["id"])
                if row:
                    compact.append(compact_doc_for_llm(row, local_score=int(hit["score"])))
        llm_candidates_sent = len(compact)
        llm_hits, provider_used, ai_error = call_ranking_llm(
            needle,
            compact,
            system_prompt=UNIFIED_RANKING_SYSTEM,
            parse_hit=parse_unified_llm_hit,
        )
        if llm_hits:
            ranked = merge_ranked_hits(local_ranked, llm_hits, keyed=True)
            mode = "ai"
    elif should_skip_llm(local_ranked):
        log.info("Skipping OpenAI for unified search %r — high-confidence local match", needle[:60])

    min_score = search_settings()["min_result_score"]
    ranked = filter_relevant_hits(ranked, min_score=min_score)

    if not ranked:
        return {
            "items": [],
            "total": 0,
            "query": needle,
            "mode": mode,
            "ai_available": ai_search_available(),
            "ai_error": ai_error,
            "candidates": len(user_candidates) + len(doc_candidates),
            "min_result_score": min_score,
            "page": offset // limit + 1,
            "page_size": limit,
        }

    items = _build_items_from_hits(ranked, users_by_login, docs_by_id, needle)
    _result_cache_set(cache_key, items)
    total = len(items)
    payload = {
        "items": items[offset : offset + limit],
        "total": total,
        "query": needle,
        "mode": mode,
        "ai_available": ai_search_available(),
        "openai_configured": openai_search_configured(),
        "ai_provider": provider_used or resolve_search_provider(),
        "candidates": len(user_candidates) + len(doc_candidates),
        "llm_candidates": llm_candidates_sent,
        "ranked": total,
        "min_result_score": min_score,
        "users_prefiltered": len(user_candidates),
        "docs_prefiltered": len(doc_candidates),
        "page": offset // limit + 1,
        "page_size": limit,
        "cached": False,
    }
    if ai_error and mode != "ai":
        payload["ai_error"] = ai_error
    return payload
