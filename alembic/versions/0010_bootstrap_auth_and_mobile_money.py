"""bootstrap auth/mobile money schema gaps

Revision ID: 0010_bootstrap_auth_and_mobile_money
Revises: 0009_add_payout_quote
Create Date: 2026-01-15 00:45:00.000000

"""

from __future__ import annotations

from alembic import op


revision = "0010_bootstrap_auth_and_mobile_money"
down_revision = "0009_add_payout_quote"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE EXTENSION IF NOT EXISTS pgcrypto;

        CREATE SCHEMA IF NOT EXISTS auth;
        CREATE SCHEMA IF NOT EXISTS rails;

        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_type t
                JOIN pg_namespace n ON n.oid = t.typnamespace
                WHERE t.typname = 'rail_type' AND n.nspname = 'rails'
            ) THEN
                CREATE TYPE rails.rail_type AS ENUM ('INTERNAL', 'MOBILE_MONEY');
            END IF;
        END
        $$;

        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_type t
                JOIN pg_namespace n ON n.oid = t.typnamespace
                WHERE t.typname = 'rail_type' AND n.nspname = 'rails'
            ) THEN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_enum e
                    JOIN pg_type t ON t.oid = e.enumtypid
                    JOIN pg_namespace n ON n.oid = t.typnamespace
                    WHERE t.typname = 'rail_type'
                      AND n.nspname = 'rails'
                      AND e.enumlabel = 'INTERNAL'
                ) THEN
                    EXECUTE 'ALTER TYPE rails.rail_type ADD VALUE ''INTERNAL''';
                END IF;
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_enum e
                    JOIN pg_type t ON t.oid = e.enumtypid
                    JOIN pg_namespace n ON n.oid = t.typnamespace
                    WHERE t.typname = 'rail_type'
                      AND n.nspname = 'rails'
                      AND e.enumlabel = 'MOBILE_MONEY'
                ) THEN
                    EXECUTE 'ALTER TYPE rails.rail_type ADD VALUE ''MOBILE_MONEY''';
                END IF;
            END IF;
        END
        $$;

        CREATE TABLE IF NOT EXISTS users.user_roles (
            user_id uuid NOT NULL,
            role text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        );

        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'user_roles_pkey'
            ) THEN
                ALTER TABLE users.user_roles
                    ADD CONSTRAINT user_roles_pkey PRIMARY KEY (user_id);
            END IF;
        END
        $$;

        CREATE TABLE IF NOT EXISTS auth.user_sessions (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            user_id uuid NOT NULL,
            device_id uuid NOT NULL,
            refresh_token_hash text NOT NULL,
            biometric_enabled boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT now(),
            last_used_at timestamptz,
            expires_at timestamptz NOT NULL,
            revoked_at timestamptz
        );

        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'user_sessions_pkey'
            ) THEN
                ALTER TABLE auth.user_sessions
                    ADD CONSTRAINT user_sessions_pkey PRIMARY KEY (id);
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'user_sessions_user_id_fkey'
            ) THEN
                ALTER TABLE auth.user_sessions
                    ADD CONSTRAINT user_sessions_user_id_fkey
                    FOREIGN KEY (user_id) REFERENCES users.users(id);
            END IF;
        END
        $$;

        CREATE UNIQUE INDEX IF NOT EXISTS ux_user_sessions_refresh_token_hash
            ON auth.user_sessions (refresh_token_hash);

        CREATE TABLE IF NOT EXISTS app.mobile_money_payouts (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            transaction_id uuid NOT NULL,
            provider text NOT NULL,
            phone_e164 text,
            provider_ref text,
            external_ref text,
            status text NOT NULL,
            amount_cents bigint NOT NULL,
            currency text NOT NULL,
            last_error text,
            attempt_count integer NOT NULL DEFAULT 0,
            last_attempt_at timestamptz,
            next_retry_at timestamptz,
            retryable boolean NOT NULL DEFAULT true,
            provider_response jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        );

        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'mobile_money_payouts_pkey'
            ) THEN
                ALTER TABLE app.mobile_money_payouts
                    ADD CONSTRAINT mobile_money_payouts_pkey PRIMARY KEY (id);
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'mobile_money_payouts_transaction_id_key'
            ) THEN
                ALTER TABLE app.mobile_money_payouts
                    ADD CONSTRAINT mobile_money_payouts_transaction_id_key UNIQUE (transaction_id);
            END IF;
        END
        $$;

        CREATE TABLE IF NOT EXISTS public.webhook_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            provider text NOT NULL,
            path text NOT NULL,
            signature text,
            signature_valid boolean,
            signature_error text,
            headers jsonb,
            body jsonb,
            body_raw text,
            provider_ref text,
            external_ref text,
            status_raw text,
            payout_transaction_id text,
            payout_status_before text,
            payout_status_after text,
            update_applied boolean,
            ignored boolean,
            ignore_reason text,
            received_at timestamptz NOT NULL DEFAULT now()
        );

        ALTER TABLE alembic_version
            ALTER COLUMN version_num TYPE text;

        ALTER TABLE ledger.ledger_transactions
            ADD COLUMN IF NOT EXISTS provider text;
        ALTER TABLE ledger.ledger_transactions
            ADD COLUMN IF NOT EXISTS phone_e164 text;

        CREATE OR REPLACE VIEW ledger.wallet_entries AS
        SELECT account_id AS wallet_id, transaction_id, created_at
        FROM ledger.ledger_entries;

        CREATE OR REPLACE FUNCTION users.register_user_secure(
            p_email text,
            p_phone text,
            p_full_name text,
            p_country ledger.country_code,
            p_password_hash text
        ) RETURNS uuid
        LANGUAGE plpgsql AS $$
        DECLARE
          v_user_id uuid;
          v_wallet_id uuid;
        BEGIN
          INSERT INTO users.users (email, phone_e164, full_name, country, is_active, created_at, password_hash)
          VALUES (p_email, p_phone, p_full_name, p_country, TRUE, now(), p_password_hash)
          RETURNING id INTO v_user_id;

          INSERT INTO ledger.ledger_accounts (owner_type, owner_id, country, currency, account_type, is_active)
          VALUES ('USER', v_user_id, p_country, 'XOF', 'WALLET', TRUE)
          RETURNING id INTO v_wallet_id;

          INSERT INTO ledger.wallet_balances(account_id, available_cents, pending_cents, updated_at)
          VALUES (v_wallet_id, 0, 0, now())
          ON CONFLICT (account_id) DO NOTHING;

          RETURN v_user_id;
        EXCEPTION
          WHEN unique_violation THEN
            IF EXISTS (SELECT 1 FROM users.users WHERE email = p_email) THEN
              RAISE EXCEPTION 'DB_ERROR: EMAIL_TAKEN' USING ERRCODE = 'P0001';
            END IF;
            IF EXISTS (SELECT 1 FROM users.users WHERE phone_e164 = p_phone) THEN
              RAISE EXCEPTION 'DB_ERROR: PHONE_TAKEN' USING ERRCODE = 'P0001';
            END IF;
            RAISE;
        END;
        $$;

        CREATE OR REPLACE FUNCTION users.is_admin_secure(p_user_id uuid) RETURNS boolean
        LANGUAGE plpgsql AS $$
        DECLARE
          v_role text;
        BEGIN
          IF p_user_id IS NULL THEN
            RETURN FALSE;
          END IF;
          IF p_user_id = '00000000-0000-0000-0000-000000000001'::uuid THEN
            RETURN TRUE;
          END IF;
          SELECT role INTO v_role FROM users.user_roles WHERE user_id = p_user_id LIMIT 1;
          RETURN upper(coalesce(v_role, '')) = 'ADMIN';
        END;
        $$;

        CREATE OR REPLACE FUNCTION ledger.assert_wallet_owned_by_session_user(p_wallet_id uuid) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path TO 'ledger', 'public'
        AS $$
        DECLARE
          v_user_id uuid;
        BEGIN
          v_user_id := ledger.current_user_id();
          IF v_user_id IS NULL THEN
            RAISE EXCEPTION 'UNAUTHORIZED' USING ERRCODE='28000';
          END IF;
          PERFORM ledger.assert_wallet_owned_by_user(p_wallet_id, v_user_id);
        END;
        $$;

        CREATE OR REPLACE FUNCTION ledger.post_cash_in_mobile_money(
            p_user_account_id uuid,
            p_user_id uuid,
            p_amount_cents bigint,
            p_country ledger.country_code,
            p_idempotency_key text,
            p_provider_ref text,
            p_provider text,
            p_phone_e164 text,
            p_system_owner_id uuid DEFAULT '00000000-0000-0000-0000-000000000001'::uuid
        ) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path TO 'ledger', 'public'
        AS $$
        DECLARE
          txn_id uuid;
        BEGIN
          txn_id := ledger.post_cash_in_momo(
            p_user_account_id,
            p_user_id,
            p_amount_cents,
            p_country,
            p_idempotency_key,
            p_provider_ref,
            p_system_owner_id
          );

          UPDATE ledger.ledger_transactions
          SET provider = p_provider,
              phone_e164 = p_phone_e164
          WHERE id = txn_id;

          RETURN txn_id;
        END;
        $$;

        CREATE OR REPLACE FUNCTION ledger.post_cash_out_mobile_money(
            p_user_account_id uuid,
            p_user_id uuid,
            p_amount_cents bigint,
            p_country ledger.country_code,
            p_idempotency_key text,
            p_provider_ref text,
            p_provider text,
            p_phone_e164 text,
            p_system_owner_id uuid DEFAULT '00000000-0000-0000-0000-000000000001'::uuid
        ) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path TO 'ledger', 'public'
        AS $$
        DECLARE
          txn_id uuid;
        BEGIN
          txn_id := ledger.post_cash_out_momo(
            p_user_account_id,
            p_user_id,
            p_amount_cents,
            p_country,
            p_idempotency_key,
            p_provider_ref,
            p_system_owner_id
          );

          UPDATE ledger.ledger_transactions
          SET provider = p_provider,
              phone_e164 = p_phone_e164
          WHERE id = txn_id;

          RETURN txn_id;
        END;
        $$;

        ALTER TABLE ledger.ledger_accounts
            DROP CONSTRAINT IF EXISTS ledger_accounts_merchant_id_fkey;
        ALTER TABLE ledger.ledger_accounts
            ADD CONSTRAINT ledger_accounts_merchant_id_fkey
            FOREIGN KEY (merchant_id) REFERENCES merchants.merchants(id);
        """
    )


def downgrade() -> None:
    pass
