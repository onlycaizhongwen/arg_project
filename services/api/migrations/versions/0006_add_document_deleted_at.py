"""add document deleted at

Revision ID: 0006_deleted_at
Revises: 0005_permission_tags
Create Date: 2026-05-16
"""
from __future__ import annotations

from alembic import op


revision = "0006_deleted_at"
down_revision = "0005_permission_tags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE document ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ")
    op.execute("ALTER TABLE document_version ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ")
    op.execute("CREATE INDEX IF NOT EXISTS idx_document_status ON document (tenant_id, status)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_document_version_status "
        "ON document_version (document_id, status)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_document_version_status")
    op.execute("DROP INDEX IF EXISTS idx_document_status")
    op.execute("ALTER TABLE document_version DROP COLUMN IF EXISTS deleted_at")
    op.execute("ALTER TABLE document DROP COLUMN IF EXISTS deleted_at")
