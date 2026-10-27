"""Fast profile enrichment with minimal API calls."""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Callable

from app.scraper.email_utils import extract_emails_from_text, is_usable_email, normalize_email, pick_best_email
from app.scraper.graphql_batch import graphql_fetch_users

log = logging.getLogger(__name__)

StopChecker = Callable[[], bool]


def _clean_text(value: Any, max_len: int | None = None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if max_len and len(text) > max_len:
        return text[:max_len]
    return text


def _safe_json(value: Any) -> Any:
    if value is None:
        return None
    try:
        return json.loads(json.dumps(value, default=str))
    except (TypeError, ValueError):
        return str(value)


def _profile_has_usable_email(profile: dict[str, Any]) -> bool:
    if normalize_email(profile.get("email")):
        return True
    texts = [
        profile.get("bio"),
        profile.get("company"),
        profile.get("location"),
        profile.get("name"),
        profile.get("blog"),
    ]
    return bool(extract_emails_from_text(*texts))


def fetch_public_emails(github: Any, login: str) -> list[dict[str, Any]]:
    try:
        response = github.request(
            "GET", f"https://api.github.com/users/{login}/public_emails"
        )
        if response.status_code in (404, 403, 422):
            return []
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else []
    except Exception:
        return []


def fetch_social_accounts(github: Any, login: str) -> list[dict[str, Any]]:
    try:
        response = github.request(
            "GET", f"https://api.github.com/users/{login}/social_accounts"
        )
        if response.status_code in (404, 403, 422):
            return []
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            return []
        return [
            {
                "provider": item.get("provider"),
                "url": item.get("url"),
                "display_name": item.get("display_name"),
            }
            for item in data
            if item.get("url")
        ]
    except Exception:
        return []


def build_full_description(
    profile: dict[str, Any],
    public_emails: list[dict[str, Any]],
    social_accounts: list[dict[str, Any]],
) -> str | None:
    parts: list[str] = []
    for key in ("bio", "company", "location"):
        t = _clean_text(profile.get(key))
        if t:
            parts.append(t if key == "bio" else f"{key.title()}: {t}")
    blog = _clean_text(profile.get("blog"))
    if blog:
        parts.append(f"Website: {blog}")
    tw = _clean_text(profile.get("twitter_username"))
    if tw:
        parts.append(f"Twitter: @{tw.lstrip('@')}")
    for entry in public_emails:
        if entry.get("email"):
            parts.append(f"Email: {entry['email']}")
    return "\n".join(parts) if parts else None


def build_user_row(
    profile: dict[str, Any],
    country: str,
    *,
    public_emails: list[dict[str, Any]] | None = None,
    social_accounts: list[dict[str, Any]] | None = None,
    minimal_storage: bool = True,
) -> dict[str, Any]:
    public_emails = public_emails or []
    social_accounts = social_accounts or []
    description = build_full_description(profile, public_emails, social_accounts)
    email, email_source, all_email_list = pick_best_email(profile, public_emails, description)
    bio = _clean_text(profile.get("bio"), max_len=4000) or description
    now = datetime.now(timezone.utc).isoformat()

    profile_data = (
        {"scraped_at": now, "email_source": email_source}
        if minimal_storage
        else {
            "profile": _safe_json(profile),
            "public_emails": _safe_json(public_emails),
            "scraped_at": now,
        }
    )

    return {
        "id": profile["id"],
        "login": profile["login"],
        "name": _clean_text(profile.get("name"), max_len=500),
        "location": _clean_text(profile.get("location"), max_len=500),
        "company": _clean_text(profile.get("company"), max_len=500),
        "email": email,
        "email_source": email_source,
        "bio": bio,
        "description": _clean_text(description, max_len=8000),
        "blog": _clean_text(profile.get("blog"), max_len=500),
        "twitter_username": _clean_text(profile.get("twitter_username"), max_len=100),
        "github_url": _clean_text(profile.get("html_url"), max_len=500),
        "avatar_url": _clean_text(profile.get("avatar_url"), max_len=500),
        "public_repos": profile.get("public_repos"),
        "public_gists": profile.get("public_gists"),
        "followers": profile.get("followers"),
        "following": profile.get("following"),
        "created_at": profile.get("created_at"),
        "updated_at": profile.get("updated_at"),
        "last_scraped_at": now,
        "country": country,
        "all_emails": all_email_list,
        "social_links": social_accounts,
        "profile_data": profile_data,
    }


def enrich_from_profile(
    github: Any,
    profile: dict[str, Any],
    country: str,
    *,
    full: bool = False,
    email_only: bool = True,
    skip_email_api_if_found: bool = True,
) -> dict[str, Any] | None:
    login = profile.get("login")
    if not login:
        return None

    emails: list[dict[str, Any]] = []
    social: list[dict[str, Any]] = []

    need_email_api = not skip_email_api_if_found or not _profile_has_usable_email(profile)

    if full:
        if need_email_api:
            emails = fetch_public_emails(github, login)
        social = fetch_social_accounts(github, login)
    elif need_email_api:
        emails = fetch_public_emails(github, login)
    elif profile.get("email") and is_usable_email(str(profile.get("email", ""))):
        emails = [{"email": profile["email"], "primary": True}]

    row = build_user_row(
        profile,
        country,
        public_emails=emails,
        social_accounts=social,
        minimal_storage=not full,
    )
    if email_only and not row.get("email"):
        return None
    return row


def rest_fetch_users_parallel(
    github: Any,
    logins: list[str],
    *,
    workers: int = 25,
    should_stop: StopChecker | None = None,
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not logins:
        return out

    def task(login: str) -> tuple[str, dict[str, Any] | None]:
        if should_stop and should_stop():
            return login, None
        try:
            return login, github.get_user(login)
        except Exception:
            return login, None

    with ThreadPoolExecutor(max_workers=min(workers, len(logins))) as pool:
        futures = [pool.submit(task, login) for login in logins]
        for fut in as_completed(futures):
            if should_stop and should_stop():
                break
            login, prof = fut.result()
            if prof:
                out[login] = prof
    return out


def fetch_profiles_fast(
    github: Any,
    logins: list[str],
    *,
    workers: int = 25,
    should_stop: StopChecker | None = None,
) -> dict[str, dict[str, Any]]:
    profiles = graphql_fetch_users(github, logins)
    missing = [login for login in logins if login not in profiles]
    if missing and not (should_stop and should_stop()):
        rest = rest_fetch_users_parallel(
            github, missing, workers=workers, should_stop=should_stop
        )
        profiles.update(rest)
    return profiles


def enrich_profiles_batch(
    github: Any,
    logins: list[str],
    country: str,
    *,
    full: bool = False,
    email_only: bool = True,
    should_stop: StopChecker | None = None,
    workers: int = 25,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """
    Returns (rows stored, stats dict).
    """
    stats = {"candidates": len(logins), "profiles": 0, "with_email": 0, "skipped": 0}

    if not logins or (should_stop and should_stop()):
        return [], stats

    profiles = fetch_profiles_fast(github, logins, workers=workers, should_stop=should_stop)
    stats["profiles"] = len(profiles)

    rows: list[dict[str, Any]] = []
    worker_count = max(1, min(workers, len(profiles)))

    def email_task(login: str) -> dict[str, Any] | None:
        if should_stop and should_stop():
            return None
        prof = profiles.get(login)
        if not prof:
            return None
        return enrich_from_profile(
            github,
            prof,
            country,
            full=full,
            email_only=email_only,
            skip_email_api_if_found=True,
        )

    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        futures = {pool.submit(email_task, login): login for login in logins if login in profiles}
        for fut in as_completed(futures):
            if should_stop and should_stop():
                break
            try:
                row = fut.result()
                if row:
                    rows.append(row)
                    stats["with_email"] += 1
                else:
                    stats["skipped"] += 1
            except Exception:
                stats["skipped"] += 1

    return rows, stats


def enrich_user_profile(
    github: Any,
    login: str,
    country: str,
    *,
    full: bool = False,
    email_only: bool = True,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if profile is None:
        profile = github.get_user(login)
    if not profile:
        return None
    return enrich_from_profile(github, profile, country, full=full, email_only=email_only)

