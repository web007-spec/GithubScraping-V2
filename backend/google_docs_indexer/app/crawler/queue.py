"""Async crawl queue and worker pool."""

import asyncio
from dataclasses import dataclass

from loguru import logger


@dataclass
class CrawlTask:
    """A document to crawl."""

    document_id: str
    google_doc_id: str
    url: str


class CrawlQueue:
    """Asyncio queue wrapper with graceful shutdown."""

    def __init__(self, maxsize: int = 0) -> None:
        self._queue: asyncio.Queue[CrawlTask | None] = asyncio.Queue(maxsize=maxsize)
        self._shutdown = False

    @property
    def size(self) -> int:
        return self._queue.qsize()

    @property
    def is_shutdown(self) -> bool:
        return self._shutdown

    async def put(self, task: CrawlTask) -> None:
        if self._shutdown:
            raise RuntimeError("Queue is shut down")
        await self._queue.put(task)

    async def put_many(self, tasks: list[CrawlTask]) -> None:
        for task in tasks:
            await self.put(task)

    async def get(self) -> CrawlTask | None:
        return await self._queue.get()

    def task_done(self) -> None:
        self._queue.task_done()

    async def join(self) -> None:
        await self._queue.join()

    async def shutdown(self, workers: int) -> None:
        """Signal workers to stop by sending sentinel values."""
        self._shutdown = True
        for _ in range(workers):
            await self._queue.put(None)
        logger.info("Queue shutdown initiated for {} workers", workers)


class WorkerPool:
    """Manage multiple async workers."""

    def __init__(self, num_workers: int) -> None:
        self._num_workers = num_workers
        self._tasks: list[asyncio.Task[None]] = []

    @property
    def num_workers(self) -> int:
        return self._num_workers

    async def start(self, worker_fn, queue: CrawlQueue) -> None:
        """Start worker coroutines."""
        self._tasks = [
            asyncio.create_task(worker_fn(i, queue), name=f"worker-{i}")
            for i in range(self._num_workers)
        ]
        logger.info("Started {} workers", self._num_workers)

    async def wait(self) -> None:
        """Wait for all workers to complete."""
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    async def stop(self) -> None:
        """Cancel all workers."""
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
