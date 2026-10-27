from __future__ import annotations

from pathlib import Path

from app.crawler.parser import ExtractionResult


def extract_docx(path: Path) -> ExtractionResult:
    try:
        from docx import Document
    except ImportError:
        return ExtractionResult(raw_text="", word_count=0)

    doc = Document(str(path))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    raw = "\n".join(parts).strip()
    return ExtractionResult(raw_text=raw[:500_000], word_count=len(raw.split()))
