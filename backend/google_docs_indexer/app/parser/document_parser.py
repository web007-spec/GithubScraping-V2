"""HTML document parser using BeautifulSoup and selectolax."""

from dataclasses import dataclass, field

from bs4 import BeautifulSoup
from loguru import logger
from selectolax.parser import HTMLParser

from app.parser.cleaner import clean_html, clean_text

try:
    from langdetect import detect as langdetect_detect
    from langdetect.lang_detect_exception import LangDetectException

    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False


@dataclass
class ParsedDocument:
    """Structured parse result."""

    title: str | None = None
    body_text: str = ""
    clean_text: str = ""
    headings: list[str] = field(default_factory=list)
    paragraphs: list[str] = field(default_factory=list)
    lists: list[str] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)
    links: list[tuple[str, str | None]] = field(default_factory=list)
    images: list[tuple[str, str | None]] = field(default_factory=list)
    word_count: int = 0
    character_count: int = 0
    language: str | None = None
    html: str = ""


class DocumentParser:
    """Parse Google Docs HTML export."""

    def parse(self, html: str) -> ParsedDocument:
        """Parse HTML and extract structured content."""
        html = clean_html(html)
        title = _extract_title_fast(html)
        soup = BeautifulSoup(html, "html.parser")

        if not title:
            title = _extract_title(soup)
        headings = _extract_headings(soup)
        paragraphs = _extract_paragraphs(soup)
        lists = _extract_lists(soup)
        tables = _extract_tables(soup)
        links = _extract_links(soup)
        images = _extract_images(soup)

        body_text = soup.get_text(separator="\n", strip=True)
        cleaned = clean_text(body_text)
        word_count = len(cleaned.split()) if cleaned else 0
        character_count = len(cleaned)
        language = _detect_language(cleaned)

        return ParsedDocument(
            title=title,
            body_text=body_text,
            clean_text=cleaned,
            headings=headings,
            paragraphs=paragraphs,
            lists=lists,
            tables=tables,
            links=links,
            images=images,
            word_count=word_count,
            character_count=character_count,
            language=language,
            html=html,
        )

    def parse_txt(self, text: str) -> ParsedDocument:
        """Parse plain text export."""
        cleaned = clean_text(text)
        lines = [ln for ln in cleaned.splitlines() if ln.strip()]
        title = lines[0] if lines else None
        return ParsedDocument(
            title=title,
            body_text=text,
            clean_text=cleaned,
            paragraphs=lines,
            word_count=len(cleaned.split()) if cleaned else 0,
            character_count=len(cleaned),
            language=_detect_language(cleaned),
            html="",
        )


def _extract_title(soup: BeautifulSoup) -> str | None:
    """Extract title using selectolax fast path, then BeautifulSoup fallback."""
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    return None


def _extract_title_fast(html: str) -> str | None:
    """Fast title extraction with selectolax."""
    tree = HTMLParser(html)
    if tree.body is None:
        return None
    title_node = tree.css_first("title")
    if title_node and title_node.text():
        return title_node.text(strip=True)
    h1 = tree.css_first("h1")
    if h1 and h1.text():
        return h1.text(strip=True)
    return None


def _extract_headings(soup: BeautifulSoup) -> list[str]:
    headings: list[str] = []
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        text = tag.get_text(strip=True)
        if text:
            headings.append(text)
    return headings


def _extract_paragraphs(soup: BeautifulSoup) -> list[str]:
    paragraphs: list[str] = []
    for tag in soup.find_all("p"):
        text = tag.get_text(strip=True)
        if text:
            paragraphs.append(text)
    if not paragraphs:
        for tag in soup.find_all("div"):
            text = tag.get_text(strip=True)
            if text and len(text) > 20:
                paragraphs.append(text)
    return paragraphs


def _extract_lists(soup: BeautifulSoup) -> list[str]:
    lists: list[str] = []
    for tag in soup.find_all(["ul", "ol"]):
        items = [li.get_text(strip=True) for li in tag.find_all("li")]
        if items:
            lists.append("\n".join(f"- {item}" for item in items))
    return lists


def _extract_tables(soup: BeautifulSoup) -> list[str]:
    tables: list[str] = []
    for table in soup.find_all("table"):
        rows: list[str] = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if cells:
                rows.append(" | ".join(cells))
        if rows:
            tables.append("\n".join(rows))
    return tables


def _extract_links(soup: BeautifulSoup) -> list[tuple[str, str | None]]:
    links: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href in seen:
            continue
        seen.add(href)
        links.append((href, a.get_text(strip=True) or None))
    return links


def _extract_images(soup: BeautifulSoup) -> list[tuple[str, str | None]]:
    images: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for img in soup.find_all("img", src=True):
        src = img["src"].strip()
        if not src or src in seen:
            continue
        seen.add(src)
        images.append((src, img.get("alt")))
    return images


def _detect_language(text: str) -> str | None:
    if not text or len(text) < 20:
        return None
    if not HAS_LANGDETECT:
        return None
    try:
        return langdetect_detect(text[:5000])
    except LangDetectException:
        logger.debug("Language detection failed")
        return None
