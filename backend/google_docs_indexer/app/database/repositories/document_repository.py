"""Document repository."""

from datetime import datetime

from sqlalchemy import func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus
from app.models.link import Link
from app.models.image import Image


class DocumentRepository:
    """Data access for documents."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, doc_id: str) -> Document | None:
        result = await self._session.execute(select(Document).where(Document.id == doc_id))
        return result.scalar_one_or_none()

    async def get_by_google_doc_id(self, google_doc_id: str) -> Document | None:
        result = await self._session.execute(
            select(Document).where(Document.google_doc_id == google_doc_id)
        )
        return result.scalar_one_or_none()

    async def get_by_url(self, url: str) -> Document | None:
        result = await self._session.execute(select(Document).where(Document.url == url))
        return result.scalar_one_or_none()

    async def get_by_sha256(self, sha256: str) -> Document | None:
        result = await self._session.execute(select(Document).where(Document.sha256 == sha256))
        return result.scalar_one_or_none()

    async def create_discovered(self, google_doc_id: str, url: str) -> Document:
        doc = Document(google_doc_id=google_doc_id, url=url, status=DocumentStatus.DISCOVERED)
        self._session.add(doc)
        await self._session.flush()
        return doc

    async def update_status(
        self, doc: Document, status: DocumentStatus, error_message: str | None = None
    ) -> Document:
        doc.status = status
        if error_message is not None:
            doc.error_message = error_message
        await self._session.flush()
        return doc

    async def save_parsed(
        self,
        doc: Document,
        *,
        title: str | None,
        clean_text: str | None,
        html: str | None,
        word_count: int | None,
        character_count: int | None,
        language: str | None,
        sha256: str | None,
        links: list[tuple[str, str | None]],
        images: list[tuple[str, str | None]],
    ) -> Document:
        doc.title = title
        doc.clean_text = clean_text
        doc.html = html
        doc.word_count = word_count
        doc.character_count = character_count
        doc.language = language
        doc.sha256 = sha256
        doc.status = DocumentStatus.PARSED
        doc.error_message = None

        for href, link_text in links:
            self._session.add(Link(document_id=doc.id, href=href, text=link_text))
        for src, alt in images:
            self._session.add(Image(document_id=doc.id, src=src, alt=alt))

        await self._session.flush()
        return doc

    async def get_pending(self, limit: int = 1000) -> list[Document]:
        statuses = [
            DocumentStatus.DISCOVERED,
            DocumentStatus.QUEUED,
            DocumentStatus.FAILED,
        ]
        result = await self._session.execute(
            select(Document)
            .where(Document.status.in_(statuses))
            .order_by(Document.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_failed(self, limit: int = 1000) -> list[Document]:
        result = await self._session.execute(
            select(Document)
            .where(Document.status == DocumentStatus.FAILED)
            .order_by(Document.updated_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_by_status(self) -> dict[str, int]:
        result = await self._session.execute(
            select(Document.status, func.count(Document.id)).group_by(Document.status)
        )
        return {row[0].value: row[1] for row in result.all()}

    async def search(
        self,
        query: str | None = None,
        title: str | None = None,
        language: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Document]:
        stmt = select(Document).where(Document.status == DocumentStatus.PARSED)

        if title:
            stmt = stmt.where(Document.title.ilike(f"%{title}%"))
        if language:
            stmt = stmt.where(Document.language == language)
        if date_from:
            stmt = stmt.where(Document.created_at >= date_from)
        if date_to:
            stmt = stmt.where(Document.created_at <= date_to)
        if query:
            pattern = f"%{query}%"
            stmt = stmt.where(
                or_(
                    Document.title.ilike(pattern),
                    Document.clean_text.ilike(pattern),
                )
            )

        stmt = stmt.order_by(Document.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def full_text_search(self, query: str, limit: int = 50) -> list[Document]:
        """PostgreSQL full-text search when tsvector column exists."""
        try:
            result = await self._session.execute(
                text(
                    """
                    SELECT d.* FROM documents d
                    WHERE d.status = 'parsed'
                    AND to_tsvector('english', coalesce(d.title, '') || ' ' || coalesce(d.clean_text, ''))
                        @@ plainto_tsquery('english', :query)
                    ORDER BY ts_rank(
                        to_tsvector('english', coalesce(d.title, '') || ' ' || coalesce(d.clean_text, '')),
                        plainto_tsquery('english', :query)
                    ) DESC
                    LIMIT :limit
                    """
                ),
                {"query": query, "limit": limit},
            )
            rows = result.mappings().all()
            if rows:
                ids = [row["id"] for row in rows]
                docs_result = await self._session.execute(
                    select(Document).where(Document.id.in_(ids))
                )
                docs = {d.id: d for d in docs_result.scalars().all()}
                return [docs[i] for i in ids if i in docs]
        except Exception:
            pass
        return await self.search(query=query, limit=limit)

    async def get_all_parsed(self, limit: int | None = None, offset: int = 0) -> list[Document]:
        stmt = (
            select(Document)
            .where(Document.status == DocumentStatus.PARSED)
            .order_by(Document.created_at.desc())
            .offset(offset)
        )
        if limit:
            stmt = stmt.limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def mark_duplicates_skipped(self) -> int:
        """Mark documents with duplicate sha256 as skipped."""
        subq = (
            select(Document.sha256)
            .where(Document.sha256.isnot(None))
            .group_by(Document.sha256)
            .having(func.count(Document.id) > 1)
        )
        dup_hashes = [row[0] for row in (await self._session.execute(subq)).all()]
        if not dup_hashes:
            return 0

        await self._session.execute(
            update(Document)
            .where(Document.sha256.in_(dup_hashes))
            .where(Document.status != DocumentStatus.PARSED)
            .values(status=DocumentStatus.DUPLICATE)
        )
        return len(dup_hashes)
