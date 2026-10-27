"""Archive payload helpers for google_documents (mirrors indexer archive_payload)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def build_minimal_archive_data(
    *,
    headings: str | None = None,
    clean_text: str | None = None,
) -> dict[str, Any]:
    """Legacy CSV rows may lack archive_json; derive structure from stored text."""
    archive: dict[str, Any] = {}
    if headings:
        archive["headings"] = [
            part.strip() for part in str(headings).split("|") if part.strip()
        ][:200]
    if clean_text:
        paragraphs = [
            p.strip() for p in re.split(r"\n{2,}", str(clean_text)) if p.strip()
        ][:300]
        if paragraphs:
            archive["paragraphs"] = paragraphs
    return archive


def archive_json_loads(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def rebuild_search_text_from_row(row: dict[str, Any]) -> str:
    parts: list[str] = []
    if row.get("title"):
        parts.append(str(row["title"]))
    if row.get("headings"):
        parts.append(str(row["headings"]).replace("|", " "))
    if row.get("clean_text"):
        parts.append(str(row["clean_text"]))
    archive = row.get("archive_data")
    if isinstance(archive, str):
        archive = archive_json_loads(archive)
    if isinstance(archive, dict):
        for link in archive.get("links") or []:
            if isinstance(link, dict):
                if link.get("text"):
                    parts.append(str(link["text"]))
                if link.get("href"):
                    parts.append(str(link["href"]))
    return _collapse("\n".join(p for p in parts if p))


def content_archived_at_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def cap_html(html: str | None, *, max_len: int = 500_000) -> str | None:
    if not html:
        return None
    text = str(html)
    if len(text) <= max_len:
        return text
    return text[:max_len]
