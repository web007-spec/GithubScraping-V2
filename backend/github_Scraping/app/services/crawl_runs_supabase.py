"""Google Docs crawl runs — Supabase persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.supabase_client import table_execute

TABLE = "google_docs_crawl_runs"
ACTIVE_STATUSES = ("pending", "running", "stopping")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_run_raw(run_id: str) -> dict[str, Any] | None:
    result = table_execute(
        lambda sb: sb.table(TABLE).select("*").eq("id", run_id).limit(1)
    )
    rows = result.data or []
    return rows[0] if rows else None


def list_runs_raw(limit: int = 20) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 100))
    result = table_execute(
        lambda sb: sb.table(TABLE).select("*").order("created_at", desc=True).limit(limit)
    )
    return result.data or []


def get_active_run_raw() -> dict[str, Any] | None:
    result = table_execute(
        lambda sb: sb.table(TABLE)
        .select("*")
        .in_("status", list(ACTIVE_STATUSES))
        .order("created_at", desc=True)
        .limit(1)
    )
    rows = result.data or []
    return rows[0] if rows else None


def insert_run_raw(*, mode: str, config: dict[str, Any]) -> dict[str, Any]:
    insert = table_execute(
        lambda sb: sb.table(TABLE)
        .insert(
            {
                "status": "pending",
                "mode": mode,
                "config": config,
                "log_lines": [],
                "current_phase": "pending",
            }
        )
    )
    return insert.data[0]


def update_run_raw(run_id: str, patch: dict[str, Any]) -> None:
    patch = dict(patch)
    patch["updated_at"] = _now_iso()
    table_execute(lambda sb: sb.table(TABLE).update(patch).eq("id", run_id))


def append_log_raw(run_id: str, message: str) -> None:
    row = fetch_run_raw(run_id)
    if not row:
        return
    lines = list(row.get("log_lines") or [])
    lines.append({"ts": _now_iso(), "message": message})
    if len(lines) > 200:
        lines = lines[-200:]
    update_run_raw(run_id, {"log_lines": lines})
