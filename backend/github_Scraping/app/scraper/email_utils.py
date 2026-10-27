"""Email detection and validation for GitHub profiles."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote

EMAIL_PATTERN = re.compile(
    r"\b[a-zA-Z0-9][a-zA-Z0-9._%+-]*@[a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,}\b",
    re.IGNORECASE,
)
MAILTO_PATTERN = re.compile(r"mailto:([^\s?&]+)", re.IGNORECASE)
# GitHub placeholder / automated addresses (not real contact emails)
JUNK_EMAIL = re.compile(
    r"(noreply|no-reply|users\.noreply\.github|@github\.com$|@localhost)",
    re.IGNORECASE,
)
# Common false positives from bios (image filenames, domains without TLD intent)
JUNK_SUFFIX = re.compile(r"\.(png|jpg|jpeg|gif|svg|webp|js|css|html)$", re.IGNORECASE)


def normalize_email(addr: str | None) -> str | None:
    if not addr:
        return None
    text = unquote(str(addr).strip().lower())
    if text.startswith("mailto:"):
        text = text[7:]
    text = text.strip(" <>\"'")
    if not text or "@" not in text:
        return None
    if not is_usable_email(text):
        return None
    return text


def is_usable_email(addr: str) -> bool:
    if JUNK_EMAIL.search(addr):
        return False
    if JUNK_SUFFIX.search(addr.split("@")[-1]):
        return False
    local, _, domain = addr.partition("@")
    if len(local) < 1 or len(domain) < 3 or "." not in domain:
        return False
    return True


def extract_emails_from_text(*texts: str | None) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for t in texts:
        if not t:
            continue
        for match in MAILTO_PATTERN.findall(t):
            norm = normalize_email(match)
            if norm and norm not in seen:
                seen.add(norm)
                found.append(norm)
        for match in EMAIL_PATTERN.findall(t):
            norm = normalize_email(match)
            if norm and norm not in seen:
                seen.add(norm)
                found.append(norm)
    return found


def pick_best_email(
    profile: dict[str, Any],
    public_emails: list[dict[str, Any]],
    extra_text: str | None = None,
) -> tuple[str | None, str, list[str]]:
    """Choose best contact email; never return GitHub noreply placeholders."""
    all_addresses: list[str] = []
    seen: set[str] = set()

    def add(addr: str | None, _source: str = "") -> None:
        norm = normalize_email(addr)
        if norm and norm not in seen:
            seen.add(norm)
            all_addresses.append(norm)

    profile_email = normalize_email(profile.get("email"))
    if profile_email:
        add(profile_email)

    for entry in public_emails:
        add(entry.get("email"))

    bio_texts = [
        profile.get("bio"),
        profile.get("company"),
        profile.get("location"),
        profile.get("name"),
        profile.get("blog"),
        extra_text,
    ]
    for addr in extract_emails_from_text(*bio_texts):
        add(addr)

    primary = None
    fallback = None
    for entry in public_emails:
        addr = normalize_email(entry.get("email"))
        if not addr:
            continue
        if entry.get("primary"):
            primary = addr
            break
        if not fallback:
            fallback = addr

    if primary:
        return primary, "public_emails_api", all_addresses
    if fallback:
        return fallback, "public_emails_api", all_addresses
    if profile_email and profile_email in all_addresses:
        return profile_email, "profile", all_addresses
    if all_addresses:
        return all_addresses[0], "bio_text", all_addresses

    return None, "none", all_addresses
