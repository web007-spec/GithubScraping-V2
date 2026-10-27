"""Parser tests."""

from app.parser.cleaner import clean_text
from app.parser.document_parser import DocumentParser


def test_parse_html(sample_html):
    parser = DocumentParser()
    result = parser.parse(sample_html)

    assert result.title == "Sample Document"
    assert "Main Heading" in result.headings
    assert len(result.paragraphs) >= 1
    assert len(result.links) == 1
    assert result.links[0][0] == "https://example.com"
    assert len(result.images) == 1
    assert len(result.lists) == 1
    assert len(result.tables) == 1
    assert result.word_count > 0
    assert result.character_count > 0


def test_parse_txt():
    parser = DocumentParser()
    text = "My Title\n\nParagraph one.\nParagraph two."
    result = parser.parse_txt(text)
    assert result.title == "My Title"
    assert result.word_count > 0


def test_clean_text():
    text = "Hello   world\n\n\n\nSecond line"
    cleaned = clean_text(text)
    assert "  " not in cleaned
    assert "\n\n\n" not in cleaned
