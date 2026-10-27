"""Crawl orchestration service."""

import asyncio
from dataclasses import dataclass, field

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config.settings import Settings, get_settings
from app.crawler.queue import CrawlQueue, CrawlTask, WorkerPool
from app.database.repositories.crawl_log_repository import CrawlLogRepository
from app.database.repositories.document_repository import DocumentRepository
from app.database.repositories.statistics_repository import StatisticsRepository
from app.downloader.document_downloader import DocumentDownloader
from app.models.document import DocumentStatus
from app.parser.document_parser import DocumentParser
from app.utils.hashing import compute_sha256


@dataclass
class CrawlStats:
    """In-memory crawl statistics."""

    downloaded: int = 0
    failed: int = 0
    skipped: int = 0
    duplicates: int = 0
    total_elapsed_ms: int = 0
    processed: int = 0

    @property
    def avg_download_ms(self) -> float:
        if self.processed == 0:
            return 0.0
        return self.total_elapsed_ms / self.processed


class CrawlService:
    """Orchestrate document crawling with worker pool."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings or get_settings()
        self._parser = DocumentParser()
        self._stats = CrawlStats()
        self._queue = CrawlQueue()
        self._pool = WorkerPool(self._settings.max_workers)
        self._shutdown_event = asyncio.Event()

    @property
    def stats(self) -> CrawlStats:
        return self._stats

    @property
    def queue(self) -> CrawlQueue:
        return self._queue

    async def load_pending_into_queue(self, limit: int = 10000) -> int:
        """Load pending documents from DB into queue."""
        async with self._session_factory() as session:
            repo = DocumentRepository(session)
            pending = await repo.get_pending(limit=limit)
            tasks = [
                CrawlTask(
                    document_id=doc.id,
                    google_doc_id=doc.google_doc_id,
                    url=doc.url,
                )
                for doc in pending
            ]
            for doc in pending:
                await repo.update_status(doc, DocumentStatus.QUEUED)
            await session.commit()

        await self._queue.put_many(tasks)
        logger.info("Queued {} documents for crawling", len(tasks))
        return len(tasks)

    async def load_failed_into_queue(self, limit: int = 1000) -> int:
        """Load failed documents for retry."""
        async with self._session_factory() as session:
            repo = DocumentRepository(session)
            failed = await repo.get_failed(limit=limit)
            tasks = [
                CrawlTask(
                    document_id=doc.id,
                    google_doc_id=doc.google_doc_id,
                    url=doc.url,
                )
                for doc in failed
            ]
            for doc in failed:
                await repo.update_status(doc, DocumentStatus.QUEUED)
            await session.commit()

        await self._queue.put_many(tasks)
        logger.info("Queued {} failed documents for retry", len(tasks))
        return len(tasks)

    async def run(self) -> CrawlStats:
        """Run crawl until queue is empty."""
        async with DocumentDownloader(self._settings) as downloader:
            await self._pool.start(
                lambda worker_id, q: self._worker(worker_id, q, downloader),
                self._queue,
            )
            await self._queue.join()
            await self._queue.shutdown(self._pool.num_workers)
            await self._pool.wait()

        await self._persist_statistics()
        return self._stats

    async def shutdown(self) -> None:
        """Gracefully shut down workers."""
        self._shutdown_event.set()
        await self._queue.shutdown(self._settings.max_workers)
        await self._pool.wait()

    async def _worker(
        self,
        worker_id: int,
        queue: CrawlQueue,
        downloader: DocumentDownloader,
    ) -> None:
        logger.debug("Worker {} started", worker_id)
        while True:
            task = await queue.get()
            if task is None:
                queue.task_done()
                logger.debug("Worker {} stopping", worker_id)
                break

            try:
                await self._process_task(task, downloader)
            except Exception as exc:
                logger.exception("Worker {} error processing {}: {}", worker_id, task.url, exc)
            finally:
                queue.task_done()

    async def _process_task(self, task: CrawlTask, downloader: DocumentDownloader) -> None:
        async with self._session_factory() as session:
            doc_repo = DocumentRepository(session)
            log_repo = CrawlLogRepository(session)

            doc = await doc_repo.get_by_id(task.document_id)
            if not doc:
                logger.warning("Document not found: {}", task.document_id)
                return

            await doc_repo.update_status(doc, DocumentStatus.DOWNLOADING)

            fmt = "html"
            if "txt" in self._settings.export_format_list and "html" not in self._settings.export_format_list:
                fmt = "txt"

            result = await downloader.download(task.google_doc_id, fmt=fmt)
            self._stats.processed += 1
            self._stats.total_elapsed_ms += result.elapsed_ms

            await log_repo.create(
                url=result.url,
                status_code=result.status_code,
                error=result.error,
                elapsed_ms=result.elapsed_ms,
            )

            if result.error or result.content is None:
                self._stats.failed += 1
                await doc_repo.update_status(doc, DocumentStatus.FAILED, result.error)
                await session.commit()
                return

            if isinstance(result.content, bytes):
                self._stats.skipped += 1
                await doc_repo.update_status(
                    doc, DocumentStatus.SKIPPED, "Binary/PDF content not indexed"
                )
                await session.commit()
                return

            if fmt == "html":
                parsed = self._parser.parse(result.content)
            else:
                parsed = self._parser.parse_txt(result.content)

            content_hash = compute_sha256(parsed.clean_text or result.content)
            duplicate = await doc_repo.get_by_sha256(content_hash)
            if duplicate and duplicate.id != doc.id:
                self._stats.duplicates += 1
                await doc_repo.update_status(doc, DocumentStatus.DUPLICATE, "Duplicate content")
                await session.commit()
                return

            await doc_repo.save_parsed(
                doc,
                title=parsed.title,
                clean_text=parsed.clean_text,
                html=parsed.html or (result.content if fmt == "html" else None),
                word_count=parsed.word_count,
                character_count=parsed.character_count,
                language=parsed.language,
                sha256=content_hash,
                links=parsed.links,
                images=parsed.images,
            )
            self._stats.downloaded += 1
            await session.commit()
            logger.info(
                "Indexed doc {} ({}) - {} words",
                task.google_doc_id,
                parsed.title or "untitled",
                parsed.word_count,
            )

    async def _persist_statistics(self) -> None:
        async with self._session_factory() as session:
            doc_repo = DocumentRepository(session)
            log_repo = CrawlLogRepository(session)
            stats_repo = StatisticsRepository(session)

            status_counts = await doc_repo.count_by_status()
            total = sum(status_counts.values())
            downloaded = status_counts.get(DocumentStatus.PARSED.value, 0)
            failed = status_counts.get(DocumentStatus.FAILED.value, 0)
            skipped = status_counts.get(DocumentStatus.SKIPPED.value, 0)
            duplicates = status_counts.get(DocumentStatus.DUPLICATE.value, 0)
            discovered = status_counts.get(DocumentStatus.DISCOVERED.value, 0) + status_counts.get(
                DocumentStatus.QUEUED.value, 0
            )

            success_rate = (downloaded / total * 100) if total else 0.0
            avg_ms = await log_repo.average_elapsed_ms()

            metrics = {
                "total_discovered": float(total),
                "downloaded": float(downloaded),
                "failed": float(failed),
                "skipped": float(skipped),
                "duplicates": float(duplicates),
                "success_rate": success_rate,
                "avg_download_ms": avg_ms or self._stats.avg_download_ms,
                "queue_size": float(self._queue.size),
                "workers": float(self._settings.max_workers),
            }
            for name, value in metrics.items():
                await stats_repo.upsert(name, value)
            await session.commit()
