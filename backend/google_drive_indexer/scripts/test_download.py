"""Quick download strategy probe — dev only."""
import asyncio
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.settings import get_settings
from app.utils.http import RateLimitedSession

FID = "0B7jrEyvkmdl3WjhTREFMOGFGYWc"


async def main() -> None:
    settings = get_settings()
    async with RateLimitedSession(settings) as session:
        view = f"https://drive.google.com/file/d/{FID}/view?usp=sharing"
        st, html = await session.get_text(view)
        print("view", st, len(html))
        for pat in [
            "mimeType",
            "application/pdf",
            "docs.google.com",
            "spreadsheets",
            "presentation",
            "confirm=",
            "downloadUrl",
        ]:
            print(pat, pat in html)
        for m in re.finditer(r"confirm=([0-9A-Za-z_-]+)", html):
            print("confirm token", m.group(1)[:40])
        doc_export = f"https://docs.google.com/document/d/{FID}/export?format=html"
        st2, html2 = await session.get_text(doc_export)
        print("doc export", st2, len(html2), "login" if "sign in" in html2.lower() else "ok")
        pdf_export = f"https://drive.google.com/uc?export=pdf&id={FID}"
        try:
            st3, data = await session.get_bytes(pdf_export, max_bytes=500000)
            print("pdf export", st3, len(data))
        except Exception as exc:
            print("pdf export err", exc)


if __name__ == "__main__":
    asyncio.run(main())
