from __future__ import annotations

from pathlib import Path

from app.crawler.parser import ExtractionResult


def extract_csv(path: Path) -> ExtractionResult:
    try:
        import pandas as pd
    except ImportError:
        return ExtractionResult(raw_text=path.read_text(encoding="utf-8", errors="replace")[:200_000], word_count=0)

    frame = pd.read_csv(path, dtype=str, nrows=5000)
    raw = frame.fillna("").to_csv(index=False)
    return ExtractionResult(raw_text=raw[:500_000], word_count=len(raw.split()))
