"""Google Drive explorer API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.dependencies import require_admin
from app.services import drive_crawl_runs as crawl_service

router = APIRouter(prefix="/google-drive", tags=["google-drive"])
public_router = APIRouter(prefix="/public/google-drive", tags=["public-google-drive"])


class CrawlStartBody(BaseModel):
    mode: str = Field(
        default="batch_search",
        description="batch_search | search | from_discovered | folder_crawl",
    )
    query: str = Field(default="", max_length=500)
    target: int = Field(default=500, ge=10, le=50_000)
    max_results: int = Field(default=50, ge=1, le=100)
    categories: list[str] = Field(..., min_length=1, max_length=80)
    max_depth: int = Field(default=4, ge=1, le=8)
    max_files: int = Field(default=500, ge=1, le=10_000)
    workers: int = Field(default=6, ge=1, le=32)
    resume: bool = True
    seed_urls: list[str] = Field(default_factory=list, max_length=50)


@public_router.get("/categories")
async def list_categories() -> dict:
    from google_drive_db.categories import categories_for_api

    return {"categories": categories_for_api()}


@public_router.get("/stats")
async def public_stats() -> dict:
    from app.services.drive_db_backend import get_stats, storage_ready

    status = await run_in_threadpool(storage_ready)
    if not status.get("ok"):
        return {"ok": False, **status, "total": 0, "indexed": 0}
    stats = await run_in_threadpool(get_stats)
    return {"ok": True, **stats}


@public_router.get("/")
async def public_list(
    q: str = Query("", max_length=200),
    mime_type: str = Query("", max_length=120),
    extension: str = Query("", max_length=20),
    category: str = Query("", max_length=80),
    sort: str = Query("indexed_at", max_length=40),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    from app.services.drive_db_backend import list_files, storage_ready

    status = await run_in_threadpool(storage_ready)
    if not status.get("ok"):
        raise HTTPException(503, detail="Google Drive storage is not ready")
    items, total = await run_in_threadpool(
        lambda: list_files(
            q=q,
            mime_type=mime_type,
            extension=extension,
            category=category,
            sort=sort,
            order=order,
            limit=limit,
            offset=offset,
        )
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@public_router.get("/{file_id}")
async def public_file(file_id: str) -> dict:
    from app.services.drive_db_backend import get_file, storage_ready

    status = await run_in_threadpool(storage_ready)
    if not status.get("ok"):
        raise HTTPException(503, detail="Google Drive storage is not ready")
    item = await run_in_threadpool(lambda: get_file(file_id))
    if not item:
        raise HTTPException(404, detail="File not found")
    return item


@router.post("/crawl/start")
async def start_crawl(body: CrawlStartBody, _admin: dict = Depends(require_admin)) -> dict:
    run = await run_in_threadpool(
        lambda: crawl_service.start_run(
            {
                "mode": body.mode,
                "query": body.query.strip(),
                "target": body.target,
                "max_results": body.max_results,
                "categories": body.categories,
                "max_depth": body.max_depth,
                "max_files": body.max_files,
                "workers": body.workers,
                "resume": body.resume,
                "seed_urls": body.seed_urls,
            }
        )
    )
    return {"run": run}


@router.get("/crawl/active")
async def active_crawl(_admin: dict = Depends(require_admin)) -> dict:
    run = await run_in_threadpool(crawl_service.get_active_run)
    return {"run": run}


@router.get("/crawl/runs")
async def list_runs(limit: int = Query(20, ge=1, le=100), _admin: dict = Depends(require_admin)) -> dict:
    runs = await run_in_threadpool(lambda: crawl_service.list_runs(limit))
    return {"runs": runs}


@router.get("/crawl/status/{run_id}")
async def crawl_status(run_id: str, _admin: dict = Depends(require_admin)) -> dict:
    run = await run_in_threadpool(lambda: crawl_service.fetch_run(run_id))
    return {"run": run}


@router.post("/crawl/stop/{run_id}")
async def stop_crawl(run_id: str, _admin: dict = Depends(require_admin)) -> dict:
    run = await run_in_threadpool(lambda: crawl_service.stop_run(run_id))
    return {"run": run}
