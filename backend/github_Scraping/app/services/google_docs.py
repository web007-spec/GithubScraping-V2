"""Google Docs explorer — list, import, and preview helpers."""

from __future__ import annotations

import csv
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import HTTPException

from app.services.google_docs_archive import (
    archive_json_loads,
    build_minimal_archive_data,
    cap_html,
    content_archived_at_iso,
    rebuild_search_text_from_row,
)
from app.services.docs_db_backend import (
    fetch_candidates_for_ranking as _db_fetch_candidates,
    get_document as _db_get_document,
    get_stats as _db_get_stats,
    list_documents as _db_list_documents,
    search_documents as _db_search_documents,
    upsert_documents as _db_upsert_documents,
)

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

DEFAULT_CSV_PATH = (
    Path(__file__).resolve().parents[3]
    / "google_docs_indexer"
    / "data"
    / "results.csv"
)
INDEXER_ROOT = Path(__file__).resolve().parents[3] / "google_docs_indexer"


def _apply_metadata_fields(payload: dict[str, Any], record: dict[str, str]) -> None:
    shared_by_email = (record.get("shared_by_email") or "").strip() or None
    shared_by_name = (record.get("shared_by_name") or "").strip() or None
    shared_at = (record.get("shared_at") or "").strip() or None
    document_modified_at = (record.get("document_modified_at") or "").strip() or None
    payload["shared_by_email"] = shared_by_email
    payload["shared_by_name"] = shared_by_name
    payload["shared_at"] = shared_at
    payload["document_modified_at"] = document_modified_at or shared_at


def _needs_email_enrichment(email: Any) -> bool:
    try:
        import sys

        indexer_root = str(INDEXER_ROOT)
        if indexer_root not in sys.path:
            sys.path.insert(0, indexer_root)
        from app.parser.metadata_extractor import is_placeholder_email

        return is_placeholder_email(str(email or ""))
    except Exception:
        return False


def _enrich_metadata_if_missing(payload: dict[str, Any]) -> None:
    doc_id = str(payload.get("google_doc_id") or "").strip()
    if not doc_id:
        return
    try:
        import sys

        indexer_root = str(INDEXER_ROOT)
        if indexer_root not in sys.path:
            sys.path.insert(0, indexer_root)
        from app.parser.metadata_extractor import fetch_document_metadata_sync, is_placeholder_email

        existing = str(payload.get("shared_by_email") or "").strip()
        if existing and not is_placeholder_email(existing):
            return

        meta = fetch_document_metadata_sync(doc_id)
        if meta.shared_by_email:
            payload["shared_by_email"] = meta.shared_by_email
        if meta.shared_by_name:
            payload["shared_by_name"] = meta.shared_by_name
        if meta.shared_at:
            payload["shared_at"] = meta.shared_at
        if meta.document_modified_at:
            payload["document_modified_at"] = meta.document_modified_at
    except Exception as exc:
        log.debug("Metadata enrichment skipped for %s: %s", doc_id, exc)


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


def _first_image_url(images: list[tuple[str, str | None]] | None) -> str | None:
    if not images:
        return None
    for src, _alt in images:
        src = str(src or "").strip()
        if src.startswith(("http://", "https://")):
            return src
    return None


