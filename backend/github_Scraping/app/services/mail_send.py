"""Send outreach email via Gmail/Outlook SMTP (deliverability-safe)."""

from __future__ import annotations

import asyncio
import base64
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from app.config import get_settings
from app.services.email_deliverability import (
    format_from_header,
    sanitize_email_body,
    text_to_simple_html,
)
from app.services.smtp_utils import (
    detect_email_provider,
    normalize_app_password,
    normalize_smtp_body,
    normalize_smtp_user,
    validate_smtp_user_for_provider,
)


def _env_creds(provider: str) -> dict | None:
    if provider == "gmail":
        user, passwd = os.getenv("SMTP_GMAIL_USER"), os.getenv("SMTP_GMAIL_PASS")
    else:
        user, passwd = os.getenv("SMTP_OUTLOOK_USER"), os.getenv("SMTP_OUTLOOK_PASS")
    if user and passwd:
        return {
            "user": normalize_smtp_user(user),
            "pass": normalize_app_password(passwd),
        }
    return None


def _gmail_oauth_access_token(refresh_token: str) -> str:
    settings = get_settings()
    client_id = (settings.google_client_id or "").strip()
    client_secret = (settings.google_client_secret or "").strip()
    if not client_id or not client_secret:
        raise ValueError("Google OAuth is not configured on the server.")
    with httpx.Client(timeout=30.0) as client:
        res = client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
    data = res.json() if res.content else {}
    if not res.is_success:
        raise ValueError(
            data.get("error_description") or data.get("error") or "OAuth token refresh failed"
        )
    access = data.get("access_token")
    if not access:
        raise ValueError("OAuth did not return an access token.")
    return str(access)


def _gmail_transport(smtp: dict) -> tuple[smtplib.SMTP, str]:
    creds = (smtp.get("gmail") or {}) if smtp else {}
    user = creds.get("user") or ""
    oauth = creds.get("oauth") if isinstance(creds.get("oauth"), dict) else {}
    refresh = str(oauth.get("refreshToken") or "").strip()
    passwd = creds.get("pass") or ""

    if user and refresh:
        validate_smtp_user_for_provider("gmail", user)
        access = _gmail_oauth_access_token(refresh)
        auth_string = f"user={user}\1auth=Bearer {access}\1\1"
        auth_b64 = base64.b64encode(auth_string.encode()).decode()
        transport = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30)
        code, resp = transport.docmd("AUTH", "XOAUTH2 " + auth_b64)
        if code != 235:
            raise ValueError(resp.decode() if isinstance(resp, bytes) else str(resp))
        return transport, user

    if not user or not passwd:
        env = _env_creds("gmail")
        if not env:
            raise ValueError(
                "Gmail is not configured. Extension → Configuration → "
                "Connect with Google (your existing account) or 16-character App Password."
            )
        user, passwd = env["user"], env["pass"]
    validate_smtp_user_for_provider("gmail", user)
    transport = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30)
    transport.login(user, passwd)
    return transport, user


def _outlook_transport(smtp: dict) -> tuple[smtplib.SMTP, str]:
    creds = (smtp.get("outlook") or {}) if smtp else {}
    user = creds.get("user") or ""
    passwd = creds.get("pass") or ""
    if not user or not passwd:
        env = _env_creds("outlook")
        if not env:
            raise ValueError(
                "Outlook is not configured. Add Outlook address and App Password in the extension."
            )
        user, passwd = env["user"], env["pass"]
    validate_smtp_user_for_provider("outlook", user)
    host = os.getenv("SMTP_OUTLOOK_HOST", "smtp-mail.outlook.com")
    port = int(os.getenv("SMTP_OUTLOOK_PORT", "587"))
    transport = smtplib.SMTP(host, port, timeout=30)
    transport.ehlo()
    transport.starttls(context=ssl.create_default_context())
    transport.ehlo()
    transport.login(user, passwd)
    return transport, user


async def run_smtp_test(body: dict) -> dict:
    """Verify SMTP credentials from extension test request body."""
    from app.services.smtp_utils import normalize_smtp_body

    provider = "outlook" if body.get("provider") == "outlook" else "gmail"
    smtp = normalize_smtp_body(body if isinstance(body, dict) else {})
    block = smtp.get(provider)
    if not block:
        raise ValueError(
            f"{provider.title()} is not configured. "
            "Extension → Connect with Google or App Password → Save → Test."
        )
    await asyncio.to_thread(verify_smtp_login, provider, smtp)
    return {
        "ok": True,
        "provider": provider,
        "message": f"{provider.title()} account recognized and ready to send.",
    }


def verify_smtp_login(provider: str, smtp: dict) -> dict:
    transport, _ = (
        _gmail_transport(smtp) if provider == "gmail" else _outlook_transport(smtp)
    )
    try:
        transport.noop()
    finally:
        try:
            transport.quit()
        except Exception:
            pass
    return {"ok": True, "provider": provider}


def send_contact_email(
    *,
    to: str,
    subject: str,
    body: str,
    provider: str,
    smtp: dict,
    from_name: str | None = None,
) -> dict:
    to_addr = str(to).strip()
    if not to_addr:
        raise ValueError("Recipient email is required.")

    resolved = provider if provider in ("gmail", "outlook") else detect_email_provider(to_addr)
    if not resolved:
        raise ValueError("Only Gmail and Outlook recipient addresses are supported.")

    smtp_norm = normalize_smtp_body({"smtp": smtp})
    transport, from_addr = (
        _gmail_transport(smtp_norm)
        if resolved == "gmail"
        else _outlook_transport(smtp_norm)
    )

    text = sanitize_email_body(body)
    html_body = text_to_simple_html(text)
    subj = (subject or "Following up").strip()
    label = (
        (from_name or "").strip()
        or smtp_norm.get(resolved, {}).get("user", "").split("@")[0]
        or from_addr.split("@")[0]
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subj
    msg["From"] = format_from_header(from_addr, label)
    msg["To"] = to_addr
    msg["Reply-To"] = from_addr
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        transport.sendmail(from_addr, [to_addr], msg.as_string())
        message_id = msg.get("Message-ID", "")
    finally:
        try:
            transport.quit()
        except Exception:
            pass

    return {"messageId": message_id, "provider": resolved, "from": from_addr}
