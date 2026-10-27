"""Public unified AI search (GitHub users + Google Docs)."""

from __future__ import annotations

from fastapi import APIRouter, Query
from starlette.concurrency import run_in_threadpool

router = APIRouter(prefix="/public/search", tags=["public-search"])


@router.get("/ai")
async def public_ai_search(
    q: str = Query(..., min_length=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=40),
) -> dict:
    from app.services.unified_ai_search import unified_ai_search

    offset = (page - 1) * page_size
    return await run_in_threadpool(
        lambda: unified_ai_search(q=q, limit=page_size, offset=offset)
    )
