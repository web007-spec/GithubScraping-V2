"""Dump mobilebasic snippets around sharing/publish markers."""
import re
import sys
from pathlib import Path

import httpx

doc = sys.argv[1]
r = httpx.get(
    f"https://docs.google.com/document/d/{doc}/mobilebasic",
    timeout=60,
    headers={"User-Agent": "Mozilla/5.0"},
)
text = r.text
for pat in (
    "published",
    "Published",
    "shared by",
    "Shared by",
    "last edited",
    "Last edited",
    "owner",
    "creator",
    "collaborator",
    "email",
):
    for m in re.finditer(pat, text, re.I):
        start = max(0, m.start() - 120)
        end = min(len(text), m.end() + 200)
        snippet = text[start:end].replace("\n", " ")
        print(f"\n--- {pat} @ {m.start()} ---")
        print(snippet[:400])
