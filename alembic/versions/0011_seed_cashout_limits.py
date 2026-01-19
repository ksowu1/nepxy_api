"""seed cashout limit data

Revision ID: 0011_seed_cashout_limits
Revises: 0010_bootstrap_auth_and_mobile_money
Create Date: 2026-01-18 00:10:00.000000

"""

from __future__ import annotations

from alembic import op


revision = "0011_seed_cashout_limits"
down_revision = "0010_bootstrap_auth_and_mobile_money"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO limits.account_limits (
          kyc_tier,
          daily_send_cents,
          monthly_send_cents,
          daily_cashout_cents,
          is_active
        ) VALUES
          (1, 1000000, 5000000, 1000000, TRUE),
          (2, 2500000, 15000000, 2500000, TRUE)
        ON CONFLICT (kyc_tier) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM limits.account_limits
        WHERE kyc_tier IN (1, 2);
        """
    )
