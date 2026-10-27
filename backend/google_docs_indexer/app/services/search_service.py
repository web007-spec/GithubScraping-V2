"""Search service."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.document_repository import DocumentRepository
from app.models.document import Document


class SearchService:
    """Document search operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = DocumentRepository(session)

    async def search(
        self,
        query: str | None = None,
        title: str | None = None,
        language: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        full_text: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Document]:
        if full_text and query:
            return await self._repo.full_text_search(query, limit=limit)
        return await self._repo.search(
            query=query,
            title=title,
            language=language,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
