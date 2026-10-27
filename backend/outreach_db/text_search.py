"""MongoDB $text search helpers — accurate candidate retrieval."""

from __future__ import annotations

import re
from typing import Any

_TOKEN_RE = re.compile(r"[a-z0-9@._+-]+", re.I)
_TEXT_SPECIAL_RE = re.compile(r'["\\]')
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "with",
    }
)


def query_tokens(query: str) -> list[str]:
    return [token for token in _TOKEN_RE.findall(str(query or "").strip().lower()) if len(token) > 1]


def substantive_tokens(query: str) -> list[str]:
    return [token for token in query_tokens(query) if token not in _STOPWORDS and len(token) >= 2]


def is_searchable_query(query: str) -> bool:
    """Reject empty / stopword-only queries that produce noisy matches."""
    raw = str(query or "").strip()
    if not raw:
        return False
    if "@" in raw:
        return True
    tokens = substantive_tokens(raw)
    if not tokens:
        return False
    return any(len(token) >= 3 for token in tokens) or len(tokens) >= 2


def format_text_search(query: str) -> str:
    """
    Build a MongoDB $text query string favoring precision (AND / phrase).
    """
    raw = str(query or "").strip()
    if not raw or not is_searchable_query(raw):
        return ""
    tokens = substantive_tokens(raw)
    if not tokens:
        return ""
    if len(tokens) == 1:
        return tokens[0]
    phrase = " ".join(tokens)
    return f'"{phrase}"'


def regex_pattern(query: str) -> str:
    """Escaped pattern; single terms use word boundaries to avoid substring noise."""
    raw = str(query or "").strip().replace("%", "")
    if not raw:
        return ""
    tokens = substantive_tokens(raw)
    if len(tokens) == 1:
        return rf"\b{re.escape(tokens[0])}\b"
    return re.escape(raw)


def text_score_boost(meta_score: float | None) -> int:
    """Map MongoDB textScore (typically 0–2+) to a 0–25 local boost."""
    if meta_score is None:
        return 0
    try:
        value = float(meta_score)
    except (TypeError, ValueError):
        return 0
    if value <= 0:
        return 0
    return min(25, int(value * 12))


def merge_text_rows(
    primary: list[dict[str, Any]],
    secondary: list[dict[str, Any]],
    *,
    limit: int,
    id_field: str,
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for row in primary + secondary:
        item_id = str(row.get(id_field) or row.get("id") or "")
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        merged.append(row)
        if len(merged) >= limit:
            break
    return merged
