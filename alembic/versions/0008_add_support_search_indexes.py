"""add support search indexes

Revision ID: 0008_add_support_search_indexes
Revises: 0007_add_reconcile_reports
Create Date: 2026-01-14 00:10:00.000000

"""

from __future__ import annotations

from alembic import op


revision = "0008_add_support_search_indexes"
down_revision = "0007_add_reconcile_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_phone ON users.users (phone_e164);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mm_payouts_provider_ref ON app.mobile_money_payouts (provider_ref);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ledger_tx_external_ref ON ledger.ledger_transactions (external_ref);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_webhook_events_external_ref ON app.webhook_events (external_ref);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_webhook_events_provider_ref ON app.webhook_events (provider_ref);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_webhook_events_provider_ref;")
    op.execute("DROP INDEX IF EXISTS idx_webhook_events_external_ref;")
    op.execute("DROP INDEX IF EXISTS idx_ledger_tx_external_ref;")
    op.execute("DROP INDEX IF EXISTS idx_mm_payouts_provider_ref;")
    op.execute("DROP INDEX IF EXISTS idx_users_phone;")
