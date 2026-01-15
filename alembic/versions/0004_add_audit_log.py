"""add audit_log table

Revision ID: 0004_add_audit_log
Revises: 0003_add_country_gh
Create Date: 2026-01-12 00:30:00.000000

"""

from __future__ import annotations

from alembic import op


revision = "0004_add_audit_log"
down_revision = "0003_add_country_gh"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS app.audit_log (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            actor_user_id uuid NOT NULL,
            action text NOT NULL,
            target_id text,
            metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.audit_log;")
