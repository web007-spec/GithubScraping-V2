"""URL utility tests."""

from app.utils.url_utils import (
    build_export_url,
    extract_google_doc_id,
    is_google_docs_url,
    normalize_google_docs_url,
)


def test_extract_doc_id_from_edit_url():
    url = "https://docs.google.com/document/d/1abcDEF123_xyz/edit"
    assert extract_google_doc_id(url) == "1abcDEF123_xyz"


def test_extract_doc_id_from_open_url():
    url = "https://docs.google.com/open?id=1abcDEF123_xyz"
    assert extract_google_doc_id(url) == "1abcDEF123_xyz"


def test_normalize_url():
    raw = "https://docs.google.com/document/d/abc123/edit?usp=sharing"
    normalized = normalize_google_docs_url(raw)
    assert normalized == "https://docs.google.com/document/d/abc123/edit"


def test_is_google_docs_url():
    assert is_google_docs_url("https://docs.google.com/document/d/abc/edit")
    assert not is_google_docs_url("https://example.com/doc")


def test_build_export_url():
    url = build_export_url("abc123", "html")
    assert url == "https://docs.google.com/document/d/abc123/export?format=html"
