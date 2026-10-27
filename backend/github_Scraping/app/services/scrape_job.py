"""Background scrape execution (no Redis/Celery)."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from time import monotonic
from typing import Any

from app.config import get_settings
from app.crypto import decrypt_token
from app.scraper.core import GitHubClient, ScrapeConfig, ScrapeRunner
from app.services.run_stop import finalize_run_as_stopped, is_stop_requested
from app.services.runs import append_log_line, fetch_run, get_run_status, make_run_updater, update_run
from app.services.supabase_client import get_supabase, table_execute

log = logging.getLogger(__name__)


def execute_scrape_run(run_id: str, config_dict: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    config = ScrapeConfig(**config_dict)
    total = 0

    def should_stop() -> bool:
        if is_stop_requested(run_id):
            return True
        return get_run_status(run_id) in ("stopping", "stopped")

    try:
        token_row = table_execute(
            lambda sb: sb.table("github_tokens")
            .select("*")
            .eq("is_active", True)
            .order("last_used_at", desc=True)
            .limit(1)
        )
        if not token_row.data:
            raise RuntimeError("No active GitHub token")

        row = token_row.data[0]
        token_id = row["id"]
        plain = decrypt_token(row["token_value"], settings.token_encryption_key)
        rate_update_lock = threading.Lock()
        rate_update_state: dict[str, Any] = {
            "last_emit": 0.0,
            "remaining": None,
            "reset_at": None,
        }

        def on_rate_limit(remaining: int | None, reset_at: datetime | None) -> None:
            if should_stop():
                return
            now_mono = monotonic()
            with rate_update_lock:
                prev_remaining = rate_update_state["remaining"]
                prev_reset = rate_update_state["reset_at"]
                elapsed = now_mono - float(rate_update_state["last_emit"] or 0.0)
                remaining_delta = (
                    abs(int(prev_remaining) - int(remaining))
                    if prev_remaining is not None and remaining is not None
                    else None
                )
                should_emit = (
                    elapsed >= 10.0
                    or rate_update_state["last_emit"] == 0.0
                    or (remaining is not None and remaining <= 100)
                    or (remaining_delta is not None and remaining_delta >= 50)
                    or (reset_at is not None and reset_at != prev_reset)
                )
                if not should_emit:
                    return
                rate_update_state["last_emit"] = now_mono
                rate_update_state["remaining"] = remaining
                rate_update_state["reset_at"] = reset_at

            fields: dict[str, Any] = {}
            if remaining is not None:
                fields["rate_limit_remaining"] = remaining
            if reset_at is not None:
                fields["rate_limit_reset_at"] = reset_at.isoformat()
            if fields:
                update_run(run_id, fields)
            if token_id:
                table_execute(
                    lambda sb: sb.table("github_tokens")
                    .update(
                        {
                            "rate_limit_remaining": remaining,
                            "rate_limit_reset_at": reset_at.isoformat() if reset_at else None,
                            "last_used_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    .eq("id", token_id)
                )

        github = GitHubClient(plain, on_rate_limit=on_rate_limit)
        github._stop_check = should_stop

        update_run(
            run_id,
            {
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        append_log_line(run_id, "Scrape started")

        runner = ScrapeRunner(
            supabase=get_supabase(),
            github=github,
            config=config,
            run_id=run_id,
            get_status=lambda: "stopping" if should_stop() else get_run_status(run_id),
            should_stop=should_stop,
            append_log=lambda msg: append_log_line(run_id, msg),
            update_run=make_run_updater(run_id),
        )

        total = runner.run()
        status = "stopped" if should_stop() else "completed"

        update_run(
            run_id,
            {
                "status": status,
                "ended_at": datetime.now(timezone.utc).isoformat(),
                "total_users_found": total,
                "estimated_seconds_remaining": 0,
                "current_country": None,
            },
        )
        append_log_line(run_id, f"Run finished: {status}, {total} users")
        return {"run_id": run_id, "status": status, "total_users_found": total}

    except Exception as exc:
        if should_stop():
            finalize_run_as_stopped(run_id, total_users=total)
            return {"run_id": run_id, "status": "stopped", "total_users_found": total}
        log.exception("Scrape job failed: %s", run_id)
        update_run(
            run_id,
            {
                "status": "failed",
                "ended_at": datetime.now(timezone.utc).isoformat(),
                "last_error": str(exc),
            },
        )
        append_log_line(run_id, f"ERROR: {exc}")
        raise
    finally:
        current = fetch_run(run_id)
        if current and current.get("status") == "stopping":
            finalize_run_as_stopped(run_id, total_users=current.get("total_users_found") or total)
