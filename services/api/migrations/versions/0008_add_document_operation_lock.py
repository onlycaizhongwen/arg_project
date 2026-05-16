"""add document operation lock

Revision ID: 0008_operation_lock
Revises: 0007_audit_event
Create Date: 2026-05-16
"""
from __future__ import annotations

from alembic import op


revision = "0008_operation_lock"
down_revision = "0007_audit_event"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE document ADD COLUMN IF NOT EXISTS operation_status TEXT")
    op.execute("ALTER TABLE document ADD COLUMN IF NOT EXISTS operation_lock_id UUID")
    op.execute("ALTER TABLE document ADD COLUMN IF NOT EXISTS operation_started_at TIMESTAMPTZ")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_document_operation_status
        ON document (tenant_id, operation_status, operation_started_at)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_document_operation_status")
    op.execute("ALTER TABLE document DROP COLUMN IF EXISTS operation_started_at")
    op.execute("ALTER TABLE document DROP COLUMN IF EXISTS operation_lock_id")
    op.execute("ALTER TABLE document DROP COLUMN IF EXISTS operation_status")
