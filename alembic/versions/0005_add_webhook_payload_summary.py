"""add payload_summary to webhook_events

Revision ID: 0005_add_webhook_payload_summary
Revises: 0004_add_audit_log
Create Date: 2026-01-12 00:40:00.000000

"""

from __future__ import annotations

from alembic import op


revision = "0005_add_webhook_payload_summary"
down_revision = "0004_add_audit_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE app.webhook_events ADD COLUMN IF NOT EXISTS payload_summary jsonb;")


def downgrade() -> None:
    op.execute("ALTER TABLE app.webhook_events DROP COLUMN IF EXISTS payload_summary;")
