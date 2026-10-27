"""Tests for metadata_extractor email ranking."""

from app.parser.metadata_extractor import (
    extract_document_metadata,
    is_placeholder_email,
)


def test_rejects_placeholder_emails() -> None:
    assert is_placeholder_email("no_reply@example.com")
    assert is_placeholder_email("name@email.com")
    assert not is_placeholder_email("contact@acme.org")


def test_prefers_mailto_over_template_content() -> None:
    meta = extract_document_metadata(
        export_html='<a href="mailto:real.owner@gmail.com">Email</a>',
        clean_text="Name\nno_reply@example.com\nMore text",
    )
    assert meta.shared_by_email == "real.owner@gmail.com"


def test_picks_best_content_email_when_no_mailto() -> None:
    meta = extract_document_metadata(
        clean_text="Contact Jane at jane@onecommunityglobal.org for details.",
    )
    assert meta.shared_by_email == "jane@onecommunityglobal.org"
