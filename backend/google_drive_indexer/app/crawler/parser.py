"""Text extraction dispatcher."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExtractionResult:
    raw_text: str
    word_count: int
    page_count: int | None = None
    language: str | None = None


def extract_text(path: Path, mime_type: str) -> ExtractionResult:
    suffix = path.suffix.lower()
    mime = (mime_type or "").lower()

    if suffix == ".pdf" or mime == "application/pdf":
        from app.extractors.pdf import extract_pdf

        return extract_pdf(path)
    if suffix in {".docx"} or "wordprocessingml" in mime:
        from app.extractors.docx import extract_docx

        return extract_docx(path)
    if suffix in {".xlsx", ".xls"} or "spreadsheetml" in mime:
        from app.extractors.xlsx import extract_xlsx

        return extract_xlsx(path)
    if suffix == ".csv" or mime == "text/csv":
        from app.extractors.csv import extract_csv

        return extract_csv(path)
    if suffix in {".html", ".htm"} or mime == "text/html":
        from app.extractors.html import extract_html

        return extract_html(path)
    if suffix == ".txt" or mime.startswith("text/"):
        from app.extractors.txt import extract_txt

        return extract_txt(path)
    if mime.startswith("image/"):
        from app.extractors.image import extract_image_meta

        return extract_image_meta(path)

    return ExtractionResult(raw_text="", word_count=0)
