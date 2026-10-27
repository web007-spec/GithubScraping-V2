"""Crawl public Google Docs and persist results directly to the database."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from loguru import logger

from app.config.settings import Settings, get_settings
from app.crawler.discovery import DiscoveryService, UrlListDiscoverySource
from app.crawler.queue import CrawlQueue, CrawlTask, WorkerPool
from app.crawler.search_discovery import WebSearchDiscoverySource
from app.downloader.document_downloader import DocumentDownloader
from app.parser.document_parser import DocumentParser
from app.parser.metadata_extractor import extract_document_metadata
from app.services.batch_search_service import BatchSearchService
from app.services.document_store import (
    ProgressCallback,
    is_db_storage_enabled,
    load_resume_state,
    persist_row,
    require_db_storage,
)
from app.utils.archive_payload import archive_json_dumps, build_archive_data, build_search_text
from app.utils.csv_writer import CsvRow
from app.utils.hashing import compute_sha256
from app.utils.preview_utils import build_excerpt, build_preview_url, first_image_url


@dataclass
class CrawlStats:
    crawled: int = 0
    parsed: int = 0
    failed: int = 0
    duplicate: int = 0
    skipped: int = 0

    def record(self, row: CsvRow) -> None:
        self.crawled += 1
        status = str(row.status or "").strip().lower()
        if status == "parsed":
            self.parsed += 1
        elif status == "failed":
            self.failed += 1
        elif status == "duplicate":
            self.duplicate += 1
        elif status == "skipped":
            self.skipped += 1


class CsvCrawlService:
    """Discover and crawl public Google Docs, saving each result to the database."""

    def __init__(
        self,
        settings: Settings | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._parser = DocumentParser()
        self._seen_hashes: set[str] = set()
        self._crawled_ids: set[str] = set()
        self._stats = CrawlStats()
        self._queue = CrawlQueue()
        self._pool = WorkerPool(self._settings.max_workers)
        self._on_progress = on_progress

    @property
    def stats(self) -> CrawlStats:
        return self._stats

    async def crawl_from_file(
        self,
        url_file: Path,
        resume: bool = False,
    ) -> CrawlStats:
        require_db_storage()
        self._init_crawl_state(resume)

        discovery = DiscoveryService([UrlListDiscoverySource(url_file)])
        discovered = await discovery.discover_urls()
        await self._crawl_discovered(discovered, url_file, resume=resume)
        return await self._crawl_uncrawled_from_catalog(url_file)

    async def crawl_from_discovered(
        self,
        url_file: Path | None = None,
        resume: bool = True,
    ) -> CrawlStats:
        url_file = url_file or self._settings.discovered_urls_file
        return await self.crawl_from_file(url_file, resume=resume)

    async def crawl_from_search(
        self,
        query: str,
        max_results: int | None = None,
        save_urls: Path | None = None,
        resume: bool = True,
        discovery_target: int | None = None,
    ) -> CrawlStats:
        require_db_storage()
        self._init_crawl_state(resume)
        limit = max_results or self._settings.search_max_results
        save_path = save_urls or self._settings.discovered_urls_file
        goal = max(int(discovery_target or 10_000), 100)

        search_source = WebSearchDiscoverySource(query, max_results=limit, settings=self._settings)
        logger.info("Searching: {} (up to {} results)", search_source.search_query, limit)

        discovery = DiscoveryService([search_source])
        discovered = await discovery.discover_urls()

        if discovered:
            self._append_discovered_urls(save_path, discovered, resume=resume)
            await self._crawl_discovered(discovered, f"search:{query}", resume=resume)
        else:
            logger.warning("No Google Docs found for search query: {}", query)

        catalog_size = len(BatchSearchService._load_existing_ids(save_path))
        if catalog_size < goal:
            queries = BatchSearchService.load_queries(self._settings.queries_file)
            if not queries:
                queries = BatchSearchService.generate_queries([query.strip()])
            logger.info(
                "Growing catalog from {} toward {} using {} queries",
                catalog_size,
                goal,
                len(queries),
            )
            batch = BatchSearchService(self._settings)
            batch_discovered = await batch.discover(
                queries,
                target=goal,
                results_per_query=limit,
                output=save_path,
                resume=True,
            )
            if batch_discovered:
                await self._crawl_discovered(batch_discovered, "batch-search", resume=resume)

        await self._crawl_uncrawled_from_catalog(save_path)

        if self._stats.crawled == 0:
            logger.warning(
                "No new documents crawled this run ({} already stored in database)",
                len(self._crawled_ids),
            )

        return self._stats

    async def crawl_from_batch_search(
        self,
        queries: list[str],
        target: int = 1000,
        discovered_file: Path | None = None,
        resume: bool = True,
        results_per_query: int | None = None,
    ) -> CrawlStats:
        require_db_storage()
        self._init_crawl_state(resume)

        discovered_path = discovered_file or self._settings.discovered_urls_file
        per_query = results_per_query or self._settings.search_max_results
        goal = max(int(target), 100)
        batch = BatchSearchService(self._settings)
        discovered = await batch.discover(
            queries,
            target=goal,
            results_per_query=per_query,
            output=discovered_path,
            resume=resume,
        )

        if discovered:
            await self._crawl_discovered(discovered, "batch-search", resume=resume)
        else:
            catalog_size = len(BatchSearchService._load_existing_ids(discovered_path))
            logger.warning(
                "Batch search found 0 new URLs (catalog has {}, goal {})",
                catalog_size,
                goal,
            )

        await self._crawl_uncrawled_from_catalog(discovered_path)

        if self._stats.crawled == 0:
            logger.warning(
                "No new documents crawled this run ({} already stored in database)",
                len(self._crawled_ids),
            )

        return self._stats

    def _init_crawl_state(self, resume: bool) -> None:
        if not is_db_storage_enabled():
            return
        if resume:
            self._crawled_ids, self._seen_hashes = load_resume_state()
            logger.info("Resume: skipping {} documents already in database", len(self._crawled_ids))

    async def _crawl_uncrawled_from_catalog(
        self,
        url_file: Path | None = None,
    ) -> CrawlStats:
        """Crawl URLs in the catalog file that are not yet stored in the database."""
        path = url_file or self._settings.discovered_urls_file
        if not path.is_file():
            return self._stats

        catalog_ids = BatchSearchService._load_existing_ids(path)
        pending_count = sum(1 for doc_id in catalog_ids if doc_id not in self._crawled_ids)
        if pending_count == 0:
            logger.info(
                "Catalog {} has {} URLs — all already in database",
                path,
                len(catalog_ids),
            )
            return self._stats

        logger.info(
            "Catalog sweep: {} of {} URLs in {} need crawling",
            pending_count,
            len(catalog_ids),
            path,
        )
        discovery = DiscoveryService([UrlListDiscoverySource(path)])
        discovered = await discovery.discover_urls()
        return await self._crawl_discovered(discovered, path, resume=True)

    @staticmethod
    def _append_discovered_urls(
        path: Path,
        discovered: list[tuple[str, str]],
        resume: bool = True,
    ) -> None:
        existing = BatchSearchService._load_existing_ids(path) if resume else set()
        new_urls = [url for doc_id, url in discovered if doc_id not in existing]
        if new_urls:
            BatchSearchService._append_urls(path, new_urls)
            logger.info("Saved {} new URLs to {} ({} total)", len(new_urls), path, len(existing) + len(new_urls))

    async def _crawl_discovered(
        self,
        discovered: list[tuple[str, str]],
        label: Path | str,
        resume: bool = False,
    ) -> CrawlStats:
        pending = [
            (doc_id, url)
            for doc_id, url in discovered
            if doc_id not in self._crawled_ids
        ]

        if not pending:
            logger.warning("No new URLs to crawl from {}", label)
            return self._stats

        logger.info(
            "Crawling {} documents ({} skipped as already in database)",
            len(pending),
            len(discovered) - len(pending),
        )

        tasks = [
            CrawlTask(document_id=doc_id, google_doc_id=doc_id, url=url)
            for doc_id, url in pending
        ]
        await self._queue.put_many(tasks)

        async with DocumentDownloader(self._settings) as downloader:
            await self._pool.start(
                lambda worker_id, q: self._worker(worker_id, q, downloader),
                self._queue,
            )
            await self._queue.join()
            await self._queue.shutdown(self._pool.num_workers)
            await self._pool.wait()

        logger.info(
            "Crawl complete: {} parsed, {} failed, {} duplicate, {} skipped",
            self._stats.parsed,
            self._stats.failed,
            self._stats.duplicate,
            self._stats.skipped,
        )
        return self._stats

    async def _worker(
        self,
        worker_id: int,
        queue: CrawlQueue,
        downloader: DocumentDownloader,
    ) -> None:
        while True:
            task = await queue.get()
            if task is None:
                queue.task_done()
                break
            try:
                row = await self._process(task, downloader)
                persist_row(row)
                self._stats.record(row)
                self._crawled_ids.add(task.google_doc_id)
                if self._on_progress:
                    self._on_progress(row)
            except Exception as exc:
                logger.exception("Worker {} failed on {}: {}", worker_id, task.url, exc)
                failed = CsvRow(
                    google_doc_id=task.google_doc_id,
                    url=task.url,
                    status="failed",
                    error=str(exc),
                )
                try:
                    persist_row(failed)
                    self._stats.record(failed)
                    self._crawled_ids.add(task.google_doc_id)
                    if self._on_progress:
                        self._on_progress(failed)
                except Exception:
                    logger.exception("Could not persist failure for {}", task.url)
            finally:
                queue.task_done()

    async def _process(self, task: CrawlTask, downloader: DocumentDownloader) -> CsvRow:
        result = await downloader.download(task.google_doc_id, fmt="html")

        if result.error or result.content is None:
            return CsvRow(
                google_doc_id=task.google_doc_id,
                url=task.url,
                status="failed",
                error=result.error,
                elapsed_ms=result.elapsed_ms,
            )

        if isinstance(result.content, bytes):
            return CsvRow(
                google_doc_id=task.google_doc_id,
                url=task.url,
                status="skipped",
                error="Binary content not indexed",
                elapsed_ms=result.elapsed_ms,
            )

        parsed = self._parser.parse(result.content)
        page_result = await downloader.download_page(task.google_doc_id, suffix="mobilebasic")
        page_html = page_result.content if isinstance(page_result.content, str) else ""
        metadata = extract_document_metadata(
            export_html=result.content,
            page_html=page_html,
            clean_text=parsed.clean_text,
        )
        if not metadata.shared_by_email:
            edit_result = await downloader.download_page(task.google_doc_id, suffix="edit")
            edit_html = edit_result.content if isinstance(edit_result.content, str) else ""
            if edit_html:
                metadata = extract_document_metadata(
                    export_html=result.content,
                    page_html=page_html,
                    edit_html=edit_html,
                    clean_text=parsed.clean_text,
                )
        content_hash = compute_sha256(parsed.clean_text or result.content)

        if content_hash in self._seen_hashes:
            return CsvRow(
                google_doc_id=task.google_doc_id,
                url=task.url,
                title=parsed.title,
                sha256=content_hash,
                status="duplicate",
                elapsed_ms=result.elapsed_ms,
            )

        self._seen_hashes.add(content_hash)
        preview = build_preview_url(task.google_doc_id)
        embedded = first_image_url(parsed.images)
        archive = build_archive_data(parsed)
        return CsvRow(
            google_doc_id=task.google_doc_id,
            url=task.url,
            title=parsed.title,
            excerpt=build_excerpt(parsed.clean_text),
            clean_text=parsed.clean_text,
            search_text=build_search_text(parsed),
            headings=" | ".join(parsed.headings),
            word_count=parsed.word_count,
            character_count=parsed.character_count,
            language=parsed.language,
            sha256=content_hash,
            preview_url=preview,
            preview_image_url=embedded or preview,
            links_count=len(parsed.links),
            images_count=len(parsed.images),
            archive_json=archive_json_dumps(archive),
            shared_by_email=metadata.shared_by_email,
            shared_by_name=metadata.shared_by_name,
            shared_at=metadata.shared_at,
            document_modified_at=metadata.document_modified_at,
            status="parsed",
            elapsed_ms=result.elapsed_ms,
        )
