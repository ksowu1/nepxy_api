"""add request_id to webhook_events tables

Revision ID: 0013_add_webhook_request_id
Revises: 0012_add_payout_request_id
Create Date: 2026-01-26 00:45:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0013_add_webhook_request_id"
down_revision = "0012_add_payout_request_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "webhook_events",
        sa.Column("request_id", sa.Text(), nullable=True),
        schema="app",
    )
    op.add_column(
        "webhook_events",
        sa.Column("request_id", sa.Text(), nullable=True),
        schema="public",
    )


def downgrade() -> None:
    op.drop_column("webhook_events", "request_id", schema="public")
    op.drop_column("webhook_events", "request_id", schema="app")
