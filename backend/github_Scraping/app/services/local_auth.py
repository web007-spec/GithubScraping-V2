"""Local JWT authentication backed by MongoDB auth_users."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from fastapi import HTTPException
from jose import JWTError, jwt

from app.config import Settings, get_settings
from app.services.database import use_mongodb

log = logging.getLogger(__name__)

TOKEN_AUDIENCE = "authenticated"
TOKEN_EXPIRE_DAYS = 7


def auth_enabled() -> bool:
    return use_mongodb()


def _jwt_secret(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    secret = (settings.auth_jwt_secret or settings.token_encryption_key or "").strip()
    if len(secret) < 32:
        raise RuntimeError(
            "AUTH_JWT_SECRET or TOKEN_ENCRYPTION_KEY (32+ chars) required for MongoDB auth"
        )
    return secret


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def _user_label(row: dict[str, Any]) -> str:
    meta = row.get("user_metadata") or {}
    return (
        meta.get("display_name")
        or meta.get("full_name")
        or meta.get("name")
        or row.get("email", "").split("@")[0]
        or "User"
    )


def _avatar_url(row: dict[str, Any]) -> str | None:
    meta = row.get("user_metadata") or {}
    url = meta.get("avatar_url")
    return str(url).strip() if url else None


def create_access_token(user: dict[str, Any], settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user["id"],
        "email": user.get("email"),
        "app_metadata": user.get("app_metadata") or {},
        "user_metadata": user.get("user_metadata") or {},
        "aud": TOKEN_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=TOKEN_EXPIRE_DAYS)).timestamp()),
    }
    return jwt.encode(payload, _jwt_secret(settings), algorithm="HS256")


def verify_access_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    try:
        return jwt.decode(
            token,
            _jwt_secret(settings),
            algorithms=["HS256"],
            audience=TOKEN_AUDIENCE,
            options={"verify_aud": True},
        )
    except JWTError as exc:
        raise HTTPException(401, detail="Invalid or expired token. Sign in again.") from exc


def register_user(
    *,
    email: str,
    password: str,
    role: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    from outreach_db import auth_users

    settings = get_settings()
    normalized = email.strip().lower()
    if auth_users.get_by_email(normalized):
        raise HTTPException(409, detail="This email is already registered. Use Sign in instead.")
    user = auth_users.create_user(
        email=normalized,
        password_hash=hash_password(password),
        role=role or settings.admin_role,
        user_id=user_id,
    )
    return user


def login_user(*, email: str, password: str) -> dict[str, Any]:
    from outreach_db import auth_users

    row = auth_users.get_by_email(email)
    if not row or not row.get("password_hash"):
        raise HTTPException(401, detail="Wrong email or password.")
    if not verify_password(password, row["password_hash"]):
        raise HTTPException(401, detail="Wrong email or password.")
    row.pop("password_hash", None)
    settings = get_settings()
    token = create_access_token(row, settings)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": TOKEN_EXPIRE_DAYS * 86400,
        "user": {
            "id": row["id"],
            "email": row.get("email"),
            "role": (row.get("app_metadata") or {}).get("role"),
            "user_metadata": row.get("user_metadata") or {},
        },
    }


def grant_admin_role(user_id: str) -> None:
    from outreach_db import auth_users

    auth_users.update_user(user_id, {"app_metadata": {"role": get_settings().admin_role}})


def list_registered_users() -> list[dict[str, Any]]:
    from outreach_db import auth_users

    users: list[dict[str, Any]] = []
    for row in auth_users.list_all():
        uid = row.get("id")
        email = row.get("email")
        if not uid or not email:
            continue
        users.append(
            {
                "id": uid,
                "email": email,
                "display_name": _user_label(row),
                "avatar_url": _avatar_url(row),
            }
        )
    return users


def update_profile(user_id: str, *, metadata_patch: dict[str, Any]) -> dict[str, Any]:
    from outreach_db import auth_users

    row = auth_users.get_by_id(user_id)
    if not row:
        raise HTTPException(404, detail="User not found")
    meta = dict(row.get("user_metadata") or {})
    meta.update({k: v for k, v in metadata_patch.items() if v is not None})
    updated = auth_users.update_user(user_id, {"user_metadata": meta})
    if not updated:
        raise HTTPException(404, detail="User not found")
    updated.pop("password_hash", None)
    return updated


def change_password(user_id: str, *, current_password: str, new_password: str) -> None:
    from outreach_db import auth_users

    row = auth_users.get_by_id(user_id)
    if not row:
        raise HTTPException(404, detail="User not found")
    if not verify_password(current_password, str(row.get("password_hash") or "")):
        raise HTTPException(403, detail="Current password is incorrect")
    cleaned = new_password.strip()
    if len(cleaned) < 6:
        raise HTTPException(400, detail="New password must be at least 6 characters")
    if len(cleaned) > 128:
        raise HTTPException(400, detail="New password must be 128 characters or fewer")
    auth_users.set_password_hash(user_id, hash_password(cleaned))


def import_user_from_supabase(
    *,
    user_id: str,
    email: str,
    role: str,
    user_metadata: dict[str, Any] | None,
    password: str | None = None,
) -> dict[str, Any]:
    """Import a Supabase auth user into MongoDB (optional password for first login)."""
    from outreach_db import auth_users

    existing = auth_users.get_by_id(user_id) or auth_users.get_by_email(email)
    if existing:
        existing.pop("password_hash", None)
        return existing
    pwd_hash = hash_password(password or str(uuid.uuid4()))
    return auth_users.create_user(
        email=email,
        password_hash=pwd_hash,
        role=role,
        user_metadata=user_metadata,
        user_id=user_id,
    )
