"""Export service for indexed documents."""

import csv
import json
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.document_repository import DocumentRepository
from app.models.document import Document


class ExportService:
    """Export documents to CSV, JSON, or Markdown."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = DocumentRepository(session)

    async def export(
        self,
        output_path: Path,
        fmt: str = "json",
        limit: int | None = None,
    ) -> int:
        docs = await self._repo.get_all_parsed(limit=limit)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if fmt == "csv":
            self._export_csv(docs, output_path)
        elif fmt == "markdown":
            self._export_markdown(docs, output_path)
        else:
            self._export_json(docs, output_path)

        return len(docs)

    def _doc_to_dict(self, doc: Document) -> dict:
        return {
            "id": doc.id,
            "google_doc_id": doc.google_doc_id,
            "url": doc.url,
            "title": doc.title,
            "clean_text": doc.clean_text,
            "word_count": doc.word_count,
            "character_count": doc.character_count,
            "language": doc.language,
            "sha256": doc.sha256,
            "status": doc.status.value,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        }

    def _export_json(self, docs: list[Document], path: Path) -> None:
        data = [self._doc_to_dict(d) for d in docs]
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _export_csv(self, docs: list[Document], path: Path) -> None:
        fields = [
            "id",
            "google_doc_id",
            "url",
            "title",
            "word_count",
            "character_count",
            "language",
            "sha256",
            "status",
            "created_at",
        ]
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for doc in docs:
                row = self._doc_to_dict(doc)
                writer.writerow(row)

    def _export_markdown(self, docs: list[Document], path: Path) -> None:
        parts: list[str] = ["# Google Docs Export\n"]
        for doc in docs:
            parts.append(f"## {doc.title or 'Untitled'}\n")
            parts.append(f"- **URL:** {doc.url}\n")
            parts.append(f"- **Language:** {doc.language or 'unknown'}\n")
            parts.append(f"- **Words:** {doc.word_count or 0}\n\n")
            if doc.clean_text:
                parts.append(doc.clean_text)
            parts.append("\n---\n")
        path.write_text("\n".join(parts), encoding="utf-8")
