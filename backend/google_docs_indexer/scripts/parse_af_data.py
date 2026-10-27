"""Search AF_initDataCallback blocks for emails."""
import re
import sys

import httpx

doc = sys.argv[1]
r = httpx.get(
    f"https://docs.google.com/document/d/{doc}/mobilebasic",
    timeout=60,
    headers={"User-Agent": "Mozilla/5.0"},
)
text = r.text
email_re = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
for m in re.finditer(r"AF_initDataCallback\(\{key:\s*'([^']+)'[^}]*data:(.*?)\}\);", text, re.S):
    key = m.group(1)
    block = m.group(2)[:50000]
    emails = email_re.findall(block)
    if emails:
        print(key, emails[:10])

# Also search WIZ_global_data
idx = text.find("WIZ_global_data")
if idx >= 0:
    chunk = text[idx : idx + 200000]
    emails = email_re.findall(chunk)
    print("WIZ emails", emails[:10])
