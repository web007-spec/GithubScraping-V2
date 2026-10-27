from __future__ import annotations

from pathlib import Path

from app.crawler.parser import ExtractionResult


def extract_txt(path: Path) -> ExtractionResult:
    raw = path.read_text(encoding="utf-8", errors="replace").strip()
    return ExtractionResult(raw_text=raw[:500_000], word_count=len(raw.split()))
