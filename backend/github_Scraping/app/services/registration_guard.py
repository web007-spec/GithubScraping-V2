"""Registration IP lock helpers — MongoDB auth."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.services.supabase_client import table_execute


def _fetch_ip_lock(owner_ip: str) -> dict[str, Any] | None:
    result = table_execute(
        lambda client: client.table("registration_ip_locks")
        .select("*")
        .eq("owner_ip", owner_ip)
        .limit(1)
    )
    rows = result.data or []
    return rows[0] if rows else None


def _delete_ip_lock(owner_ip: str) -> None:
    table_execute(lambda client: client.table("registration_ip_locks").delete().eq("owner_ip", owner_ip))


def ensure_can_register(*, owner_ip: str, email: str) -> None:
    """
    Validate MongoDB registration is allowed.

    Only enforces unique email. Old IP locks are removed so they cannot block
    sign-up after the Supabase → MongoDB migration or on localhost.
    """
    from outreach_db import auth_users

    normalized = email.strip().lower()
    if auth_users.get_by_email(normalized):
        raise HTTPException(409, detail="This email is already registered. Use Sign in instead.")

    if _fetch_ip_lock(owner_ip):
        _delete_ip_lock(owner_ip)
