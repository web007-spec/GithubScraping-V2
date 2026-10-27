"""Fetch and extract text from profile URLs (blog, website, LinkedIn) for AI analysis."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.parse import urlparse

import httpx

URL_FETCH_TIMEOUT_S = 10.0
MAX_URLS = 4
MAX_HTML_READ_CHARS = 120_000
MAX_SNIPPET_CHARS = 3500
MAX_LINKEDIN_CHARS = 5000
MAX_LLM_INPUT_CHARS = 14_000
URL_IN_TEXT = re.compile(r'https?://[^\s<>"\')\]]+', re.I)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

NOISE_PATTERNS = [
    re.compile(r"^Accept all cookies.*$", re.I | re.M),
    re.compile(r"^This website uses cookies.*$", re.I | re.M),
    re.compile(r"^Sign in to LinkedIn.*$", re.I | re.M),
    re.compile(r"^Skip to (main )?content.*$", re.I | re.M),
    re.compile(r"^Enable JavaScript.*$", re.I | re.M),
    re.compile(r"^Privacy Policy.*$", re.I | re.M),
]


def normalize_url(raw: Any) -> str | None:
    s = str(raw or "").strip()
    if not s:
        return None
    if re.match(r"^https?://", s, re.I):
        return s
    if re.match(r"^[\w.-]+\.[a-z]{2,}", s, re.I):
        return f"https://{s}"
    return None


def normalize_linkedin_url(raw: Any) -> str | None:
    s = str(raw or "").strip()
    if "linkedin.com" not in s.lower():
        return None
    if not re.match(r"^https?://", s, re.I):
        s = f"https://{s.lstrip('/')}"
    try:
        parsed = urlparse(s)
        path = parsed.path.rstrip("/")
        if not re.search(r"/in/[^/]+", path, re.I):
            return None
        return f"https://www.linkedin.com{path}"
    except Exception:
        return None


def extract_urls_from_profile(user: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()

    def add(raw: Any, *, linkedin_only: bool = False) -> None:
        if linkedin_only:
            u = normalize_linkedin_url(raw)
        else:
            u = normalize_url(raw)
            if u and "linkedin.com" in u.lower():
                return
        if u and u.lower() not in seen:
            seen.add(u.lower())
            urls.append(u)

    for field in ("linkedin", "blog", "website"):
        if field == "linkedin":
            add(user.get(field), linkedin_only=True)
        else:
            add(user.get(field))

    text = "\n".join(
        str(user.get(k) or "")
        for k in ("bio", "description", "company", "location", "notes")
        if user.get(k)
    )
    for match in URL_IN_TEXT.findall(text):
        clean = match.rstrip(".,;:!?)")
        if "github.com" in clean.lower():
            continue
        if "linkedin.com/in/" in clean.lower():
            add(clean, linkedin_only=True)
        else:
            add(clean)

    slug = re.search(r"linkedin\.com/in/[a-zA-Z0-9_-]+", text, re.I)
    if slug:
        add(f"https://www.{slug.group(0).lstrip('/')}", linkedin_only=True)

    return urls[:MAX_URLS]


def html_to_plain_text(html: str) -> str:
    t = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    t = re.sub(r"<style[\s\S]*?</style>", " ", t, flags=re.I)
    t = re.sub(r"<noscript[\s\S]*?</noscript>", " ", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def extract_meta_from_html(html: str) -> str:
    parts: list[str] = []

    def pick(pattern: str) -> str | None:
        m = re.search(pattern, html, re.I)
        return m.group(1).strip() if m else None

    og_title = pick(r'property=["\']og:title["\'][^>]*content=["\']([^"\']+)')
    og_desc = pick(r'property=["\']og:description["\'][^>]*content=["\']([^"\']+)')
    meta_desc = pick(r'name=["\']description["\'][^>]*content=["\']([^"\']+)')
    if og_title:
        parts.append(f"Title: {og_title}")
    if og_desc:
        parts.append(f"Description: {og_desc}")
    elif meta_desc:
        parts.append(f"Description: {meta_desc}")
    return "\n".join(parts)


def optimize_extracted_text(text: str, url: str = "") -> str:
    t = str(text or "").replace("\r\n", "\n")
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    for pat in NOISE_PATTERNS:
        t = pat.sub("", t)
    lines = [ln.strip() for ln in t.split("\n") if len(ln.strip()) > 2]
    seen: set[str] = set()
    unique: list[str] = []
    for line in lines:
        key = line.lower()[:120]
        if key in seen:
            continue
        seen.add(key)
        unique.append(line)
    max_len = MAX_LINKEDIN_CHARS if "linkedin.com" in url.lower() else MAX_SNIPPET_CHARS
    return "\n".join(unique)[:max_len]


def fetch_direct(url: str) -> dict[str, Any]:
    try:
        with httpx.Client(
            timeout=URL_FETCH_TIMEOUT_S,
            follow_redirects=True,
            headers=BROWSER_HEADERS,
        ) as client:
            res = client.get(url)
    except Exception as exc:
        return {
            "url": url,
            "ok": False,
            "error": str(exc) or "Could not connect to site",
            "snippet": "",
            "source": "direct",
        }

    content_type = res.headers.get("content-type", "")
    title = ""
    snippet = ""

    try:
        if "text/html" in content_type:
            html = res.text
            if len(html) > MAX_HTML_READ_CHARS:
                html = html[:MAX_HTML_READ_CHARS]
            title_m = re.search(r"<title[^>]*>([^<]*)</title>", html, re.I)
            title = title_m.group(1).strip() if title_m else ""
            meta = extract_meta_from_html(html)
            plain = html_to_plain_text(html)
            snippet = optimize_extracted_text(
                "\n\n".join(x for x in (meta, plain) if x), url
            )
        else:
            snippet = f"(Non-HTML: {content_type or 'unknown'})"
    except Exception as exc:
        return {
            "url": url,
            "ok": False,
            "status": res.status_code,
            "error": str(exc) or "Failed to read page body",
            "snippet": "",
            "source": "direct",
        }

    return {
        "url": url,
        "ok": res.is_success and bool(snippet),
        "status": res.status_code,
        "title": title,
        "snippet": snippet or "(No readable text extracted)",
        "source": "direct",
        "linkedInFull": "linkedin.com" in url.lower()
        and len(snippet) > 250
        and res.status_code != 999,
    }


def fetch_all_url_previews(urls: list[str]) -> list[dict[str, Any]]:
    if not urls:
        return []
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(4, len(urls))) as pool:
        futures = {pool.submit(fetch_direct, u): u for u in urls}
        for fut in as_completed(futures):
            try:
                results.append(fut.result())
            except Exception as exc:
                url = futures[fut]
                results.append(
                    {
                        "url": url,
                        "ok": False,
                        "error": str(exc) or "Fetch failed",
                        "snippet": "",
                        "source": "error",
                    }
                )
    order = {u: i for i, u in enumerate(urls)}
    results.sort(key=lambda r: order.get(r.get("url", ""), 999))
    return results


def trim_for_llm(text: str, max_chars: int = MAX_LLM_INPUT_CHARS) -> str:
    s = str(text or "")
    if len(s) <= max_chars:
        return s
    return f"{s[:max_chars]}\n\n[...trimmed for API size limits...]"


def build_source_brief(user: dict[str, Any], url_previews: list[dict[str, Any]] | None = None) -> str:
    lines: list[str] = []
    name = user.get("name") or user.get("login") or "Unknown"
    lines.append(f"Name: {name}")
    if user.get("login"):
        lines.append(f"GitHub: @{user['login']}")
    if user.get("html_url"):
        lines.append(f"Profile: {user['html_url']}")
    if user.get("company"):
        lines.append(f"Company: {user['company']}")
    loc = user.get("location") or user.get("country")
    if loc:
        lines.append(f"Location: {loc}")
    if user.get("bio") or user.get("description"):
        lines.append(f"Bio: {user.get('bio') or user.get('description')}")

    emails: list[str] = []
    if user.get("email"):
        emails.append(str(user["email"]))
    for e in user.get("allEmails") or []:
        if e and str(e) not in emails:
            emails.append(str(e))
    if emails:
        lines.append(f"Emails: {', '.join(emails)}")
    if user.get("blog") or user.get("website"):
        lines.append(
            f"Links: {' · '.join(x for x in (user.get('blog'), user.get('website')) if x)}"
        )
    if user.get("twitter"):
        lines.append(f"Twitter: {user['twitter']}")
    if user.get("followers") is not None:
        lines.append(f"Followers: {user['followers']}")
    if user.get("githubCreatedAt"):
        lines.append(f"GitHub joined: {user['githubCreatedAt']}")

    previews = url_previews or []
    linkedin = [p for p in previews if "linkedin.com" in str(p.get("url", "")).lower()]
    other = [p for p in previews if p not in linkedin]

    if linkedin:
        lines.append("")
        lines.append("— LinkedIn profile (site visit) —")
        for p in linkedin:
            lines.append(f"\n[{p.get('url')}]")
            if p.get("title"):
                lines.append(f"Title: {p['title']}")
            if p.get("error"):
                lines.append(f"Note: {p['error']}")
            elif not p.get("ok"):
                lines.append(f"Note: HTTP {p.get('status', '?')}")
            if p.get("snippet"):
                lines.append(str(p["snippet"])[:MAX_LINKEDIN_CHARS])

    if other:
        lines.append("")
        lines.append("— Website previews (site visit) —")
        for p in other:
            lines.append(f"\n[{p.get('url')}]")
            if p.get("title"):
                lines.append(f"Title: {p['title']}")
            if p.get("error"):
                lines.append(f"Note: {p['error']}")
            elif not p.get("ok"):
                lines.append(f"Note: HTTP {p.get('status', '?')}")
            if p.get("snippet"):
                lines.append(str(p["snippet"])[:1200])

    return "\n".join(lines)


def public_url_previews(previews: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "url": p.get("url"),
            "ok": p.get("ok"),
            "status": p.get("status"),
            "title": p.get("title"),
            "error": p.get("error"),
            "source": p.get("source"),
            "linkedInFull": bool(p.get("linkedInFull")),
        }
        for p in previews
    ]
