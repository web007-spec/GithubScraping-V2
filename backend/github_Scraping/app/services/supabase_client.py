"""Supabase client with thread-local instances and resilient HTTP settings."""

from __future__ import annotations

import logging
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, TypeVar

import certifi
import httpx
from supabase import Client, create_client

from app.config import get_settings
from app.services.database import use_mongodb

log = logging.getLogger(__name__)
_local = threading.local()

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

T = TypeVar("T")

# Transient network / connection errors (including stale closed httpx client)
_RETRY_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.ReadError,
    httpx.RemoteProtocolError,
    httpx.WriteError,
    httpx.TimeoutException,
    OSError,
    RuntimeError,
)


def _client_options():
    """Build options compatible with supabase-py 2.4–2.6+."""
    timeout = httpx.Timeout(90.0, connect=30.0)
    try:
        from supabase.lib.client_options import SyncClientOptions

        http_client = httpx.Client(
            http2=False,
            verify=certifi.where(),
            timeout=timeout,
            transport=httpx.HTTPTransport(retries=2),
        )
        return SyncClientOptions(httpx_client=http_client)
    except ImportError:
        pass

    from supabase.lib.client_options import ClientOptions

    return ClientOptions(
        auto_refresh_token=False,
        persist_session=False,
        postgrest_client_timeout=timeout,
        storage_client_timeout=timeout,
        function_client_timeout=timeout,
    )


def _build_client() -> Client | Any:
    settings = get_settings()
    if use_mongodb():
        from outreach_db.mongo_adapter import MongoOnlyClient, MongoSupabaseClient

        return MongoOnlyClient(MongoSupabaseClient())

    if not (settings.supabase_url or "").strip() or not (settings.supabase_service_role_key or "").strip():
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required when DATABASE_STORAGE=supabase")

    real = create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
        _client_options(),
    )
    return real


def get_supabase() -> Client | Any:
    """One Supabase client per thread (safe for APScheduler + FastAPI)."""
    client = getattr(_local, "client", None)
    if client is None:
        client = _build_client()
        _local.client = client
    return client


def _close_client(client: Client) -> None:
    """Close all httpx sessions attached to a Supabase client."""
    for attr in ("postgrest", "storage", "functions"):
        part = getattr(client, attr, None)
        if part is None:
            continue
        session = getattr(part, "session", None)
        if session is not None:
            try:
                session.close()
            except Exception:
                pass


def reset_supabase() -> None:
    """Drop the thread-local client and close its HTTP session."""
    client = getattr(_local, "client", None)
    _local.client = None
    if client is not None:
        _close_client(client)


def _should_retry(exc: Exception) -> bool:
    msg = str(exc).lower()
    if isinstance(exc, RuntimeError):
        return "closed" in msg
    if any(
        token in msg
        for token in (
            "ssl",
            "unexpected_eof",
            "eof occurred",
            "connection reset",
            "broken pipe",
            "connection aborted",
        )
    ):
        return True
    return isinstance(exc, _RETRY_EXCEPTIONS)


def supabase_retry(fn: Callable[[], T], *, retries: int = 3, base_delay: float = 0.35) -> T:
    """Run fn with retries; resets Supabase client between attempts."""
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            return fn()
        except Exception as exc:
            if not _should_retry(exc):
                raise
            last_exc = exc
            reset_supabase()
            if attempt < retries - 1:
                delay = base_delay * (2**attempt)
                log.warning(
                    "Supabase request failed (%s), retry %s/%s in %.1fs",
                    exc,
                    attempt + 1,
                    retries,
                    delay,
                )
                time.sleep(delay)
    assert last_exc is not None
    raise last_exc


def table_execute(build: Callable[[Any], Any]) -> Any:
    """
    Execute a Supabase query with retries.

    `build` receives a fresh Client on each attempt so retries never reuse a
    closed httpx session. When MONGODB_URI is set, table operations use MongoDB.
    """

    def attempt() -> Any:
        sb = get_supabase()
        result = build(sb)
        if hasattr(result, "execute"):
            return result.execute()
        return result

    if use_mongodb():
        return attempt()
    return supabase_retry(attempt)
