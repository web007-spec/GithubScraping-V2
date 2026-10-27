"""CSV export utilities for local testing without a database."""

from __future__ import annotations

import csv
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger


CSV_FIELDS = [
    "google_doc_id",
    "url",
    "title",
    "excerpt",
    "clean_text",
    "search_text",
    "headings",
    "word_count",
    "character_count",
    "language",
    "sha256",
    "preview_url",
    "preview_image_url",
    "links_count",
    "images_count",
    "archive_json",
    "shared_by_email",
    "shared_by_name",
    "shared_at",
    "document_modified_at",
    "status",
    "error",
    "elapsed_ms",
    "crawled_at",
]

VALID_STATUSES = frozenset(
    {"discovered", "queued", "downloading", "parsed", "failed", "skipped", "duplicate", ""}
)

_DOC_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{20,}$")


@dataclass
class CsvRow:
    """Single crawled document row."""

    google_doc_id: str
    url: str
    title: str | None = None
    excerpt: str | None = None
    clean_text: str | None = None
    headings: str | None = None
    word_count: int | None = None
    character_count: int | None = None
    language: str | None = None
    sha256: str | None = None
    preview_url: str | None = None
    preview_image_url: str | None = None
    links_count: int = 0
    images_count: int = 0
    search_text: str | None = None
    archive_json: str | None = None
    shared_by_email: str | None = None
    shared_by_name: str | None = None
    shared_at: str | None = None
    document_modified_at: str | None = None
    status: str = "pending"
    error: str | None = None
    elapsed_ms: int | None = None
    crawled_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def _configure_csv_limits() -> None:
    try:
        csv.field_size_limit(sys.maxsize)
    except OverflowError:
        csv.field_size_limit(2**31 - 1)


def is_valid_doc_row(row: dict[str, str]) -> bool:
    doc_id = str(row.get("google_doc_id") or "").strip()
    url = str(row.get("url") or "").strip()
    status = str(row.get("status") or "").strip().lower()

    if not doc_id or not _DOC_ID_RE.match(doc_id):
        return False
    if "docs.google.com/document" not in url:
        return False
    if status.startswith("http"):
        return False
    if status and status not in VALID_STATUSES:
        return False
    return True


def read_csv_rows(path: Path, *, skip_invalid: bool = True) -> list[dict[str, str]]:
    """Read CSV results; skips corrupt legacy rows and handles large text fields."""
    if not path.exists():
        return []

    _configure_csv_limits()
    rows: list[dict[str, str]] = []
    skipped = 0

    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        reader = csv.DictReader(handle)
        index = 1
        while True:
            index += 1
            try:
                row = next(reader)
            except StopIteration:
                break
            except csv.Error as exc:
                skipped += 1
                logger.warning("Skipping corrupt CSV row {} in {}: {}", index, path.name, exc)
                continue

            if skip_invalid and not is_valid_doc_row(row):
                skipped += 1
                logger.debug("Skipping invalid CSV row {} in {}", index, path.name)
                continue
            rows.append(row)

    if skipped:
        logger.warning("Skipped {} invalid row(s) in {}", skipped, path.name)
    return rows


def repair_csv_file(path: Path) -> list[dict[str, str]]:
    """Rewrite CSV keeping only valid document rows (fixes legacy corrupt exports)."""
    if not path.exists():
        return []

    _configure_csv_limits()
    source = path
    backup = path.with_suffix(path.suffix + ".bak")

    rows: list[dict[str, str]] = []
    try:
        rows = read_csv_rows(path, skip_invalid=True)
    except csv.Error:
        rows = []

    if not rows and backup.is_file():
        source = backup
        try:
            rows = read_csv_rows(backup, skip_invalid=True)
        except csv.Error:
            rows = []

    if path.exists() and source == path:
        try:
            import shutil

            shutil.copy2(path, backup)
        except OSError:
            pass

    write_csv_dict_rows(rows, path)
    logger.info("Repaired CSV {} ({} valid rows)", path, len(rows))
    return rows


def write_csv_dict_rows(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})


def write_csv_rows(rows: list[CsvRow], output_path: Path) -> None:
    """Write crawl results to a CSV file."""
    write_csv_dict_rows([asdict(row) for row in rows], output_path)


def append_csv_row(row: CsvRow, output_path: Path) -> None:
    """Append a single row, writing header if file is new."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not output_path.exists() or output_path.stat().st_size == 0
    with output_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(asdict(row))
