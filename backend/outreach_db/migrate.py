"""One-time migration: copy all Supabase Postgres tables into MongoDB."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

log = logging.getLogger(__name__)

TABLES = [
    "github_users",
    "github_user_country_stats",
    "scraping_runs",
    "github_tokens",
    "scheduled_jobs",
    "google_documents",
    "google_docs_crawl_runs",
    "extension_contacts",
    "extension_join_requests",
    "extension_ai_access_requests",
    "registration_ip_locks",
    "app_releases",
    "chat_conversations",
    "chat_members",
    "chat_messages",
    "chat_typing",
    "chat_direct_pairs",
    "chat_presence",
    "chat_reactions",
    "chat_message_unlocks",
]

PAGE_SIZE = 500


def _load_env() -> None:
    from dotenv import load_dotenv

    api_env = BACKEND_ROOT / "github_Scraping" / ".env"
    if api_env.is_file():
        load_dotenv(api_env)


def _fetch_all_rows(sb: Any, table: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        end = offset + PAGE_SIZE - 1
        try:
            result = sb.table(table).select("*").range(offset, end).execute()
        except Exception as exc:
            msg = str(exc).lower()
            if "pgrst205" in msg or "could not find" in msg:
                log.warning("  %s: table missing in Supabase, skipping", table)
                return []
            raise
        batch = result.data or []
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        log.info("  %s: fetched %s rows…", table, len(rows))
    return rows


PAGE_SIZE = 500
BATCH_WRITE = 200


def _sanitize_doc(doc: dict[str, Any]) -> dict[str, Any]:
    """Text-indexed collections reject non-string `language` (including null)."""
    out = dict(doc)
    if not isinstance(out.get("language"), str):
        out.pop("language", None)
    return out


def _upsert_rows(table: str, rows: list[dict[str, Any]]) -> int:
    from pymongo import ReplaceOne

    from outreach_db.client import ensure_indexes, get_database

    if not rows:
        return 0
    ensure_indexes()
    col = get_database()[table]
    ops: list[ReplaceOne] = []
    loose = 0

    for row in rows:
        doc = _sanitize_doc(dict(row))
        doc_id = doc.get("id")
        if doc_id:
            ops.append(ReplaceOne({"id": doc_id}, doc, upsert=True))
        elif table == "github_user_country_stats" and doc.get("country"):
            ops.append(ReplaceOne({"country": doc["country"]}, doc, upsert=True))
        elif table == "chat_members":
            ops.append(
                ReplaceOne(
                    {"conversation_id": doc.get("conversation_id"), "user_id": doc.get("user_id")},
                    doc,
                    upsert=True,
                )
            )
        elif table == "chat_typing":
            ops.append(
                ReplaceOne(
                    {"conversation_id": doc.get("conversation_id"), "user_id": doc.get("user_id")},
                    doc,
                    upsert=True,
                )
            )
        elif table == "chat_direct_pairs":
            ops.append(
                ReplaceOne({"user_a": doc.get("user_a"), "user_b": doc.get("user_b")}, doc, upsert=True)
            )
        elif table == "chat_presence" and doc.get("user_id"):
            ops.append(ReplaceOne({"user_id": doc["user_id"]}, doc, upsert=True))
        elif table == "chat_reactions":
            ops.append(
                ReplaceOne(
                    {
                        "message_id": doc.get("message_id"),
                        "user_id": doc.get("user_id"),
                        "emoji": doc.get("emoji"),
                    },
                    doc,
                    upsert=True,
                )
            )
        elif table == "google_documents" and doc.get("google_doc_id"):
            ops.append(ReplaceOne({"google_doc_id": doc["google_doc_id"]}, doc, upsert=True))
        elif table == "extension_contacts" and doc.get("github_login"):
            ops.append(ReplaceOne({"github_login": doc["github_login"]}, doc, upsert=True))
        else:
            col.insert_one(doc)
            loose += 1

    for i in range(0, len(ops), BATCH_WRITE):
        col.bulk_write(ops[i : i + BATCH_WRITE], ordered=False)

    return len(rows)


def migrate(*, dry_run: bool = False, tables: list[str] | None = None) -> dict[str, int]:
    _load_env()
    from supabase import create_client

    from outreach_db.client import ping

    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    mongo_uri = os.environ.get("MONGODB_URI", "").strip()

    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    if not mongo_uri:
        raise RuntimeError("MONGODB_URI required")
    if not ping():
        raise RuntimeError("Cannot connect to MongoDB — start the service and check MONGODB_URI")

    sb = create_client(url, key)
    summary: dict[str, int] = {}
    target_tables = tables or TABLES

    for table in target_tables:
        log.info("Migrating %s…", table)
        rows = _fetch_all_rows(sb, table)
        log.info("  %s: %s rows from Supabase", table, len(rows))
        if dry_run:
            summary[table] = len(rows)
            continue
        summary[table] = _upsert_rows(table, rows)

    return summary


def main() -> None:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Migrate Supabase tables to MongoDB")
    parser.add_argument("--dry-run", action="store_true", help="Count rows only, do not write")
    parser.add_argument("--table", action="append", help="Migrate only these tables (repeatable)")
    args = parser.parse_args()

    summary = migrate(dry_run=args.dry_run, tables=args.table)
    total = sum(summary.values())
    print("\nMigration complete:" if not args.dry_run else "\nDry run:")
    for table, count in summary.items():
        print(f"  {table}: {count}")
    print(f"  TOTAL: {total}")


if __name__ == "__main__":
    main()
