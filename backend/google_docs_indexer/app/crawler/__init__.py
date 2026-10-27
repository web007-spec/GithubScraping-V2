"""Crawler package."""

from app.crawler.discovery import (
    DiscoveryService,
    DiscoverySource,
    InMemoryDiscoverySource,
    SearchApiDiscoverySource,
    UrlListDiscoverySource,
)
from app.crawler.search_discovery import WebSearchDiscoverySource
from app.crawler.queue import CrawlQueue, CrawlTask, WorkerPool

__all__ = [
    "DiscoveryService",
    "DiscoverySource",
    "InMemoryDiscoverySource",
    "SearchApiDiscoverySource",
    "UrlListDiscoverySource",
    "WebSearchDiscoverySource",
    "CrawlQueue",
    "CrawlTask",
    "WorkerPool",
]
