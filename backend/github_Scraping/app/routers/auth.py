from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field

from app.config import Settings, get_settings
from app.dependencies import security, verify_jwt
from app.services.database import use_mongodb
from app.services.registration_guard import ensure_can_register
from app.services.supabase_client import get_supabase, table_execute

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger(__name__)


class GrantAdminResponse(BaseModel):
    ok: bool
    message: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    registration_secret: str | None = None


class RegisterResponse(BaseModel):
    ok: bool
    message: str
    email: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict[str, Any]


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = None
    avatar_url: str | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6, max_length=128)


def _check_registration_allowed(
    settings: Settings,
    registration_secret: str | None,
) -> None:
    if not settings.allow_public_registration:
        raise HTTPException(403, detail="Registration is disabled on this server")
    if settings.registration_secret:
        if registration_secret != settings.registration_secret:
            raise HTTPException(403, detail="Invalid registration secret")


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _is_missing_table_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "registration_ip_locks" in msg and ("does not exist" in msg or "404" in msg or "42p01" in msg)


def _auth_user_id(created: Any) -> str:
    user = getattr(created, "user", None)
    if user is not None:
        return str(getattr(user, "id", "") or "")
    if isinstance(created, dict):
        data = created.get("user") or created
        if isinstance(data, dict):
            return str(data.get("id") or "")
    return ""


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return verify_jwt(credentials.credentials, settings)


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, settings: Settings = Depends(get_settings)) -> LoginResponse:
    if not use_mongodb():
        raise HTTPException(
            400,
            detail="MongoDB auth is not enabled. Set MONGODB_URI and DATABASE_STORAGE=mongodb.",
        )
    from app.services.local_auth import login_user

    result = login_user(email=str(body.email), password=body.password)
    return LoginResponse(**result)


@router.post("/register", response_model=RegisterResponse)
async def register_user(
    request: Request,
    body: RegisterRequest,
    settings: Settings = Depends(get_settings),
) -> RegisterResponse:
    _check_registration_allowed(settings, body.registration_secret)

    email = str(body.email).strip().lower()
    owner_ip = _client_ip(request)

    if use_mongodb():
        from app.services.local_auth import register_user as mongo_register

        try:
            ensure_can_register(owner_ip=owner_ip, email=email)
            mongo_register(email=email, password=body.password)
            return RegisterResponse(
                ok=True,
                message="Account created. You can sign in now.",
                email=email,
            )
        except HTTPException:
            raise
        except Exception as exc:
            log.warning("register_user failed for %s: %s", email, exc)
            if _is_missing_table_error(exc):
                raise HTTPException(
                    500,
                    detail="Registration IP protection table is missing in MongoDB.",
                ) from exc
            msg = str(exc).lower()
            if "duplicate" in msg or "23505" in msg or "already registered" in msg:
                raise HTTPException(
                    409,
                    detail="This email is already registered. Use Sign in instead.",
                ) from exc
            raise HTTPException(400, detail=f"Could not create account: {exc}") from exc

    sb = get_supabase()
    try:
        existing_ip = table_execute(
            lambda client: client.table("registration_ip_locks")
            .select("email, created_at")
            .eq("owner_ip", owner_ip)
            .limit(1)
        )
        if existing_ip.data:
            raise HTTPException(
                409,
                detail="An account has already been registered from this IP address. Sign in with the existing account or contact the server owner.",
            )

        table_execute(
            lambda client: client.table("registration_ip_locks").insert(
                {"owner_ip": owner_ip, "email": email, "status": "pending"}
            )
        )
        inserted_ip_lock = True

        created = sb.auth.admin.create_user(
            {
                "email": email,
                "password": body.password,
                "email_confirm": True,
                "app_metadata": {"role": settings.admin_role},
            }
        )
        user_id = _auth_user_id(created)
        table_execute(
            lambda client: client.table("registration_ip_locks")
            .update({"user_id": user_id or None, "status": "created"})
            .eq("owner_ip", owner_ip)
        )
        return RegisterResponse(
            ok=True,
            message="Account created. You can sign in now.",
            email=email,
        )
    except HTTPException:
        raise
    except Exception as exc:
        msg = str(exc).lower()
        log.warning("register_user failed for %s: %s", email, exc)
        if inserted_ip_lock:
            try:
                table_execute(
                    lambda client: client.table("registration_ip_locks")
                    .delete()
                    .eq("owner_ip", owner_ip)
                    .eq("status", "pending")
                )
            except Exception:
                pass
        if _is_missing_table_error(exc):
            raise HTTPException(
                500,
                detail="Registration IP protection table is missing.",
            ) from exc
        if "duplicate" in msg or "23505" in msg:
            raise HTTPException(
                409,
                detail="An account has already been registered from this IP address.",
            ) from exc
        if "already" in msg or "registered" in msg or "exists" in msg:
            raise HTTPException(
                409,
                detail="This email is already registered. Use Sign in instead.",
            ) from exc
        raise HTTPException(400, detail=f"Could not create account: {exc}") from exc


