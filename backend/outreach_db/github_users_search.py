"""GitHub user search — MongoDB $text + precise field regex."""

from __future__ import annotations

from typing import Any

from outreach_db.client import get_database, strip_mongo_id
from outreach_db.text_search import (
    format_text_search,
    is_searchable_query,
    merge_text_rows,
    regex_pattern,
    text_score_boost,
)

USER_SEARCH_FIELDS = ("login", "name", "email", "bio", "location", "country", "company")
USER_LIST_PROJECTION = {
    "id": 1,
    "login": 1,
    "name": 1,
    "bio": 1,
    "location": 1,
    "country": 1,
    "email": 1,
    "company": 1,
    "followers": 1,
    "avatar_url": 1,
}


def _col():
    return get_database().github_users


def _regex_user_filter(needle: str) -> dict[str, Any]:
    pattern = regex_pattern(needle)
    if not pattern:
        return {}
    return {"$or": [{field: {"$regex": pattern, "$options": "i"}} for field in USER_SEARCH_FIELDS]}


def _fetch_text_users(needle: str, *, limit: int) -> list[dict[str, Any]]:
    text_q = format_text_search(needle)
    if not text_q:
        return []
    col = _col()
    try:
        cursor = (
            col.find(
                {"$text": {"$search": text_q}},
                {**USER_LIST_PROJECTION, "score": {"$meta": "textScore"}},
            )
            .sort([("score", {"$meta": "textScore"}), ("followers", -1)])
            .limit(limit)
        )
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for doc in cursor:
        row = strip_mongo_id(doc) or {}
        row["_text_score_boost"] = text_score_boost(doc.get("score"))
        rows.append(row)
    return rows


def _fetch_regex_users(needle: str, *, limit: int) -> list[dict[str, Any]]:
    filt = _regex_user_filter(needle)
    if not filt:
        return []
    col = _col()
    rows = [
        strip_mongo_id(doc) or {}
        for doc in col.find(filt, USER_LIST_PROJECTION).sort("followers", -1).limit(limit)
    ]
    return [row for row in rows if row]


def fetch_candidates_for_ranking(q: str, *, limit: int = 60) -> list[dict[str, Any]]:
    needle = q.strip()
    limit = max(1, min(limit, 80))
    if not needle or not is_searchable_query(needle):
        return []

    text_rows = _fetch_text_users(needle, limit=limit)
    if len(text_rows) >= limit:
        return text_rows[:limit]

    regex_rows = _fetch_regex_users(needle, limit=limit)
    return merge_text_rows(text_rows, regex_rows, limit=limit, id_field="login")
