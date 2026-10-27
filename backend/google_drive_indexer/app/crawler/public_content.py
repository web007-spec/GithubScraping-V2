"""Fetch text/binary from public Google Docs, Sheets, Slides, and Drive files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup

from app.settings import Settings
from app.utils.drive_ids import is_valid_drive_id
from app.utils.drive_urls import DriveResourceKind
from app.utils.http import RateLimitedSession

_EXPORTS: list[tuple[DriveResourceKind | str, str, str]] = [
    ("document", "html", "https://docs.google.com/document/d/{id}/export?format=html"),
    ("document", "txt", "https://docs.google.com/document/d/{id}/export?format=txt"),
    ("spreadsheet", "csv", "https://docs.google.com/spreadsheets/d/{id}/export?format=csv"),
    ("spreadsheet", "xlsx", "https://docs.google.com/spreadsheets/d/{id}/export?format=xlsx"),
    ("presentation", "txt", "https://docs.google.com/presentation/d/{id}/export?format=txt"),
    ("presentation", "pdf", "https://docs.google.com/presentation/d/{id}/export?format=pdf"),
]

_VIEW_URL = "https://drive.google.com/file/d/{id}/view?usp=sharing"
_MOBILE_DOC = "https://docs.google.com/document/d/{id}/mobilebasic"
_CONFIRM_RE = re.compile(r"confirm=([0-9A-Za-z_-]+)")


@dataclass
class PublicFetchResult:
    ok: bool
    data: bytes
    mime_type: str
    extension: str
    strategy: str
    error: str | None = None


def _looks_like_login(text: str) -> bool:
    low = text.lower()
    return "sign in" in low and "accounts.google.com" in low


def _looks_like_login_bytes(data: bytes) -> bool:
    if not data or b"<html" not in data[:800].lower():
        return False
    return _looks_like_login(data[:4096].decode("utf-8", errors="ignore"))


def _guess_ext(mime: str, fmt: str) -> str:
    if fmt in {"html", "htm"}:
        return "html"
    if fmt == "txt":
        return "txt"
    if fmt == "csv":
        return "csv"
    if fmt in {"xlsx", "xls"}:
        return "xlsx"
    if fmt == "pdf":
        return "pdf"
    if "pdf" in mime:
        return "pdf"
    return fmt or "bin"


async def probe_public_access(session: RateLimitedSession, file_id: str) -> tuple[bool, str | None]:
    if not is_valid_drive_id(file_id):
        return False, "Invalid file id"
    view = _VIEW_URL.format(id=file_id)
    status, html = await session.get_text(view)
    if status in (401, 403, 404):
        return False, f"Not public (HTTP {status})"
    if status >= 400:
        return False, f"HTTP {status}"
    if _looks_like_login(html):
        return False, "Sign-in required"
    # Export probe — docs often work even when uc download returns 500.
    for kind, fmt, template in _EXPORTS[:2]:
        url = template.format(id=file_id)
        st, text = await session.get_text(url)
        if st == 200 and text and not _looks_like_login(text) and len(text) > 80:
            return True, None
    if len(html) > 2000:
        return True, None
    return False, "No public content detected"


async def fetch_public_content(
    session: RateLimitedSession,
    settings: Settings,
    *,
    file_id: str,
    mime_type: str = "",
    suggested_name: str = "",
    kind_hint: DriveResourceKind | str = "file",
) -> PublicFetchResult:
    if not is_valid_drive_id(file_id):
        return PublicFetchResult(False, b"", "", "", "invalid", "Invalid file id")

    kinds_to_try: list[str] = []
    for candidate in (kind_hint, mime_type, "document", "spreadsheet", "presentation", "file"):
        label = str(candidate or "").strip().lower()
        if not label:
            continue
        if "spreadsheet" in label or "sheet" in label:
            label = "spreadsheet"
        elif "presentation" in label or "slide" in label:
            label = "presentation"
        elif "document" in label or label == "gdoc":
            label = "document"
        elif label == "file":
            label = "file"
        if label not in kinds_to_try:
            kinds_to_try.append(label)

    for kind in kinds_to_try:
        for fmt, template in ((f, t) for k, f, t in _EXPORTS if k == kind):
            url = template.format(id=file_id)
            status, text = await session.get_text(url)
            if status == 200 and text and not _looks_like_login(text) and len(text) > 40:
                ext = _guess_ext("text/html" if fmt == "html" else f"text/{fmt}", fmt)
                return PublicFetchResult(
                    True,
                    text.encode("utf-8"),
                    "text/html" if fmt == "html" else f"text/{fmt}",
                    ext,
                    f"export-{kind}-{fmt}",
                )
            if status == 200:
                try:
                    status_b, data = await session.get_bytes(url, max_bytes=settings.max_file_size_bytes)
                    if status_b == 200 and data and not _looks_like_login_bytes(data):
                        ext = _guess_ext("application/octet-stream", fmt)
                        return PublicFetchResult(
                            True, data, f"application/{fmt}", ext, f"export-bytes-{kind}-{fmt}"
                        )
                except Exception:
                    pass

    # Google Doc mobile basic (lightweight HTML).
    mobile = _MOBILE_DOC.format(id=file_id)
    status, text = await session.get_text(mobile)
    if status == 200 and text and not _looks_like_login(text) and len(text) > 80:
        return PublicFetchResult(True, text.encode("utf-8"), "text/html", "html", "mobilebasic")

    # Drive download with virus-scan confirm token.
    binary = await _download_drive_binary(session, settings, file_id)
    if binary.ok:
        return binary

    # Scrape readable text from the public view page.
    scraped = await _scrape_view_text(session, file_id)
    if scraped.ok:
        return scraped

    return PublicFetchResult(False, b"", "", "", "none", "Could not fetch public content")


async def _download_drive_binary(
    session: RateLimitedSession,
    settings: Settings,
    file_id: str,
) -> PublicFetchResult:
    base = f"https://drive.google.com/uc?export=download&id={file_id}"
    try:
        status, data = await session.get_bytes(base, max_bytes=settings.max_file_size_bytes)
    except Exception as exc:
        return PublicFetchResult(False, b"", "", "", "uc", str(exc))

    if status == 200 and data and not _looks_like_login_bytes(data):
        ext = ".pdf" if data[:4] == b"%PDF" else "bin"
        return PublicFetchResult(True, data, "application/octet-stream", ext.lstrip("."), "uc-direct")

    # Parse confirm interstitial.
    try:
        status, html = await session.get_text(base)
    except Exception:
        html = ""
    if status == 200 and html:
        match = _CONFIRM_RE.search(html)
        if match:
            confirm = match.group(1)
            url = f"{base}&confirm={confirm}"
            try:
                status, data = await session.get_bytes(url, max_bytes=settings.max_file_size_bytes)
                if status == 200 and data and not _looks_like_login_bytes(data):
                    return PublicFetchResult(
                        True, data, "application/octet-stream", "bin", "uc-confirm"
                    )
            except Exception:
                pass

    usercontent = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
    try:
        status, data = await session.get_bytes(usercontent, max_bytes=settings.max_file_size_bytes)
        if status == 200 and data and not _looks_like_login_bytes(data):
            return PublicFetchResult(True, data, "application/octet-stream", "bin", "usercontent")
    except Exception:
        pass

    return PublicFetchResult(False, b"", "", "", "uc", f"Download failed HTTP {status}")


async def _scrape_view_text(session: RateLimitedSession, file_id: str) -> PublicFetchResult:
    status, html = await session.get_text(_VIEW_URL.format(id=file_id))
    if status != 200 or _looks_like_login(html):
        return PublicFetchResult(False, b"", "", "", "scrape", "View page not public")
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    if len(text) < 80:
        return PublicFetchResult(False, b"", "", "", "scrape", "No extractable text")
    return PublicFetchResult(True, text.encode("utf-8"), "text/plain", "txt", "view-scrape")


def write_fetched_bytes(
    settings: Settings,
    *,
    file_id: str,
    data: bytes,
    extension: str,
    digest_prefix: str,
) -> Path:
    ext = extension if extension.startswith(".") else f".{extension}" if extension else ".bin"
    dest = Path(settings.download_path)
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / f"{file_id}_{digest_prefix}{ext}"
    out.write_bytes(data)
    return out
