"""Extract sharing contact email and document dates from public Google Docs pages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from urllib.parse import unquote

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
MAILTO_RE = re.compile(r"mailto:([^\"'>\s?#]+)", re.I)
UST_RE = re.compile(r"ust=(\d{13,16})")
MS_TS_RE = re.compile(r"\b(1[56]\d{11})\b")

PLACEHOLDER_EMAILS = frozenset(
    {
        "email@address.com",
        "name@email.com",
        "you@email.com",
        "your.email@example.com",
        "email@example.com",
        "user@example.com",
        "name@example.com",
        "john.doe@example.com",
        "jane.doe@example.com",
        "no_reply@example.com",
        "noreply@example.com",
        "donotreply@example.com",
        "test@test.com",
        "user@domain.com",
    }
)

PLACEHOLDER_SUFFIXES = (
    "@example.com",
    "@email.com",
    "@address.com",
    "@test.com",
    "@domain.com",
    "@sample.com",
    "@yourdomain.com",
)

BLOCKED_EMAIL_SUFFIXES = (
    "@google.com",
    "@googlemail.com",
    "@docs.google.com",
)

SOURCE_SCORES = {
    "mailto_page": 100,
    "mailto_export": 95,
    "mailto_edit": 90,
    "page": 70,
    "export": 55,
    "edit": 50,
    "content": 30,
}


@dataclass
class DocumentMetadata:
    shared_by_email: str | None = None
    shared_by_name: str | None = None
    shared_at: str | None = None
    document_modified_at: str | None = None
    contact_emails: list[str] | None = None


def is_placeholder_email(email: str | None) -> bool:
    """Return True when an address is a template/placeholder, not a real contact."""
    normalized = _normalize_email(email, allow_placeholders=True)
    if not normalized:
        return True
    return _normalize_email(email) is None


def _iso_from_millis(value: int) -> str | None:
    try:
        if value > 10_000_000_000_000:
            value = value // 1000
        if value < 1_000_000_000_000:
            value *= 1000
        dt = datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        if dt.year < 2005 or dt.year > 2035:
            return None
        return dt.isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def _normalize_email(raw: str | None, *, allow_placeholders: bool = False) -> str | None:
    email = unquote(unescape(str(raw or "").strip())).strip(".,;:\"'()[]<>")
    if not email or "@" not in email:
        return None
    email = email.lower()
    local, _, domain = email.partition("@")
    if not local or not domain or "." not in domain:
        return None
    if not allow_placeholders:
        if email in PLACEHOLDER_EMAILS:
            return None
        if any(email.endswith(suffix) for suffix in PLACEHOLDER_SUFFIXES):
            return None
        if any(email.endswith(suffix) for suffix in BLOCKED_EMAIL_SUFFIXES):
            return None
        if local in {"noreply", "no_reply", "donotreply", "do-not-reply"}:
            return None
        if "no-reply" in email:
            return None
        if local in {"email", "name", "you", "your.email", "user", "username"}:
            return None
    if not EMAIL_RE.fullmatch(email):
        return None
    return email


def _score_email(email: str, source: str) -> float:
    score = float(SOURCE_SCORES.get(source, 20))
    lower = email.lower()
    if any(lower.endswith(suffix) for suffix in PLACEHOLDER_SUFFIXES):
        score -= 80
    if lower in PLACEHOLDER_EMAILS:
        score -= 80
    if lower.split("@", 1)[0] in {"noreply", "no_reply", "donotreply"}:
        score -= 60
    if any(provider in lower for provider in ("@gmail.", "@yahoo.", "@outlook.", "@hotmail.", "@icloud.", "@live.")):
        score += 8
    if any(lower.endswith(suffix) for suffix in (".edu", ".org", ".gov", ".co.uk")):
        score += 5
    return score


def _rank_emails(candidates: list[tuple[str, str]]) -> list[str]:
    """Rank (email, source) pairs by quality; highest first."""
    best: dict[str, float] = {}
    order: list[str] = []
    for email, source in candidates:
        normalized = _normalize_email(email)
        if not normalized:
            continue
        score = _score_email(normalized, source)
        prev = best.get(normalized)
        if prev is None:
            order.append(normalized)
            best[normalized] = score
        else:
            best[normalized] = max(prev, score)
    order.sort(key=lambda item: best[item], reverse=True)
    return order


def _collect_emails(text: str, source: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for match in EMAIL_RE.findall(text or ""):
        normalized = _normalize_email(match)
        if normalized and normalized not in seen:
            seen.add(normalized)
            pairs.append((normalized, source))
    return pairs


def _collect_mailto(text: str, source: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for match in MAILTO_RE.findall(text or ""):
        normalized = _normalize_email(match)
        if normalized and normalized not in seen:
            seen.add(normalized)
            mailto_source = f"mailto_{source}"
            pairs.append((normalized, mailto_source))
    return pairs


def _collect_timestamps(*chunks: str) -> list[int]:
    values: list[int] = []
    for chunk in chunks:
        if not chunk:
            continue
        for match in UST_RE.findall(chunk):
            try:
                values.append(int(match))
            except ValueError:
                continue
        for match in MS_TS_RE.findall(chunk):
            try:
                values.append(int(match))
            except ValueError:
                continue
    return values


def _pick_shared_at(*chunks: str) -> str | None:
    stamps = _collect_timestamps(*chunks)
    if not stamps:
        return None
    converted = [_iso_from_millis(value) for value in stamps]
    valid = [item for item in converted if item]
    return max(valid) if valid else None


def _name_before_email(text: str, email: str) -> str | None:
    idx = text.lower().find(email.lower())
    if idx <= 0:
        return None
    prefix = text[max(0, idx - 80) : idx]
    prefix = re.sub(r"\s+", " ", prefix).strip(" |:-–—\t")
    if not prefix or len(prefix) < 2:
        return None
    tokens = [part for part in re.split(r"[|\n,;]", prefix) if part.strip()]
    candidate = tokens[-1].strip() if tokens else prefix
    if "@" in candidate or len(candidate) > 64:
        return None
    if candidate.startswith("[") or candidate.lower() in {"email address", "contact number"}:
        return None
    return candidate


def extract_document_metadata(
    *,
    export_html: str = "",
    page_html: str = "",
    edit_html: str = "",
    clean_text: str = "",
) -> DocumentMetadata:
    """Best-effort contact email for public docs (Google account email is rarely exposed)."""
    candidates: list[tuple[str, str]] = []
    candidates.extend(_collect_mailto(page_html, "page"))
    candidates.extend(_collect_mailto(export_html, "export"))
    candidates.extend(_collect_mailto(edit_html, "edit"))
    candidates.extend(_collect_emails(page_html, "page"))
    candidates.extend(_collect_emails(export_html, "export"))
    candidates.extend(_collect_emails(edit_html, "edit"))

    content_source = clean_text or ""
    if content_source:
        candidates.extend(_collect_emails(content_source[:16000], "content"))

    ranked = _rank_emails(candidates)
    shared_by_email = ranked[0] if ranked else None

    shared_by_name = None
    if shared_by_email and clean_text:
        shared_by_name = _name_before_email(clean_text, shared_by_email)

    shared_at = _pick_shared_at(page_html, export_html, edit_html)
    document_modified_at = shared_at

    return DocumentMetadata(
        shared_by_email=shared_by_email,
        shared_by_name=shared_by_name,
        shared_at=shared_at,
        document_modified_at=document_modified_at,
        contact_emails=ranked[:20] or None,
    )


def fetch_document_metadata_sync(
    doc_id: str,
    *,
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    timeout: float = 30.0,
) -> DocumentMetadata:
    """Fetch public Google Doc pages and extract sharing/contact metadata."""
    import httpx

    doc_id = str(doc_id or "").strip()
    if not doc_id:
        return DocumentMetadata()

    urls = (
        ("page", f"https://docs.google.com/document/d/{doc_id}/mobilebasic"),
        ("export", f"https://docs.google.com/document/d/{doc_id}/export?format=html"),
        ("edit", f"https://docs.google.com/document/d/{doc_id}/edit"),
    )
    page_html = ""
    export_html = ""
    edit_html = ""
    headers = {"User-Agent": user_agent}

    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
            for kind, url in urls:
                try:
                    response = client.get(url)
                except Exception:
                    continue
                if response.status_code != 200:
                    continue
                text = response.text
                if kind == "page":
                    page_html = text
                elif kind == "export":
                    export_html = text
                elif kind == "edit":
                    edit_html = text
    except Exception:
        return DocumentMetadata()

    return extract_document_metadata(
        export_html=export_html,
        page_html=page_html,
        edit_html=edit_html,
    )
