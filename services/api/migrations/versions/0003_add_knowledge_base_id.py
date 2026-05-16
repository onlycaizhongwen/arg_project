"""add knowledge base id

Revision ID: 0003_knowledge_base
Revises: 0002_retry_count
Create Date: 2026-05-16
"""
from __future__ import annotations

from alembic import op


revision = "0003_knowledge_base"
down_revision = "0002_retry_count"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE document
        ADD COLUMN IF NOT EXISTS knowledge_base_id TEXT NOT NULL DEFAULT 'kb-default'
        """
    )
    op.execute(
        """
        ALTER TABLE text_chunk
        ADD COLUMN IF NOT EXISTS knowledge_base_id TEXT NOT NULL DEFAULT 'kb-default'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_document_tenant_kb
        ON document (tenant_id, knowledge_base_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_text_chunk_tenant_kb
        ON text_chunk (tenant_id, knowledge_base_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_text_chunk_tenant_kb")
    op.execute("DROP INDEX IF EXISTS idx_document_tenant_kb")
    op.execute("ALTER TABLE text_chunk DROP COLUMN IF EXISTS knowledge_base_id")
    op.execute("ALTER TABLE document DROP COLUMN IF EXISTS knowledge_base_id")
