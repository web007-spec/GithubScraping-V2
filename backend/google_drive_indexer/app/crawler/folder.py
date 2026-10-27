"""Enumerate publicly accessible files in Drive folders (no auth bypass)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from app.utils.drive_ids import is_valid_drive_id
from app.utils.drive_urls import DriveResource, extract_resource, normalize_public_url
from app.utils.http import RateLimitedSession

_MIME_HINT_RE = re.compile(r"application/(vnd\.google-apps\.\w+|[a-z0-9.+-]+)")


@dataclass
class DriveFileEntry:
    file_id: str
    name: str
    mime_type: str
    extension: str
    size: int | None
    public_url: str
    folder_id: str | None = None
    is_folder: bool = False
    kind: str = "file"


@dataclass
class FolderScanResult:
    folder_id: str
    folder_name: str
    folder_url: str
    files: list[DriveFileEntry] = field(default_factory=list)
    subfolders: list[str] = field(default_factory=list)
    restricted: bool = False
    error: str | None = None


def _guess_extension(name: str, mime_type: str) -> str:
    if "." in name:
        return name.rsplit(".", 1)[-1].lower()
    mapping = {
        "application/pdf": "pdf",
        "application/vnd.google-apps.document": "gdoc",
        "application/vnd.google-apps.spreadsheet": "gsheet",
        "application/vnd.google-apps.presentation": "gslide",
        "text/plain": "txt",
        "text/csv": "csv",
        "text/html": "html",
        "application/json": "json",
    }
    if mime_type.startswith("image/"):
        return mime_type.split("/", 1)[-1]
    return mapping.get(mime_type, "")


def _kind_from_mime(mime_type: str, is_folder: bool) -> str:
    if is_folder:
        return "folder"
    mime = (mime_type or "").lower()
    if "document" in mime:
        return "document"
    if "spreadsheet" in mime:
        return "spreadsheet"
    if "presentation" in mime:
        return "presentation"
    return "file"


def _parse_embedded_entries(html: str, folder_id: str) -> list[DriveFileEntry]:
    entries: list[DriveFileEntry] = []
    seen: set[str] = set()

    soup = BeautifulSoup(html, "lxml")
    for anchor in soup.select('a[href*="/file/d/"], a[href*="/drive/folders/"], a[href*="/document/d/"]'):
        href = anchor.get("href") or ""
        resource = extract_resource(href if href.startswith("http") else f"https://drive.google.com{href}")
        if not resource or not is_valid_drive_id(resource.resource_id):
            continue
        if resource.resource_id in seen or resource.resource_id == folder_id:
            continue
        seen.add(resource.resource_id)

        name = (anchor.get_text() or resource.resource_id).strip()[:500]
        is_folder = resource.kind == "folder"
        mime = "application/vnd.google-apps.folder" if is_folder else ""
        if not is_folder:
            aria = (anchor.get("aria-label") or anchor.get("data-tooltip") or "").lower()
            mime_match = _MIME_HINT_RE.search(aria)
            if mime_match:
                mime = mime_match.group(1)

        entries.append(
            DriveFileEntry(
                file_id=resource.resource_id,
                name=name,
                mime_type=mime,
                extension="",
                size=None,
                public_url=resource.url,
                folder_id=folder_id,
                is_folder=is_folder,
                kind=_kind_from_mime(mime, is_folder) if not is_folder else "folder",
            )
        )

    # data-id attributes from Drive folder grid (reliable).
    for tag in soup.select("[data-id]"):
        fid = (tag.get("data-id") or "").strip()
        if not is_valid_drive_id(fid) or fid in seen or fid == folder_id:
            continue
        seen.add(fid)
        name = (tag.get("data-tooltip") or tag.get("aria-label") or fid).strip()[:500]
        entries.append(
            DriveFileEntry(
                file_id=fid,
                name=name,
                mime_type="",
                extension="",
                size=None,
                public_url=normalize_public_url("file", fid),
                folder_id=folder_id,
                kind="file",
            )
        )

    return entries


async def scan_public_folder(
    session: RateLimitedSession,
    folder: DriveResource,
    *,
    max_depth: int = 4,
) -> FolderScanResult:
    url = folder.url
    status, html = await session.get_text(url)
    result = FolderScanResult(
        folder_id=folder.resource_id,
        folder_name=folder.resource_id,
        folder_url=url,
    )
    if status in (401, 403, 404):
        result.restricted = True
        result.error = f"Folder not publicly accessible (HTTP {status})"
        return result
    if status >= 400:
        result.error = f"HTTP {status}"
        return result

    lower = html.lower()
    if "sign in" in lower and "accounts.google.com" in lower and "servicelogin" in lower:
        result.restricted = True
        result.error = "Sign-in required — folder is not public"
        return result

    title_match = re.search(r"<title>([^<]+)</title>", html, re.I)
    if title_match:
        result.folder_name = title_match.group(1).replace(" - Google Drive", "").strip()[:300]

    entries = _parse_embedded_entries(html, folder.resource_id)
    for entry in entries:
        if entry.is_folder:
            if max_depth > 0:
                result.subfolders.append(entry.file_id)
        else:
            entry.extension = _guess_extension(entry.name, entry.mime_type)
            if entry.kind == "file" and entry.mime_type:
                entry.kind = _kind_from_mime(entry.mime_type, False)
            result.files.append(entry)
    return result


async def probe_file_public(session: RateLimitedSession, file_id: str) -> tuple[bool, str | None]:
    from app.crawler.public_content import probe_public_access

    return await probe_public_access(session, file_id)
