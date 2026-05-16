"""add text chunk full text index

Revision ID: 0004_chunk_fts
Revises: 0003_knowledge_base
Create Date: 2026-05-16
"""
from __future__ import annotations

from alembic import op


revision = "0004_chunk_fts"
down_revision = "0003_knowledge_base"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_text_chunk_content_fts ON text_chunk
        USING GIN (to_tsvector('simple', content))
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_text_chunk_content_fts")
