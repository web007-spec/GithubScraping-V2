from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from croniter import croniter
from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import require_admin
from app.models.schemas import ScheduleCreate, ScheduleResponse
from app.services.supabase_client import get_supabase

router = APIRouter(prefix="/schedule", tags=["schedule"])


def _next_run(cron_expression: str, base: datetime | None = None) -> datetime:
    base = base or datetime.now(timezone.utc)
    itr = croniter(cron_expression, base)
    nxt = itr.get_next(datetime)
    if nxt.tzinfo is None:
        nxt = nxt.replace(tzinfo=timezone.utc)
    return nxt


def _to_response(row: dict) -> ScheduleResponse:
    return ScheduleResponse(
        id=row["id"],
        name=row["name"],
        cron_expression=row["cron_expression"],
        config=row.get("config") or {},
        active=row.get("active", True),
        last_run_at=row.get("last_run_at"),
        next_run_at=row.get("next_run_at"),
    )


@router.post("", response_model=ScheduleResponse)
async def create_schedule(body: ScheduleCreate, _user=Depends(require_admin)) -> ScheduleResponse:
    try:
        next_at = _next_run(body.cron_expression)
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, detail=f"Invalid cron expression: {exc}") from exc

    insert = (
        get_supabase()
        .table("scheduled_jobs")
        .insert(
            {
                "name": body.name,
                "cron_expression": body.cron_expression,
                "config": body.config.model_dump(),
                "active": body.active,
                "next_run_at": next_at.isoformat(),
            }
        )
        .execute()
    )
    return _to_response(insert.data[0])


@router.get("", response_model=list[ScheduleResponse])
async def list_schedules(_user=Depends(require_admin)) -> list[ScheduleResponse]:
    result = (
        get_supabase()
        .table("scheduled_jobs")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return [_to_response(r) for r in (result.data or [])]


@router.delete("/{job_id}")
async def delete_schedule(job_id: UUID, _user=Depends(require_admin)) -> dict:
    get_supabase().table("scheduled_jobs").delete().eq("id", str(job_id)).execute()
    return {"ok": True}


@router.patch("/{job_id}/toggle")
async def toggle_schedule(
    job_id: UUID,
    active: bool = Query(...),
    _user=Depends(require_admin),
) -> ScheduleResponse:
    sb = get_supabase()
    fields: dict = {"active": active}
    if active:
        row = sb.table("scheduled_jobs").select("cron_expression").eq("id", str(job_id)).single().execute()
        fields["next_run_at"] = _next_run(row.data["cron_expression"]).isoformat()
    sb.table("scheduled_jobs").update(fields).eq("id", str(job_id)).execute()
    updated = sb.table("scheduled_jobs").select("*").eq("id", str(job_id)).single().execute()
    return _to_response(updated.data)
