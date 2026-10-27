"""Fast per-country counts from github_user_country_stats (DB-maintained)."""

from __future__ import annotations

import logging

from app.services.country_cache import get_cached_countries, invalidate_country_cache, set_cached_countries
from app.services.supabase_client import table_execute

log = logging.getLogger(__name__)

EXCLUDED_COUNTRY_KEYWORDS = ("korea",)


def is_excluded_country(country: object) -> bool:
    name = str(country or "").strip().lower()
    return any(keyword in name for keyword in EXCLUDED_COUNTRY_KEYWORDS)


def _without_excluded_countries(items: list[dict]) -> list[dict]:
    return [item for item in items if not is_excluded_country(item.get("country"))]


def fetch_country_counts(*, allow_fallback_scan: bool = False) -> dict:
    """
    Return {countries: [{country, count}], total}.
    Uses stats table (O(countries)); falls back to scanning if table missing.
    """
    cached = get_cached_countries()
    if cached is not None:
        cached = dict(cached)
        cached["countries"] = _without_excluded_countries(cached.get("countries") or [])
        cached["total"] = sum(int(i.get("count") or 0) for i in cached["countries"])
        return cached

    try:
        result = table_execute(
            lambda sb: sb.table("github_user_country_stats")
            .select("country,user_count")
            .order("user_count", desc=True)
        )
        rows = result.data or []
        if rows:
            items = [
                {"country": r["country"], "count": int(r["user_count"])}
                for r in rows
                if r.get("country") and not is_excluded_country(r.get("country"))
            ]
            payload = {"countries": items, "total": sum(i["count"] for i in items)}
            set_cached_countries(payload)
            return payload
    except Exception as exc:
        log.warning("country_stats table unavailable (%s), using fallback scan", exc)

    if not allow_fallback_scan:
        return {"countries": [], "total": 0, "degraded": True}

    return _scan_github_users_fallback()


def _scan_github_users_fallback() -> dict:
    counts: dict[str, int] = {}
    offset = 0
    batch = 2000
    while True:
        result = table_execute(
            lambda sb: sb.table("github_users")
            .select("country")
            .not_.is_("country", "null")
            .not_.is_("email", "null")
            .range(offset, offset + batch - 1)
        )
        rows = result.data or []
        if not rows:
            break
        for row in rows:
            c = row.get("country")
            if c and not is_excluded_country(c):
                counts[str(c)] = counts.get(str(c), 0) + 1
        if len(rows) < batch:
            break
        offset += batch

    items = [
        {"country": name, "count": count}
        for name, count in sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    ]
    payload = {"countries": items, "total": sum(counts.values())}
    set_cached_countries(payload)
    return payload


def rebuild_country_stats() -> None:
    """Call SQL rebuild after bulk import (normally automatic via trigger)."""
    try:
        table_execute(lambda sb: sb.rpc("rebuild_github_user_country_stats"))
        invalidate_country_cache()
    except Exception as exc:
        log.warning("rebuild_github_user_country_stats failed: %s", exc)
        raise
