#!/usr/bin/env python3
"""Generate per-SQL-file MongoDB scripts in schema/mongodb/."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from outreach_db.mongodb_schema import _index_specs  # noqa: E402

# SQL filename -> collection names (Postgres-only files map to empty list + note)
SQL_MODULES: dict[str, tuple[str, list[str]]] = {
    "github_users.sql": (
        "Collection `github_users` — GitHub user profiles scraped via REST API.",
        ["github_users"],
    ),
    "github_users_indexes.sql": (
        "Additional indexes on `github_users` (base table indexes).",
        ["github_users"],
    ),
    "github_users_country_indexes.sql": (
        "Partial indexes on `github_users` for users with email, per country.",
        ["github_users"],
    ),
    "github_users_enrichment.sql": (
        "Enrichment columns on `github_users` (schemaless in MongoDB — no migration needed).",
        ["github_users"],
    ),
    "fix_github_users_identity_conflicts.sql": (
        "Postgres-only: dedupe conflicting login/id rows. MongoDB uses unique indexes on id and login.",
        [],
    ),
    "country_stats.sql": (
        "Collection `github_user_country_stats` — run rebuildCountryStats() instead of SQL triggers.",
        ["github_user_country_stats"],
    ),
    "management_tables.sql": (
        "Collections: scraping_runs, github_tokens, scheduled_jobs.",
        ["scraping_runs", "github_tokens", "scheduled_jobs"],
    ),
    "google_documents.sql": ("Collection `google_documents`.", ["google_documents"]),
    "google_docs_crawl_runs.sql": ("Collection `google_docs_crawl_runs`.", ["google_docs_crawl_runs"]),
    "google_docs_archive.sql": (
        "Archive fields on `google_documents` (content_archived_at index).",
        ["google_documents"],
    ),
    "google_docs_sharing_metadata.sql": (
        "Sharing metadata fields on `google_documents` (shared_by_email, shared_at).",
        ["google_documents"],
    ),
    "google_docs_setup.sql": (
        "Combined Google Docs schema: google_documents + google_docs_crawl_runs.",
        ["google_documents", "google_docs_crawl_runs"],
    ),
    "chat.sql": (
        "Chat collections: chat_conversations, chat_members, chat_messages, chat_typing, "
        "chat_direct_pairs, chat_presence, chat_reactions.",
        [
            "chat_conversations",
            "chat_members",
            "chat_messages",
            "chat_typing",
            "chat_direct_pairs",
            "chat_presence",
            "chat_reactions",
        ],
    ),
    "chat_v2.sql": ("Chat v2 — indexes on chat_messages (client_message_id).", ["chat_messages"]),
    "chat_v3.sql": ("Chat v3 — chat_reactions collection.", ["chat_reactions"]),
    "chat_v4.sql": ("Chat v4 — chat_presence collection.", ["chat_presence"]),
    "chat_v5.sql": ("Chat v5 — chat_direct_pairs collection.", ["chat_direct_pairs"]),
    "chat_v6.sql": ("Chat v6 — chat_typing collection.", ["chat_typing"]),
    "chat_v7.sql": ("Chat v7 — client message dedupe index on chat_messages.", ["chat_messages"]),
    "chat_v8.sql": (
        "Password-protected messages: is_protected fields on chat_messages + chat_message_unlocks.",
        ["chat_messages", "chat_message_unlocks"],
    ),
    "extension_contacts.sql": ("Collection `extension_contacts`.", ["extension_contacts"]),
    "extension_join_requests.sql": ("Collection `extension_join_requests`.", ["extension_join_requests"]),
    "extension_ai_access_requests.sql": (
        "Collection `extension_ai_access_requests`.",
        ["extension_ai_access_requests"],
    ),
    "extension_anon_read.sql": (
        "Postgres-only: RLS policies for anonymous read. Enforced in application code for MongoDB.",
        [],
    ),
    "registration_ip_locks.sql": ("Collection `registration_ip_locks`.", ["registration_ip_locks"]),
    "app_releases.sql": ("Collection `app_releases`.", ["app_releases"]),
    "profile_avatars_storage.sql": (
        "Postgres/Supabase Storage only — avatar files stored on disk or Supabase bucket, not MongoDB.",
        [],
    ),
    "auth_users": (
        "Collection `auth_users` for MongoDB auth mode (no Postgres SQL file).",
        ["auth_users"],
    ),
}

# Build collection -> index specs lookup
COL_SPECS: dict[str, list[dict]] = {}
for col, specs in _index_specs():
    COL_SPECS[col] = specs


def py_keys_to_js(keys: list) -> str:
    parts = []
    for k, v in keys:
        if k == "text":
            parts.append(f'{json.dumps(k)}: "text"')
        else:
            parts.append(f"{json.dumps(k)}: {v}")
    return "{" + ", ".join(parts) + "}"


def spec_to_js(col: str, spec: dict) -> str:
    keys_js = py_keys_to_js(spec["keys"])
    opts = {k: spec[k] for k in ("unique", "sparse", "name", "default_language", "partialFilterExpression") if k in spec}
    if opts:
        opts_js = json.dumps(opts, separators=(",", ": ")).strip("{}")
        return f'idx("{col}", {{ keys: {keys_js}, {opts_js} }});'
    return f'idx("{col}", {{ keys: {keys_js} }});'


def render_module(sql_name: str, description: str, collections: list[str]) -> str:
    stem = sql_name.replace(".sql", "")
    lines = [
        f"/**",
        f" * MongoDB equivalent of schema/{sql_name}",
        f" * {description}",
        f" *",
        f" *   mongosh \"$MONGODB_URI\" schema/mongodb/{stem}.mongodb.js",
        f" */",
        "",
        'load("schema/mongodb/_common.mongodb.js");',
        "",
        f'print("Applying schema/mongodb/{stem}.mongodb.js to " + mongoDbName());',
        "",
    ]
    if not collections:
        lines.extend(
            [
                'print("No MongoDB operations — Postgres/Supabase only. See schema/mongodb/README.md.");',
                "",
            ]
        )
        return "\n".join(lines)

    seen_cols: set[str] = set()
    for col in collections:
        if col in seen_cols:
            continue
        seen_cols.add(col)
        specs = COL_SPECS.get(col, [])
        if not specs:
            continue
        lines.append(f"// {col}")
        for spec in specs:
            lines.append(spec_to_js(col, spec))
        lines.append("")

    if sql_name == "country_stats.sql":
        lines.extend(
            [
                "// Replaces SQL rebuild_github_user_country_stats() + trigger",
                "rebuildCountryStats();",
                "",
            ]
        )

    lines.append('print("Done.");')
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    out_dir = ROOT / "schema" / "mongodb"
    for sql_name, (desc, cols) in SQL_MODULES.items():
        stem = sql_name.replace(".sql", "")
        path = out_dir / f"{stem}.mongodb.js"
        path.write_text(render_module(sql_name, desc, cols), encoding="utf-8")
        print(f"Wrote {path.name}")


if __name__ == "__main__":
    main()
