"""add document audit event

Revision ID: 0007_audit_event
Revises: 0006_deleted_at
Create Date: 2026-05-16
"""
from __future__ import annotations

from alembic import op


revision = "0007_audit_event"
down_revision = "0006_deleted_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS document_audit_event (
            id UUID PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            document_id UUID NOT NULL,
            document_version_id UUID,
            job_id UUID,
            operation TEXT NOT NULL,
            actor_id TEXT NOT NULL DEFAULT 'system',
            request_source TEXT NOT NULL DEFAULT 'api',
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_document_audit_event_document
        ON document_audit_event (tenant_id, document_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_document_audit_event_operation
        ON document_audit_event (tenant_id, operation, created_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_document_audit_event_operation")
    op.execute("DROP INDEX IF EXISTS idx_document_audit_event_document")
    op.execute("DROP TABLE IF EXISTS document_audit_event")
