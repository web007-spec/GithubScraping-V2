"""Build archive payloads for AI search and long-term storage."""

from __future__ import annotations

import json
from typing import Any

from app.parser.cleaner import clean_text


def build_archive_data(parsed: Any) -> dict[str, Any]:
    """Structured document body for archive / future AI retrieval."""
    links = [{"href": href, "text": text or ""} for href, text in (parsed.links or [])[:500]]
    images = [{"src": src, "alt": alt or ""} for src, alt in (parsed.images or [])[:100]]
    return {
        "headings": list(parsed.headings or [])[:200],
        "paragraphs": list(parsed.paragraphs or [])[:300],
        "lists": list(parsed.lists or [])[:80],
        "tables": list(parsed.tables or [])[:40],
        "links": links,
        "images": images,
    }


def build_search_text(parsed: Any) -> str:
    """Single normalized text field for full-text / AI search."""
    parts: list[str] = []
    if parsed.title:
        parts.append(str(parsed.title))
    if parsed.headings:
        parts.append(" ".join(str(h) for h in parsed.headings))
    if parsed.clean_text:
        parts.append(str(parsed.clean_text))
    for href, text in (parsed.links or [])[:150]:
        if text:
            parts.append(str(text))
        if href:
            parts.append(str(href))
    return clean_text("\n".join(parts))


def archive_json_dumps(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def archive_json_loads(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def rebuild_search_text_from_row(row: dict[str, Any]) -> str:
    """Rebuild search_text from stored columns (CSV import / legacy rows)."""
    parts: list[str] = []
    if row.get("title"):
        parts.append(str(row["title"]))
    if row.get("headings"):
        parts.append(str(row["headings"]).replace("|", " "))
    if row.get("clean_text"):
        parts.append(str(row["clean_text"]))
    archive = row.get("archive_data")
    if isinstance(archive, dict):
        for link in archive.get("links") or []:
            if isinstance(link, dict):
                parts.append(str(link.get("text") or ""))
                parts.append(str(link.get("href") or ""))
    return clean_text("\n".join(p for p in parts if p))
