"""Re-fetch full profiles for users already in the database."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import get_settings
from app.crypto import decrypt_token
from app.dependencies import require_admin
from app.scraper.core import GitHubClient
from app.scraper.profile import enrich_user_profile
from app.services.supabase_client import get_supabase
from app.services.user_rows import upsert_user_rows

router = APIRouter(prefix="/users", tags=["users"])
log = logging.getLogger(__name__)


@router.post("/enrich")
async def enrich_existing_users(
    limit: int = Query(100, ge=1, le=500),
    country: str | None = None,
    _user=Depends(require_admin),
) -> dict:
    settings = get_settings()
    sb = get_supabase()

    token_row = (
        sb.table("github_tokens")
        .select("*")
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if not token_row.data:
        raise HTTPException(400, detail="No active GitHub token")

    plain = decrypt_token(token_row.data[0]["token_value"], settings.token_encryption_key)
    github = GitHubClient(plain)

    query = sb.table("github_users").select("login,country")
    if country:
        query = query.eq("country", country)
    rows = query.limit(limit).execute().data or []

    updated = 0
    with_email = 0
    with_bio = 0
    errors = 0
    pending: list[dict] = []

    for row in rows:
        login = row["login"]
        c = row.get("country") or country or "unknown"
        try:
            enriched = enrich_user_profile(github, login, c, full=False, email_only=True)
            if not enriched or not enriched.get("email"):
                errors += 1
                continue
            pending.append(enriched)
            if enriched.get("email"):
                with_email += 1
            if enriched.get("bio") or enriched.get("description"):
                with_bio += 1
            if len(pending) >= 50:
                upsert_user_rows(pending)
                updated += len(pending)
                pending.clear()
        except Exception as exc:
            log.warning("Enrich failed for %s: %s", login, exc)
            errors += 1

    if pending:
        upsert_user_rows(pending)
        updated += len(pending)

    return {
        "processed": len(rows),
        "updated": updated,
        "with_email": with_email,
        "with_description": with_bio,
        "errors": errors,
        "note": "Stores full profile in profile_data. GitHub hides most emails unless public.",
    }
