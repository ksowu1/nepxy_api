"""add request_id to payout and webhook tables

Revision ID: 0012_add_request_id_columns
Revises: 0011_seed_cashout_limits
Create Date: 2026-01-23 00:00:00.000000

"""

from __future__ import annotations

from alembic import op


revision = "0012_add_request_id_columns"
down_revision = "0011_seed_cashout_limits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE app.mobile_money_payouts ADD COLUMN IF NOT EXISTS request_id text;")
    op.execute("ALTER TABLE app.webhook_events ADD COLUMN IF NOT EXISTS request_id text;")
    op.execute("ALTER TABLE public.webhook_events ADD COLUMN IF NOT EXISTS request_id text;")


def downgrade() -> None:
    pass
