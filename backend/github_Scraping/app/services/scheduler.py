"""Check scheduled_jobs and start scrapes (no Celery beat)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from croniter import croniter

from app.services.job_runner import start_scrape_run
from app.services.supabase_client import table_execute

log = logging.getLogger(__name__)


def check_due_schedules() -> int:
    try:
        return _check_due_schedules()
    except Exception:
        log.exception("check_due_schedules failed")
        return 0


def _check_due_schedules() -> int:
    now = datetime.now(timezone.utc).isoformat()

    due = table_execute(
        lambda sb: sb.table("scheduled_jobs")
        .select("*")
        .eq("active", True)
        .lte("next_run_at", now)
    )
    started = 0
    for job in due.data or []:
        active_run = table_execute(
            lambda sb: sb.table("scraping_runs")
            .select("id")
            .in_("status", ["pending", "running", "stopping"])
            .limit(1)
        )
        if active_run.data:
            log.info("Skipping schedule %s: scrape already active", job["id"])
            continue

        config = job.get("config") or {}
        insert = table_execute(
            lambda sb: sb.table("scraping_runs").insert(
                {
                    "status": "pending",
                    "config": config,
                    "countries_completed": [],
                    "log_lines": [{"ts": now, "message": f"Scheduled: {job['name']}"}],
                }
            )
        )
        run_id = str(insert.data[0]["id"])
        job_id = start_scrape_run(run_id, config)
        table_execute(
            lambda sb: sb.table("scraping_runs")
            .update({"celery_task_id": job_id})
            .eq("id", run_id)
        )

        itr = croniter(job["cron_expression"], datetime.now(timezone.utc))
        next_run = itr.get_next(datetime)
        if next_run.tzinfo is None:
            next_run = next_run.replace(tzinfo=timezone.utc)

        table_execute(
            lambda sb: sb.table("scheduled_jobs")
            .update(
                {
                    "last_run_at": now,
                    "next_run_at": next_run.isoformat(),
                }
            )
            .eq("id", job["id"])
        )
        started += 1
        log.info("Started scheduled scrape %s for job %s", run_id, job["name"])

    return started
