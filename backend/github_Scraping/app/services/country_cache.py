"""Short-lived cache for /users/countries aggregation."""

from __future__ import annotations

import time
from typing import Any

_cache: dict[str, Any] = {"data": None, "expires": 0.0}
TTL_SECONDS = 45


def get_cached_countries() -> dict | None:
    if _cache["data"] is not None and time.time() < _cache["expires"]:
        return _cache["data"]
    return None


def set_cached_countries(payload: dict) -> None:
    _cache["data"] = payload
    _cache["expires"] = time.time() + TTL_SECONDS


def invalidate_country_cache() -> None:
    _cache["data"] = None
    _cache["expires"] = 0.0
