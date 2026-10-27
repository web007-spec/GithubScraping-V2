"""Batch web search for discovering public Google Drive folder/file URLs."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Callable

from loguru import logger

from app.crawler.search_backends import search_all_backends
from app.settings import Settings, get_settings
from app.utils.drive_ids import is_valid_drive_id
from app.utils.drive_urls import extract_resource

ProgressFn = Callable[[int], None]


class BatchSearchService:
    """Run many search queries concurrently to discover Drive URLs."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def discover(
        self,
        queries: list[str],
        *,
        target: int = 500,
        results_per_query: int = 50,
        output: Path | None = None,
        resume: bool = True,
        on_progress: ProgressFn | None = None,
    ) -> list[str]:
        output = output or self._settings.discovered_urls_file
        seen_ids = self._load_existing_ids(output) if resume else set()
        discovered: list[str] = []
        initial_count = len(seen_ids)

        if initial_count >= target:
            logger.info(
                "Catalog already has {} URLs (goal {}). Skipping batch search.",
                initial_count,
                target,
            )
            if on_progress:
                on_progress(initial_count)
            return self._load_urls(output)

        if seen_ids:
            logger.info(
                "Resuming with {} URLs in {}; discovering up to {} total",
                len(seen_ids),
                output,
                target,
            )

        semaphore = asyncio.Semaphore(self._settings.search_concurrency)
        lock = asyncio.Lock()
        query_count = 0

        async def run_query(raw_query: str) -> None:
            nonlocal query_count
            async with semaphore:
                if len(seen_ids) >= target:
                    return

                query = raw_query.strip()
                if not query:
                    return

                urls = await search_all_backends(
                    query,
                    max_results=results_per_query,
                    settings=self._settings,
                )

                new_urls: list[str] = []
                async with lock:
                    for url in urls:
                        if len(seen_ids) >= target:
                            break
                        resource = extract_resource(url)
                        if not resource or not is_valid_drive_id(resource.resource_id):
                            continue
                        seen_ids.add(resource.resource_id)
                        discovered.append(resource.url)
                        new_urls.append(resource.url)

                    query_count += 1
                    if new_urls:
                        self._append_urls(output, new_urls)
                        logger.info(
                            "Query {} (+{} new, total {}/{}): {}",
                            query_count,
                            len(new_urls),
                            len(seen_ids),
                            target,
                            raw_query[:50],
                        )
                    else:
                        logger.debug("Query {} (0 new): {}", query_count, raw_query[:50])

                    if on_progress:
                        on_progress(len(seen_ids))

        await asyncio.gather(*(run_query(q) for q in queries))

        logger.info(
            "Batch search complete: {} new URLs this run ({} total in catalog, goal {})",
            len(discovered),
            len(seen_ids),
            target,
        )
        return self._load_urls(output)

    @staticmethod
    def load_queries(path: Path) -> list[str]:
        if not path.exists():
            logger.warning("Query file not found: {}", path)
            return []
        queries: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                queries.append(line)
        logger.info("Loaded {} search queries from {}", len(queries), path)
        return queries

    @staticmethod
    def _load_existing_ids(path: Path) -> set[str]:
        ids: set[str] = set()
        if not path.exists():
            return ids
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            resource = extract_resource(line)
            if resource:
                ids.add(resource.resource_id)
        return ids

    @staticmethod
    def _load_urls(path: Path) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        if not path.exists():
            return urls
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            resource = extract_resource(line)
            if resource and resource.resource_id not in seen:
                seen.add(resource.resource_id)
                urls.append(resource.url)
        return urls

    @staticmethod
    def _append_urls(path: Path, urls: list[str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            for url in urls:
                handle.write(url + "\n")
