"""add search diagnostic event

Revision ID: 0010_search_diag
Revises: 0009_retry_link
Create Date: 2026-05-16
"""
from __future__ import annotations

from alembic import op


revision = "0010_search_diag"
down_revision = "0009_retry_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS search_diagnostic_event (
            id UUID PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_search_diagnostic_event_type
        ON search_diagnostic_event (tenant_id, event_type, created_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_search_diagnostic_event_type")
    op.execute("DROP TABLE IF EXISTS search_diagnostic_event")
