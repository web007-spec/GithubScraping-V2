"""Google Docs URL normalization and ID extraction."""

import re
from urllib.parse import parse_qs, urlparse, urlunparse

GOOGLE_DOC_PATTERNS = (
    re.compile(r"docs\.google\.com/document/d/([a-zA-Z0-9_-]+)"),
    re.compile(r"docs\.google\.com/open\?id=([a-zA-Z0-9_-]+)"),
    re.compile(r"drive\.google\.com/file/d/([a-zA-Z0-9_-]+)"),
)

EXPORT_FORMATS = ("html", "txt", "pdf")


def is_google_docs_url(url: str) -> bool:
    """Return True if URL appears to reference a Google Doc."""
    return extract_google_doc_id(url) is not None


def extract_google_doc_id(url: str) -> str | None:
    """Extract Google Document ID from various URL formats."""
    url = url.strip()
    for pattern in GOOGLE_DOC_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)

    parsed = urlparse(url)
    if "docs.google.com" in parsed.netloc:
        qs = parse_qs(parsed.query)
        if "id" in qs and qs["id"]:
            return qs["id"][0]
    return None


def normalize_google_docs_url(url: str) -> str | None:
    """
    Normalize a Google Docs URL to canonical form.

    Returns None if the URL is not a valid Google Docs URL.
    """
    doc_id = extract_google_doc_id(url)
    if not doc_id:
        return None
    return f"https://docs.google.com/document/d/{doc_id}/edit"


def build_export_url(doc_id: str, fmt: str = "html") -> str:
    """Build public export URL for a Google Doc."""
    if fmt not in EXPORT_FORMATS:
        raise ValueError(f"Unsupported export format: {fmt}")
    return f"https://docs.google.com/document/d/{doc_id}/export?format={fmt}"


def canonical_view_url(doc_id: str) -> str:
    """Return canonical view URL."""
    return f"https://docs.google.com/document/d/{doc_id}/view"
