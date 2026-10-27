"""MongoDB connection and collection indexes."""

from __future__ import annotations

import os
import threading
from typing import Any

_local = threading.local()

DEFAULT_DB = "outreach_console"


def _from_app_settings(name: str) -> str:
    try:
        import sys
        from pathlib import Path

        scraping = Path(__file__).resolve().parents[1] / "github_Scraping"
        if str(scraping) not in sys.path:
            sys.path.insert(0, str(scraping))
        from app.config import get_settings

        settings = get_settings()
        return str(getattr(settings, name, "") or "").strip()
    except Exception:
        return ""


def mongodb_uri() -> str:
    return (
        (os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI") or "").strip()
        or _from_app_settings("mongodb_uri")
    )


def mongodb_db_name() -> str:
    return (
        (os.environ.get("MONGODB_DB_NAME") or os.environ.get("MONGO_DB_NAME") or "").strip()
        or _from_app_settings("mongodb_db_name")
        or DEFAULT_DB
    )


def get_client():
    from pymongo import MongoClient

    uri = mongodb_uri()
    if not uri:
        raise RuntimeError("MONGODB_URI is not set")
    client = getattr(_local, "mongo_client", None)
    if client is None:
        client = MongoClient(uri, serverSelectionTimeoutMS=8000)
        _local.mongo_client = client
    return client


def get_database():
    return get_client()[mongodb_db_name()]


def ping() -> bool:
    try:
        get_client().admin.command("ping")
        return True
    except Exception:
        return False


def strip_mongo_id(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if not doc:
        return doc
    out = dict(doc)
    out.pop("_id", None)
    return out


def ensure_indexes() -> None:
    """Create indexes for all application collections (see outreach_db/mongodb_schema.py)."""
    from outreach_db.mongodb_schema import ensure_indexes as _apply

    _apply()
