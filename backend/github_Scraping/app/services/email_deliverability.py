"""Email body sanitization and formatting (inbox-friendly outreach)."""

from __future__ import annotations

import html
import re

SUSPICIOUS_MEET_LOOKUP = re.compile(
    r"https?://meet\.google\.com/lookup/[^\s)]+", re.IGNORECASE
)


def sanitize_email_body(body: str) -> str:
    text = (
        SUSPICIOUS_MEET_LOOKUP.sub("https://meet.google.com/new", str(body or ""))
        .replace("\r\n", "\n")
        .strip()
    )
    lines = text.split("\n")
    non_empty = [ln for ln in lines if ln.strip()]
    only_link = len(non_empty) <= 2 and all(
        re.match(r"^https?://", ln.strip(), re.I) or not ln.strip() for ln in lines
    )
    if only_link and non_empty:
        return (
            "Hello,\n\n"
            "I wanted to follow up with you. Please reply to this email when you have a moment.\n\n"
            "If you would like to meet by video, you can use Google Meet:\n"
            "https://meet.google.com/new\n\n"
            "Best regards"
        )
    return text


def text_to_simple_html(text: str) -> str:
    escaped = html.escape(text)
    parts = []
    for line in escaped.split("\n"):
        parts.append(f"<p>{line}</p>" if line.strip() else "<br/>")
    return (
        '<div style="font-family:Arial,sans-serif;font-size:14px;'
        'line-height:1.5;color:#222;">'
        + "".join(parts)
        + "</div>"
    )


def format_from_header(email: str, display_name: str | None = None) -> str:
    addr = str(email or "").strip()
    if not addr:
        return addr
    name = re.sub(r'[<>"\r\n]', "", str(display_name or "")).strip()
    if not name:
        return addr
    return f'"{name}" <{addr}>'
