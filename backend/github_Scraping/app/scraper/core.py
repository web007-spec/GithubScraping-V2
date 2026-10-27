"""
Scraper core: callable per-country with progress callbacks for the management UI.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import requests
from supabase import Client

from app.services.supabase_client import table_execute

from app.scraper.date_buckets import build_date_buckets_from_range
from app.scraper.profile import enrich_profiles_batch
from app.scraper.search import search_collect_logins
from app.scraper.constants import (
    COUNTRY_LOCATION_TERMS,
    DEFAULT_DATE_BUCKETS,
    DEFAULT_FOLLOWER_BUCKETS,
    GITHUB_API,
    PER_PAGE,
    GRAPHQL_BATCH_SIZE,
    PROFILE_ENRICH_CHUNK,
    PROFILE_FETCH_WORKERS,
    RATE_LIMIT_THROTTLE_BELOW,
    REQUEST_DELAY_MAX,
    REQUEST_DELAY_MIN,
    SEARCH_MAX_RESULTS,
    SKIP_SCRAPE_HOURS,
    UPSERT_BATCH_SIZE,
)

log = logging.getLogger(__name__)


def _estimate_remaining(config: ScrapeConfig, completed: list[str]) -> int | None:
    total = len(config.countries)
    if total == 0:
        return None
    remaining = total - len(completed)
    buckets = len(config.follower_buckets) * len(config.effective_date_buckets())
    return remaining * buckets * 60


StatusChecker = Callable[[], str | None]
StopChecker = Callable[[], bool]
LogCallback = Callable[[str], None]
RateLimitCallback = Callable[[int | None, datetime | None], None]


@dataclass
class ScrapeConfig:
    countries: list[str] = field(default_factory=list)
    max_per_location: int | None = None
    follower_buckets: list[str] = field(default_factory=lambda: list(DEFAULT_FOLLOWER_BUCKETS))
    date_buckets: list[str] = field(default_factory=lambda: list(DEFAULT_DATE_BUCKETS))
    join_date_start: str | None = None
    join_date_end: str | None = None
    search_sort: str = "joined"
    search_order: str = "desc"
    skip_recent_hours: int = SKIP_SCRAPE_HOURS
    full_profile: bool = False
    email_only: bool = True
    use_email_search_hint: bool = True
    profile_workers: int = PROFILE_FETCH_WORKERS

    def effective_date_buckets(self) -> list[str]:
        if self.join_date_start and self.join_date_end:
            return build_date_buckets_from_range(self.join_date_start, self.join_date_end)
        return self.date_buckets


_thread_local = threading.local()


class GitHubClient:
    def __init__(self, token: str, on_rate_limit: RateLimitCallback | None = None) -> None:
        self.token = token
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )
        self._on_rate_limit = on_rate_limit
        self._rate_limit_lock = threading.Lock()
        self._remaining: int | None = None

    def _emit_rate_limit(self, response: requests.Response) -> None:
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")
        rem_int = int(remaining) if remaining is not None else None
        if rem_int is not None:
            self._remaining = rem_int
        reset_dt = None
        if reset:
            reset_dt = datetime.fromtimestamp(int(reset), tz=timezone.utc)
        if self._on_rate_limit:
            with self._rate_limit_lock:
                self._on_rate_limit(rem_int, reset_dt)

    def _throttle(self) -> None:
        if self._remaining is not None and self._remaining > RATE_LIMIT_THROTTLE_BELOW:
            return
        delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
        if delay > 0:
            time.sleep(delay)

    def _handle_rate_limit(
        self, response: requests.Response, stop_check: StopChecker | None = None
    ) -> None:
        if response.status_code != 403:
            return
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining is not None and remaining != "0":
            return
        reset_header = response.headers.get("X-RateLimit-Reset")
        if not reset_header:
            return
        reset_at = int(reset_header)
        sleep_for = max(0, reset_at - time.time()) + 2
        log.warning("Rate limited. Sleeping %.1f seconds.", sleep_for)
        end = time.time() + sleep_for
        while time.time() < end:
            if stop_check and stop_check():
                raise RuntimeError("Scrape stopped")
            time.sleep(min(1.0, end - time.time()))

    def request(
        self,
        method: str,
        url: str,
        *,
        stop_check: StopChecker | None = None,
        **kwargs: Any,
    ) -> requests.Response:
        if stop_check and stop_check():
            raise RuntimeError("Scrape stopped")
        last_error: Exception | None = None
        for attempt in range(5):
            if stop_check and stop_check():
                raise RuntimeError("Scrape stopped")
            self._throttle()
            timeout = 5 if (stop_check and stop_check()) else 15
            try:
                response = self.session.request(method, url, timeout=timeout, **kwargs)
            except requests.RequestException as exc:
                last_error = exc
                time.sleep(2 ** attempt)
                continue

            self._emit_rate_limit(response)

            if response.status_code == 403:
                remaining = response.headers.get("X-RateLimit-Remaining")
                if remaining == "0":
                    self._handle_rate_limit(response, stop_check=stop_check)
                    continue
                return response

            if response.status_code in (502, 503, 504):
                time.sleep(2 ** attempt)
                continue

            return response

        if last_error:
            raise last_error
        raise RuntimeError(f"Failed after retries: {method} {url}")

    def search_users(
        self,
        query: str,
        page: int = 1,
        *,
        sort: str = "joined",
        order: str = "desc",
    ) -> dict[str, Any]:
        stop_check = getattr(self, "_stop_check", None)
        response = self.request(
            "GET",
            f"{GITHUB_API}/search/users",
            stop_check=stop_check,
            params={
                "q": query,
                "per_page": PER_PAGE,
                "page": page,
                "sort": sort,
                "order": order,
            },
        )
        if response.status_code == 422:
            return {"total_count": 0, "items": []}
        response.raise_for_status()
        return response.json()

    def get_user(self, login: str) -> dict[str, Any] | None:
        stop_check = getattr(self, "_stop_check", None)
        response = self.request(
            "GET", f"{GITHUB_API}/users/{login}", stop_check=stop_check
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def check_rate_limit(self) -> dict[str, Any]:
        response = self.request("GET", f"{GITHUB_API}/rate_limit")
        response.raise_for_status()
        return response.json()


def load_recently_scraped_logins(
    supabase: Client,
    hours: int,
    should_stop: StopChecker | None = None,
) -> set[str]:
    """Skip logins we already stored recently (email rows only — faster query)."""
    if hours <= 0:
        return set()
    from app.scraper.constants import RECENT_SKIP_MAX_LOGINS

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    logins: set[str] = set()
    offset = 0
    page_size = 1000
    while len(logins) < RECENT_SKIP_MAX_LOGINS:
        if should_stop and should_stop():
            break
        result = table_execute(
            lambda sb: sb.table("github_users")
            .select("login")
            .gte("last_scraped_at", cutoff)
            .not_.is_("email", "null")
            .range(offset, offset + page_size - 1)
        )
        rows = result.data or []
        if not rows:
            break
        for row in rows:
            logins.add(row["login"])
        if len(rows) < page_size:
            break
        offset += page_size
    return logins


def _worker_github(
    token: str,
    on_rate_limit: RateLimitCallback | None,
) -> GitHubClient:
    client = getattr(_thread_local, "github", None)
    if client is None:
        client = GitHubClient(token, on_rate_limit=on_rate_limit)
        _thread_local.github = client
    return client


def enrich_profiles_parallel(
    token: str,
    logins: list[str],
    country: str,
    *,
    on_rate_limit: RateLimitCallback | None = None,
    workers: int = PROFILE_FETCH_WORKERS,
    full_profile: bool = False,
    email_only: bool = True,
    should_stop: StopChecker | None = None,
) -> list[dict[str, Any]]:
    """GraphQL batch profiles + parallel email enrichment."""
    if not logins or (should_stop and should_stop()):
        return []

    gh = _worker_github(token, on_rate_limit)
    gh._stop_check = should_stop
    rows, _stats = enrich_profiles_batch(
        gh,
        logins,
        country,
        full=full_profile,
        email_only=email_only,
        should_stop=should_stop,
        workers=workers,
    )
    return rows


def upsert_batches(
    supabase: Client,
    rows: list[dict[str, Any]],
    *,
    email_only: bool = True,
) -> int:
    from app.services.user_rows import upsert_user_rows

    if email_only:
        rows = [r for r in rows if r.get("email")]
    if not rows:
        return 0
    for i in range(0, len(rows), UPSERT_BATCH_SIZE):
        batch = rows[i : i + UPSERT_BATCH_SIZE]
        upsert_user_rows(batch)
    return len(rows)


def scrape_country(
    country: str,
    config: ScrapeConfig,
    github: GitHubClient,
    supabase: Client,
    *,
    seen_logins: set[str],
    recently_scraped: set[str],
    should_stop: StopChecker | None = None,
    on_log: LogCallback | None = None,
) -> list[dict[str, Any]]:
    """Search → batch enrich (GraphQL) → store users with email only."""
    location_term = COUNTRY_LOCATION_TERMS.get(country, country)
    collected: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    country_stored = 0
    stats_total = {"candidates": 0, "profiles": 0, "with_email": 0, "skipped": 0}

    def log_msg(msg: str) -> None:
        log.info(msg)
        if on_log:
            on_log(msg)

    date_buckets = config.effective_date_buckets()
    sort_field = config.search_sort if config.search_sort in ("joined", "followers", "repositories") else "joined"
    sort_order = config.search_order if config.search_order in ("asc", "desc") else "desc"
    chunk_size = min(PROFILE_ENRICH_CHUNK, GRAPHQL_BATCH_SIZE)

    for followers in config.follower_buckets:
        for created in date_buckets:
            if should_stop and should_stop():
                log_msg(f"Stop requested during {country}")
                return collected

            if config.max_per_location is not None and country_stored >= config.max_per_location:
                break

            room = None
            if config.max_per_location is not None:
                room = config.max_per_location - country_stored

            logins = search_collect_logins(
                github,
                location_term,
                followers,
                created,
                sort_field=sort_field,
                sort_order=sort_order,
                use_email_hint=config.use_email_search_hint,
                seen=seen_logins,
                skip=recently_scraped,
                should_stop=should_stop,
                max_logins=room,
                on_log=log_msg,
            )

            if not logins:
                continue

            stats_total["candidates"] += len(logins)

            for i in range(0, len(logins), chunk_size):
                if should_stop and should_stop():
                    if pending:
                        upsert_batches(supabase, pending, email_only=config.email_only)
                    return collected

                chunk = logins[i : i + chunk_size]
                new_rows, batch_stats = enrich_profiles_batch(
                    github,
                    chunk,
                    country,
                    full=config.full_profile,
                    email_only=config.email_only,
                    should_stop=should_stop,
                    workers=config.profile_workers,
                )
                for k in ("profiles", "with_email", "skipped"):
                    stats_total[k] += batch_stats.get(k, 0)

                for row in new_rows:
                    pending.append(row)
                    collected.append(row)
                    country_stored += 1

                if len(pending) >= UPSERT_BATCH_SIZE:
                    upsert_batches(supabase, pending, email_only=config.email_only)
                    pending.clear()

                if config.max_per_location is not None and country_stored >= config.max_per_location:
                    break

    if pending:
        upsert_batches(supabase, pending, email_only=config.email_only)

    log_msg(
        f"Finished {country}: {country_stored} saved | "
        f"searched {stats_total['candidates']} → "
        f"profiles {stats_total['profiles']} → "
        f"email {stats_total['with_email']} | "
        f"skipped {stats_total['skipped']} (no email)"
    )
    return collected


@dataclass
class ScrapeRunner:
    """Runs a full multi-country scrape with DB progress updates."""

    supabase: Client
    github: GitHubClient
    config: ScrapeConfig
    run_id: str
    get_status: StatusChecker
    should_stop: StopChecker
    append_log: LogCallback
    update_run: Callable[[dict[str, Any]], None]

    def run(self) -> int:
        seen: set[str] = set()
        recent = load_recently_scraped_logins(
            self.supabase, self.config.skip_recent_hours, should_stop=self.should_stop
        )
        total = 0
        completed: list[str] = []

        for country in self.config.countries:
            if self.should_stop():
                self.append_log("Stop requested — ending scrape")
                break

            self.update_run({"current_country": country, "status": "running"})
            mode = (
                f"fast ({self.config.profile_workers} workers)"
                if not self.config.full_profile
                else f"full profile ({self.config.profile_workers} workers)"
            )
            store = "save email only" if self.config.email_only else "all profiles"
            hint = "+ in:email search" if self.config.use_email_search_hint else ""
            self.append_log(f"=== {country} [{mode}{hint}, {store}] ===")

            users = scrape_country(
                country,
                self.config,
                self.github,
                self.supabase,
                seen_logins=seen,
                recently_scraped=recent,
                should_stop=self.should_stop,
                on_log=self.append_log,
            )
            total += len(users)
            if self.should_stop():
                self.append_log("Stop requested — ending scrape")
                break
            completed.append(country)
            eta = _estimate_remaining(self.config, completed)
            self.update_run(
                {
                    "total_users_found": total,
                    "countries_completed": completed,
                    "current_country": country,
                    "estimated_seconds_remaining": eta,
                }
            )

        return total
