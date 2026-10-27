"""OpenAI-first AI search helpers — minimize API calls, maximize accuracy."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Callable

from app.config import get_settings
from app.services.ai_analysis import ai_providers_configured, call_llm_json

log = logging.getLogger(__name__)

_LLM_RANK_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_MAX_LLM_CACHE = 96

UNIFIED_RANKING_SYSTEM = """You rank search results for a workspace archive (GitHub users + Google Docs).

Input: user query and a short list of pre-filtered candidates (already keyword-matched locally).

Rules:
- Prefer EXACT and phrase keyword matches over vague semantic similarity.
- Score 0–100; only return items scoring 65+.
- Sort highest score first.
- Be strict: unrelated templates or generic docs score below 42.

Output JSON array only, no markdown:
[{"type":"user|doc","id":"login_or_google_doc_id","score":85,"reason":"one short sentence"}]"""

DOCS_RANKING_SYSTEM = """You rank Google Docs search results.

Input: user query and pre-filtered document candidates.

Rules:
- Prefer EXACT title/heading/phrase matches over loose topical similarity.
- Score 0–100; only return items scoring 62+.
- Sort highest score first.
- Be strict: boilerplate templates score below 40.

Output JSON array only:
[{"id":"google_doc_id","score":85,"reason":"one short sentence"}]"""


def search_settings() -> dict[str, Any]:
    s = get_settings()
    return {
        "provider": (s.ai_search_provider or "openai").strip().lower(),
        "llm_top_n": max(4, min(int(s.ai_search_llm_top_n or 14), 24)),
        "skip_llm_min_score": max(85, min(int(s.ai_search_skip_llm_min_score or 93), 100)),
        "cache_ttl_sec": max(60, int(s.ai_search_cache_ttl_sec or 600)),
        "min_result_score": max(55, min(int(s.ai_search_min_result_score or 65), 100)),
        "max_tokens": 900,
    }


def openai_search_configured() -> bool:
    return bool((get_settings().openai_api_key or "").strip())


def ai_search_available() -> bool:
    providers = ai_providers_configured()
    cfg = search_settings()
    if cfg["provider"] == "openai":
        return providers.get("openai", False)
    if cfg["provider"] == "gemini":
        return providers.get("gemini", False)
    return bool(providers.get("openai") or providers.get("gemini"))


def resolve_search_provider() -> str | None:
    """OpenAI first when configured (default for search)."""
    providers = ai_providers_configured()
    cfg = search_settings()
    mode = cfg["provider"]
    if mode == "openai":
        return "openai" if providers.get("openai") else None
    if mode == "gemini":
        return "gemini" if providers.get("gemini") else None
    # auto: OpenAI preferred for search accuracy
    if providers.get("openai"):
        return "openai"
    if providers.get("gemini"):
        return "gemini"
    return None


def should_skip_llm(local_hits: list[dict[str, Any]]) -> bool:
    """Skip OpenAI when local ranking already found a near-exact match."""
    if not local_hits:
        return True
    best = max(int(hit.get("score", 0)) for hit in local_hits)
    return best >= search_settings()["skip_llm_min_score"]


def trim_for_llm(local_hits: list[dict[str, Any]], *, limit: int | None = None) -> list[dict[str, Any]]:
    cap = limit or search_settings()["llm_top_n"]
    return sorted(local_hits, key=lambda item: int(item.get("score", 0)), reverse=True)[:cap]


def compact_user_for_llm(row: dict[str, Any], *, local_score: int = 0) -> dict[str, Any]:
    return {
        "t": "u",
        "id": str(row.get("login") or row.get("id") or "")[:64],
        "n": str(row.get("name") or "")[:80],
        "b": str(row.get("bio") or "")[:140],
        "e": str(row.get("email") or "")[:80],
        "l": str(row.get("location") or row.get("country") or "")[:60],
        "c": str(row.get("company") or "")[:60],
        "ls": local_score,
    }


def compact_doc_for_llm(row: dict[str, Any], *, local_score: int = 0) -> dict[str, Any]:
    headings = str(row.get("headings") or "")
    if headings and "|" in headings:
        headings = ", ".join(part.strip() for part in headings.split("|")[:3] if part.strip())
    return {
        "t": "d",
        "id": str(row.get("google_doc_id") or row.get("id") or "")[:64],
        "title": str(row.get("title") or "Untitled")[:100],
        "excerpt": str(row.get("excerpt") or "")[:160],
        "headings": headings[:120],
        "email": str(row.get("shared_by_email") or "")[:80],
        "ls": local_score,
    }


def _llm_cache_key(query: str, payload: list[dict[str, Any]]) -> str:
    ids = ",".join(sorted(str(item.get("id") or "") for item in payload))
    raw = f"{query.strip().lower()}|{ids}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _llm_cache_get(key: str) -> list[dict[str, Any]] | None:
    row = _LLM_RANK_CACHE.get(key)
    if not row:
        return None
    ts, payload = row
    if time.time() - ts > search_settings()["cache_ttl_sec"]:
        _LLM_RANK_CACHE.pop(key, None)
        return None
    return payload


def _llm_cache_set(key: str, payload: list[dict[str, Any]]) -> None:
    if len(_LLM_RANK_CACHE) >= _MAX_LLM_CACHE:
        oldest = min(_LLM_RANK_CACHE.items(), key=lambda item: item[1][0])[0]
        _LLM_RANK_CACHE.pop(oldest, None)
    _LLM_RANK_CACHE[key] = (time.time(), payload)


def call_ranking_llm(
    query: str,
    compact_payload: list[dict[str, Any]],
    *,
    system_prompt: str,
    parse_hit: Callable[[dict[str, Any]], dict[str, Any] | None],
) -> tuple[list[dict[str, Any]], str | None, str | None]:
    """
    One OpenAI call (or configured provider) to re-rank a small candidate set.
    Returns (hits, provider_used, error).
    """
    if not compact_payload:
        return [], None, None

    cache_key = _llm_cache_key(query, compact_payload)
    cached = _llm_cache_get(cache_key)
    if cached is not None:
        return cached, resolve_search_provider(), None

    provider = resolve_search_provider()
    if not provider:
        return [], None, "No AI provider configured for search"

    user_msg = (
        f"Query:\n{query.strip()}\n\n"
        f"Candidates (t=u user, t=d doc; ls=local pre-score):\n"
        f"{json.dumps(compact_payload, ensure_ascii=False, separators=(',', ':'))}"
    )

    try:
        ranked_raw, used = call_llm_json(
            system_prompt,
            user_msg,
            provider=provider,
            max_tokens=search_settings()["max_tokens"],
            temperature=0.0,
        )
    except Exception as exc:
        log.warning("Search LLM ranking failed (%s): %s", provider, exc)
        return [], provider, str(exc)

    cleaned: list[dict[str, Any]] = []
    for item in ranked_raw:
        if not isinstance(item, dict):
            continue
        parsed = parse_hit(item)
        if parsed:
            cleaned.append(parsed)
    cleaned.sort(key=lambda item: int(item.get("score", 0)), reverse=True)
    _llm_cache_set(cache_key, cleaned)
    log.info(
        "Search LLM ranked %s hits for %r via %s (%s candidates)",
        len(cleaned),
        query[:60],
        used,
        len(compact_payload),
    )
    return cleaned, used, None


def parse_unified_llm_hit(item: dict[str, Any]) -> dict[str, Any] | None:
    kind = str(item.get("type") or item.get("t") or "").strip().lower()
    if kind in {"u", "user"}:
        kind = "user"
    elif kind in {"d", "doc"}:
        kind = "doc"
    item_id = str(item.get("id") or "").strip()
    try:
        score = int(item.get("score", 0))
    except (TypeError, ValueError):
        score = 0
    reason = str(item.get("reason") or "").strip()
    if kind not in {"user", "doc"} or not item_id or score < 65:
        return None
    return {"type": kind, "id": item_id, "score": score, "reason": reason}


def parse_doc_llm_hit(item: dict[str, Any]) -> dict[str, Any] | None:
    doc_id = str(item.get("id") or "").strip()
    try:
        score = int(item.get("score", 0))
    except (TypeError, ValueError):
        score = 0
    reason = str(item.get("reason") or "").strip()
    if not doc_id or score < 62:
        return None
    return {"id": doc_id, "score": score, "reason": reason}


def merge_ranked_hits(
    local: list[dict[str, Any]],
    llm: list[dict[str, Any]],
    *,
    keyed: bool = False,
) -> list[dict[str, Any]]:
    """Merge local + LLM scores; local exact matches are never demoted."""
    if keyed:
        by_key: dict[tuple[str, str], dict[str, Any]] = {}
        for hit in local:
            key = (str(hit["type"]), str(hit["id"]))
            by_key[key] = dict(hit)
        for hit in llm:
            key = (str(hit["type"]), str(hit["id"]))
            prev = by_key.get(key)
            if prev:
                prev["score"] = max(int(prev["score"]), int(hit["score"]))
                if hit.get("reason"):
                    prev["reason"] = hit["reason"]
            else:
                by_key[key] = dict(hit)
        merged = list(by_key.values())
        merged.sort(key=lambda item: int(item["score"]), reverse=True)
        return merged

    by_id: dict[str, dict[str, Any]] = {}
    for hit in local:
        item_id = str(hit.get("id") or "")
        if item_id:
            by_id[item_id] = dict(hit)
    for hit in llm:
        item_id = str(hit.get("id") or "")
        if not item_id:
            continue
        prev = by_id.get(item_id)
        if prev:
            prev["score"] = max(int(prev["score"]), int(hit["score"]))
            if hit.get("reason"):
                prev["reason"] = hit["reason"]
        else:
            by_id[item_id] = dict(hit)
    merged = list(by_id.values())
    merged.sort(key=lambda item: int(item["score"]), reverse=True)
    return merged
