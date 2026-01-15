"""add gh to country_code enum

Revision ID: 0003_add_country_gh
Revises: 0002_idempotency_keys
Create Date: 2026-01-12 00:20:00.000000

"""

from __future__ import annotations

from alembic import op


revision = "0003_add_country_gh"
down_revision = "0002_idempotency_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE ledger.country_code ADD VALUE IF NOT EXISTS 'GH';")


def downgrade() -> None:
    # Enum values cannot be removed easily; keep no-op.
    pass
