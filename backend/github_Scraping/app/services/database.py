"""Application database backend selection."""

from __future__ import annotations

from app.config import get_settings


def use_mongodb() -> bool:
    settings = get_settings()
    mode = (settings.database_storage or "auto").strip().lower()
    if mode == "supabase":
        return False
    if mode == "mongodb":
        uri = (settings.mongodb_uri or "").strip()
        if not uri:
            raise RuntimeError("DATABASE_STORAGE=mongodb but MONGODB_URI is not set")
        return True
    return bool((settings.mongodb_uri or "").strip())


def storage_label() -> str:
    return "mongodb" if use_mongodb() else "supabase"
