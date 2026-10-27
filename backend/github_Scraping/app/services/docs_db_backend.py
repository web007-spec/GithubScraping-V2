"""Google Docs storage backend — MongoDB (preferred) or Supabase."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.services.database import use_mongodb as app_use_mongodb

log = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


def use_mongodb_for_docs() -> bool:
    settings = get_settings()
    docs_mode = (settings.google_docs_storage or "auto").strip().lower()
    if docs_mode == "supabase":
        return False
    if docs_mode == "mongodb":
        uri = (settings.mongodb_uri or "").strip()
        if not uri:
            raise RuntimeError("GOOGLE_DOCS_STORAGE=mongodb but MONGODB_URI is not set")
        return True
    return app_use_mongodb()


def use_mongodb() -> bool:
    return use_mongodb_for_docs()


def storage_label() -> str:
    return "mongodb" if use_mongodb() else "supabase"


def ensure_storage() -> None:
    if not use_mongodb():
        return
    from outreach_db.client import ensure_indexes

    ensure_indexes()
    log.info("MongoDB indexes ensured for Google Docs collections")


def storage_ready() -> dict[str, Any]:
    from app.services.database import use_mongodb

    if use_mongodb():
        from outreach_db.client import ping
        from google_docs_db import crawl_runs, documents

        if not ping():
            return {"ok": False, "storage": "mongodb", "missing": ["mongodb_connection"]}
        ready = documents.is_ready() and crawl_runs.is_ready()
        return {
            "ok": ready,
            "storage": "mongodb",
            "missing_tables": [] if ready else ["google_documents", "google_docs_crawl_runs"],
        }

    from app.services.supabase_client import table_execute

    missing: list[str] = []
    for table in ("google_documents", "google_docs_crawl_runs"):
        try:
            table_execute(lambda sb, t=table: sb.table(t).select("id", count="exact", head=True))
        except Exception as exc:
            msg = str(exc).lower()
            if table in msg or "pgrst205" in msg or "could not find" in msg:
                missing.append(table)
            else:
                raise
    return {
        "ok": not missing,
        "storage": "supabase",
        "missing_tables": missing,
    }


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


def list_documents(**kwargs) -> tuple[list[dict[str, Any]], int | None]:
    if use_mongodb():
        from google_docs_db import documents as mongo_docs

        items, total = mongo_docs.list_documents(**kwargs)
        return items, total

    from app.services.google_docs_supabase import list_documents as sb_list

    return sb_list(**kwargs)


def get_document(google_doc_id: str) -> dict[str, Any] | None:
    if use_mongodb():
        from google_docs_db import documents as mongo_docs

        return mongo_docs.get_by_doc_id(google_doc_id)

    from app.services.google_docs_supabase import get_document as sb_get

    return sb_get(google_doc_id)


def search_documents(**kwargs) -> tuple[list[dict[str, Any]], int | None]:
    if use_mongodb():
        from google_docs_db import documents as mongo_docs

        return mongo_docs.search_documents(**kwargs)

    from app.services.google_docs_supabase import search_documents as sb_search

    return sb_search(**kwargs)


def fetch_candidates_for_ranking(q: str, *, limit: int = 120) -> list[dict[str, Any]]:
    if use_mongodb():
        from google_docs_db import documents as mongo_docs

        return mongo_docs.fetch_candidates_for_ranking(q, limit=limit)

    from app.services.google_docs_supabase import fetch_candidates_for_ranking as sb_fetch

    return sb_fetch(q, limit=limit)


def get_stats() -> dict[str, Any]:
    if use_mongodb():
        from google_docs_db import documents as mongo_docs

        return mongo_docs.get_stats()

    from app.services.google_docs_supabase import get_stats as sb_stats

    return sb_stats()


def upsert_documents(batch: list[dict[str, Any]]) -> int:
    if use_mongodb():
        from google_docs_db import documents as mongo_docs

        return mongo_docs.upsert_many(batch)

    from app.services.google_docs_supabase import upsert_batch as sb_upsert

    return sb_upsert(batch)


# ---------------------------------------------------------------------------
# Crawl runs
# ---------------------------------------------------------------------------


def crawl_fetch_run(run_id: str) -> dict[str, Any] | None:
    if use_mongodb():
        from google_docs_db import crawl_runs as mongo_runs

        return mongo_runs.fetch_run(run_id)

    from app.services.crawl_runs_supabase import fetch_run_raw

    return fetch_run_raw(run_id)


def crawl_list_runs(limit: int = 20) -> list[dict[str, Any]]:
    if use_mongodb():
        from google_docs_db import crawl_runs as mongo_runs

        return mongo_runs.list_runs(limit)

    from app.services.crawl_runs_supabase import list_runs_raw

    return list_runs_raw(limit)


def crawl_get_active_run() -> dict[str, Any] | None:
    if use_mongodb():
        from google_docs_db import crawl_runs as mongo_runs

        return mongo_runs.get_active_run()

    from app.services.crawl_runs_supabase import get_active_run_raw

    return get_active_run_raw()


def crawl_insert_run(*, mode: str, config: dict[str, Any]) -> dict[str, Any]:
    if use_mongodb():
        from google_docs_db import crawl_runs as mongo_runs

        return mongo_runs.insert_run(mode=mode, config=config)

    from app.services.crawl_runs_supabase import insert_run_raw

    return insert_run_raw(mode=mode, config=config)


def crawl_update_run(run_id: str, patch: dict[str, Any]) -> None:
    if use_mongodb():
        from google_docs_db import crawl_runs as mongo_runs

        mongo_runs.update_run(run_id, patch)
        return

    from app.services.crawl_runs_supabase import update_run_raw

    update_run_raw(run_id, patch)


def crawl_append_log(run_id: str, message: str) -> None:
    if use_mongodb():
        from google_docs_db import crawl_runs as mongo_runs

        mongo_runs.append_log(run_id, message)
        return

    from app.services.crawl_runs_supabase import append_log_raw

    append_log_raw(run_id, message)
