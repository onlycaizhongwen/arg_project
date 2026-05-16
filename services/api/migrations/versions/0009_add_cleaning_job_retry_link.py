"""add cleaning job retry link

Revision ID: 0009_retry_link
Revises: 0008_operation_lock
Create Date: 2026-05-16
"""
from __future__ import annotations

from alembic import op


revision = "0009_retry_link"
down_revision = "0008_operation_lock"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE cleaning_job ADD COLUMN IF NOT EXISTS retry_of_job_id UUID")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_cleaning_job_retry_of
        ON cleaning_job (retry_of_job_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_cleaning_job_retry_of")
    op.execute("ALTER TABLE cleaning_job DROP COLUMN IF EXISTS retry_of_job_id")
