"""Google Docs explorer API (public read + admin crawl/import)."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.dependencies import require_admin
from app.services import docs_crawl_runs as crawl_runs_service
from app.services import google_docs as docs_service
from app.services.supabase_client import table_execute

router = APIRouter(prefix="/google-docs", tags=["google-docs"])
public_router = APIRouter(prefix="/public/google-docs", tags=["public-google-docs"])


class ImportCsvBody(BaseModel):
    csv_path: str | None = Field(
        default=None,
        description="Optional absolute path to results.csv; defaults to indexer data file",
    )
    only_parsed: bool = True


class CrawlStartBody(BaseModel):
    mode: str = Field(default="batch_search", description="search | batch_search | from_discovered | from_file")
    query: str = Field(default="", max_length=500)
    target: int = Field(default=10_000, ge=10, le=50_000)
    max_results: int = Field(default=50, ge=1, le=100)
    workers: int = Field(default=40, ge=1, le=100)
    resume: bool = True
    auto_import: bool = True


@router.post("/setup-schema")
async def setup_schema(_admin: dict = Depends(require_admin)) -> dict:
    from app.config import get_settings
    from app.services.google_docs_schema import apply_google_docs_schema

    settings = get_settings()
    if not (settings.supabase_db_password or settings.supabase_database_url):
        raise HTTPException(
            503,
            detail=(
                "Set SUPABASE_DB_PASSWORD in backend/.env (Supabase Dashboard → "
                "Project Settings → Database → Database password), restart the API, "
                "or run schema/google_docs_setup.sql in the Supabase SQL Editor."
            ),
        )
    return await run_in_threadpool(
        lambda: apply_google_docs_schema(
            supabase_url=settings.supabase_url,
            db_password=settings.supabase_db_password,
            database_url=settings.supabase_database_url,
        )
    )


@router.get("/setup-schema/status")
async def setup_schema_status(_admin: dict = Depends(require_admin)) -> dict:
    from app.services.docs_db_backend import storage_ready, use_mongodb

    if use_mongodb():
        status = await run_in_threadpool(storage_ready)
        return {**status, "can_auto_setup": False}

    from app.config import get_settings
    from app.services.google_docs_schema import check_google_docs_schema

    settings = get_settings()
    if settings.supabase_db_password or settings.supabase_database_url:
        status = await run_in_threadpool(
            lambda: check_google_docs_schema(
                supabase_url=settings.supabase_url,
                db_password=settings.supabase_db_password,
                database_url=settings.supabase_database_url,
            )
        )
        return {
            **status,
            "storage": "supabase",
            "can_auto_setup": True,
            "sql_file": "schema/google_docs_setup.sql",
        }

    status = await run_in_threadpool(storage_ready)
    return {
        **status,
        "can_auto_setup": False,
        "sql_file": "schema/google_docs_setup.sql",
    }


def _list_response(
    q: str,
    status: str,
    sort: str,
    order: str,
    page: int,
    page_size: int,
) -> dict:
    offset = (page - 1) * page_size
    descending = order.lower() != "asc"
    items, total = docs_service.list_documents(
        q=q,
        status=status,
        sort=sort,
        descending=descending,
        offset=offset,
        limit=page_size,
    )
    has_more = total is not None and offset + len(items) < total
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": has_more,
    }


# ---------------------------------------------------------------------------
# Public (no auth) — parsed documents only
# ---------------------------------------------------------------------------


def _is_missing_table_exc(exc: Exception, table: str) -> bool:
    msg = str(exc).lower()
    return table in msg or "pgrst205" in msg or "could not find" in msg or (
        "404" in msg and "json could not be generated" in msg
    )


def _tables_missing_via_api() -> list[str]:
    missing: list[str] = []
    for table in ("google_documents", "google_docs_crawl_runs"):
        try:
            table_execute(lambda sb, t=table: sb.table(t).select("id", count="exact", head=True))
        except Exception as exc:
            if _is_missing_table_exc(exc, table):
                missing.append(table)
            else:
                raise
    return missing


@public_router.get("/setup-status")
async def public_setup_status() -> dict:
    from app.services.docs_db_backend import storage_ready, storage_label

    status = await run_in_threadpool(storage_ready)
    return {
        **status,
        "sql_file": "schema/google_docs_setup.sql" if status.get("storage") == "supabase" else None,
    }


@public_router.get("/search")
async def public_search_docs(
    q: str = Query(..., min_length=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    ai: bool = Query(default=True, description="Use LLM relevance ranking when API keys are configured"),
) -> dict:
    offset = (page - 1) * page_size
    if ai:
        from app.services.google_docs_ai_search import search_documents_ai

        items, total, meta = await run_in_threadpool(
            lambda: search_documents_ai(q=q, limit=page_size, offset=offset)
        )
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "query": q,
            **meta,
        }

    items, total = await run_in_threadpool(
        lambda: docs_service.search_documents(q=q, limit=page_size, offset=offset)
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "query": q,
        "mode": "keyword",
    }


@public_router.get("/stats")
async def public_docs_stats() -> dict:
    return await run_in_threadpool(docs_service.get_stats)


@public_router.get("")
async def public_list_docs(
    q: str = Query(default=""),
    sort: str = Query(default="crawled_at"),
    order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
) -> dict:
    return await run_in_threadpool(
        lambda: _list_response(q, "parsed", sort, order, page, page_size)
    )


@public_router.get("/{google_doc_id}/preview-image")
async def public_preview_image(google_doc_id: str) -> Response:
    content, media_type = await docs_service.fetch_preview_bytes(google_doc_id)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@public_router.get("/{google_doc_id}")
async def public_get_doc(google_doc_id: str) -> dict:
    row = await run_in_threadpool(lambda: docs_service.get_document(google_doc_id))
    if not row or str(row.get("status") or "") != "parsed":
        raise HTTPException(404, detail="Document not found")
    row.pop("html", None)
    row.pop("clean_text", None)
    return row


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------


@router.get("/search")
async def admin_search_docs(
    q: str = Query(..., min_length=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    ai: bool = Query(default=True),
    _admin: dict = Depends(require_admin),
) -> dict:
    offset = (page - 1) * page_size
    if ai:
        from app.services.google_docs_ai_search import search_documents_ai

        items, total, meta = await run_in_threadpool(
            lambda: search_documents_ai(q=q, limit=page_size, offset=offset)
        )
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "query": q,
            **meta,
        }

    items, total = await run_in_threadpool(
        lambda: docs_service.search_documents(q=q, limit=page_size, offset=offset)
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "query": q,
        "mode": "keyword",
    }


@router.post("/archive/import-csv")
async def archive_import_csv(
    body: ImportCsvBody | None = None,
    _admin: dict = Depends(require_admin),
) -> dict:
    """Import full document content (body + links + archive_data) from indexer CSV."""
    path = None
    only_parsed = True
    if body:
        only_parsed = body.only_parsed
        if body.csv_path:
            path = Path(body.csv_path)
            if not path.is_file():
                raise HTTPException(404, detail=f"CSV not found: {path}")
    return await run_in_threadpool(
        lambda: docs_service.import_csv(path, only_parsed=only_parsed)
    )


@router.get("/stats")
async def docs_stats(_admin: dict = Depends(require_admin)) -> dict:
    return await run_in_threadpool(docs_service.get_stats)


@router.get("/crawl/runs")
async def list_crawl_runs(
    limit: int = Query(default=20, ge=1, le=100),
    _admin: dict = Depends(require_admin),
) -> list[dict]:
    return await run_in_threadpool(lambda: crawl_runs_service.list_runs(limit))


@router.get("/crawl/active")
async def active_crawl_run(_admin: dict = Depends(require_admin)) -> dict | None:
    return await run_in_threadpool(crawl_runs_service.get_active_run)


@router.get("/crawl/status/{run_id}")
async def crawl_status(run_id: UUID, _admin: dict = Depends(require_admin)) -> dict:
    return await run_in_threadpool(lambda: crawl_runs_service.fetch_run(str(run_id)))


@router.post("/crawl/start")
async def crawl_start(
    body: CrawlStartBody,
    _admin: dict = Depends(require_admin),
) -> dict:
    config = body.model_dump()
    return await run_in_threadpool(lambda: crawl_runs_service.start_run(config))


@router.post("/crawl/stop/{run_id}")
async def crawl_stop(run_id: UUID, _admin: dict = Depends(require_admin)) -> dict:
    return await run_in_threadpool(lambda: crawl_runs_service.stop_run(str(run_id)))


@router.get("")
async def list_docs(
    q: str = Query(default=""),
    status: str = Query(default="parsed"),
    sort: str = Query(default="crawled_at"),
    order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
    _admin: dict = Depends(require_admin),
) -> dict:
    return await run_in_threadpool(
        lambda: _list_response(q, status, sort, order, page, page_size)
    )


@router.get("/{google_doc_id}/preview-image")
async def preview_image(
    google_doc_id: str,
    _admin: dict = Depends(require_admin),
) -> Response:
    content, media_type = await docs_service.fetch_preview_bytes(google_doc_id)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.get("/{google_doc_id}")
async def get_doc(
    google_doc_id: str,
    _admin: dict = Depends(require_admin),
) -> dict:
    row = await run_in_threadpool(lambda: docs_service.get_document(google_doc_id))
    if not row:
        raise HTTPException(404, detail="Document not found")
    return row


@router.post("/import-csv")
async def import_csv(
    body: ImportCsvBody | None = None,
    _admin: dict = Depends(require_admin),
) -> dict:
    path = None
    only_parsed = True
    if body:
        only_parsed = body.only_parsed
        if body.csv_path:
            path = Path(body.csv_path)
            if not path.is_file():
                raise HTTPException(404, detail=f"CSV not found: {path}")
    return await run_in_threadpool(
        lambda: docs_service.import_csv(path, only_parsed=only_parsed)
    )
