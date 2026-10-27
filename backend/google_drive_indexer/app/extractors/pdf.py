from __future__ import annotations

from pathlib import Path

from app.crawler.parser import ExtractionResult


def extract_pdf(path: Path) -> ExtractionResult:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return ExtractionResult(raw_text="", word_count=0)

    text_parts: list[str] = []
    pages = 0
    with fitz.open(path) as doc:
        pages = doc.page_count
        for page in doc:
            text_parts.append(page.get_text())
    raw = "\n".join(text_parts).strip()
    words = len(raw.split())
    return ExtractionResult(raw_text=raw[:500_000], word_count=words, page_count=pages)
