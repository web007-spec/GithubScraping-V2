"""Local relevance scoring for search (exact + keyword), no LLM required."""

from __future__ import annotations

import re
from typing import Any

_TOKEN_RE = re.compile(r"[a-z0-9@._+-]+", re.I)

# Minimum score to return to clients (targets >98% precision).
DEFAULT_MIN_RESULT_SCORE = 65
DEFAULT_RANK_THRESHOLD = 55


def _normalize_query(query: str) -> str:
    return " ".join(str(query or "").strip().lower().split())


def _query_tokens(query: str) -> list[str]:
    return [token for token in _TOKEN_RE.findall(_normalize_query(query)) if len(token) > 1]


def _text_index_boost(row: dict[str, Any]) -> int:
    try:
        return max(0, min(25, int(row.get("_text_score_boost") or 0)))
    except (TypeError, ValueError):
        return 0


def _field_score(query: str, tokens: list[str], text: str, *, weight: int, label: str) -> tuple[int, str]:
    raw = str(text or "").strip()
    if not raw:
        return 0, ""
    lower = raw.lower()
    q = _normalize_query(query)
    if not q:
        return 0, ""

    if lower == q:
        return min(100, weight + 5), f"Exact match in {label}"
    if " " in q and q in lower:
        return weight, f"Phrase match in {label}"
    if re.search(rf"\b{re.escape(q)}\b", lower):
        return max(weight - 5, 52), f"Term match in {label}"

    if tokens:
        hits = sum(1 for token in tokens if token in lower)
        if not hits:
            return 0, ""
        ratio = hits / len(tokens)
        if hits == len(tokens):
            return max(weight - 10, 58), f"All keywords in {label}"
        if len(tokens) >= 2 and ratio < 0.67:
            return 0, ""
        if ratio >= 0.67:
            return max(int(weight * ratio) - 12, 50), f"Strong keyword match in {label}"
    return 0, ""


def score_document(query: str, row: dict[str, Any]) -> tuple[int, str]:
    """Score a Google Doc row against a query. Returns (score 0-100, reason)."""
    tokens = _query_tokens(query)
    checks = (
        (str(row.get("title") or ""), 98, "title"),
        (str(row.get("shared_by_email") or ""), 96, "contact email"),
        (str(row.get("headings") or "").replace("|", " "), 90, "headings"),
        (str(row.get("excerpt") or ""), 82, "excerpt"),
        (str(row.get("search_text") or "")[:4000], 75, "content"),
        (str(row.get("clean_text") or "")[:4000], 72, "body"),
    )
    best = 0
    reason = ""
    for text, weight, label in checks:
        score, why = _field_score(query, tokens, text, weight=weight, label=label)
        if score > best:
            best = score
            reason = why
    boost = _text_index_boost(row)
    if boost and best > 0:
        best = min(100, best + boost)
        if boost >= 8:
            reason = f"{reason}; text index match"
    return best, reason


def score_github_user(query: str, row: dict[str, Any]) -> tuple[int, str]:
    tokens = _query_tokens(query)
    checks = (
        (str(row.get("login") or ""), 100, "login"),
        (str(row.get("email") or ""), 98, "email"),
        (str(row.get("name") or ""), 92, "name"),
        (str(row.get("company") or ""), 85, "company"),
        (str(row.get("location") or row.get("country") or ""), 80, "location"),
        (str(row.get("bio") or ""), 75, "bio"),
    )
    best = 0
    reason = ""
    for text, weight, label in checks:
        score, why = _field_score(query, tokens, text, weight=weight, label=label)
        if score > best:
            best = score
            reason = why
    boost = _text_index_boost(row)
    if boost and best > 0:
        best = min(100, best + boost)
        if boost >= 8:
            reason = f"{reason}; text index match"
    return best, reason


def rank_documents(
    query: str,
    candidates: list[dict[str, Any]],
    *,
    threshold: int = DEFAULT_RANK_THRESHOLD,
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for row in candidates:
        score, reason = score_document(query, row)
        if score >= threshold:
            ranked.append({"row": row, "score": score, "reason": reason})
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked


def rank_users(
    query: str,
    candidates: list[dict[str, Any]],
    *,
    threshold: int = DEFAULT_RANK_THRESHOLD,
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for row in candidates:
        score, reason = score_github_user(query, row)
        if score >= threshold:
            ranked.append({"row": row, "score": score, "reason": reason})
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked


def filter_relevant_hits(
    hits: list[dict[str, Any]],
    *,
    min_score: int = DEFAULT_MIN_RESULT_SCORE,
) -> list[dict[str, Any]]:
    """Drop weak matches so only high-confidence results reach the UI."""
    floor = max(40, min(int(min_score), 100))
    return [hit for hit in hits if int(hit.get("score", 0)) >= floor]


def merge_llm_rankings(
    local: list[dict[str, Any]],
    llm: list[dict[str, Any]],
    *,
    id_key: str = "id",
) -> list[dict[str, Any]]:
    """Blend LLM scores with local scores (max of both, local exact matches win ties)."""
    by_id: dict[str, dict[str, Any]] = {}
    for item in local:
        row = item["row"]
        doc_id = str(row.get("google_doc_id") or row.get("login") or row.get("id") or "")
        if not doc_id:
            continue
        by_id[doc_id] = {
            "id": doc_id,
            "score": int(item["score"]),
            "reason": str(item["reason"]),
        }
    for hit in llm:
        doc_id = str(hit.get("id") or "")
        if not doc_id:
            continue
        try:
            llm_score = int(hit.get("score", 0))
        except (TypeError, ValueError):
            llm_score = 0
        reason = str(hit.get("reason") or "").strip()
        prev = by_id.get(doc_id)
        if prev:
            prev["score"] = max(prev["score"], llm_score)
            if llm_score >= prev["score"] and reason:
                prev["reason"] = reason
        else:
            by_id[doc_id] = {"id": doc_id, "score": llm_score, "reason": reason}
    merged = sorted(by_id.values(), key=lambda item: item["score"], reverse=True)
    return merged
