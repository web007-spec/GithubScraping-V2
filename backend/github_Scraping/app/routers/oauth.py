"""Google OAuth for extension Gmail send (existing Google account, not App Password)."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings

router = APIRouter(prefix="/api/oauth/google", tags=["oauth"])


class GoogleTokenBody(BaseModel):
    code: str = Field(..., min_length=1)
    redirectUri: str = Field(..., min_length=1)


@router.get("/config")
async def google_oauth_config() -> dict:
    settings = get_settings()
    client_id = (settings.google_client_id or "").strip()
    if not client_id:
        return {
            "ok": False,
            "error": (
                "Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to backend/.env, "
                "or use a 16-character Gmail App Password in the extension."
            ),
        }
    return {"ok": True, "clientId": client_id}


@router.post("/token")
async def google_oauth_token(body: GoogleTokenBody) -> dict:
    settings = get_settings()
    client_id = (settings.google_client_id or "").strip()
    client_secret = (settings.google_client_secret or "").strip()
    if not client_id or not client_secret:
        raise HTTPException(
            400,
            detail="Server OAuth not configured. Use App Password in the extension.",
        )

    async with httpx.AsyncClient(timeout=30.0) as client:
        token_res = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": body.code.strip(),
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": body.redirectUri.strip(),
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        data = token_res.json() if token_res.content else {}

    if not token_res.is_success:
        raise HTTPException(
            400,
            detail=data.get("error_description") or data.get("error") or "Token exchange failed",
        )

    refresh_token = data.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            400,
            detail=(
                "No refresh token returned. Revoke this app at "
                "https://myaccount.google.com/permissions and connect again."
            ),
        )

    email = None
    access_token = data.get("access_token")
    if access_token:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                info_res = await client.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            if info_res.is_success:
                email = (info_res.json() or {}).get("email")
        except Exception:
            pass

    return {"ok": True, "refreshToken": refresh_token, "email": email}
