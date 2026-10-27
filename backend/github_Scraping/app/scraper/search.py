"""GitHub user search with email-hint fallback and pagination."""

from __future__ import annotations

import logging
from typing import Any, Callable

from app.scraper.constants import PER_PAGE, SEARCH_MAX_RESULTS

log = logging.getLogger(__name__)

StopChecker = Callable[[], bool]


def build_search_query(
    location_term: str,
    followers: str,
    created: str,
    *,
    use_email_hint: bool = True,
) -> str:
    q = f'location:{location_term} followers:{followers} created:{created} type:user'
    if use_email_hint:
        q += " in:email"
    return q


def search_collect_logins(
    github: Any,
    location_term: str,
    followers: str,
    created: str,
    *,
    sort_field: str = "joined",
    sort_order: str = "desc",
    use_email_hint: bool = True,
    seen: set[str] | None = None,
    skip: set[str] | None = None,
    should_stop: StopChecker | None = None,
    max_logins: int | None = None,
    on_log: Callable[[str], None] | None = None,
) -> list[str]:
    """
    Run search (email-hint first). If zero results, retry without in:email.
    Returns ordered unique logins.
    """
    seen = seen or set()
    skip = skip or set()
    collected: list[str] = []

    base = f"location:{location_term} followers:{followers} created:{created} type:user"
    query_variants = [base + " in:email", base] if use_email_hint else [base]

    for variant_idx, query in enumerate(query_variants):
        if should_stop and should_stop():
            break
        page = 1
        variant_hits = 0

        while page * PER_PAGE <= SEARCH_MAX_RESULTS:
            if should_stop and should_stop():
                break
            if max_logins is not None and len(collected) >= max_logins:
                break

            try:
                data = github.search_users(
                    query, page=page, sort=sort_field, order=sort_order
                )
            except Exception as exc:
                if on_log:
                    on_log(f"Search error: {exc}")
                break

            items = data.get("items") or []
            total = data.get("total_count", 0)

            if page == 1 and total == 0:
                break

            for item in items:
                login = item.get("login")
                if not login or login in seen or login in skip:
                    continue
                seen.add(login)
                collected.append(login)
                variant_hits += 1
                if max_logins is not None and len(collected) >= max_logins:
                    break

            if on_log and page == 1:
                hint = "in:email" if "in:email" in query else "broad"
                on_log(f"Search [{hint}] total≈{total}, page {page}: +{len(items)} users")

            if len(items) < PER_PAGE or page * PER_PAGE >= min(total, SEARCH_MAX_RESULTS):
                break
            page += 1

    return collected
