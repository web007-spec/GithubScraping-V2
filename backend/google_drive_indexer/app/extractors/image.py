from __future__ import annotations

from pathlib import Path

from app.crawler.parser import ExtractionResult


def extract_image_meta(path: Path) -> ExtractionResult:
    try:
        from PIL import Image
    except ImportError:
        return ExtractionResult(raw_text=path.name, word_count=0)

    with Image.open(path) as img:
        meta = f"{path.name} {img.format} {img.size[0]}x{img.size[1]}"
    return ExtractionResult(raw_text=meta, word_count=len(meta.split()))
