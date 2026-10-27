"""Normalize DB rows and handle missing Supabase columns gracefully."""

from __future__ import annotations

import logging
from typing import Any

from app.services.country_cache import invalidate_country_cache
from app.services.supabase_client import table_execute

log = logging.getLogger(__name__)

# Original table columns (always safe)
BASE_COLUMNS = {
    "id",
    "login",
    "name",
    "location",
    "company",
    "email",
    "bio",
    "public_repos",
    "followers",
    "following",
    "created_at",
    "updated_at",
    "last_scraped_at",
    "country",
}

EXTENDED_COLUMNS = BASE_COLUMNS | {
    "blog",
    "twitter_username",
    "github_url",
    "public_gists",
    "avatar_url",
    "email_source",
    "description",
    "all_emails",
    "social_links",
    "profile_data",
}

USER_SELECT_BASE = ",".join(sorted(BASE_COLUMNS))
USER_SELECT_EXTENDED = ",".join(sorted(EXTENDED_COLUMNS))
USER_LIST_COLUMNS = EXTENDED_COLUMNS - {"profile_data", "social_links", "avatar_url"}
USER_SELECT_LIST = ",".join(sorted(USER_LIST_COLUMNS))


def slim_row(row: dict[str, Any], extended: bool = True) -> dict[str, Any]:
    allowed = EXTENDED_COLUMNS if extended else BASE_COLUMNS
    return {k: v for k, v in row.items() if k in allowed}


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[Any, dict[str, Any]] = {}
    by_login: dict[str, Any] = {}
    for row in rows:
        row_id = row.get("id")
        login = str(row.get("login") or "").strip().lower()
        if row_id is None or not login:
            continue
        old_id_for_login = by_login.get(login)
        if old_id_for_login is not None and old_id_for_login in by_id:
            by_id.pop(old_id_for_login, None)
        by_id[row_id] = row
        by_login[login] = row_id
    return list(by_id.values())


def _upsert_rows(rows: list[dict[str, Any]]) -> None:
    try:
        table_execute(
            lambda sb: sb.table("github_users").upsert(rows, on_conflict="id")
        )
    except Exception as exc:
        msg = str(exc).lower()
        if "duplicate key" not in msg and "23505" not in msg:
            raise
        log.warning("ID upsert hit a secondary unique conflict; retrying rows by login")
        for row in rows:
            table_execute(
                lambda sb, r=row: sb.table("github_users").upsert(r, on_conflict="login")
            )


def upsert_user_rows(rows: list[dict[str, Any]], *, require_email: bool = True) -> None:
    if not rows:
        return
    if require_email:
        rows = [r for r in rows if r.get("email")]
    rows = _dedupe_rows(rows)
    if not rows:
        return
    extended_rows = [slim_row(r, extended=True) for r in rows]
    try:
        _upsert_rows(extended_rows)
    except Exception as exc:
        msg = str(exc).lower()
        if "column" not in msg and "42703" not in msg:
            raise
        log.warning("Extended columns missing — upserting base columns only. Run github_users_enrichment.sql")
        base_rows = [slim_row(r, extended=False) for r in rows]
        _upsert_rows(base_rows)
    invalidate_country_cache()
