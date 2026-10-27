"""Application users — stored in MongoDB (replaces Supabase Auth)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from outreach_db.client import ensure_indexes, get_database, strip_mongo_id


def _col():
    ensure_indexes()
    return get_database().auth_users


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_by_id(user_id: str) -> dict[str, Any] | None:
    doc = _col().find_one({"id": user_id})
    return strip_mongo_id(doc)


def get_by_email(email: str) -> dict[str, Any] | None:
    doc = _col().find_one({"email": email.strip().lower()})
    return strip_mongo_id(doc)


def list_all() -> list[dict[str, Any]]:
    cursor = _col().find({}).sort("email", 1)
    return [strip_mongo_id(doc) for doc in cursor if doc]


def create_user(
    *,
    email: str,
    password_hash: str,
    role: str = "admin",
    user_metadata: dict[str, Any] | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    now = _now_iso()
    doc = {
        "id": user_id or str(uuid.uuid4()),
        "email": email.strip().lower(),
        "password_hash": password_hash,
        "app_metadata": {"role": role},
        "user_metadata": dict(user_metadata or {}),
        "created_at": now,
        "updated_at": now,
    }
    _col().insert_one(doc)
    out = strip_mongo_id(doc) or doc
    out.pop("password_hash", None)
    return out


def update_user(user_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    patch = dict(patch)
    patch["updated_at"] = _now_iso()
    if "email" in patch and patch["email"]:
        patch["email"] = str(patch["email"]).strip().lower()
    _col().update_one({"id": user_id}, {"$set": patch})
    row = get_by_id(user_id)
    if row:
        row.pop("password_hash", None)
    return row


def set_password_hash(user_id: str, password_hash: str) -> None:
    update_user(user_id, {"password_hash": password_hash})
