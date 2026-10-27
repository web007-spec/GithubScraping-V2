"""Probe Google Doc pages for owner/sharer email patterns."""
import re
import sys

import httpx

doc_id = sys.argv[1] if len(sys.argv) > 1 else "1UcZq2YU5LA_YudaRj9mht5N93EeiV_pzmgx-XfTU-pA"
urls = [
    f"https://docs.google.com/document/d/{doc_id}/mobilebasic",
    f"https://docs.google.com/document/d/{doc_id}/pub",
    f"https://docs.google.com/document/d/{doc_id}/edit",
    f"https://docs.google.com/document/d/{doc_id}/export?format=html",
]
ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
email_re = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

for url in urls:
    try:
        r = httpx.get(url, follow_redirects=True, timeout=30, headers={"User-Agent": ua})
        text = r.text
        emails = email_re.findall(text)
        print(f"\n=== {url} status={r.status_code} len={len(text)} ===")
        print("emails:", emails[:15])
        for pat in ("owner", "shared", "published", "mailto", "creator", "author", "emailAddress"):
            if pat.lower() in text.lower():
                print("contains:", pat)
        for m in re.finditer(r"mailto:[^\"'\s>]+", text):
            print("mailto:", m.group()[:120])
        for m in re.finditer(r"<meta[^>]+(?:author|creator|email)[^>]*>", text, re.I):
            print("meta:", m.group()[:200])
        for m in re.finditer(r"\"email\"\s*:\s*\"([^\"@]+@[^\"]+)\"", text):
            print("json email:", m.group(1))
        for m in re.finditer(r"\"(?:owner|creator|author)(?:Email|Name)?\"\s*:\s*\"([^\"]{3,120})\"", text, re.I):
            print("json owner:", m.group(0)[:120])
        # Google bootstrap data
        for m in re.finditer(r"AF_initDataCallback\(\{key:\s*'([^']+)'", text):
            print("AF key:", m.group(1))
        for key in (
            "WIZ_global_data",
            "docs-flag",
            "docs-ml",
            "userEmail",
            "userId",
            "creator",
            "ownerId",
            "publishedUser",
            "lastModifiedBy",
            "collaborator",
        ):
            if key in text:
                idx = text.find(key)
                print(f"found {key}:", repr(text[idx : idx + 300]))
    except Exception as exc:
        print("ERR", url, exc)
