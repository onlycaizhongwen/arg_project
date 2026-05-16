"""add permission tags

Revision ID: 0005_permission_tags
Revises: 0004_chunk_fts
Create Date: 2026-05-16
"""
from __future__ import annotations

from alembic import op


revision = "0005_permission_tags"
down_revision = "0004_chunk_fts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE document
        ADD COLUMN IF NOT EXISTS permission_tags TEXT[] NOT NULL DEFAULT ARRAY['public']::text[]
        """
    )
    op.execute(
        """
        ALTER TABLE text_chunk
        ADD COLUMN IF NOT EXISTS permission_tags TEXT[] NOT NULL DEFAULT ARRAY['public']::text[]
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_document_permission_tags
        ON document USING GIN (permission_tags)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_text_chunk_permission_tags
        ON text_chunk USING GIN (permission_tags)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_text_chunk_permission_tags")
    op.execute("DROP INDEX IF EXISTS idx_document_permission_tags")
    op.execute("ALTER TABLE text_chunk DROP COLUMN IF EXISTS permission_tags")
    op.execute("ALTER TABLE document DROP COLUMN IF EXISTS permission_tags")
