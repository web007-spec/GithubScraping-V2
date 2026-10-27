"""Google Docs — Supabase storage adapter."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException

from app.services.google_docs_archive import build_minimal_archive_data, rebuild_search_text_from_row
from app.services.supabase_client import table_execute

log = logging.getLogger(__name__)

TABLE = "google_documents"
ARCHIVE_COLUMNS = frozenset({"search_text", "archive_data", "content_archived_at", "html"})
LIST_COLUMNS = (
    "id,google_doc_id,url,title,excerpt,search_text,headings,word_count,character_count,"
    "language,preview_url,preview_image_url,images_count,status,content_archived_at,"
    "shared_by_email,shared_by_name,shared_at,document_modified_at,"
    "crawled_at,created_at"
)
LIST_COLUMNS_LEGACY = (
    "id,google_doc_id,url,title,excerpt,headings,word_count,character_count,"
    "language,preview_url,preview_image_url,images_count,status,"
    "crawled_at,created_at"
)
DETAIL_COLUMNS = (
    "id,google_doc_id,url,title,excerpt,clean_text,search_text,headings,word_count,"
    "character_count,language,sha256,preview_url,preview_image_url,images_count,archive_data,"
    "status,error_message,content_archived_at,shared_by_email,shared_by_name,shared_at,"
    "document_modified_at,crawled_at,created_at,updated_at"
)
DETAIL_COLUMNS_LEGACY = (
    "id,google_doc_id,url,title,excerpt,clean_text,headings,word_count,"
    "character_count,language,sha256,preview_url,preview_image_url,images_count,"
    "status,error_message,crawled_at,created_at,updated_at"
)
SEARCH_COLUMNS = (
    "id,google_doc_id,url,title,excerpt,search_text,headings,word_count,language,preview_url,"
    "preview_image_url,content_archived_at,shared_by_email,shared_at"
)
SEARCH_COLUMNS_LEGACY = (
    "id,google_doc_id,url,title,excerpt,clean_text,headings,word_count,language,preview_url,"
    "preview_image_url,crawled_at"
)
SORT_COLUMNS = {
    "crawled_at": "crawled_at",
    "created_at": "created_at",
    "title": "title",
    "word_count": "word_count",
    "character_count": "character_count",
}


def build_preview_url(google_doc_id: str, width: int = 640, height: int = 480) -> str:
    doc_id = str(google_doc_id or "").strip()
    return f"https://drive.google.com/thumbnail?id={doc_id}&sz=w{width}-h{height}"


def build_excerpt(text: str | None, *, max_len: int = 240) -> str | None:
    if not text:
        return None
    collapsed = " ".join(str(text).split())
    if not collapsed:
        return None
    if len(collapsed) <= max_len:
        return collapsed
    return collapsed[: max_len - 1].rstrip() + "…"


def _is_missing_table(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "google_documents" in msg and (
        "pgrst205" in msg or "could not find" in msg or "does not exist" in msg
    ) and "column" not in msg


def _is_missing_archive_column(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "42703" in msg or (
        "pgrst204" in msg and any(col in msg for col in ARCHIVE_COLUMNS)
    )


def _require_table(exc: Exception) -> None:
    if _is_missing_table(exc):
        raise HTTPException(
            503,
            detail="Table google_documents is missing. Run schema/google_documents.sql in Supabase.",
        ) from exc
    raise exc


def _ensure_legacy_archive_fields(row: dict[str, Any]) -> None:
    if row.get("archive_data"):
        return
    clean_text = row.get("clean_text")
    if not clean_text:
        return
    row["archive_data"] = build_minimal_archive_data(
        headings=row.get("headings"),
        clean_text=clean_text,
    )
    if not row.get("search_text"):
        row["search_text"] = rebuild_search_text_from_row(row)


def _ensure_preview_fields(row: dict[str, Any]) -> None:
    doc_id = str(row.get("google_doc_id") or "").strip()
    if not doc_id:
        return
    if not row.get("preview_url"):
        row["preview_url"] = build_preview_url(doc_id)
    if not row.get("preview_image_url"):
        row["preview_image_url"] = row["preview_url"]


def _build_snippet(row: dict[str, Any], needle: str, *, radius: int = 120) -> str:
    source = str(row.get("search_text") or row.get("excerpt") or row.get("clean_text") or "")
    if not source:
        return ""
    lower = source.lower()
    idx = lower.find(needle.lower())
    if idx < 0:
        return source[:240] + ("…" if len(source) > 240 else "")
    start = max(0, idx - radius)
    end = min(len(source), idx + len(needle) + radius)
    snippet = source[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(source):
        snippet += "…"
    return snippet


def list_documents(
    *,
    q: str = "",
    status: str = "parsed",
    sort: str = "crawled_at",
    descending: bool = True,
    offset: int = 0,
    limit: int = 24,
) -> tuple[list[dict[str, Any]], int | None]:
    column = SORT_COLUMNS.get(sort, "crawled_at")
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    def build(sb, *, columns: str = LIST_COLUMNS):
        query = sb.table(TABLE).select(columns, count="exact")
        if status:
            query = query.eq("status", status)
        if q.strip():
            needle = q.strip()
            if columns == LIST_COLUMNS:
                query = query.or_(
                    f"title.ilike.%{needle}%,excerpt.ilike.%{needle}%,headings.ilike.%{needle}%,"
                    f"search_text.ilike.%{needle}%,clean_text.ilike.%{needle}%,"
                    f"shared_by_email.ilike.%{needle}%"
                )
            else:
                query = query.or_(
                    f"title.ilike.%{needle}%,excerpt.ilike.%{needle}%,headings.ilike.%{needle}%,"
                    f"clean_text.ilike.%{needle}%"
                )
        return query.order(column, desc=descending).range(offset, offset + limit - 1)

    try:
        result = table_execute(lambda sb: build(sb))
    except Exception as exc:
        if _is_missing_archive_column(exc):
            result = table_execute(lambda sb: build(sb, columns=LIST_COLUMNS_LEGACY))
        else:
            _require_table(exc)

    rows = result.data or []
    for row in rows:
        _ensure_preview_fields(row)
        _ensure_legacy_archive_fields(row)
    return rows, result.count


def get_document(google_doc_id: str) -> dict[str, Any] | None:
    doc_id = str(google_doc_id or "").strip()
    if not doc_id:
        return None

    def fetch(columns: str):
        return table_execute(
            lambda sb: sb.table(TABLE).select(columns).eq("google_doc_id", doc_id).limit(1)
        )

    try:
        result = fetch(DETAIL_COLUMNS)
    except Exception as exc:
        if _is_missing_archive_column(exc):
            result = fetch(DETAIL_COLUMNS_LEGACY)
        else:
            _require_table(exc)

    rows = result.data or []
    if not rows:
        return None
    row = rows[0]
    _ensure_preview_fields(row)
    _ensure_legacy_archive_fields(row)
    if not row.get("excerpt") and row.get("clean_text"):
        row["excerpt"] = build_excerpt(row.get("clean_text"))
    return row


def fetch_candidates_for_ranking(q: str, *, limit: int = 120) -> list[dict[str, Any]]:
    needle = q.strip()
    limit = max(1, min(limit, 200))
    if not needle:
        rows, _ = list_documents(status="parsed", sort="crawled_at", descending=True, limit=limit, offset=0)
        return rows

    pattern = f"%{needle}%"

    def build(sb, *, columns: str = SEARCH_COLUMNS, legacy: bool = False):
        order_col = "crawled_at" if legacy else "content_archived_at"
        return (
            sb.table(TABLE)
            .select(columns)
            .eq("status", "parsed")
            .or_(
                f"title.ilike.{pattern},excerpt.ilike.{pattern},headings.ilike.{pattern},"
                + (
                    f"clean_text.ilike.{pattern}"
                    if legacy
                    else f"search_text.ilike.{pattern},clean_text.ilike.{pattern}"
                )
            )
            .order(order_col, desc=True)
            .limit(limit)
        )

    try:
        result = table_execute(lambda sb: build(sb))
    except Exception as exc:
        if _is_missing_archive_column(exc):
            result = table_execute(lambda sb: build(sb, columns=SEARCH_COLUMNS_LEGACY, legacy=True))
        else:
            _require_table(exc)

    rows = result.data or []
    for row in rows:
        _ensure_preview_fields(row)
        _ensure_legacy_archive_fields(row)
    return rows[:limit]


def search_documents(
    *,
    q: str,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int | None]:
    needle = q.strip()
    if not needle:
        return [], 0
    limit = max(1, min(limit, 50))
    offset = max(0, offset)
    pattern = f"%{needle}%"

    def build(sb, *, columns: str = SEARCH_COLUMNS, legacy: bool = False):
        order_col = "crawled_at" if legacy else "content_archived_at"
        return (
            sb.table(TABLE)
            .select(columns, count="exact")
            .eq("status", "parsed")
            .or_(
                f"title.ilike.{pattern},excerpt.ilike.{pattern},headings.ilike.{pattern},"
                + (
                    f"clean_text.ilike.{pattern}"
                    if legacy
                    else f"search_text.ilike.{pattern},clean_text.ilike.{pattern}"
                )
            )
            .order(order_col, desc=True)
            .range(offset, offset + limit - 1)
        )

    try:
        result = table_execute(lambda sb: build(sb))
    except Exception as exc:
        if _is_missing_archive_column(exc):
            result = table_execute(lambda sb: build(sb, columns=SEARCH_COLUMNS_LEGACY, legacy=True))
        else:
            _require_table(exc)

    rows = result.data or []
    for row in rows:
        _ensure_preview_fields(row)
        _ensure_legacy_archive_fields(row)
        row["snippet"] = _build_snippet(row, needle)
    return rows, result.count


def get_stats() -> dict[str, Any]:
    try:
        total = table_execute(lambda sb: sb.table(TABLE).select("id", count="exact", head=True))
        parsed = table_execute(
            lambda sb: sb.table(TABLE).select("id", count="exact", head=True).eq("status", "parsed")
        )
        with_content = table_execute(
            lambda sb: sb.table(TABLE)
            .select("id", count="exact", head=True)
            .eq("status", "parsed")
            .not_.is_("clean_text", "null")
        )
        with_images = table_execute(
            lambda sb: sb.table(TABLE)
            .select("id", count="exact", head=True)
            .eq("status", "parsed")
            .gt("images_count", 0)
        )
    except Exception as exc:
        _require_table(exc)

    return {
        "total": total.count or 0,
        "parsed": parsed.count or 0,
        "with_content": with_content.count or 0,
        "with_images": with_images.count or 0,
    }


def _strip_archive_columns(batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: v for k, v in row.items() if k not in ARCHIVE_COLUMNS} for row in batch]


def upsert_batch(batch: list[dict[str, Any]]) -> int:
    if not batch:
        return 0
    try:
        table_execute(lambda sb: sb.table(TABLE).upsert(batch, on_conflict="google_doc_id"))
        return len(batch)
    except Exception as exc:
        if _is_missing_archive_column(exc):
            log.warning("Archive columns missing; upserting legacy columns only.")
            legacy = _strip_archive_columns(batch)
            try:
                table_execute(lambda sb: sb.table(TABLE).upsert(legacy, on_conflict="google_doc_id"))
                return len(batch)
            except Exception as legacy_exc:
                _require_table(legacy_exc)
                return 0
        _require_table(exc)
        return 0