def row_from_csv_record(record: dict[str, str]) -> dict[str, Any] | None:
    doc_id = str(record.get("google_doc_id") or "").strip()
    url = str(record.get("url") or "").strip()
    if not doc_id or not url:
        return None

    status = str(record.get("status") or "parsed").strip().lower()
    if status not in {
        "discovered",
        "queued",
        "downloading",
        "parsed",
        "failed",
        "skipped",
        "duplicate",
    }:
        status = "parsed"

    clean_text = record.get("clean_text") or None
    title = (record.get("title") or "").strip() or None
    crawled_raw = (record.get("crawled_at") or "").strip()

    word_count = _safe_int(record.get("word_count"))
    images_count = _safe_int(record.get("images_count")) or 0

    preview_url = (record.get("preview_url") or "").strip() or build_preview_url(doc_id)
    preview_image = (record.get("preview_image_url") or "").strip() or preview_url
    excerpt = (record.get("excerpt") or "").strip() or build_excerpt(clean_text)
    archive_data = archive_json_loads(record.get("archive_json"))
    if not archive_data and clean_text:
        archive_data = build_minimal_archive_data(headings=record.get("headings"), clean_text=clean_text)
    search_text = (record.get("search_text") or "").strip() or rebuild_search_text_from_row(
        {
            "title": title,
            "headings": record.get("headings"),
            "clean_text": clean_text,
            "archive_data": archive_data,
        }
    )

    payload: dict[str, Any] = {
        "google_doc_id": doc_id,
        "url": url,
        "title": title,
        "excerpt": excerpt,
        "clean_text": clean_text if status == "parsed" else None,
        "search_text": search_text or None,
        "headings": record.get("headings") or None,
        "archive_data": archive_data if archive_data else {},
        "word_count": word_count,
        "character_count": _safe_int(record.get("character_count")),
        "language": (record.get("language") or "").strip() or None,
        "sha256": (record.get("sha256") or "").strip() or None,
        "preview_url": preview_url,
        "preview_image_url": preview_image,
        "images_count": images_count,
        "status": status,
        "error_message": (record.get("error") or "").strip() or None,
        "crawled_at": crawled_raw or datetime.now(timezone.utc).isoformat(),
        "content_archived_at": content_archived_at_iso() if clean_text and status == "parsed" else None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _apply_metadata_fields(payload, record)
    if status == "parsed" and not payload.get("shared_by_email"):
        _enrich_metadata_if_missing(payload)
    return payload


def _safe_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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


def _ensure_preview_fields(row: dict[str, Any]) -> None:
    doc_id = str(row.get("google_doc_id") or "").strip()
    if not doc_id:
        return
    if not row.get("preview_url"):
        row["preview_url"] = build_preview_url(doc_id)
    if not row.get("preview_image_url"):
        row["preview_image_url"] = row["preview_url"]


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


def _postprocess_row(row: dict[str, Any]) -> None:
    _ensure_preview_fields(row)
    _ensure_legacy_archive_fields(row)


def list_documents(
    *,
    q: str = "",
    status: str = "parsed",
    sort: str = "crawled_at",
    descending: bool = True,
    offset: int = 0,
    limit: int = 24,
) -> tuple[list[dict[str, Any]], int | None]:
    rows, total = _db_list_documents(
        q=q,
        status=status,
        sort=sort,
        descending=descending,
        offset=offset,
        limit=limit,
    )
    for row in rows:
        _postprocess_row(row)
    return rows, total


def get_document(google_doc_id: str) -> dict[str, Any] | None:
    row = _db_get_document(google_doc_id)
    if not row:
        return None
    _postprocess_row(row)
    if not row.get("shared_by_email") or _needs_email_enrichment(row.get("shared_by_email")):
        patch: dict[str, Any] = dict(row)
        _enrich_metadata_if_missing(patch)
        for key in ("shared_by_email", "shared_by_name", "shared_at", "document_modified_at"):
            if patch.get(key):
                row[key] = patch[key]
    if not row.get("excerpt") and row.get("clean_text"):
        row["excerpt"] = build_excerpt(row.get("clean_text"))
    return row


def fetch_candidates_for_ranking(q: str, *, limit: int = 120) -> list[dict[str, Any]]:
    rows = _db_fetch_candidates(q, limit=limit)
    for row in rows:
        _postprocess_row(row)
    return rows


def search_documents(
    *,
    q: str,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int | None]:
    needle = q.strip()
    rows, total = _db_search_documents(q=needle, limit=limit, offset=offset)
    for row in rows:
        _postprocess_row(row)
        if "snippet" not in row:
            row["snippet"] = _build_snippet(row, needle)
    return rows, total


def get_stats() -> dict[str, Any]:
    return _db_get_stats()


def _upsert_batch(batch: list[dict[str, Any]]) -> int:
    return _db_upsert_documents(batch)


def import_csv(path: Path | None = None, *, only_parsed: bool = True) -> dict[str, Any]:
    csv_path = path or DEFAULT_CSV_PATH
    if not csv_path.is_file():
        raise HTTPException(404, detail=f"CSV not found: {csv_path}")

    imported = 0
    skipped = 0
    errors = 0

    try:
        csv.field_size_limit(sys.maxsize)
    except OverflowError:
        csv.field_size_limit(2**31 - 1)

    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        batch: list[dict[str, Any]] = []

        for record in reader:
            if only_parsed and str(record.get("status") or "").strip().lower() != "parsed":
                skipped += 1
                continue
            payload = row_from_csv_record(record)
            if not payload:
                skipped += 1
                continue
            batch.append(payload)

            if len(batch) >= 50:
                imported += _upsert_batch(batch)
                batch.clear()

        if batch:
            imported += _upsert_batch(batch)

    log.info("Imported %s Google Docs from %s (skipped=%s errors=%s)", imported, csv_path, skipped, errors)
    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "csv_path": str(csv_path),
    }


async def fetch_preview_bytes(google_doc_id: str) -> tuple[bytes, str]:
    doc_id = str(google_doc_id or "").strip()
    if not doc_id:
        raise HTTPException(400, detail="Missing google_doc_id")

    row = get_document(doc_id)
    candidates: list[str] = []
    if row:
        for key in ("preview_image_url", "preview_url"):
            url = str(row.get(key) or "").strip()
            if url and url not in candidates:
                candidates.append(url)
    candidates.append(build_preview_url(doc_id))

    last_error = "Preview unavailable"
    async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
        for url in candidates:
            try:
                response = await client.get(
                    url,
                    headers={"User-Agent": "GitHubScraper-DocsPreview/1.0"},
                )
                if response.status_code >= 400:
                    last_error = f"HTTP {response.status_code}"
                    continue
                content_type = response.headers.get("content-type", "image/jpeg")
                if "text/html" in content_type:
                    last_error = "Document requires sign-in"
                    continue
                return response.content, content_type.split(";")[0].strip() or "image/jpeg"
            except httpx.HTTPError as exc:
                last_error = str(exc)
                continue

    raise HTTPException(502, detail=last_error)
