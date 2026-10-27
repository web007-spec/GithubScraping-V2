"""Google documents collection — MongoDB."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from google_docs_db.client import ensure_indexes, get_database, strip_mongo_id
from outreach_db.text_search import (
    format_text_search,
    is_searchable_query,
    merge_text_rows,
    regex_pattern,
    text_score_boost,
)

SORT_FIELDS = {
    "crawled_at": "crawled_at",
    "created_at": "created_at",
    "title": "title",
    "word_count": "word_count",
    "character_count": "character_count",
}

# Indexed text fields + high-signal regex fields (no full clean_text regex — too noisy).
TEXT_SEARCH_FIELDS = ("title", "excerpt", "search_text", "headings")
REGEX_SEARCH_FIELDS = ("title", "headings", "shared_by_email", "excerpt")

DOC_LIST_PROJECTION = {
    "id": 1,
    "google_doc_id": 1,
    "url": 1,
    "title": 1,
    "excerpt": 1,
    "search_text": 1,
    "headings": 1,
    "clean_text": 1,
    "shared_by_email": 1,
    "word_count": 1,
    "character_count": 1,
    "language": 1,
    "preview_url": 1,
    "preview_image_url": 1,
    "status": 1,
    "crawled_at": 1,
    "content_archived_at": 1,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _col():
    ensure_indexes()
    return get_database().google_documents


def _regex_filter(needle: str, *, fields: tuple[str, ...] = REGEX_SEARCH_FIELDS) -> dict[str, Any]:
    pattern = regex_pattern(needle)
    if not pattern:
        return {}
    return {"$or": [{field: {"$regex": pattern, "$options": "i"}} for field in fields]}


def _fetch_text_documents(needle: str, *, limit: int) -> list[dict[str, Any]]:
    text_q = format_text_search(needle)
    if not text_q:
        return []
    col = _col()
    try:
        cursor = (
            col.find(
                {"status": "parsed", "$text": {"$search": text_q}},
                {**DOC_LIST_PROJECTION, "score": {"$meta": "textScore"}},
            )
            .sort([("score", {"$meta": "textScore"}), ("content_archived_at", -1)])
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


def _fetch_regex_documents(needle: str, *, limit: int) -> list[dict[str, Any]]:
    filt = _regex_filter(needle)
    if not filt:
        return []
    col = _col()
    query = {"status": "parsed", **filt}
    rows = [
        strip_mongo_id(doc) or {}
        for doc in col.find(query, DOC_LIST_PROJECTION).sort("content_archived_at", -1).limit(limit)
    ]
    return [row for row in rows if row]


def is_ready() -> bool:
    try:
        _col().estimated_document_count()
        return True
    except Exception:
        return False


def count(*, status: str | None = None, extra: dict[str, Any] | None = None) -> int:
    query: dict[str, Any] = dict(extra or {})
    if status:
        query["status"] = status
    return _col().count_documents(query)


def get_stats() -> dict[str, Any]:
    col = _col()
    return {
        "total": col.count_documents({}),
        "parsed": col.count_documents({"status": "parsed"}),
        "with_content": col.count_documents({"status": "parsed", "clean_text": {"$nin": [None, ""]}}),
        "with_images": col.count_documents({"status": "parsed", "images_count": {"$gt": 0}}),
    }


def get_by_doc_id(google_doc_id: str) -> dict[str, Any] | None:
    doc = _col().find_one({"google_doc_id": google_doc_id.strip()})
    return strip_mongo_id(doc)


def list_documents(
    *,
    q: str = "",
    status: str = "parsed",
    sort: str = "crawled_at",
    descending: bool = True,
    offset: int = 0,
    limit: int = 24,
) -> tuple[list[dict[str, Any]], int]:
    col = _col()
    query: dict[str, Any] = {}
    if status:
        query["status"] = status
    if q.strip():
        candidates = fetch_candidates_for_ranking(q, limit=min(200, offset + limit + 50))
        total = len(candidates)
        start = max(0, offset)
        end = start + max(1, min(limit, 100))
        return candidates[start:end], total

    sort_field = SORT_FIELDS.get(sort, "crawled_at")
    direction = -1 if descending else 1
    total = col.count_documents(query)
    cursor = col.find(query).sort(sort_field, direction).skip(max(0, offset)).limit(max(1, min(limit, 100)))
    return [strip_mongo_id(doc) for doc in cursor if doc], total


def search_documents(
    *,
    q: str,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    needle = q.strip()
    if not needle:
        return [], 0
    rows = fetch_candidates_for_ranking(needle, limit=min(200, offset + limit + 50))
    total = len(rows)
    start = max(0, offset)
    end = start + max(1, min(limit, 50))
    return rows[start:end], total


def fetch_candidates_for_ranking(q: str, *, limit: int = 120) -> list[dict[str, Any]]:
    """
    Accurate pre-filter: MongoDB $text index first, then tight field regex.
    Never pads with unrelated documents.
    """
    needle = q.strip()
    limit = max(1, min(limit, 200))
    if not needle or not is_searchable_query(needle):
        return []

    text_rows = _fetch_text_documents(needle, limit=limit)
    if len(text_rows) >= limit:
        return text_rows[:limit]

    regex_rows = _fetch_regex_documents(needle, limit=limit)
    return merge_text_rows(text_rows, regex_rows, limit=limit, id_field="google_doc_id")


def upsert_many(batch: list[dict[str, Any]]) -> int:
    if not batch:
        return 0
    col = _col()
    now = _now_iso()
    count = 0
    for payload in batch:
        doc_id = str(payload.get("google_doc_id") or "").strip()
        if not doc_id:
            continue
        existing = col.find_one({"google_doc_id": doc_id}, {"id": 1, "created_at": 1})
        update = dict(payload)
        update["updated_at"] = update.get("updated_at") or now
        if existing:
            update.setdefault("id", existing.get("id"))
            update.setdefault("created_at", existing.get("created_at") or now)
        else:
            update.setdefault("id", str(uuid.uuid4()))
            update.setdefault("created_at", now)
        col.update_one({"google_doc_id": doc_id}, {"$set": update}, upsert=True)
        count += 1
    return count
