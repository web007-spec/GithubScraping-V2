from __future__ import annotations

import logging
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import Settings, get_settings
from app.services.database import use_mongodb

log = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


def _payload_from_supabase_user(user: Any) -> dict[str, Any]:
    app_meta = getattr(user, "app_metadata", None) or {}
    if isinstance(app_meta, dict):
        metadata = app_meta
    else:
        metadata = dict(app_meta) if app_meta else {}

    return {
        "sub": user.id,
        "email": getattr(user, "email", None),
        "app_metadata": metadata,
        "user_metadata": getattr(user, "user_metadata", None) or {},
    }


def verify_jwt(token: str, settings: Settings) -> dict[str, Any]:
    """Verify bearer token — MongoDB local JWT or legacy Supabase JWT."""
    if use_mongodb():
        from app.services.local_auth import verify_access_token

        return verify_access_token(token, settings)

    return verify_supabase_jwt(token, settings)


def verify_supabase_jwt(token: str, settings: Settings) -> dict[str, Any]:
    """
    Validate JWT locally first (fast path). Falls back to Supabase Auth API only
    when local verification is unavailable or the token fails local checks.
    """
    secret = (settings.supabase_jwt_secret or settings.auth_jwt_secret or "").strip()
    if secret and len(secret) >= 32:
        try:
            return jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                audience="authenticated",
                options={"verify_aud": True},
            )
        except JWTError:
            pass

    from app.services.supabase_client import get_supabase

    sb = get_supabase()
    try:
        response = sb.auth.get_user(token)
        if response and response.user:
            return _payload_from_supabase_user(response.user)
    except Exception as exc:
        log.debug("Supabase get_user failed: %s", exc)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token. Sign out and sign in again.",
    )


async def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    payload = verify_jwt(credentials.credentials, settings)
    role = (payload.get("app_metadata") or {}).get("role")
    if role != settings.admin_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required. Sign out, then sign in again after registration.",
        )
    return payload
