"""Shared MongoDB storage for Google Docs (used by API and crawl worker)."""

from google_docs_db.client import ensure_indexes, get_database, ping
from google_docs_db import crawl_runs, documents

__all__ = ["crawl_runs", "documents", "ensure_indexes", "get_database", "ping"]
