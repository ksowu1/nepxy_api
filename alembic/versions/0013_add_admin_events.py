"""add admin_events audit table

Revision ID: 0013_add_admin_events
Revises: 0012_add_request_id_columns
Create Date: 2026-01-24 00:00:00.000000

"""

from __future__ import annotations

from alembic import op


revision = "0013_add_admin_events"
down_revision = "0012_add_request_id_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS audit;")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS audit.admin_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            created_at timestamptz NOT NULL DEFAULT now(),
            admin_user_id uuid NOT NULL,
            action text NOT NULL,
            entity_type text NOT NULL,
            entity_id text,
            metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
            request_id text
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit.admin_events;")
