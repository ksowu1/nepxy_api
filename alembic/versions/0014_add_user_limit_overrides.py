"""add user limit overrides table

Revision ID: 0014_add_user_limit_overrides
Revises: 0013_add_webhook_request_id
Create Date: 2026-01-26 21:12:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0014_add_user_limit_overrides"
down_revision = "0013_add_webhook_request_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_limit_overrides",
        sa.Column("user_id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("max_cashout_per_day_cents", sa.BigInteger(), nullable=True),
        sa.Column("max_cashout_per_month_cents", sa.BigInteger(), nullable=True),
        sa.Column("max_cashout_count_per_day", sa.Integer(), nullable=True),
        sa.Column("max_cashout_count_per_month", sa.Integer(), nullable=True),
        sa.Column("max_cashin_per_day_cents", sa.BigInteger(), nullable=True),
        sa.Column("max_cashin_per_month_cents", sa.BigInteger(), nullable=True),
        sa.Column("max_cashout_count_per_window", sa.Integer(), nullable=True),
        sa.Column("cashout_window_minutes", sa.Integer(), nullable=True),
        sa.Column("max_distinct_receivers_per_day", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        schema="app",
    )


def downgrade() -> None:
    op.drop_table("user_limit_overrides", schema="app")
