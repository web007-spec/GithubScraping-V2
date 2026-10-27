"""Supabase client integration."""

from functools import lru_cache

from loguru import logger
from supabase import Client, create_client

from app.config.settings import Settings, get_settings


@lru_cache
def get_supabase_client(settings: Settings | None = None) -> Client | None:
    """
    Create Supabase client if credentials are configured.

    Returns None when Supabase is not configured (DB-only mode).
    """
    settings = settings or get_settings()
    if not settings.supabase_url or not settings.supabase_key:
        logger.debug("Supabase credentials not configured; skipping client init")
        return None
    if settings.supabase_url == "https://your-project.supabase.co":
        return None
    return create_client(settings.supabase_url, settings.supabase_key)


async def sync_document_to_supabase(doc_data: dict) -> bool:
    """
    Optional sync of document metadata to Supabase REST API.

    Primary storage uses PostgreSQL via SQLAlchemy; this provides
    supplementary REST access when configured.
    """
    client = get_supabase_client()
    if client is None:
        return False
    try:
        client.table("google_documents").upsert(doc_data, on_conflict="google_doc_id").execute()
        return True
    except Exception as exc:
        logger.warning("Supabase sync failed: {}", exc)
        return False
