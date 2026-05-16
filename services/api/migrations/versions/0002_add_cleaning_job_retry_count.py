"""add cleaning job retry count

Revision ID: 0002_retry_count
Revises: 0001_initial
Create Date: 2026-05-16
"""
from __future__ import annotations

from alembic import op


revision = "0002_retry_count"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE cleaning_job
        ADD COLUMN IF NOT EXISTS retry_count INTEGER NOT NULL DEFAULT 0
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE cleaning_job DROP COLUMN IF EXISTS retry_count")
