"""Google Drive storage backend — MongoDB."""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


def storage_ready() -> dict[str, Any]:
    from outreach_db.client import ping
    from google_drive_db import crawl_runs, files

    if not ping():
        return {"ok": False, "storage": "mongodb", "missing": ["mongodb_connection"]}
    ready = files.is_ready() and crawl_runs.is_ready()
    return {"ok": ready, "storage": "mongodb", "missing_tables": [] if ready else ["google_drive_files"]}


def list_files(**kwargs) -> tuple[list[dict[str, Any]], int]:
    from google_drive_db import files as mongo_files

    return mongo_files.list_files(**kwargs)


def get_stats() -> dict[str, Any]:
    from google_drive_db import files as mongo_files

    return mongo_files.get_stats()


def get_file(file_id: str) -> dict[str, Any] | None:
    from google_drive_db import files as mongo_files

    return mongo_files.get_public_file(file_id)


def crawl_fetch_run(run_id: str) -> dict[str, Any] | None:
    from google_drive_db import crawl_runs

    return crawl_runs.fetch_run(run_id)


def crawl_list_runs(limit: int = 20) -> list[dict[str, Any]]:
    from google_drive_db import crawl_runs

    return crawl_runs.list_runs(limit)


def crawl_get_active_run() -> dict[str, Any] | None:
    from google_drive_db import crawl_runs

    return crawl_runs.get_active_run()


def crawl_insert_run(*, mode: str, config: dict[str, Any]) -> dict[str, Any]:
    from google_drive_db import crawl_runs

    return crawl_runs.insert_run(mode=mode, config=config)


def crawl_update_run(run_id: str, patch: dict[str, Any]) -> None:
    from google_drive_db import crawl_runs

    crawl_runs.update_run(run_id, patch)
