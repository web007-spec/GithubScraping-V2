"""Google Drive crawl run persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from app.services.drive_crawl_runner import heal_run_status, is_crawl_active, start_drive_crawl, terminate_crawl
from app.services.drive_db_backend import (
    crawl_fetch_run,
    crawl_get_active_run,
    crawl_insert_run,
    crawl_list_runs,
    crawl_update_run,
    storage_ready,
)

ACTIVE_STATUSES = ("pending", "running", "stopping")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_storage() -> None:
    status = storage_ready()
    if not status.get("ok"):
        raise HTTPException(
            503,
            detail="MongoDB is not reachable. Set MONGODB_URI in backend/.env and restart the API.",
        )


def _heal_and_persist(run_id: str, row: dict[str, Any]) -> dict[str, Any]:
    healed = heal_run_status(run_id, row)
    if healed.get("status") != row.get("status") or (
        healed.get("last_error") and healed.get("last_error") != row.get("last_error")
    ):
        patch: dict[str, Any] = {"status": healed.get("status")}
        if healed.get("last_error"):
            patch["last_error"] = healed.get("last_error")
        if healed.get("status") in ("failed", "stopped"):
            patch["ended_at"] = patch.get("ended_at") or _now_iso()
            patch["current_phase"] = str(healed.get("status"))
        try:
            crawl_update_run(run_id, patch)
        except Exception:
            pass
    return healed


def fetch_run(run_id: str) -> dict[str, Any]:
    _require_storage()
    row = crawl_fetch_run(run_id)
    if not row:
        raise HTTPException(404, detail="Crawl run not found")
    return _heal_and_persist(run_id, row)


def list_runs(limit: int = 20) -> list[dict[str, Any]]:
    _require_storage()
    rows = crawl_list_runs(limit)
    return [_heal_and_persist(str(r.get("id")), r) for r in rows]


def get_active_run() -> dict[str, Any] | None:
    _require_storage()
    row = crawl_get_active_run()
    if not row:
        return None
    run_id = str(row.get("id"))
    healed = _heal_and_persist(run_id, row)
    if str(healed.get("status") or "") not in ACTIVE_STATUSES:
        return None
    return healed


def start_run(config: dict[str, Any]) -> dict[str, Any]:
    _require_storage()
    active = get_active_run()
    if active and is_crawl_active(str(active.get("id"))):
        raise HTTPException(409, detail="A Google Drive crawl is already active")

    mode = str(config.get("mode") or "batch_search").strip()
    categories = list(config.get("categories") or [])
    if not categories:
        raise HTTPException(400, detail="Select at least one content category to crawl")

    if mode == "folder_crawl":
        seed_urls = list(config.get("seed_urls") or [])
        if not seed_urls:
            raise HTTPException(400, detail="At least one public Drive folder or file URL is required")
    elif mode == "search":
        if not str(config.get("query") or "").strip():
            raise HTTPException(400, detail="Search query is required for search mode")
    elif mode not in ("batch_search", "from_discovered"):
        raise HTTPException(400, detail=f"Unsupported crawl mode: {mode}")

    row = crawl_insert_run(mode=mode, config=config)
    run_id = str(row["id"])

    try:
        pid = start_drive_crawl(run_id)
        crawl_update_run(
            run_id,
            {"worker_pid": pid, "status": "running", "started_at": _now_iso()},
        )
    except Exception as exc:
        crawl_update_run(
            run_id,
            {
                "status": "failed",
                "last_error": str(exc),
                "ended_at": _now_iso(),
                "current_phase": "failed",
            },
        )
        raise HTTPException(500, detail=str(exc)) from exc

    return fetch_run(run_id)


def stop_run(run_id: str) -> dict[str, Any]:
    row = fetch_run(run_id)
    status = str(row.get("status") or "")
    if status not in ACTIVE_STATUSES:
        return row

    crawl_update_run(run_id, {"status": "stopping", "current_phase": "stopping"})
    terminate_crawl(run_id)
    return fetch_run(run_id)


def mark_worker_exit(run_id: str, exit_code: int) -> None:
    row = crawl_fetch_run(run_id)
    if not row:
        return
    status = str(row.get("status") or "")
    if status in ("completed", "stopped", "failed"):
        return
    detail = str(row.get("last_error") or "").strip() or f"Worker exited with code {exit_code}"
    crawl_update_run(
        run_id,
        {
            "status": "failed",
            "last_error": detail,
            "ended_at": _now_iso(),
            "current_phase": "failed",
        },
    )
