"""Crawl log repository."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crawl_log import CrawlLog


class CrawlLogRepository:
    """Data access for crawl logs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        url: str,
        status_code: int | None,
        error: str | None,
        elapsed_ms: int | None,
    ) -> CrawlLog:
        log = CrawlLog(
            url=url,
            status_code=status_code,
            error=error,
            elapsed_ms=elapsed_ms,
        )
        self._session.add(log)
        await self._session.flush()
        return log

    async def average_elapsed_ms(self) -> float:
        result = await self._session.execute(
            select(func.avg(CrawlLog.elapsed_ms)).where(CrawlLog.elapsed_ms.isnot(None))
        )
        avg = result.scalar()
        return float(avg or 0.0)

    async def count_total(self) -> int:
        result = await self._session.execute(select(func.count(CrawlLog.id)))
        return int(result.scalar() or 0)
