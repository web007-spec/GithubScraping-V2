"""Parse and build public Google Drive URLs (folders + files only)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qs, urlparse

_FOLDER_RE = re.compile(r"/drive/folders/([a-zA-Z0-9_-]+)")
_FILE_RE = re.compile(r"/file/d/([a-zA-Z0-9_-]+)")
_OPEN_RE = re.compile(r"[?&]id=([a-zA-Z0-9_-]+)")
_DOC_RE = re.compile(r"/document/d/([a-zA-Z0-9_-]+)")
_SHEET_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]+)")
_SLIDE_RE = re.compile(r"/presentation/d/([a-zA-Z0-9_-]+)")

DriveResourceKind = Literal["folder", "file", "document", "spreadsheet", "presentation"]


@dataclass(frozen=True)
class DriveResource:
    kind: DriveResourceKind
    resource_id: str
    url: str


def extract_resource(url: str) -> DriveResource | None:
    raw = (url or "").strip()
    if not raw:
        return None
    if not raw.startswith("http"):
        raw = f"https://drive.google.com/{raw.lstrip('/')}"

    for pattern, kind in (
        (_FOLDER_RE, "folder"),
        (_FILE_RE, "file"),
        (_DOC_RE, "document"),
        (_SHEET_RE, "spreadsheet"),
        (_SLIDE_RE, "presentation"),
    ):
        match = pattern.search(raw)
        if match:
            rid = match.group(1)
            return DriveResource(kind=kind, resource_id=rid, url=normalize_public_url(kind, rid))

    parsed = urlparse(raw)
    if "drive.google.com" in parsed.netloc:
        qs = parse_qs(parsed.query)
        ids = qs.get("id") or []
        if ids:
            rid = ids[0]
            if "/folders" in parsed.path:
                return DriveResource(kind="folder", resource_id=rid, url=normalize_public_url("folder", rid))
            return DriveResource(kind="file", resource_id=rid, url=normalize_public_url("file", rid))
    return None


def normalize_public_url(kind: DriveResourceKind, resource_id: str) -> str:
    if kind == "folder":
        return f"https://drive.google.com/drive/folders/{resource_id}"
    if kind == "document":
        return f"https://docs.google.com/document/d/{resource_id}/edit?usp=sharing"
    if kind == "spreadsheet":
        return f"https://docs.google.com/spreadsheets/d/{resource_id}/edit?usp=sharing"
    if kind == "presentation":
        return f"https://docs.google.com/presentation/d/{resource_id}/edit?usp=sharing"
    return f"https://drive.google.com/file/d/{resource_id}/view?usp=sharing"


def export_url(file_id: str, mime_type: str) -> str:
    """Public export endpoint for Google Workspace files."""
    return f"https://drive.google.com/uc?export={mime_type}&id={file_id}"


def direct_download_url(file_id: str) -> str:
    return f"https://drive.google.com/uc?export=download&id={file_id}"
