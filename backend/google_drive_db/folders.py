"""google_drive_folders collection."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from google_drive_db.client import ensure_indexes, get_database, strip_mongo_id


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _col():
    ensure_indexes()
    return get_database().google_drive_folders


def upsert_folder(payload: dict[str, Any]) -> dict[str, Any]:
    folder_id = str(payload.get("folder_id") or "").strip()
    if not folder_id:
        raise ValueError("folder_id required")
    col = _col()
    now = _now()
    existing = col.find_one({"folder_id": folder_id}, {"id": 1, "created_at": 1})
    doc = dict(payload)
    doc["folder_id"] = folder_id
    doc["updated_at"] = now
    if existing:
        doc.setdefault("id", existing.get("id"))
        doc.setdefault("created_at", existing.get("created_at") or now)
    else:
        doc.setdefault("id", str(uuid.uuid4()))
        doc.setdefault("created_at", now)
    col.update_one({"folder_id": folder_id}, {"$set": doc}, upsert=True)
    return strip_mongo_id(col.find_one({"folder_id": folder_id})) or doc


def get_by_folder_id(folder_id: str) -> dict[str, Any] | None:
    return strip_mongo_id(_col().find_one({"folder_id": folder_id.strip()}))
