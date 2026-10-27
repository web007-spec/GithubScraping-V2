"""Helpers for scraping_runs progress and logs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.supabase_client import table_execute

MAX_LOG_LINES = 500


def fetch_run(run_id: str) -> dict[str, Any] | None:
    result = table_execute(
        lambda sb: sb.table("scraping_runs").select("*").eq("id", run_id).single()
    )
    return result.data


def get_run_status(run_id: str) -> str | None:
    result = table_execute(
        lambda sb: sb.table("scraping_runs").select("status").eq("id", run_id).single()
    )
    run = result.data
    return run.get("status") if run else None


def update_run(run_id: str, fields: dict[str, Any]) -> None:
    table_execute(
        lambda sb: sb.table("scraping_runs").update(fields).eq("id", run_id)
    )


def append_log_line(run_id: str, message: str) -> None:
    result = table_execute(
        lambda sb: sb.table("scraping_runs").select("log_lines").eq("id", run_id).single()
    )
    run = result.data
    if not run:
        return
    lines: list[dict[str, str]] = list(run.get("log_lines") or [])
    lines.append(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "message": message,
        }
    )
    if len(lines) > MAX_LOG_LINES:
        lines = lines[-MAX_LOG_LINES:]
    update_run(run_id, {"log_lines": lines})


def make_run_updater(run_id: str):
    def updater(fields: dict[str, Any]) -> None:
        update_run(run_id, fields)

    return updater
