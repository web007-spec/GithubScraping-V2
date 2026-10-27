"""Statistics repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.statistics import Statistics


class StatisticsRepository:
    """Data access for statistics metrics."""

    METRICS = (
        "total_discovered",
        "downloaded",
        "failed",
        "skipped",
        "duplicates",
        "success_rate",
        "avg_download_ms",
        "queue_size",
        "workers",
    )

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, metric_name: str, metric_value: float) -> Statistics:
        result = await self._session.execute(
            select(Statistics).where(Statistics.metric_name == metric_name)
        )
        stat = result.scalar_one_or_none()
        if stat is None:
            stat = Statistics(metric_name=metric_name, metric_value=metric_value)
            self._session.add(stat)
        else:
            stat.metric_value = metric_value
        await self._session.flush()
        return stat

    async def get_all(self) -> dict[str, float]:
        result = await self._session.execute(select(Statistics))
        return {s.metric_name: s.metric_value for s in result.scalars().all()}
