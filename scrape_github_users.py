#!/usr/bin/env python3
"""
Scrape public GitHub user profiles via the official REST API and upsert into Supabase.

Uses scraper helpers from backend/github_Scraping/app/scraper/.
Prefer the management UI (./start-project.ps1) for day-to-day runs.

Example:
  set GITHUB_TOKEN=ghp_...
  set SUPABASE_URL=https://xxx.supabase.co
  set SUPABASE_KEY=eyJ...
  python scrape_github_users.py --max-per-location 500

  python scrape_github_users.py --token ghp_xxx --target-countries US,India,UK --max-per-location 200
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from supabase import Client, create_client

# Live FastAPI package lives under backend/github_Scraping (not backend/app).
API_ROOT = Path(__file__).resolve().parent / "backend" / "github_Scraping"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.scraper.profile import enrich_profiles_batch
from app.scraper.search import search_collect_logins

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


GITHUB_API = "https://api.github.com"
DEFAULT_COUNTRIES = [
    "US",
    "India",
    "UK",
    "Germany",
    "Canada",
    "Japan",
    "France",
    "Brazil",
    "Australia",
    "Netherlands",
    "Sweden",
    "Spain",
    "Italy",
    "Poland",
    "Ukraine",
    "Russia",
    "China",
    "Singapore",
    "Switzerland",
    "Norway",
    "Denmark",
    "Finland",
    "Belgium",
    "Austria",
    "Ireland",
    "United Arab Emirates",
    "Saudi Arabia",
    "Qatar",
    "Israel",
    "Mexico",
    "Argentina",
    "Chile",
    "Colombia",
    "Peru",
    "Indonesia",
    "Philippines",
    "Vietnam",
    "Thailand",
    "Malaysia",
    "Pakistan",
    "Bangladesh",
    "Sri Lanka",
    "Nepal",
    "Nigeria",
    "South Africa",
    "Egypt",
    "Kenya",
    "Morocco",
    "Turkey",
    "Czech Republic",
    "Portugal",
    "Romania",
    "Greece",
    "Hungary",
    "Bulgaria",
    "Serbia",
    "Croatia",
    "Slovakia",
    "Slovenia",
    "Lithuania",
    "Estonia",
    "Latvia",
    "New Zealand",
    "Taiwan",
    "Hong Kong",
]

# GitHub location: qualifier values (English names work best in search)
COUNTRY_LOCATION_TERMS: dict[str, str] = {
    "US": "United States",
    "India": "India",
    "UK": "United Kingdom",
    "Germany": "Germany",
    "Canada": "Canada",
    "Japan": "Japan",
    "France": "France",
    "Brazil": "Brazil",
    "Australia": "Australia",
    "Netherlands": "Netherlands",
    "Sweden": "Sweden",
    "Spain": "Spain",
    "Italy": "Italy",
    "Poland": "Poland",
    "Ukraine": "Ukraine",
    "Russia": "Russia",
    "China": "China",
    "Singapore": "Singapore",
    "Switzerland": "Switzerland",
    "Norway": "Norway",
    "Denmark": "Denmark",
    "Finland": "Finland",
    "Belgium": "Belgium",
    "Austria": "Austria",
    "Ireland": "Ireland",
    "United Arab Emirates": "United Arab Emirates",
    "Saudi Arabia": "Saudi Arabia",
    "Qatar": "Qatar",
    "Israel": "Israel",
    "Mexico": "Mexico",
    "Argentina": "Argentina",
    "Chile": "Chile",
    "Colombia": "Colombia",
    "Peru": "Peru",
    "Indonesia": "Indonesia",
    "Philippines": "Philippines",
    "Vietnam": "Vietnam",
    "Thailand": "Thailand",
    "Malaysia": "Malaysia",
    "Pakistan": "Pakistan",
    "Bangladesh": "Bangladesh",
    "Sri Lanka": "Sri Lanka",
    "Nepal": "Nepal",
    "Nigeria": "Nigeria",
    "South Africa": "South Africa",
    "Egypt": "Egypt",
    "Kenya": "Kenya",
    "Morocco": "Morocco",
    "Turkey": "Turkey",
    "Czech Republic": "Czech Republic",
    "Portugal": "Portugal",
    "Romania": "Romania",
    "Greece": "Greece",
    "Hungary": "Hungary",
    "Bulgaria": "Bulgaria",
    "Serbia": "Serbia",
    "Croatia": "Croatia",
    "Slovakia": "Slovakia",
    "Slovenia": "Slovenia",
    "Lithuania": "Lithuania",
    "Estonia": "Estonia",
    "Latvia": "Latvia",
    "New Zealand": "New Zealand",
    "Taiwan": "Taiwan",
    "Hong Kong": "Hong Kong",
}

FOLLOWER_BUCKETS = ["0..9", "10..99", "100..999", "1000..9999", "10000.."]

DATE_BUCKETS = [
    "2008-01-01..2010-12-31",
    "2011-01-01..2013-12-31",
    "2014-01-01..2016-12-31",
    "2017-01-01..2019-12-31",
    "2020-01-01..2022-12-31",
    "2023-01-01..2025-12-31",
]

SEARCH_MAX_RESULTS = 1000
PER_PAGE = 100
UPSERT_BATCH_SIZE = 100
SKIP_SCRAPE_HOURS = 24
REQUEST_DELAY_MIN = env_float("GITHUB_SCRAPER_REQUEST_DELAY_MIN", 0.12)
REQUEST_DELAY_MAX = env_float("GITHUB_SCRAPER_REQUEST_DELAY_MAX", 0.35)
PROFILE_FETCH_WORKERS = env_int("GITHUB_SCRAPER_PROFILE_WORKERS", 6)
PROFILE_ENRICH_CHUNK = env_int("GITHUB_SCRAPER_PROFILE_CHUNK", 20)
RECENT_SKIP_MAX_LOGINS = env_int("GITHUB_SCRAPER_RECENT_SKIP_MAX", 3000)
RATE_LIMIT_THROTTLE_BELOW = 80


class GitHubClient:
    def __init__(self, token: str) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )
        self._remaining: int | None = None

    def _throttle(self) -> None:
        if self._remaining is not None and self._remaining > RATE_LIMIT_THROTTLE_BELOW:
            return
        delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
        if delay > 0:
            time.sleep(delay)

    def _emit_rate_limit(self, response: requests.Response) -> None:
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining is None:
            return
        try:
            self._remaining = int(remaining)
        except ValueError:
            return

    def _handle_rate_limit(self, response: requests.Response) -> None:
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
        log.warning("Rate limited. Sleeping %.1f seconds until reset.", sleep_for)
        time.sleep(sleep_for)

    def request(
        self,
        method: str,
        url: str,
        *,
        stop_check: Any | None = None,
        **kwargs: Any,
    ) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(5):
            if stop_check and stop_check():
                raise RuntimeError("Scrape stopped")
            self._throttle()
            try:
                response = self.session.request(method, url, timeout=60, **kwargs)
            except requests.RequestException as exc:
                last_error = exc
                log.warning("Request failed (attempt %s): %s", attempt + 1, exc)
                time.sleep(2 ** attempt)
                continue

            self._emit_rate_limit(response)

            if response.status_code == 403:
                remaining = response.headers.get("X-RateLimit-Remaining")
                if remaining == "0":
                    self._handle_rate_limit(response)
                    continue
                return response

            if response.status_code in (502, 503, 504):
                log.warning("GitHub %s, retrying...", response.status_code)
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
        url = f"{GITHUB_API}/search/users"
        response = self.request(
            "GET",
            url,
            params={
                "q": query,
                "per_page": PER_PAGE,
                "page": page,
                "sort": sort,
                "order": order,
            },
        )
        if response.status_code == 422:
            log.warning("Unprocessable search query: %s", query)
            return {"total_count": 0, "items": []}
        response.raise_for_status()
        return response.json()

    def get_user(self, login: str) -> dict[str, Any] | None:
        url = f"{GITHUB_API}/users/{login}"
        response = self.request("GET", url)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()


def build_search_query(location_term: str, followers: str, created: str) -> str:
    return f"location:{location_term} followers:{followers} created:{created}"


def parse_github_timestamp(value: str | None) -> str | None:
    if not value:
        return None
    return value


def user_to_row(user: dict[str, Any], country: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": user["id"],
        "login": user["login"],
        "name": user.get("name"),
        "location": user.get("location"),
        "company": user.get("company"),
        "email": user.get("email"),
        "bio": user.get("bio"),
        "public_repos": user.get("public_repos"),
        "followers": user.get("followers"),
        "following": user.get("following"),
        "created_at": parse_github_timestamp(user.get("created_at")),
        "updated_at": parse_github_timestamp(user.get("updated_at")),
        "last_scraped_at": now,
        "country": country,
    }


def load_recently_scraped_logins(supabase: Client, hours: int = SKIP_SCRAPE_HOURS) -> set[str]:
    if hours <= 0:
        return set()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    logins: set[str] = set()
    page_size = 1000
    offset = 0

    while len(logins) < RECENT_SKIP_MAX_LOGINS:
        result = (
            supabase.table("github_users")
            .select("login")
            .gte("last_scraped_at", cutoff)
            .not_.is_("email", "null")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            break
        for row in rows:
            logins.add(row["login"])
        if len(rows) < page_size:
            break
        offset += page_size

    log.info("Loaded %d email logins scraped within the last %d hours.", len(logins), hours)
    return logins


def upsert_batches(supabase: Client, rows: list[dict[str, Any]]) -> None:
    for i in range(0, len(rows), UPSERT_BATCH_SIZE):
        batch_by_id: dict[Any, dict[str, Any]] = {}
        batch_login_ids: dict[str, Any] = {}
        for row in rows[i : i + UPSERT_BATCH_SIZE]:
            row_id = row.get("id")
            login = str(row.get("login") or "").strip().lower()
            if row_id is None or not login:
                continue
            old_id = batch_login_ids.get(login)
            if old_id is not None:
                batch_by_id.pop(old_id, None)
            batch_by_id[row_id] = row
            batch_login_ids[login] = row_id
        batch = list(batch_by_id.values())
        if not batch:
            continue
        try:
            supabase.table("github_users").upsert(batch, on_conflict="id").execute()
        except Exception as exc:
            msg = str(exc).lower()
            if "duplicate key" not in msg and "23505" not in msg:
                raise
            log.warning("ID upsert hit a secondary unique conflict; retrying rows by login")
            for row in batch:
                supabase.table("github_users").upsert(row, on_conflict="login").execute()
        log.info("Upserted batch of %d rows.", len(batch))


def scrape(
    github: GitHubClient,
    supabase: Client,
    countries: list[str],
    max_per_location: int | None,
    *,
    skip_recent_hours: int = SKIP_SCRAPE_HOURS,
    profile_workers: int = PROFILE_FETCH_WORKERS,
    use_email_search_hint: bool = True,
) -> None:
    seen_logins: set[str] = set()
    recently_scraped = load_recently_scraped_logins(supabase, skip_recent_hours)
    pending_rows: list[dict[str, Any]] = []
    country_counts: dict[str, int] = {c: 0 for c in countries}

    for country in countries:
        location_term = COUNTRY_LOCATION_TERMS.get(country, country)
        log.info("=== Country: %s (location: %s) ===", country, location_term)

        if max_per_location is not None and country_counts[country] >= max_per_location:
            log.info("Already at max_per_location for %s, skipping.", country)
            continue

        for followers in FOLLOWER_BUCKETS:
            for created in DATE_BUCKETS:
                if max_per_location is not None and country_counts[country] >= max_per_location:
                    break

                room = None
                if max_per_location is not None:
                    room = max(max_per_location - country_counts[country], 0)
                    if room <= 0:
                        break

                candidate_cap = room * 3 if room is not None else None
                log.info(
                    "Search: %s",
                    build_search_query(location_term, followers, created),
                )
                logins = search_collect_logins(
                    github,
                    location_term,
                    followers,
                    created,
                    use_email_hint=use_email_search_hint,
                    seen=seen_logins,
                    skip=recently_scraped,
                    max_logins=candidate_cap,
                    on_log=log.info,
                )
                if not logins:
                    continue

                for i in range(0, len(logins), PROFILE_ENRICH_CHUNK):
                    if max_per_location is not None and country_counts[country] >= max_per_location:
                        break

                    chunk = logins[i : i + PROFILE_ENRICH_CHUNK]
                    rows, stats = enrich_profiles_batch(
                        github,
                        chunk,
                        country,
                        full=False,
                        email_only=True,
                        workers=profile_workers,
                    )
                    log.info(
                        "Enriched %d candidates -> %d profiles -> %d with email.",
                        stats.get("candidates", len(chunk)),
                        stats.get("profiles", 0),
                        stats.get("with_email", len(rows)),
                    )

                    for row in rows:
                        if max_per_location is not None and country_counts[country] >= max_per_location:
                            break
                        pending_rows.append(row)
                        country_counts[country] += 1

                    if len(pending_rows) >= UPSERT_BATCH_SIZE:
                        upsert_batches(supabase, pending_rows)
                        pending_rows.clear()

        if pending_rows:
            upsert_batches(supabase, pending_rows)
            pending_rows.clear()

        log.info("Finished %s: %d users stored this run.", country, country_counts[country])

    log.info("Scrape complete. Total unique logins processed: %d", len(seen_logins))


def parse_countries(value: str) -> list[str]:
    return [c.strip() for c in value.split(",") if c.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape GitHub public users into Supabase (deduplicated)."
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"),
        help="GitHub personal access token (or GITHUB_TOKEN / GH_TOKEN env)",
    )
    parser.add_argument(
        "--supabase-url",
        default=os.environ.get("SUPABASE_URL"),
        help="Supabase project URL (or SUPABASE_URL env)",
    )
    parser.add_argument(
        "--supabase-key",
        default=os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"),
        help="Supabase service role key (or SUPABASE_KEY env)",
    )
    parser.add_argument(
        "--target-countries",
        default=",".join(DEFAULT_COUNTRIES),
        help="Comma-separated country keys (default: all developer-rich countries)",
    )
    parser.add_argument(
        "--max-per-location",
        type=int,
        default=None,
        help="Max new users to fetch per country (optional cap)",
    )
    parser.add_argument(
        "--profile-workers",
        type=int,
        default=PROFILE_FETCH_WORKERS,
        help="Parallel workers for REST fallback/email enrichment (default: 6, low-impact)",
    )
    parser.add_argument(
        "--skip-recent-hours",
        type=int,
        default=SKIP_SCRAPE_HOURS,
        help="Skip users scraped in the last N hours; set 0 to disable (default: 24)",
    )
    parser.add_argument(
        "--no-email-search-hint",
        action="store_true",
        help="Disable the faster in:email GitHub search hint.",
    )
    args = parser.parse_args()

    if not args.token:
        log.error("Missing GitHub token. Pass --token or set GITHUB_TOKEN.")
        return 1
    if not args.supabase_url or not args.supabase_key:
        log.error("Missing Supabase credentials. Set SUPABASE_URL and SUPABASE_KEY.")
        return 1

    countries = parse_countries(args.target_countries)
    unknown = [c for c in countries if c not in COUNTRY_LOCATION_TERMS]
    if unknown:
        log.warning(
            "No predefined location term for: %s. Using country name as location.",
            ", ".join(unknown),
        )
        for c in unknown:
            COUNTRY_LOCATION_TERMS[c] = c

    github = GitHubClient(args.token)
    supabase = create_client(args.supabase_url, args.supabase_key)

    try:
        scrape(
            github,
            supabase,
            countries,
            args.max_per_location,
            skip_recent_hours=args.skip_recent_hours,
            profile_workers=args.profile_workers,
            use_email_search_hint=not args.no_email_search_hint,
        )
    except KeyboardInterrupt:
        log.info("Interrupted by user.")
        return 130
    except Exception:
        log.exception("Scraper failed.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
