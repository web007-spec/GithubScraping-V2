"""Persist Google Docs crawl results to MongoDB or Supabase."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from app.utils.archive_payload import archive_json_loads, rebuild_search_text_from_row
from app.utils.csv_writer import CsvRow
from app.utils.preview_utils import build_excerpt, build_preview_url

ProgressCallback = Callable[[CsvRow], None]

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _storage_mode() -> str:
    settings = None
    try:
        from app.config.settings import get_settings

        settings = get_settings()
    except Exception:
        settings = None

    mode = (
        os.environ.get("DATABASE_STORAGE")
        or os.environ.get("GOOGLE_DOCS_STORAGE")
        or (settings.database_storage if settings else "")
        or (settings.google_docs_storage if settings else "")
        or "auto"
    ).strip().lower()
    uri = (
        os.environ.get("MONGODB_URI")
        or os.environ.get("MONGO_URI")
        or (settings.mongodb_uri if settings else "")
        or ""
    ).strip()
    supabase_url = (os.environ.get("SUPABASE_URL") or getattr(settings, "supabase_url", "") or "").strip()
    supabase_key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_KEY")
        or getattr(settings, "supabase_key", "")
        or ""
    ).strip()

    if mode == "supabase":
        return "supabase" if supabase_url and supabase_key else "none"
    if mode == "mongodb":
        return "mongodb" if uri else "none"
    if uri:
        return "mongodb"
    if supabase_url and supabase_key:
        return "supabase"
    return "none"


def _mongodb_uri() -> str:
    try:
        from app.config.settings import get_settings

        settings = get_settings()
    except Exception:
        settings = None
    return (
        os.environ.get("MONGODB_URI")
        or os.environ.get("MONGO_URI")
        or (settings.mongodb_uri if settings else "")
        or ""
    ).strip()


def _mongodb_db_name() -> str:
    try:
        from app.config.settings import get_settings

        settings = get_settings()
    except Exception:
        settings = None
    return (
        os.environ.get("MONGODB_DB_NAME")
        or os.environ.get("MONGO_DB_NAME")
        or (settings.mongodb_db_name if settings else "")
        or "outreach_console"
    ).strip()


def is_db_storage_enabled() -> bool:
    return _storage_mode() in ("mongodb", "supabase")


def require_db_storage() -> None:
    if not is_db_storage_enabled():
        raise RuntimeError(
            "Database storage is required. Set MONGODB_URI (and DATABASE_STORAGE=mongodb) "
            "or SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY in the indexer .env."
        )


def load_resume_state() -> tuple[set[str], set[str]]:
    """Return (crawled_doc_ids, content_hashes) already stored in the database."""
    crawled_ids: set[str] = set()
    seen_hashes: set[str] = set()
    if not is_db_storage_enabled():
        return crawled_ids, seen_hashes

    if _storage_mode() == "mongodb":
        uri = _mongodb_uri()
        if uri and not os.environ.get("MONGODB_URI"):
            os.environ["MONGODB_URI"] = uri
        db_name = _mongodb_db_name()
        if db_name and not os.environ.get("MONGODB_DB_NAME"):
            os.environ["MONGODB_DB_NAME"] = db_name
        from google_docs_db.client import ensure_indexes, get_database

        ensure_indexes()
        col = get_database().google_documents
        for doc in col.find(
            {},
            {"google_doc_id": 1, "sha256": 1, "status": 1},
        ):
            doc_id = str(doc.get("google_doc_id") or "").strip()
            status = str(doc.get("status") or "").strip().lower()
            if doc_id and status in ("parsed", "failed", "duplicate", "skipped"):
                crawled_ids.add(doc_id)
            sha = str(doc.get("sha256") or "").strip()
            if sha and status == "parsed":
                seen_hashes.add(sha)
        return crawled_ids, seen_hashes

    from supabase import create_client

    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    client = create_client(url, key)
    offset = 0
    page_size = 500
    while True:
        result = (
            client.table("google_documents")
            .select("google_doc_id,sha256,status")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            break
        for doc in rows:
            doc_id = str(doc.get("google_doc_id") or "").strip()
            status = str(doc.get("status") or "").strip().lower()
            if doc_id and status in ("parsed", "failed", "duplicate", "skipped"):
                crawled_ids.add(doc_id)
            sha = str(doc.get("sha256") or "").strip()
            if sha and status == "parsed":
                seen_hashes.add(sha)
        if len(rows) < page_size:
            break
        offset += page_size
    return crawled_ids, seen_hashes


def _safe_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def csv_row_to_document(row: CsvRow) -> dict[str, Any]:
    doc_id = str(row.google_doc_id or "").strip()
    url = str(row.url or "").strip()
    status = str(row.status or "pending").strip().lower()
    clean_text = row.clean_text or None
    preview = (row.preview_url or "").strip() or build_preview_url(doc_id)
    preview_image = (row.preview_image_url or "").strip() or preview
    archive_data = archive_json_loads(row.archive_json) if row.archive_json else None
    title = (row.title or "").strip() or None
    search_text = (row.search_text or "").strip() or rebuild_search_text_from_row(
        {
            "title": title,
            "headings": row.headings,
            "clean_text": clean_text,
            "archive_data": archive_data,
        }
    )
    crawled_at = (row.crawled_at or "").strip() or _now_iso()
    payload: dict[str, Any] = {
        "google_doc_id": doc_id,
        "url": url,
        "title": title,
        "excerpt": (row.excerpt or "").strip() or (build_excerpt(clean_text) if clean_text else None),
        "clean_text": clean_text,
        "search_text": search_text or None,
        "headings": row.headings or None,
        "archive_data": archive_data,
        "word_count": row.word_count if row.word_count is not None else _safe_int(row.word_count),
        "character_count": row.character_count if row.character_count is not None else _safe_int(row.character_count),
        "language": (row.language or "").strip() or None,
        "sha256": (row.sha256 or "").strip() or None,
        "preview_url": preview,
        "preview_image_url": preview_image,
        "images_count": int(row.images_count or 0),
        "status": status,
        "shared_by_email": (row.shared_by_email or "").strip() or None,
        "shared_by_name": (row.shared_by_name or "").strip() or None,
        "shared_at": (row.shared_at or "").strip() or None,
        "document_modified_at": (row.document_modified_at or row.shared_at or "").strip() or None,
        "crawled_at": crawled_at,
        "content_archived_at": crawled_at if status == "parsed" and clean_text else None,
        "updated_at": _now_iso(),
        "error": (row.error or "").strip() or None,
    }
    from app.parser.metadata_extractor import fetch_document_metadata_sync, is_placeholder_email

    if status == "parsed" and (
        not payload.get("shared_by_email")
        or is_placeholder_email(str(payload.get("shared_by_email") or ""))
    ):
        meta = fetch_document_metadata_sync(doc_id)
        if meta.shared_by_email:
            payload["shared_by_email"] = meta.shared_by_email
        if meta.shared_by_name:
            payload["shared_by_name"] = meta.shared_by_name
        if meta.shared_at:
            payload["shared_at"] = meta.shared_at
        if meta.document_modified_at:
            payload["document_modified_at"] = meta.document_modified_at
    return payload


def persist_row(row: CsvRow) -> None:
    require_db_storage()
    if _storage_mode() == "mongodb":
        uri = _mongodb_uri()
        if uri and not os.environ.get("MONGODB_URI"):
            os.environ["MONGODB_URI"] = uri
        db_name = _mongodb_db_name()
        if db_name and not os.environ.get("MONGODB_DB_NAME"):
            os.environ["MONGODB_DB_NAME"] = db_name
    payload = csv_row_to_document(row)
    if _storage_mode() == "mongodb":
        from google_docs_db import documents

        documents.upsert_many([payload])
        return

    from supabase import create_client

    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    create_client(url, key).table("google_documents").upsert(
        payload, on_conflict="google_doc_id"
    ).execute()


def register_discovered(doc_id: str, url: str) -> bool:
    """Register a discovered URL in the database without crawling yet."""
    if not is_db_storage_enabled():
        return False
    if _storage_mode() == "mongodb":
        uri = _mongodb_uri()
        if uri and not os.environ.get("MONGODB_URI"):
            os.environ["MONGODB_URI"] = uri
        db_name = _mongodb_db_name()
        if db_name and not os.environ.get("MONGODB_DB_NAME"):
            os.environ["MONGODB_DB_NAME"] = db_name
        from google_docs_db.client import ensure_indexes, get_database

        ensure_indexes()
        existing = get_database().google_documents.find_one(
            {"google_doc_id": doc_id},
            {"status": 1, "clean_text": 1},
        )
        if existing:
            status = str(existing.get("status") or "").strip().lower()
            if status not in ("", "discovered") or existing.get("clean_text"):
                return False

    row = CsvRow(google_doc_id=doc_id, url=url, status="discovered")
    payload = csv_row_to_document(row)
    payload["status"] = "discovered"
    payload.pop("clean_text", None)
    payload.pop("content_archived_at", None)
    if _storage_mode() == "mongodb":
        from google_docs_db import documents

        documents.upsert_many([payload])
        return True
    from supabase import create_client

    url_env = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    create_client(url_env, key).table("google_documents").upsert(
        payload, on_conflict="google_doc_id"
    ).execute()
    return True


def register_discovered_many(discovered: list[tuple[str, str]]) -> int:
    count = 0
    for doc_id, url in discovered:
        if register_discovered(doc_id, url):
            count += 1
    if count:
        logger.info("Registered {} discovered URLs in database", count)
    return count
