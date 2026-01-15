"""add payout quote jsonb

Revision ID: 0009_add_payout_quote
Revises: 0008_add_support_search_indexes
Create Date: 2026-01-15 00:30:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0009_add_payout_quote"
down_revision = "0008_add_support_search_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mobile_money_payouts",
        sa.Column("quote", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema="app",
    )


def downgrade() -> None:
    op.drop_column("mobile_money_payouts", "quote", schema="app")
