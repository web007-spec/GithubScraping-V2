"""SMTP credential normalization (extension → server)."""

from __future__ import annotations

import re

GMAIL_DOMAINS = {"gmail.com", "googlemail.com"}
OUTLOOK_DOMAINS = {
    "outlook.com",
    "outlook.co.uk",
    "hotmail.com",
    "live.com",
    "msn.com",
}


def normalize_app_password(pass_raw: str) -> str:
    return re.sub(r"\s+", "", str(pass_raw or "")).strip()


def normalize_smtp_user(email: str) -> str:
    return str(email or "").strip().lower()


def detect_email_provider(email: str) -> str | None:
    domain = normalize_smtp_user(email).split("@")[-1] if "@" in email else ""
    if domain in GMAIL_DOMAINS:
        return "gmail"
    if any(domain == d or domain.endswith("." + d.split(".")[-1]) for d in OUTLOOK_DOMAINS):
        if domain in OUTLOOK_DOMAINS or domain.startswith("outlook.") or domain.startswith("hotmail."):
            return "outlook"
    for d in OUTLOOK_DOMAINS:
        if domain == d or domain.endswith("." + d):
            return "outlook"
    return None


def validate_smtp_user_for_provider(provider: str, user_email: str) -> str:
    user = normalize_smtp_user(user_email)
    if not user or "@" not in user:
        raise ValueError(
            f"{'Outlook' if provider == 'outlook' else 'Gmail'} address is required."
        )
    detected = detect_email_provider(user)
    if provider == "gmail" and detected != "gmail":
        raise ValueError(
            f"Gmail account must be @gmail.com or @googlemail.com (you entered {user})."
        )
    if provider == "outlook" and detected != "outlook":
        raise ValueError(
            f"Outlook account must be @outlook.com, @hotmail.com, @live.com, etc. "
            f"(you entered {user})."
        )
    return user


def normalize_smtp_body(raw: dict) -> dict:
    smtp = raw.get("smtp") or {}
    out: dict = {"gmail": None, "outlook": None}

    gmail_block = smtp.get("gmail")
    if isinstance(gmail_block, dict):
        user = normalize_smtp_user(gmail_block.get("user") or "")
        oauth = gmail_block.get("oauth") if isinstance(gmail_block.get("oauth"), dict) else {}
        refresh = str(oauth.get("refreshToken") or "").strip()
        passwd = normalize_app_password(gmail_block.get("pass") or "")
        if user:
            try:
                validate_smtp_user_for_provider("gmail", user)
                if refresh:
                    out["gmail"] = {
                        "user": user,
                        "oauth": {"refreshToken": refresh},
                        "authMethod": "oauth2",
                    }
                elif passwd:
                    out["gmail"] = {
                        "user": user,
                        "pass": passwd,
                        "authMethod": "app_password",
                    }
            except ValueError:
                pass

    outlook_block = smtp.get("outlook")
    if isinstance(outlook_block, dict):
        user = normalize_smtp_user(outlook_block.get("user") or "")
        passwd = normalize_app_password(outlook_block.get("pass") or "")
        if user and passwd:
            try:
                validate_smtp_user_for_provider("outlook", user)
                out["outlook"] = {"user": user, "pass": passwd}
            except ValueError:
                pass

    return out
