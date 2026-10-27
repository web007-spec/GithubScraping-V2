"""Test public content fetch strategies."""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.settings import get_settings
from app.utils.http import RateLimitedSession

# Known public Google Doc (resume template style)
DOC_ID = "1lL3W8X9Y2Z_example"  # placeholder - will read from file


async def try_exports(session, fid: str, label: str) -> None:
    urls = [
        ("doc-html", f"https://docs.google.com/document/d/{fid}/export?format=html"),
        ("doc-txt", f"https://docs.google.com/document/d/{fid}/export?format=txt"),
        ("sheet-csv", f"https://docs.google.com/spreadsheets/d/{fid}/export?format=csv"),
        ("slide-txt", f"https://docs.google.com/presentation/d/{fid}/export?format=txt"),
        ("view", f"https://drive.google.com/file/d/{fid}/view"),
    ]
    print(f"\n=== {label} {fid} ===")
    for name, url in urls:
        try:
            st, text = await session.get_text(url)
            login = "sign in" in text.lower() and "accounts.google.com" in text.lower()
            print(name, st, len(text), "LOGIN" if login else "OK", text[:60].replace("\n", " "))
        except Exception as exc:
            print(name, "ERR", exc)


async def main() -> None:
    settings = get_settings()
    async with RateLimitedSession(settings) as session:
        # Real file from folder scan
        await try_exports(session, "0B7jrEyvkmdl3WjhTREFMOGFGYWc", "folder-file")
        # Read a docs URL id from docs discovered if exists
        docs_file = ROOT.parent / "google_docs_indexer" / "data" / "discovered_urls.txt"
        if docs_file.exists():
            for line in docs_file.read_text(encoding="utf-8").splitlines()[:3]:
                line = line.strip()
                if "document/d/" in line:
                    fid = line.split("/document/d/")[1].split("/")[0]
                    await try_exports(session, fid, "docs-discovered")
                    break


if __name__ == "__main__":
    asyncio.run(main())
