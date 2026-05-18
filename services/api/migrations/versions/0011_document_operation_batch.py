"""add document operation batch

Revision ID: 0011_doc_batch
Revises: 0010_search_diag
Create Date: 2026-05-18
"""
from __future__ import annotations

from alembic import op


revision = "0011_doc_batch"
down_revision = "0010_search_diag"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS document_operation_batch (
            id UUID PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            operation TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            filters JSONB NOT NULL DEFAULT '{}'::jsonb,
            total_count INTEGER NOT NULL DEFAULT 0,
            submitted_count INTEGER NOT NULL DEFAULT 0,
            succeeded_count INTEGER NOT NULL DEFAULT 0,
            failed_count INTEGER NOT NULL DEFAULT 0,
            skipped_count INTEGER NOT NULL DEFAULT 0,
            actor_id TEXT NOT NULL DEFAULT 'system',
            request_source TEXT NOT NULL DEFAULT 'api',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS document_operation_batch_item (
            id UUID PRIMARY KEY,
            batch_id UUID NOT NULL REFERENCES document_operation_batch(id) ON DELETE CASCADE,
            tenant_id TEXT NOT NULL,
            document_id UUID NOT NULL REFERENCES document(id),
            document_version_id UUID REFERENCES document_version(id),
            job_id UUID REFERENCES cleaning_job(id),
            status TEXT NOT NULL DEFAULT 'PENDING',
            error_code TEXT,
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_document_operation_batch_status
        ON document_operation_batch (tenant_id, operation, status, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_document_operation_batch_item_batch
        ON document_operation_batch_item (tenant_id, batch_id, created_at ASC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_document_operation_batch_item_job
        ON document_operation_batch_item (job_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_document_operation_batch_item_job")
    op.execute("DROP INDEX IF EXISTS idx_document_operation_batch_item_batch")
    op.execute("DROP INDEX IF EXISTS idx_document_operation_batch_status")
    op.execute("DROP TABLE IF EXISTS document_operation_batch_item")
    op.execute("DROP TABLE IF EXISTS document_operation_batch")
