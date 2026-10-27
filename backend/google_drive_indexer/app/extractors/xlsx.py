from __future__ import annotations

from pathlib import Path

from app.crawler.parser import ExtractionResult


def extract_xlsx(path: Path) -> ExtractionResult:
    try:
        import pandas as pd
    except ImportError:
        return ExtractionResult(raw_text="", word_count=0)

    frames = pd.read_excel(path, sheet_name=None, dtype=str)
    parts: list[str] = []
    for name, frame in frames.items():
        parts.append(f"## {name}")
        parts.append(frame.fillna("").to_csv(index=False))
    raw = "\n".join(parts).strip()
    return ExtractionResult(raw_text=raw[:500_000], word_count=len(raw.split()))
