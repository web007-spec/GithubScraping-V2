"""Initial schema

Revision ID: 001_initial
Revises:
Create Date: 2026-06-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

document_status = postgresql.ENUM(
    "discovered",
    "queued",
    "downloading",
    "parsed",
    "failed",
    "skipped",
    "duplicate",
    name="document_status",
    create_type=True,
)


def upgrade() -> None:
    document_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("google_doc_id", sa.String(128), nullable=False, unique=True),
        sa.Column("url", sa.Text(), nullable=False, unique=True),
        sa.Column("title", sa.String(1024)),
        sa.Column("clean_text", sa.Text()),
        sa.Column("html", sa.Text()),
        sa.Column("word_count", sa.Integer()),
        sa.Column("character_count", sa.Integer()),
        sa.Column("language", sa.String(16)),
        sa.Column("sha256", sa.String(64)),
        sa.Column("status", document_status, nullable=False, server_default="discovered"),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_documents_sha256", "documents", ["sha256"])
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_index("ix_documents_created_at", "documents", ["created_at"])

    op.create_table(
        "links",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("document_id", sa.UUID(as_uuid=False), sa.ForeignKey("documents.id", ondelete="CASCADE")),
        sa.Column("href", sa.Text(), nullable=False),
        sa.Column("text", sa.Text()),
    )
    op.create_index("ix_links_document_id", "links", ["document_id"])

    op.create_table(
        "images",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("document_id", sa.UUID(as_uuid=False), sa.ForeignKey("documents.id", ondelete="CASCADE")),
        sa.Column("src", sa.Text(), nullable=False),
        sa.Column("alt", sa.Text()),
    )
    op.create_index("ix_images_document_id", "images", ["document_id"])

    op.create_table(
        "crawl_logs",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer()),
        sa.Column("error", sa.Text()),
        sa.Column("elapsed_ms", sa.Integer()),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_crawl_logs_url", "crawl_logs", ["url"])
    op.create_index("ix_crawl_logs_timestamp", "crawl_logs", ["timestamp"])

    op.create_table(
        "statistics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("metric_name", sa.String(64), nullable=False, unique=True),
        sa.Column("metric_value", sa.Float(), server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("statistics")
    op.drop_table("crawl_logs")
    op.drop_table("images")
    op.drop_table("links")
    op.drop_table("documents")
    document_status.drop(op.get_bind(), checkfirst=True)
