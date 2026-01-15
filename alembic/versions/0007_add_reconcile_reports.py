"""add reconcile reports table

Revision ID: 0007_add_reconcile_reports
Revises: 0006_add_velocity_indexes
Create Date: 2026-01-14 00:00:00.000000

"""

from __future__ import annotations

from alembic import op


revision = "0007_add_reconcile_reports"
down_revision = "0006_add_velocity_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS app.reconcile_reports (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          run_at timestamptz NOT NULL DEFAULT now(),
          summary jsonb NOT NULL,
          items jsonb NOT NULL
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.reconcile_reports;")
