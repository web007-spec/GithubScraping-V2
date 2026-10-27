"""AI contact analysis and outreach letters (OpenAI / Gemini)."""

from __future__ import annotations

import os
from typing import Any

import httpx

from app.config import get_settings


def ai_providers_configured() -> dict[str, bool]:
    s = get_settings()
    return {
        "openai": bool((s.openai_api_key or "").strip()),
        "gemini": bool((s.gemini_api_key or "").strip()),
    }


def get_ai_config(owner_ip: str | None = None) -> dict:
    providers = ai_providers_configured()
    providers_out = {
        "openai": providers["openai"],
        "gemini": providers["gemini"],
        "openaiEnabled": providers["openai"],
    }

    if providers["gemini"]:
        default = "gemini"
    elif providers["openai"]:
        default = "openai"
    else:
        default = "gemini"

    return {
        "ok": True,
        "providers": providers_out,
        "defaultProvider": default,
        "linkedIn": {"proxycurl": bool(os.getenv("PROXYCURL_API_KEY", "").strip())},
    }


def get_ai_usage_snapshot() -> dict:
    providers = ai_providers_configured()
    return {
        "ok": True,
        "openai": {
            "configured": providers["openai"],
            "label": "OpenAI",
            "today": {"requests": 0, "totalTokens": 0},
        },
        "gemini": {
            "configured": providers["gemini"],
            "label": "Gemini",
            "today": {"requests": 0, "totalTokens": 0},
        },
        "note": "Usage totals are tracked on the API provider dashboards.",
    }


def _prepare_user_context(user: dict[str, Any]) -> tuple[str, list[str], list[dict[str, Any]]]:
    from app.services.website_preview import (
        build_source_brief,
        extract_urls_from_profile,
        fetch_all_url_previews,
        public_url_previews,
        trim_for_llm,
    )

    urls = extract_urls_from_profile(user)
    url_previews = fetch_all_url_previews(urls)
    source_brief = trim_for_llm(build_source_brief(user, url_previews))
    return source_brief, urls, public_url_previews(url_previews)


def _call_openai(system: str, user_msg: str, max_tokens: int = 2400, *, temperature: float = 0.4) -> str:
    s = get_settings()
    api_key = (s.openai_api_key or "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set on the server.")
    model = (s.openai_model or "gpt-4o-mini").strip()
    with httpx.Client(timeout=120.0) as client:
        res = client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )
    res.raise_for_status()
    data = res.json()
    return (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()


def _call_gemini(system: str, user_msg: str, max_tokens: int = 2400, *, temperature: float = 0.4) -> str:
    s = get_settings()
    api_key = (s.gemini_api_key or "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set on the server.")
    model = (s.gemini_model or "gemini-2.0-flash").strip()
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    with httpx.Client(timeout=120.0) as client:
        res = client.post(
            url,
            json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user_msg}]}],
                "generationConfig": {
                    "maxOutputTokens": max_tokens,
                    "temperature": temperature,
                },
            },
        )
    res.raise_for_status()
    data = res.json()
    parts = (
        (data.get("candidates") or [{}])[0]
        .get("content", {})
        .get("parts", [])
    )
    return "".join(p.get("text", "") for p in parts).strip()


def _call_llm(
    provider: str,
    system: str,
    user_msg: str,
    max_tokens: int = 2400,
    *,
    owner_ip: str | None = None,
    temperature: float = 0.4,
) -> tuple[str, str, bool]:
    s = get_settings()
    has_openai = bool((s.openai_api_key or "").strip())
    p = "openai" if provider == "openai" else "gemini"
    if p == "gemini":
        try:
            return _call_gemini(system, user_msg, max_tokens, temperature=temperature), "gemini", False
        except Exception as err:
            if has_openai and _should_fallback(err):
                return _call_openai(system, user_msg, max_tokens, temperature=temperature), "openai", True
            raise
    return _call_openai(system, user_msg, max_tokens, temperature=temperature), "openai", False


def call_llm_json(
    system: str,
    user_msg: str,
    *,
    provider: str = "gemini",
    max_tokens: int = 4096,
    temperature: float = 0.1,
    owner_ip: str | None = None,
) -> tuple[list[Any], str]:
    """Call LLM and parse a JSON array response."""
    import json
    import re

    raw, used_provider, _ = _call_llm(
        provider,
        system,
        user_msg,
        max_tokens,
        owner_ip=owner_ip,
        temperature=temperature,
    )
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    parsed = json.loads(text)
    if not isinstance(parsed, list):
        raise ValueError("LLM response is not a JSON array")
    return parsed, used_provider


def _should_fallback(err: Exception) -> bool:
    msg = str(err).lower()
    return "quota" in msg or "429" in msg or "resource_exhausted" in msg


def analyze_user_with_ai(
    user: dict[str, Any],
    provider: str = "gemini",
    *,
    owner_ip: str | None = None,
) -> dict:
    if provider == "openai" and not ai_providers_configured()["openai"]:
        raise ValueError("OPENAI_API_KEY is not set on the server.")
    source_brief, urls_checked, url_previews = _prepare_user_context(user)
    system = (
        "You are an expert analyst helping outreach teams understand GitHub contacts. "
        "Use ALL profile data below, including extracted text from websites the user linked "
        "(direct site visits). Prioritize LinkedIn sections when present. "
        "Respond in clear English with these sections (## headings):\n"
        "## Summary\n## Who they are\n## Online presence\n"
        "## Key signals\n## Suggested outreach angle\n"
        "Be factual. Do not invent details. If a site could not be loaded, use GitHub and "
        "other available data only."
    )
    text, used, fallback = _call_llm(
        provider,
        system,
        f"Analyze this contact:\n\n{source_brief}",
        2400,
        owner_ip=owner_ip,
    )
    if not text:
        raise ValueError("AI returned an empty analysis.")
    return {
        "ok": True,
        "provider": used,
        "providerFallback": fallback,
        "sourceBrief": source_brief,
        "analysis": text,
        "urlsChecked": urls_checked,
        "urlPreviews": url_previews,
    }


def generate_outreach_letter(
    user: dict[str, Any],
    provider: str = "gemini",
    *,
    analysis: str | None = None,
    owner_ip: str | None = None,
) -> dict:
    if provider == "openai" and not ai_providers_configured()["openai"]:
        raise ValueError("OPENAI_API_KEY is not set on the server.")
    source_brief, urls_checked, url_previews = _prepare_user_context(user)
    prior = f"\n\nPrior analysis:\n{analysis[:4000]}" if analysis else ""
    system = (
        "You write concise, professional outreach emails to developers. "
        "Tone: respectful, specific, not salesy. Avoid spam triggers (no ALL CAPS, "
        "no fake urgency, no suspicious links). Format:\n"
        "Subject: <one line>\n---\n<email body, 3-4 short paragraphs, under 220 words>"
    )
    text, used, fallback = _call_llm(
        provider,
        system,
        f"Write the best outreach email for this contact:\n\n{source_brief}{prior}",
        2200,
        owner_ip=owner_ip,
    )
    if not text:
        raise ValueError("AI returned an empty letter.")
    return {
        "ok": True,
        "provider": used,
        "providerFallback": fallback,
        "letter": text,
        "sourceBrief": source_brief,
        "urlsChecked": urls_checked,
        "urlPreviews": url_previews,
    }
