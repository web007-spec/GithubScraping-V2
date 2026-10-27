"""Save mobilebasic HTML for manual inspection."""
import sys
from pathlib import Path

import httpx

doc = sys.argv[1]
out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(f"data/sample_{doc[:12]}.html")
r = httpx.get(
    f"https://docs.google.com/document/d/{doc}/mobilebasic",
    timeout=60,
    headers={"User-Agent": "Mozilla/5.0"},
)
out.write_text(r.text, encoding="utf-8")
print("wrote", out, "len", len(r.text))
