"""Statistics dashboard service."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings, get_settings
from app.database.repositories.crawl_log_repository import CrawlLogRepository
from app.database.repositories.document_repository import DocumentRepository
from app.database.repositories.statistics_repository import StatisticsRepository
from app.models.document import DocumentStatus


@dataclass
class DashboardStats:
    """Statistics for display."""

    total_discovered: int = 0
    downloaded: int = 0
    failed: int = 0
    skipped: int = 0
    duplicates: int = 0
    success_rate: float = 0.0
    avg_download_ms: float = 0.0
    queue_size: int = 0
    workers: int = 0
    crawl_log_count: int = 0


class StatsService:
    """Aggregate and display crawl statistics."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._doc_repo = DocumentRepository(session)
        self._log_repo = CrawlLogRepository(session)
        self._stats_repo = StatisticsRepository(session)

    async def get_dashboard(self, queue_size: int = 0) -> DashboardStats:
        status_counts = await self._doc_repo.count_by_status()
        total = sum(status_counts.values())
        downloaded = status_counts.get(DocumentStatus.PARSED.value, 0)
        failed = status_counts.get(DocumentStatus.FAILED.value, 0)
        skipped = status_counts.get(DocumentStatus.SKIPPED.value, 0)
        duplicates = status_counts.get(DocumentStatus.DUPLICATE.value, 0)

        success_rate = (downloaded / total * 100) if total else 0.0
        avg_ms = await self._log_repo.average_elapsed_ms()
        log_count = await self._log_repo.count_total()

        stored = await self._stats_repo.get_all()

        return DashboardStats(
            total_discovered=total,
            downloaded=downloaded,
            failed=failed,
            skipped=skipped,
            duplicates=duplicates,
            success_rate=stored.get("success_rate", success_rate),
            avg_download_ms=stored.get("avg_download_ms", avg_ms),
            queue_size=queue_size or int(stored.get("queue_size", 0)),
            workers=int(stored.get("workers", self._settings.max_workers)),
            crawl_log_count=log_count,
        )

    def format_dashboard(self, stats: DashboardStats) -> str:
        lines = [
            "=" * 50,
            "  Google Docs Public Indexer - Statistics",
            "=" * 50,
            f"  Total discovered:     {stats.total_discovered:>8}",
            f"  Downloaded (parsed):  {stats.downloaded:>8}",
            f"  Failed:               {stats.failed:>8}",
            f"  Skipped:              {stats.skipped:>8}",
            f"  Duplicates:           {stats.duplicates:>8}",
            f"  Success rate:         {stats.success_rate:>7.1f}%",
            f"  Avg download time:    {stats.avg_download_ms:>7.0f} ms",
            f"  Queue size:           {stats.queue_size:>8}",
            f"  Workers:              {stats.workers:>8}",
            f"  Crawl log entries:    {stats.crawl_log_count:>8}",
            "=" * 50,
        ]
        return "\n".join(lines)
