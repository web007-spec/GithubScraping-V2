"""Audit shared_by_email coverage and probe pages without emails."""
import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT.parent
import sys as _sys

_sys.path[:0] = [str(ROOT), str(BACKEND)]

from google_docs_db.client import get_database

email_re = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
mailto_re = re.compile(r"mailto:[^\"'\s>]+", re.I)


def main() -> None:
    db = get_database()
    parsed = db.google_documents.count_documents({"status": "parsed"})
    with_email = db.google_documents.count_documents(
        {"status": "parsed", "shared_by_email": {"$nin": [None, ""]}}
    )
    print(f"parsed={parsed} with_email={with_email} missing={parsed - with_email}")

    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    cursor = db.google_documents.find(
        {"status": "parsed", "$or": [{"shared_by_email": None}, {"shared_by_email": ""}]},
        {"google_doc_id": 1, "clean_text": 1},
    ).limit(limit)

    for row in cursor:
        doc = row["google_doc_id"]
        text_content = (row.get("clean_text") or "")[:8000]
        content_emails = email_re.findall(text_content)
        r = httpx.get(
            f"https://docs.google.com/document/d/{doc}/mobilebasic",
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        page_emails = email_re.findall(r.text)
        mailtos = mailto_re.findall(r.text)
        print(f"\n{doc}")
        print("  content_emails:", content_emails[:5])
        print("  page_emails:", page_emails[:5])
        print("  mailtos:", mailtos[:3])


if __name__ == "__main__":
    main()
