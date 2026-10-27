from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.config import get_settings
from app.crypto import decrypt_token, encrypt_token
from app.dependencies import require_admin
from app.models.schemas import TokenCreate, TokenResponse, TokenToggle
from app.scraper.core import GitHubClient
from app.services.supabase_client import get_supabase

router = APIRouter(prefix="/tokens", tags=["tokens"])


def _preview(token: str) -> str:
    if len(token) <= 8:
        return "****"
    return f"{token[:4]}...{token[-4:]}"


def _to_response(row: dict, preview: str | None = None) -> TokenResponse:
    return TokenResponse(
        id=row["id"],
        label=row.get("label") or "default",
        is_active=row.get("is_active", False),
        last_used_at=row.get("last_used_at"),
        rate_limit_remaining=row.get("rate_limit_remaining"),
        rate_limit_reset_at=row.get("rate_limit_reset_at"),
        notes=row.get("notes"),
        token_preview=preview,
    )


def get_active_token_plain() -> tuple[str, str]:
    """Return (token_id, plaintext token) for active token."""
    settings = get_settings()
    sb = get_supabase()
    result = (
        sb.table("github_tokens")
        .select("*")
        .eq("is_active", True)
        .order("last_used_at", desc=True)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(400, detail="No active GitHub token configured")
    row = result.data[0]
    plain = decrypt_token(row["token_value"], settings.token_encryption_key)
    return str(row["id"]), plain


@router.post("", response_model=TokenResponse)
async def add_token(body: TokenCreate, _user=Depends(require_admin)) -> TokenResponse:
    settings = get_settings()
    encrypted = encrypt_token(body.token, settings.token_encryption_key)

    client = GitHubClient(body.token)
    rate = client.check_rate_limit()
    core = rate.get("resources", {}).get("core", {})

    sb = get_supabase()
    if body.is_active:
        sb.table("github_tokens").update({"is_active": False}).eq("is_active", True).execute()

    insert = (
        sb.table("github_tokens")
        .insert(
            {
                "label": body.label,
                "token_value": encrypted,
                "is_active": body.is_active,
                "notes": body.notes,
                "rate_limit_remaining": core.get("remaining"),
                "rate_limit_reset_at": (
                    datetime.fromtimestamp(core["reset"], tz=timezone.utc).isoformat()
                    if core.get("reset")
                    else None
                ),
            }
        )
        .execute()
    )
    row = insert.data[0]
    return _to_response(row, _preview(body.token))


@router.get("", response_model=list[TokenResponse])
async def list_tokens(_user=Depends(require_admin)) -> list[TokenResponse]:
    result = get_supabase().table("github_tokens").select(
        "id,label,is_active,last_used_at,rate_limit_remaining,rate_limit_reset_at,notes,created_at"
    ).order("created_at", desc=True).execute()
    return [_to_response(r) for r in (result.data or [])]


@router.patch("/{token_id}", response_model=TokenResponse)
async def toggle_token(
    token_id: UUID,
    body: TokenToggle,
    _user=Depends(require_admin),
) -> TokenResponse:
    sb = get_supabase()
    if body.is_active:
        sb.table("github_tokens").update({"is_active": False}).eq("is_active", True).execute()

    sb.table("github_tokens").update({"is_active": body.is_active}).eq("id", str(token_id)).execute()
    row = sb.table("github_tokens").select(
        "id,label,is_active,last_used_at,rate_limit_remaining,rate_limit_reset_at,notes"
    ).eq("id", str(token_id)).single().execute()
    return _to_response(row.data)


@router.post("/{token_id}/refresh-rate-limit", response_model=TokenResponse)
async def refresh_rate_limit(token_id: UUID, _user=Depends(require_admin)) -> TokenResponse:
    settings = get_settings()
    sb = get_supabase()
    row = sb.table("github_tokens").select("*").eq("id", str(token_id)).single().execute()
    if not row.data:
        raise HTTPException(404, detail="Token not found")

    plain = decrypt_token(row.data["token_value"], settings.token_encryption_key)
    client = GitHubClient(plain)
    rate = client.check_rate_limit()
    core = rate.get("resources", {}).get("core", {})
    reset_at = None
    if core.get("reset"):
        reset_at = datetime.fromtimestamp(core["reset"], tz=timezone.utc).isoformat()

    sb.table("github_tokens").update(
        {
            "rate_limit_remaining": core.get("remaining"),
            "rate_limit_reset_at": reset_at,
        }
    ).eq("id", str(token_id)).execute()

    updated = sb.table("github_tokens").select(
        "id,label,is_active,last_used_at,rate_limit_remaining,rate_limit_reset_at,notes"
    ).eq("id", str(token_id)).single().execute()
    return _to_response(updated.data, _preview(plain))
