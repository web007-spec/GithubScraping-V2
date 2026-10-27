"""Text cleaning utilities."""

import re
import unicodedata


def normalize_unicode(text: str) -> str:
    """Normalize Unicode to NFC form."""
    return unicodedata.normalize("NFC", text)


def collapse_whitespace(text: str) -> str:
    """Collapse runs of whitespace to single spaces."""
    return re.sub(r"[ \t]+", " ", text)


def remove_duplicate_blank_lines(text: str) -> str:
    """Reduce multiple consecutive blank lines to one."""
    return re.sub(r"\n{3,}", "\n\n", text)


def strip_html_tags(html: str) -> str:
    """Remove HTML tags with a simple regex (fallback)."""
    return re.sub(r"<[^>]+>", " ", html)


def clean_text(text: str) -> str:
    """
    Full cleaning pipeline for extracted text.

    - Normalize Unicode
    - Collapse whitespace
    - Remove duplicate blank lines
    - Strip leading/trailing whitespace per line
    """
    text = normalize_unicode(text)
    lines = [collapse_whitespace(line).strip() for line in text.splitlines()]
    text = "\n".join(lines)
    text = remove_duplicate_blank_lines(text)
    return text.strip()


def clean_html(html: str) -> str:
    """Remove unnecessary script/style blocks from HTML."""
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    return html.strip()
