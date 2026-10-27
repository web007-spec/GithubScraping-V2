"""Tests for drive category matching."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from google_drive_db.categories import file_matches_categories  # noqa: E402


def test_unknown_type_allowed_until_download() -> None:
    assert file_matches_categories(
        mime_type="",
        extension="",
        selected=["pdfs"],
        name="document",
    )


def test_pdf_matches_pdf_category() -> None:
    assert file_matches_categories(
        mime_type="application/pdf",
        extension="pdf",
        selected=["pdfs"],
    )
    assert not file_matches_categories(
        mime_type="application/pdf",
        extension="pdf",
        selected=["images"],
    )
