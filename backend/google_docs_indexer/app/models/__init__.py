"""Database models."""

from app.models.base import Base
from app.models.crawl_log import CrawlLog
from app.models.document import Document, DocumentStatus
from app.models.image import Image
from app.models.link import Link
from app.models.statistics import Statistics

__all__ = [
    "Base",
    "CrawlLog",
    "Document",
    "DocumentStatus",
    "Image",
    "Link",
    "Statistics",
]
