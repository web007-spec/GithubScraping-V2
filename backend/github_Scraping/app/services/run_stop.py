"""In-memory stop signals and run finalization for scrape jobs."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any

from app.services.runs import append_log_line, fetch_run, update_run

log = logging.getLogger(__name__)

_stop_events: dict[str, threading.Event] = {}
_lock = threading.Lock()

# Max time UI shows "stopping" before we force DB status to stopped
FORCE_STOP_SECONDS = 8


def register_run(run_id: str) -> None:
    """Call before starting the worker thread so Stop never misses the event."""
    with _lock:
        _stop_events[run_id] = threading.Event()


def signal_stop(run_id: str) -> None:
    with _lock:
        ev = _stop_events.get(run_id)
        if ev is not None:
            ev.set()
            log.info("Stop signalled for run %s", run_id)
        else:
            log.warning("Stop signalled for run %s but no event registered", run_id)


def is_stop_requested(run_id: str) -> bool:
    with _lock:
        ev = _stop_events.get(run_id)
        return ev is not None and ev.is_set()


def clear_run(run_id: str) -> None:
    with _lock:
        _stop_events.pop(run_id, None)


def finalize_run_as_stopped(run_id: str, *, total_users: int | None = None) -> None:
    """Write terminal stopped state to the database."""
    run = fetch_run(run_id)
    if not run:
        return
    if run.get("status") in ("stopped", "completed", "failed"):
        return

    fields: dict[str, Any] = {
        "status": "stopped",
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "current_country": None,
        "estimated_seconds_remaining": 0,
    }
    if total_users is not None:
        fields["total_users_found"] = total_users
    update_run(run_id, fields)
    append_log_line(run_id, "Scrape stopped by user")
    log.info("Finalized run %s as stopped", run_id)


def heal_stopping_run(run_id: str, *, is_thread_alive: bool) -> str:
    """
    If the worker is gone, mark stopped immediately.
    Returns the status that should be shown to the client.
    """
    run = fetch_run(run_id)
    if not run:
        return "unknown"
    status = run.get("status") or ""
    if status != "stopping":
        return status
    if not is_thread_alive:
        finalize_run_as_stopped(run_id, total_users=run.get("total_users_found"))
        return "stopped"
    return "stopping"


def schedule_force_stop(run_id: str, on_force=None) -> None:
    """After a short grace period, force DB status to stopped if still stopping."""

    def _force() -> None:
        run = fetch_run(run_id)
        if not run or run.get("status") != "stopping":
            return
        if on_force:
            try:
                on_force()
            except Exception:
                log.exception("Force-stop callback failed for run %s", run_id)
        finalize_run_as_stopped(run_id, total_users=run.get("total_users_found"))
        log.info("Force-stopped run %s after timeout", run_id)

    threading.Timer(FORCE_STOP_SECONDS, _force).start()
