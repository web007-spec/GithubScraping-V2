"""Batch GitHub user lookups via GraphQL (fewer HTTP round-trips)."""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

GRAPHQL_URL = "https://api.github.com/graphql"

USER_FIELDS = """
      databaseId
      login
      name
      email
      bio
      company
      location
      websiteUrl
      twitterUsername
      avatarUrl
      createdAt
      updatedAt
      followers { totalCount }
      following { totalCount }
      repositories(privacy: PUBLIC) { totalCount }
      gists { totalCount }
"""


def _safe_login(login: str) -> str:
    return login.replace("\\", "").replace('"', "").replace("\n", "")[:39]


def graphql_fetch_users(
    github: Any,
    logins: list[str],
) -> dict[str, dict[str, Any]]:
    """
    Fetch up to 50 users in one GraphQL request. Returns login -> REST-shaped profile dict.
    """
    if not logins:
        return {}

    batch = logins[:50]
    aliases = []
    for i, login in enumerate(batch):
        safe = _safe_login(login)
        aliases.append(f'u{i}: user(login: "{safe}") {{{USER_FIELDS}\n    }}')

    query = "query BatchUsers {\n  " + "\n  ".join(aliases) + "\n}"
    stop_check = getattr(github, "_stop_check", None)
    response = github.request(
        "POST",
        GRAPHQL_URL,
        stop_check=stop_check,
        json={"query": query},
    )
    if response.status_code != 200:
        log.warning("GraphQL batch failed: %s %s", response.status_code, response.text[:200])
        return {}

    payload = response.json()
    if payload.get("errors"):
        log.debug("GraphQL errors: %s", payload["errors"][:2])

    data = payload.get("data") or {}
    out: dict[str, dict[str, Any]] = {}
    for i, login in enumerate(batch):
        node = data.get(f"u{i}")
        if not node or not node.get("login"):
            continue
        out[login] = _graphql_to_rest_profile(node)
    return out


def _graphql_to_rest_profile(node: dict[str, Any]) -> dict[str, Any]:
    followers = (node.get("followers") or {}).get("totalCount")
    following = (node.get("following") or {}).get("totalCount")
    repos = (node.get("repositories") or {}).get("totalCount")
    gists = (node.get("gists") or {}).get("totalCount")
    return {
        "id": node.get("databaseId"),
        "login": node.get("login"),
        "name": node.get("name"),
        "email": node.get("email"),
        "bio": node.get("bio"),
        "company": node.get("company"),
        "location": node.get("location"),
        "blog": node.get("websiteUrl"),
        "twitter_username": node.get("twitterUsername"),
        "avatar_url": node.get("avatarUrl"),
        "html_url": f"https://github.com/{node.get('login')}",
        "created_at": node.get("createdAt"),
        "updated_at": node.get("updatedAt"),
        "followers": followers,
        "following": following,
        "public_repos": repos,
        "public_gists": gists,
    }
