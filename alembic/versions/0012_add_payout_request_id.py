"""add request_id to mobile_money_payouts

Revision ID: 0012_add_payout_request_id
Revises: 0011_seed_cashout_limits
Create Date: 2026-01-26 00:30:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0012_add_payout_request_id"
down_revision = "0011_seed_cashout_limits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mobile_money_payouts",
        sa.Column("request_id", sa.Text(), nullable=True),
        schema="app",
    )


def downgrade() -> None:
    op.drop_column("mobile_money_payouts", "request_id", schema="app")
