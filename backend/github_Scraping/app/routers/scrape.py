from __future__ import annotations

import time
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

from app.dependencies import require_admin
from app.models.schemas import ScrapeRunResponse, ScrapeStartRequest
from app.services.job_runner import has_active_scrapes, is_run_active, start_scrape_run, terminate_run
from app.services.run_stop import (
    finalize_run_as_stopped,
    heal_stopping_run,
    schedule_force_stop,
    signal_stop,
)
from app.services.runs import update_run
from app.services.country_stats import fetch_country_counts
from app.services.supabase_client import get_supabase

router = APIRouter(prefix="/scrape", tags=["scrape"])

RUN_SUMMARY_SELECT = (
    "id,status,started_at,ended_at,total_users_found,current_country,"
    "countries_completed,config,rate_limit_remaining,rate_limit_reset_at,"
    "estimated_seconds_remaining,last_error,celery_task_id,created_at,updated_at"
)
DASHBOARD_TTL_SECONDS = 5
_dashboard_cache: dict[str, object] = {"expires": 0.0, "payload": None}


def _to_response(row: dict) -> ScrapeRunResponse:
    return ScrapeRunResponse(
        id=row["id"],
        status=row["status"],
        started_at=row.get("started_at"),
        ended_at=row.get("ended_at"),
        total_users_found=row.get("total_users_found") or 0,
        current_country=row.get("current_country"),
        countries_completed=row.get("countries_completed") or [],
        config=row.get("config") or {},
        log_lines=row.get("log_lines") or [],
        rate_limit_remaining=row.get("rate_limit_remaining"),
        rate_limit_reset_at=row.get("rate_limit_reset_at"),
        estimated_seconds_remaining=row.get("estimated_seconds_remaining"),
        last_error=row.get("last_error"),
        celery_task_id=row.get("celery_task_id"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _fetch_run_row(run_id: str) -> dict:
    result = get_supabase().table("scraping_runs").select("*").eq("id", run_id).execute()
    if not result.data:
        raise HTTPException(404, detail="Run not found")
    return result.data[0]


def _heal_and_response(run_id: str) -> ScrapeRunResponse:
    heal_stopping_run(run_id, is_thread_alive=is_run_active(run_id))
    return _to_response(_fetch_run_row(run_id))


def _start_scrape_sync(body: ScrapeStartRequest) -> ScrapeRunResponse:
    sb = get_supabase()
    active = (
        sb.table("scraping_runs")
        .select("id")
        .in_("status", ["pending", "running", "stopping"])
        .limit(1)
        .execute()
    )
    if active.data:
        raise HTTPException(409, detail="A scrape run is already active")

    insert = (
        sb.table("scraping_runs")
        .insert(
            {
                "status": "pending",
                "config": body.config.model_dump(),
                "countries_completed": [],
                "log_lines": [],
            }
        )
        .execute()
    )
    row = insert.data[0]
    run_id = row["id"]

    job_id = start_scrape_run(str(run_id), body.config.model_dump())
    sb.table("scraping_runs").update({"celery_task_id": job_id}).eq("id", run_id).execute()

    updated = sb.table("scraping_runs").select("*").eq("id", run_id).single().execute()
    return _to_response(updated.data)


@router.post("/start", response_model=ScrapeRunResponse)
async def start_scrape(
    body: ScrapeStartRequest,
    _user=Depends(require_admin),
) -> ScrapeRunResponse:
    return await run_in_threadpool(_start_scrape_sync, body)


@router.get("/status/{run_id}", response_model=ScrapeRunResponse)
async def scrape_status(run_id: UUID, _user=Depends(require_admin)) -> ScrapeRunResponse:
    return await run_in_threadpool(_heal_and_response, str(run_id))


@router.post("/stop/{run_id}", response_model=ScrapeRunResponse)
async def stop_scrape(run_id: UUID, _user=Depends(require_admin)) -> ScrapeRunResponse:
    return await run_in_threadpool(_stop_scrape_sync, str(run_id))


def _stop_scrape_sync(rid: str) -> ScrapeRunResponse:
    row = _fetch_run_row(rid)

    if row["status"] in ("stopped", "completed", "failed"):
        return _to_response(row)

    if row["status"] == "stopping":
        return _heal_and_response(rid)

    if row["status"] not in ("running", "pending"):
        raise HTTPException(400, detail=f"Cannot stop run in status {row['status']}")

    signal_stop(rid)
    update_run(rid, {"status": "stopping"})
    schedule_force_stop(rid, on_force=lambda: terminate_run(rid))

    if not is_run_active(rid):
        finalize_run_as_stopped(rid, total_users=row.get("total_users_found"))

    return _heal_and_response(rid)


@router.get("/runs", response_model=list[ScrapeRunResponse])
async def list_runs(
    limit: int = 50,
    _user=Depends(require_admin),
) -> list[ScrapeRunResponse]:
    return await run_in_threadpool(_list_runs_sync, limit)


def _list_runs_sync(limit: int) -> list[ScrapeRunResponse]:
    result = (
        get_supabase()
        .table("scraping_runs")
        .select(RUN_SUMMARY_SELECT)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [_to_response(r) for r in (result.data or [])]


@router.get("/dashboard")
async def dashboard(_user=Depends(require_admin)) -> dict:
    return await run_in_threadpool(_dashboard_sync)


def _dashboard_sync() -> dict:
    try:
        now = time.time()
        cached = _dashboard_cache.get("payload")
        if cached is not None and now < float(_dashboard_cache.get("expires") or 0):
            return cached  # type: ignore[return-value]

        sb = get_supabase()
        country_counts = fetch_country_counts(allow_fallback_scan=not has_active_scrapes())
        total_users = int(country_counts.get("total") or 0)

        stopping = (
            sb.table("scraping_runs")
            .select("id")
            .eq("status", "stopping")
            .execute()
        )
        for row in stopping.data or []:
            heal_stopping_run(row["id"], is_thread_alive=is_run_active(row["id"]))

        active = (
            sb.table("scraping_runs")
            .select("id", count="exact")
            .in_("status", ["pending", "running", "stopping"])
            .limit(0)
            .execute()
        )
        tokens = (
            sb.table("github_tokens")
            .select("id", count="exact")
            .eq("is_active", True)
            .limit(0)
            .execute()
        )
        last = (
            sb.table("scraping_runs")
            .select(RUN_SUMMARY_SELECT)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        last_run = None
        if last.data:
            rid = last.data[0]["id"]
            heal_stopping_run(rid, is_thread_alive=is_run_active(rid))
            refreshed = (
                sb.table("scraping_runs")
                .select(RUN_SUMMARY_SELECT)
                .eq("id", rid)
                .execute()
            )
            last_run = _to_response(refreshed.data[0])

        payload = {
            "total_users": total_users,
            "active_runs": active.count or 0,
            "active_tokens": tokens.count or 0,
            "countries": country_counts.get("countries") or [],
            "last_run": last_run,
        }
        _dashboard_cache["payload"] = payload
        _dashboard_cache["expires"] = now + DASHBOARD_TTL_SECONDS
        return payload
    except Exception as exc:
        raise HTTPException(500, detail=f"Dashboard error: {exc}") from exc
