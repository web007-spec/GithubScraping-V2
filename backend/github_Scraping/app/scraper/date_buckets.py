"""Build GitHub `created:` search buckets from a join-date range."""

from __future__ import annotations

from datetime import date, datetime


def build_date_buckets_from_range(
    start: str,
    end: str,
    years_per_chunk: int = 3,
) -> list[str]:
    """
    Split [start, end] into chunks for GitHub search (max ~1000 results per query).
    Example: 2014-01-01..2025-12-31 → multiple 3-year buckets.
    """
    start_date = datetime.strptime(start[:10], "%Y-%m-%d").date()
    end_date = datetime.strptime(end[:10], "%Y-%m-%d").date()
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    buckets: list[str] = []
    year = start_date.year
    while year <= end_date.year:
        chunk_start = date(year, 1, 1)
        if chunk_start < start_date:
            chunk_start = start_date
        chunk_end_year = min(year + years_per_chunk - 1, end_date.year)
        chunk_end = date(chunk_end_year, 12, 31)
        if chunk_end > end_date:
            chunk_end = end_date
        if chunk_start <= chunk_end:
            buckets.append(f"{chunk_start.isoformat()}..{chunk_end.isoformat()}")
        year += years_per_chunk

    if not buckets:
        buckets.append(f"{start_date.isoformat()}..{end_date.isoformat()}")
    return buckets
