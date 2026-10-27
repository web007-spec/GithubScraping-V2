"""Validate Google Drive resource identifiers."""

from __future__ import annotations

import re

from app.utils.drive_urls import DriveResourceKind, extract_resource

# Real Drive IDs: alphanumeric + _ - ; typically 25–44 chars.
_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{20,50}$")
_JUNK_MARKERS = ("u003d", "x220", "x27", "\\u", "http", "www.", "null", "undefined")


def is_valid_drive_id(resource_id: str) -> bool:
    rid = (resource_id or "").strip()
    if not rid or rid in {"_gd", "gd"}:
        return False
    if not _ID_RE.match(rid):
        return False
    lower = rid.lower()
    return not any(marker in lower for marker in _JUNK_MARKERS)


def filter_valid_resources(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for url in urls:
        resource = extract_resource(url)
        if not resource or not is_valid_drive_id(resource.resource_id):
            continue
        if resource.resource_id in seen:
            continue
        seen.add(resource.resource_id)
        out.append(resource.url)
    return out
