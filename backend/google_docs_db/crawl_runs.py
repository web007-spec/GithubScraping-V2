"""Google Docs crawl runs — MongoDB."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from google_docs_db.client import ensure_indexes, get_database, strip_mongo_id

ACTIVE_STATUSES = ("pending", "running", "stopping")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _col():
    ensure_indexes()
    return get_database().google_docs_crawl_runs


def is_ready() -> bool:
    try:
        _col().estimated_document_count()
        return True
    except Exception:
        return False


def fetch_run(run_id: str) -> dict[str, Any] | None:
    doc = _col().find_one({"id": run_id})
    return strip_mongo_id(doc)


def list_runs(limit: int = 20) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 100))
    cursor = _col().find({}).sort("created_at", -1).limit(limit)
    return [strip_mongo_id(doc) for doc in cursor if doc]


def get_active_run() -> dict[str, Any] | None:
    doc = (
        _col()
        .find({"status": {"$in": list(ACTIVE_STATUSES)}})
        .sort("created_at", -1)
        .limit(1)
    )
    for row in doc:
        return strip_mongo_id(row)
    return None


def insert_run(*, mode: str, config: dict[str, Any]) -> dict[str, Any]:
    now = _now_iso()
    run_id = str(uuid.uuid4())
    doc = {
        "id": run_id,
        "status": "pending",
        "mode": mode,
        "config": config,
        "log_lines": [],
        "current_phase": "pending",
        "discovered_count": 0,
        "crawled_count": 0,
        "parsed_count": 0,
        "failed_count": 0,
        "imported_count": 0,
        "last_error": None,
        "worker_pid": None,
        "started_at": None,
        "ended_at": None,
        "created_at": now,
        "updated_at": now,
    }
    _col().insert_one(doc)
    return strip_mongo_id(doc) or doc


def update_run(run_id: str, patch: dict[str, Any]) -> None:
    patch = dict(patch)
    patch["updated_at"] = _now_iso()
    _col().update_one({"id": run_id}, {"$set": patch})


def append_log(run_id: str, message: str) -> None:
    row = fetch_run(run_id)
    if not row:
        return
    lines = list(row.get("log_lines") or [])
    lines.append({"ts": _now_iso(), "message": message})
    if len(lines) > 200:
        lines = lines[-200:]
    update_run(run_id, {"log_lines": lines})
