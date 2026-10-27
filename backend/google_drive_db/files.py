"""google_drive_files collection."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from google_drive_db.client import ensure_indexes, get_database, strip_mongo_id

TEXT_FIELDS = ("name", "raw_text", "search_text", "description")

LIST_SORT_FIELDS = {
    "indexed_at": "indexed_at",
    "name": "name",
    "word_count": "word_count",
    "created_at": "created_at",
}


def _build_excerpt(text: str | None, *, max_len: int = 240) -> str | None:
    if not text:
        return None
    cleaned = " ".join(str(text).split())
    if not cleaned:
        return None
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


def _public_list_item(doc: dict[str, Any]) -> dict[str, Any]:
    excerpt = doc.get("excerpt")
    if not excerpt:
        excerpt = _build_excerpt(doc.get("search_text") or doc.get("raw_text"))
    character_count = doc.get("character_count")
    raw = doc.get("raw_text") or doc.get("search_text") or ""
    if character_count is None and raw:
        character_count = len(str(raw))
    return {
        "id": doc.get("id"),
        "file_id": doc.get("file_id"),
        "folder_id": doc.get("folder_id"),
        "name": doc.get("name"),
        "mime_type": doc.get("mime_type"),
        "extension": doc.get("extension"),
        "size": doc.get("size"),
        "public_url": doc.get("public_url"),
        "word_count": doc.get("word_count"),
        "character_count": character_count,
        "excerpt": excerpt,
        "language": doc.get("language"),
        "categories": doc.get("categories") or [],
        "status": doc.get("status"),
        "indexed_at": doc.get("indexed_at"),
        "created_at": doc.get("created_at"),
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _col():
    ensure_indexes()
    return get_database().google_drive_files


def find_by_file_id(file_id: str) -> dict[str, Any] | None:
    return strip_mongo_id(_col().find_one({"file_id": file_id.strip()}))


def find_by_hash(sha256: str) -> dict[str, Any] | None:
    if not sha256:
        return None
    return strip_mongo_id(_col().find_one({"sha256": sha256}))


def upsert_file(payload: dict[str, Any]) -> dict[str, Any]:
    file_id = str(payload.get("file_id") or "").strip()
    if not file_id:
        raise ValueError("file_id required")
    col = _col()
    now = _now()
    existing = col.find_one({"file_id": file_id}, {"id": 1, "created_at": 1})
    doc = dict(payload)
    doc["file_id"] = file_id
    doc["updated_at"] = now
    if existing:
        doc.setdefault("id", existing.get("id"))
        doc.setdefault("created_at", existing.get("created_at") or now)
    else:
        doc.setdefault("id", str(uuid.uuid4()))
        doc.setdefault("created_at", now)
    raw = str(doc.get("raw_text") or "")
    if raw and not doc.get("search_text"):
        doc["search_text"] = raw[:8000]
    if not doc.get("word_count") and raw:
        doc["word_count"] = len(raw.split())
    if raw and not doc.get("character_count"):
        doc["character_count"] = len(raw)
    if raw and not doc.get("excerpt"):
        doc["excerpt"] = _build_excerpt(raw)
    lang = doc.get("language")
    if lang is None or not isinstance(lang, str):
        doc.pop("language", None)
    col.update_one({"file_id": file_id}, {"$set": doc}, upsert=True)
    return strip_mongo_id(col.find_one({"file_id": file_id})) or doc


def is_ready() -> bool:
    try:
        _col().estimated_document_count()
        return True
    except Exception:
        return False


def list_files(
    *,
    q: str = "",
    mime_type: str = "",
    extension: str = "",
    category: str = "",
    sort: str = "indexed_at",
    order: str = "desc",
    limit: int = 24,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    col = _col()
    query: dict[str, Any] = {"status": {"$ne": "failed"}}
    if mime_type:
        query["mime_type"] = mime_type
    if extension:
        query["extension"] = extension.lstrip(".").lower()
    if category:
        query["categories"] = {"$in": [category]}
    if q.strip():
        pattern = re.escape(q.strip())
        query["$or"] = [{field: {"$regex": pattern, "$options": "i"}} for field in TEXT_FIELDS]

    total = col.count_documents(query)
    sort_field = LIST_SORT_FIELDS.get(sort, "indexed_at")
    sort_dir = -1 if order.lower() != "asc" else 1
    cursor = (
        col.find(query)
        .sort(sort_field, sort_dir)
        .skip(max(0, offset))
        .limit(max(1, min(limit, 100)))
    )
    return [_public_list_item(strip_mongo_id(doc) or {}) for doc in cursor if doc], total


def get_public_file(file_id: str) -> dict[str, Any] | None:
    doc = find_by_file_id(file_id)
    if not doc or doc.get("status") == "failed":
        return None
    public = _public_list_item(doc)
    public["raw_text"] = doc.get("raw_text")
    return public


def get_stats() -> dict[str, Any]:
    col = _col()
    return {
        "total": col.count_documents({}),
        "indexed": col.count_documents({"status": "indexed"}),
        "failed": col.count_documents({"status": "failed"}),
        "with_text": col.count_documents({"raw_text": {"$nin": [None, ""]}}),
        "with_content": col.count_documents({"raw_text": {"$nin": [None, ""]}}),
    }
