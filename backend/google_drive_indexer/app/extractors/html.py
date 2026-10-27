from __future__ import annotations

from pathlib import Path

from app.crawler.parser import ExtractionResult


def extract_html(path: Path) -> ExtractionResult:
    from bs4 import BeautifulSoup

    html = path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html, "lxml")
    raw = soup.get_text("\n", strip=True)
    return ExtractionResult(raw_text=raw[:500_000], word_count=len(raw.split()))
