from __future__ import annotations

import csv
import io
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from app.dependencies import require_admin
from supabase import Client

from app.services.country_stats import (
    fetch_country_counts,
    is_excluded_country,
    rebuild_country_stats,
)
from app.services.job_runner import has_active_scrapes
from app.services.supabase_client import table_execute
from app.services.user_rows import USER_SELECT_BASE, USER_SELECT_EXTENDED, USER_SELECT_LIST

router = APIRouter(prefix="/users", tags=["users"])
log = logging.getLogger(__name__)

SORT_COLUMNS = {
    "followers": "followers",
    "repos": "public_repos",
    "public_repos": "public_repos",
    "joined": "created_at",
    "created_at": "created_at",
    "login": "login",
    "scraped": "last_scraped_at",
    "last_scraped_at": "last_scraped_at",
}


def _is_missing_column_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "column" in msg or "42703" in msg or "does not exist" in msg


def _run_user_list(build) -> tuple[list[dict], int | None]:
    result = table_execute(build)
    return result.data or [], result.count


def _run_user_detail(login: str) -> dict | None:
    try:
        result = table_execute(
            lambda sb: sb.table("github_users")
            .select(USER_SELECT_EXTENDED)
            .ilike("login", login)
            .limit(1)
        )
    except Exception as exc:
        if not _is_missing_column_error(exc):
            raise
        result = table_execute(
            lambda sb: sb.table("github_users")
            .select(USER_SELECT_BASE)
            .ilike("login", login)
            .limit(1)
        )
    rows = result.data or []
    return rows[0] if rows else None


def _list_users_page(
    sb: Client,
    select_cols: str,
    filters: dict,
    column: str,
    descending: bool,
    offset: int,
    page_size: int,
):
    q = _list_users_query(sb, select_cols, **dict(filters))
    return q.order(column, desc=descending).range(offset, offset + page_size)


def _list_users_query(sb, select_cols: str, **filters):
    include_count = bool(filters.pop("include_count", False))
    if include_count:
        q = sb.table("github_users").select(select_cols, count="exact")
    else:
        q = sb.table("github_users").select(select_cols)
    country = filters.get("country")
    if country:
        q = q.eq("country", "__excluded_country__" if is_excluded_country(country) else country)
    if filters.get("followers_min") is not None:
        q = q.gte("followers", filters["followers_min"])
    if filters.get("followers_max") is not None:
        q = q.lte("followers", filters["followers_max"])
    if filters.get("created_after"):
        q = q.gte("created_at", filters["created_after"])
    if filters.get("created_before"):
        q = q.lte("created_at", filters["created_before"])
    if filters.get("has_email") is True:
        q = q.not_.is_("email", "null")
    elif filters.get("has_email") is False:
        q = q.is_("email", "null")
    if filters.get("has_bio") is True:
        q = q.not_.is_("bio", "null")
    elif filters.get("has_bio") is False:
        q = q.is_("bio", "null")
    if filters.get("search"):
        safe = str(filters["search"]).replace(",", " ")
        q = q.or_(
            f"login.ilike.%{safe}%,name.ilike.%{safe}%,location.ilike.%{safe}%,"
            f"bio.ilike.%{safe}%,email.ilike.%{safe}%,company.ilike.%{safe}%"
        )
    return q


@router.get("/countries")
async def list_countries(_user=Depends(require_admin)) -> dict:
    """Per-country counts from indexed stats table (fast for LAN clients)."""
    return await run_in_threadpool(
        fetch_country_counts,
        allow_fallback_scan=not has_active_scrapes(),
    )


@router.post("/countries/rebuild")
async def rebuild_countries_index(_user=Depends(require_admin)) -> dict:
    """Rebuild country stats from github_users (after bulk migration)."""
    try:
        rebuild_country_stats()
        return fetch_country_counts()
    except Exception as exc:
        raise HTTPException(500, detail=str(exc)) from exc


@router.get("")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=1000),
    search: str | None = None,
    country: str | None = None,
    followers_min: int | None = None,
    followers_max: int | None = None,
    created_after: str | None = None,
    created_before: str | None = None,
    has_email: bool | None = None,
    has_bio: bool | None = None,
    sort_by: str = Query("last_scraped_at"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    include_count: bool = Query(False),
    _user=Depends(require_admin),
) -> dict:
    scrape_active = has_active_scrapes()
    if scrape_active:
        page_size = min(page_size, 100)
        include_count = False

    filters = {
        "country": country,
        "followers_min": followers_min,
        "followers_max": followers_max,
        "created_after": created_after,
        "created_before": created_before,
        "has_email": has_email,
        "has_bio": has_bio,
        "search": search,
        "include_count": include_count,
    }
    column = SORT_COLUMNS.get(sort_by, "last_scraped_at")
    descending = sort_order == "desc"
    offset = (page - 1) * page_size

    try:
        items, total = await run_in_threadpool(
            _run_user_list,
            lambda sb: _list_users_page(
                sb, USER_SELECT_LIST, filters, column, descending, offset, page_size
            ),
        )
    except Exception as exc:
        if not _is_missing_column_error(exc):
            log.exception("List users failed")
            raise HTTPException(500, detail=str(exc)) from exc
        log.warning("Extended columns missing — using base columns. Run github_users_enrichment.sql")
        items, total = await run_in_threadpool(
            _run_user_list,
            lambda sb: _list_users_page(
                sb, USER_SELECT_BASE, filters, column, descending, offset, page_size
            ),
        )

    has_more = len(items) > page_size
    items = items[:page_size]
    return {
        "items": items,
        "total": total,
        "has_more": has_more,
        "page": page,
        "page_size": page_size,
        "limited_by_active_scrape": scrape_active,
    }


@router.get("/profile/{login}")
async def get_user_profile(
    login: str,
    _user=Depends(require_admin),
) -> dict:
    clean_login = login.strip()
    if not clean_login:
        raise HTTPException(404, detail="User not found")
    row = await run_in_threadpool(_run_user_detail, clean_login)
    if not row or is_excluded_country(row.get("country")):
        raise HTTPException(404, detail="User not found")
    return {"user": row}


@router.get("/export")
async def export_users(
    format: str = Query("csv", pattern="^(csv|json)$"),
    country: str | None = None,
    _user=Depends(require_admin),
):
    if country and is_excluded_country(country):
        raise HTTPException(404, detail="Country is not available")

    if has_active_scrapes():
        raise HTTPException(
            409,
            detail="Exports are disabled while a scrape is running. Open the user list or stop the scrape first.",
        )

    def export_page(sb: Client, cols: str, off: int, size: int):
        q = sb.table("github_users").select(cols)
        if country:
            q = q.eq("country", country)
        return q.range(off, off + size - 1)

    select_cols = USER_SELECT_EXTENDED
    all_rows: list[dict] = []
    offset = 0
    batch = 500
    while True:
        try:
            chunk = table_execute(lambda sb: export_page(sb, select_cols, offset, batch))
        except Exception as exc:
            if offset > 0 or not _is_missing_column_error(exc):
                raise HTTPException(500, detail=str(exc)) from exc
            select_cols = USER_SELECT_BASE
            chunk = table_execute(lambda sb: export_page(sb, select_cols, offset, batch))
        rows = chunk.data or []
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < batch:
            break
        offset += batch

    if format == "json":
        content = json.dumps(all_rows, indent=2, default=str)
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=github_users.json"},
        )

    output = io.StringIO()
    if all_rows:
        writer = csv.DictWriter(output, fieldnames=all_rows[0].keys())
        writer.writeheader()
        writer.writerows(all_rows)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=github_users.csv"},
    )
