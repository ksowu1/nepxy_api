"""add velocity limit indexes

Revision ID: 0006_add_velocity_indexes
Revises: 0005_add_webhook_payload_summary
Create Date: 2026-01-12 00:50:00.000000

"""

from __future__ import annotations

from alembic import op


revision = "0006_add_velocity_indexes"
down_revision = "0005_add_webhook_payload_summary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ledger_txn_created_by_type_created_at
        ON ledger.ledger_transactions (created_by, type, created_at DESC);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_mobile_money_payouts_created_at
        ON app.mobile_money_payouts (created_at);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_mobile_money_payouts_phone_created_at
        ON app.mobile_money_payouts (phone_e164, created_at DESC);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_mobile_money_payouts_phone_created_at;")
    op.execute("DROP INDEX IF EXISTS idx_mobile_money_payouts_created_at;")
    op.execute("DROP INDEX IF EXISTS idx_ledger_txn_created_by_type_created_at;")
