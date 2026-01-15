"""add idempotency keys table

Revision ID: 0002_idempotency_keys
Revises: 0001_baseline_schema
Create Date: 2026-01-12 00:10:00.000000

"""

from __future__ import annotations

from alembic import op


revision = "0002_idempotency_keys"
down_revision = "0001_baseline_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS app.idempotency_keys (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            user_id uuid NOT NULL,
            idempotency_key text NOT NULL,
            route_key text NOT NULL,
            request_hash text,
            response_json jsonb NOT NULL,
            status_code integer NOT NULL,
            created_at timestamp with time zone DEFAULT now() NOT NULL
        );
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'idempotency_keys_pkey'
            ) THEN
                ALTER TABLE app.idempotency_keys
                    ADD CONSTRAINT idempotency_keys_pkey PRIMARY KEY (id);
            END IF;
        END
        $$;
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_idempotency_keys_user_route ON app.idempotency_keys USING btree (user_id, idempotency_key, route_key);"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.idempotency_keys;")