@router.post("/grant-admin", response_model=GrantAdminResponse)
async def grant_admin(
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    x_registration_secret: str | None = Header(default=None),
) -> GrantAdminResponse:
    _check_registration_allowed(settings, x_registration_secret)

    role = (user.get("app_metadata") or {}).get("role")
    if role == settings.admin_role:
        return GrantAdminResponse(ok=True, message="Already an admin")

    user_id = user.get("sub")
    if not user_id:
        raise HTTPException(400, detail="Invalid token: missing user id")

    if use_mongodb():
        from app.services.local_auth import grant_admin_role

        grant_admin_role(str(user_id))
    else:
        sb = get_supabase()
        sb.auth.admin.update_user_by_id(
            user_id,
            {"app_metadata": {"role": settings.admin_role}},
        )

    return GrantAdminResponse(
        ok=True,
        message="Admin access granted. Sign out and sign in again if the dashboard does not load.",
    )


@router.get("/me")
async def me(user: dict = Depends(get_current_user)) -> dict:
    return {
        "id": user.get("sub"),
        "email": user.get("email"),
        "role": (user.get("app_metadata") or {}).get("role"),
        "user_metadata": user.get("user_metadata") or {},
    }


@router.patch("/profile")
async def patch_profile(
    body: ProfileUpdateRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    if not use_mongodb():
        raise HTTPException(400, detail="Profile API requires MongoDB auth mode.")
    from app.services.local_auth import update_profile as save_profile

    patch: dict[str, Any] = {}
    if body.display_name is not None:
        patch["display_name"] = body.display_name.strip()
    if body.avatar_url is not None:
        patch["avatar_url"] = body.avatar_url.strip()
    updated = save_profile(str(user.get("sub")), metadata_patch=patch)
    return {
        "id": updated.get("id"),
        "email": updated.get("email"),
        "role": (updated.get("app_metadata") or {}).get("role"),
        "user_metadata": updated.get("user_metadata") or {},
    }


@router.post("/password")
async def change_password(
    body: ChangePasswordRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    if not use_mongodb():
        raise HTTPException(400, detail="Password change API requires MongoDB auth mode.")
    from app.services.local_auth import change_password as save_password

    save_password(
        str(user.get("sub")),
        current_password=body.current_password,
        new_password=body.new_password,
    )
    return {"ok": True, "message": "Password updated."}


@router.post("/avatar")
async def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    if not use_mongodb():
        raise HTTPException(400, detail="Avatar upload requires MongoDB auth mode.")

    from uuid import uuid4

    from app.services.local_auth import update_profile as save_profile

    content = await file.read()
    if not content:
        raise HTTPException(400, detail="Empty file")
    if len(content) > settings.avatar_max_bytes:
        raise HTTPException(400, detail="Avatar must be 2 MB or smaller")

    avatars_root = settings.avatars_path
    avatars_root.mkdir(parents=True, exist_ok=True)
    user_id = str(user.get("sub") or "")
    ext = ".webp"
    if file.content_type == "image/png":
        ext = ".png"
    elif file.content_type == "image/jpeg":
        ext = ".jpg"
    storage_path = f"{user_id}/{uuid4()}{ext}"
    dest = (avatars_root / storage_path).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        dest.relative_to(avatars_root.resolve())
    except ValueError as exc:
        raise HTTPException(400, detail="Invalid avatar path") from exc
    dest.write_bytes(content)

    base = str(request.base_url).rstrip("/")
    avatar_url = f"{base}/auth/avatars/{storage_path}"
    updated = save_profile(user_id, metadata_patch={"avatar_url": avatar_url})
    return {
        "avatar_url": avatar_url,
        "user_metadata": updated.get("user_metadata") or {},
    }


@router.get("/avatars/{storage_path:path}")
async def get_avatar(storage_path: str, settings: Settings = Depends(get_settings)):
    from fastapi.responses import FileResponse

    root = settings.avatars_path.resolve()
    path = (root / storage_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(404, detail="Avatar not found") from exc
    if not path.is_file():
        raise HTTPException(404, detail="Avatar not found")
    return FileResponse(path)
