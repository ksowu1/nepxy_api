--
-- PostgreSQL database dump
--

\restrict M0CO4ow6DDcoG18gcgxTeXNzkBgWIJHJkWC100HLbxmF6phmyXXd0tyM4mVor4N

-- Dumped from database version 18.1
-- Dumped by pg_dump version 18.1

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: app; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA app;


--
-- Name: audit; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA audit;

--
-- Name: auth; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA auth;


--
-- Name: kyc; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA kyc;


--
-- Name: ledger; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA ledger;


--
-- Name: limits; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA limits;


--
-- Name: merchants; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA merchants;


--
-- Name: users; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA users;

--
-- Name: rails; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA rails;

--
-- Name: rail_type; Type: TYPE; Schema: rails; Owner: -
--

CREATE TYPE rails.rail_type AS ENUM (
    'INTERNAL',
    'MOBILE_MONEY'
);


--
-- Name: country_code; Type: TYPE; Schema: ledger; Owner: -
--

CREATE TYPE ledger.country_code AS ENUM (
    'TG',
    'BJ',
    'BF',
    'ML',
    'GH'
);


--
-- Name: entry_dc; Type: TYPE; Schema: ledger; Owner: -
--

CREATE TYPE ledger.entry_dc AS ENUM (
    'DEBIT',
    'CREDIT'
);


--
-- Name: party_type; Type: TYPE; Schema: ledger; Owner: -
--

CREATE TYPE ledger.party_type AS ENUM (
    'USER',
    'MERCHANT',
    'SYSTEM'
);


--
-- Name: txn_status; Type: TYPE; Schema: ledger; Owner: -
--

CREATE TYPE ledger.txn_status AS ENUM (
    'PENDING',
    'POSTED',
    'FAILED',
    'REVERSED',
    'CANCELLED'
);


--
-- Name: get_user_tier(uuid); Type: FUNCTION; Schema: kyc; Owner: -
--

CREATE FUNCTION kyc.get_user_tier(p_user_id uuid) RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
  t INT;
BEGIN
  SELECT tier INTO t
  FROM kyc.kyc_profiles
  WHERE user_id = p_user_id;

  RETURN COALESCE(t, 1);
END;
$$;


--
-- Name: actor_user_id(); Type: FUNCTION; Schema: ledger; Owner: -
--

CREATE FUNCTION ledger.actor_user_id() RETURNS uuid
    LANGUAGE sql STABLE
    AS $$
  SELECT NULLIF(current_setting('app.user_id', true), '')::uuid;
$$;


--
-- Name: apply_balance_delta(uuid, bigint); Type: FUNCTION; Schema: ledger; Owner: -
--

CREATE FUNCTION ledger.apply_balance_delta(p_account_id uuid, p_delta bigint) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
  INSERT INTO ledger.wallet_balances(account_id, available_cents, pending_cents, updated_at)
  VALUES (p_account_id, p_delta, 0, now())
  ON CONFLICT (account_id)
  DO UPDATE SET
    available_cents = ledger.wallet_balances.available_cents + EXCLUDED.available_cents,
    updated_at = now();
END;
$$;


--
-- Name: assert_is_merchant_wallet(uuid); Type: FUNCTION; Schema: ledger; Owner: -
--

CREATE FUNCTION ledger.assert_is_merchant_wallet(p_wallet_id uuid) RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
  v_owner_type text;
  v_acct_type text;
BEGIN
  SELECT a.owner_type::text, a.account_type::text
  INTO v_owner_type, v_acct_type
  FROM ledger.ledger_accounts a
  WHERE a.id = p_wallet_id;

  IF v_owner_type IS NULL THEN
    RAISE EXCEPTION 'MERCHANT_WALLET_NOT_FOUND'
      USING ERRCODE = 'P0001';
  END IF;

  IF v_acct_type <> 'WALLET' THEN
    RAISE EXCEPTION 'MERCHANT_WALLET_NOT_FOUND'
      USING ERRCODE = 'P0001';
  END IF;

  IF v_owner_type <> 'MERCHANT' THEN
    RAISE EXCEPTION 'NOT_A_MERCHANT_WALLET'
      USING ERRCODE = 'P0001';
  END IF;
END;
$$;


--
-- Name: assert_is_wallet(uuid); Type: FUNCTION; Schema: ledger; Owner: -
--

CREATE FUNCTION ledger.assert_is_wallet(p_account_id uuid) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'ledger', 'public'
    AS $$
DECLARE
  v_type text;
BEGIN
  SELECT account_type::text
    INTO v_type
  FROM ledger.ledger_accounts
  WHERE id = p_account_id;

  IF NOT FOUND OR v_type <> 'WALLET' THEN
    RAISE EXCEPTION 'WALLET_NOT_FOUND'
      USING ERRCODE = 'P0002';
  END IF;
END;
$$;


--
-- Name: assert_merchant_wallet(uuid); Type: FUNCTION; Schema: ledger; Owner: -
--

CREATE FUNCTION ledger.assert_merchant_wallet(p_wallet_id uuid) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'ledger', 'public'
    AS $$
DECLARE
  v_owner_type text;
  v_account_type text;
BEGIN
  SELECT owner_type::text, account_type::text
    INTO v_owner_type, v_account_type
  FROM ledger.ledger_accounts
  WHERE id = p_wallet_id;

  IF NOT FOUND OR v_account_type <> 'WALLET' THEN
    RAISE EXCEPTION 'MERCHANT_WALLET_NOT_FOUND'
      USING ERRCODE = 'P0002';
  END IF;

  IF v_owner_type <> 'MERCHANT' THEN
    RAISE EXCEPTION 'NOT_A_MERCHANT_WALLET'
      USING ERRCODE = 'P0001';
  END IF;
END;
$$;


--
-- Name: assert_wallet_owned_by_current_user(uuid); Type: FUNCTION; Schema: ledger; Owner: -
--

CREATE FUNCTION ledger.assert_wallet_owned_by_current_user(p_wallet_id uuid) RETURNS void
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

  IF NOT EXISTS (
    SELECT 1
    FROM ledger.ledger_accounts
    WHERE id = p_wallet_id
      AND owner_type = 'USER'
      AND owner_id = v_user_id
      AND account_type = 'WALLET'
  ) THEN
    RAISE EXCEPTION 'WALLET_NOT_OWNED' USING ERRCODE='42501';
  END IF;
END;
$$;

--
-- Name: assert_wallet_owned_by_session_user(uuid); Type: FUNCTION; Schema: ledger; Owner: -
--

CREATE FUNCTION ledger.assert_wallet_owned_by_session_user(p_wallet_id uuid) RETURNS void
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


--
-- Name: assert_wallet_owned_by_user(uuid, uuid); Type: FUNCTION; Schema: ledger; Owner: -
--

CREATE FUNCTION ledger.assert_wallet_owned_by_user(p_wallet_id uuid, p_user_id uuid) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'ledger', 'public'
    AS $$
DECLARE
  v_owner_type text;
  v_owner_id uuid;
  v_account_type text;
BEGIN
  SELECT owner_type::text, owner_id, account_type::text
    INTO v_owner_type, v_owner_id, v_account_type
  FROM ledger.ledger_accounts
  WHERE id = p_wallet_id;

  IF NOT FOUND OR v_account_type <> 'WALLET' THEN
    RAISE EXCEPTION 'WALLET_NOT_FOUND'
      USING ERRCODE = 'P0002';
  END IF;

  IF v_owner_type <> 'USER' OR v_owner_id <> p_user_id THEN
    RAISE EXCEPTION 'WALLET_NOT_OWNED'
      USING ERRCODE = 'P0001';
  END IF;
END;
$$;


--
-- Name: current_user_id(); Type: FUNCTION; Schema: ledger; Owner: -
--

CREATE FUNCTION ledger.current_user_id() RETURNS uuid
    LANGUAGE sql STABLE
    AS $$
  SELECT nullif(current_setting('app.user_id', true), '')::uuid
$$;


--
-- Name: enforce_balanced_transaction(); Type: FUNCTION; Schema: ledger; Owner: -
--

CREATE FUNCTION ledger.enforce_balanced_transaction() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  tid  UUID;
  deb  BIGINT;
  cred BIGINT;
BEGIN
  tid := COALESCE(NEW.transaction_id, OLD.transaction_id);

  SELECT
    COALESCE(SUM(CASE WHEN dc='DEBIT'  THEN amount_cents ELSE 0 END), 0),
    COALESCE(SUM(CASE WHEN dc='CREDIT' THEN amount_cents ELSE 0 END), 0)
  INTO deb, cred
  FROM ledger.ledger_entries
  WHERE transaction_id = tid;

  IF deb <> cred THEN
    RAISE EXCEPTION 'Unbalanced transaction % (debit %, credit %)', tid, deb, cred;
  END IF;

  RETURN COALESCE(NEW, OLD);
END;
$$;


--
-- Name: get_available_balance(uuid); Type: FUNCTION; Schema: ledger; Owner: -
--

CREATE FUNCTION ledger.get_available_balance(p_account_id uuid) RETURNS bigint
    LANGUAGE plpgsql
    AS $$
DECLARE
  bal BIGINT;
BEGIN
  SELECT available_cents INTO bal
  FROM ledger.wallet_balances
  WHERE account_id = p_account_id;

  IF bal IS NOT NULL THEN
    RETURN bal;
  END IF;

  SELECT COALESCE(SUM(
    CASE
      WHEN e.dc='CREDIT' THEN e.amount_cents
      WHEN e.dc='DEBIT'  THEN -e.amount_cents
      ELSE 0
    END
  ), 0)
  INTO bal
  FROM ledger.ledger_entries e
  JOIN ledger.ledger_transactions t ON t.id = e.transaction_id
  WHERE e.account_id = p_account_id
    AND t.status IN ('POSTED','REVERSED'); -- adjust if you want to exclude REVERSED

  RETURN COALESCE(bal, 0);
END;
$$;


--
-- Name: get_available_balance_secure(uuid); Type: FUNCTION; Schema: ledger; Owner: -
--

CREATE FUNCTION ledger.get_available_balance_secure(p_account_id uuid) RETURNS bigint
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'ledger', 'app', 'public'
    AS $$
DECLARE
  v_user_id uuid;
BEGIN
  v_user_id := ledger.actor_user_id();
  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'UNAUTHORIZED' USING ERRCODE = '28000';
  END IF;

  PERFORM ledger.assert_wallet_owned_by_user(p_account_id, v_user_id);
  RETURN ledger.get_available_balance(p_account_id);
END;
$$;


--
-- Name: get_my_wallets_secure(); Type: FUNCTION; Schema: ledger; Owner: -
--

CREATE FUNCTION ledger.get_my_wallets_secure() RETURNS TABLE(wallet_id uuid, owner_id uuid, owner_type text, currency text, country text, account_type text)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'ledger', 'public'
    AS $$
DECLARE
  v_user_id uuid;
BEGIN
  v_user_id := current_setting('app.user_id', true)::uuid;

  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'DB_ERROR: UNAUTHORIZED_WALLET_ACCESS';
  END IF;

  RETURN QUERY
  SELECT
    a.id,
    a.owner_id,
    a.owner_type::text,
    a.currency::text,
    a.country::text,
    a.account_type::text
  FROM ledger.ledger_accounts a
  WHERE a.owner_type = 'USER'
    AND a.owner_id = v_user_id
    AND a.account_type = 'WALLET'
  ORDER BY a.created_at DESC;
END;
$$;


--
-- Name: get_system_account(uuid, ledger.country_code, text, text); Type: FUNCTION; Schema: ledger; Owner: -
--

CREATE FUNCTION ledger.get_system_account(p_system_owner_id uuid, p_country ledger.country_code, p_account_type text, p_currency text DEFAULT 'XOF'::text) RETURNS uuid
    LANGUAGE plpgsql
    AS $$
DECLARE
  aid UUID;
BEGIN
  SELECT id INTO aid
  FROM ledger.ledger_accounts
  WHERE owner_type='SYSTEM'
    AND owner_id=p_system_owner_id
    AND country=p_country
    AND currency=p_currency
    AND account_type=p_account_type
  LIMIT 1;

  IF aid IS NOT NULL THEN
    RETURN aid;
  END IF;

  INSERT INTO ledger.ledger_accounts(owner_type, owner_id, country, currency, account_type)
  VALUES ('SYSTEM', p_system_owner_id, p_country, p_currency, p_account_type)
  RETURNING id INTO aid;

  RETURN aid;
END;
$$;


--
-- Name: get_wallet_activity(uuid, integer, text); Type: FUNCTION; Schema: ledger; Owner: -
--

CREATE FUNCTION ledger.get_wallet_activity(p_account_id uuid, p_limit integer DEFAULT 50, p_cursor text DEFAULT NULL::text) RETURNS TABLE(transaction_id uuid, created_at timestamp with time zone, direction text, amount_cents bigint, net_cents bigint, memo text)
    LANGUAGE plpgsql
    AS $$
DECLARE
  cursor_ts  timestamptz;
  cursor_txn uuid;
BEGIN
  IF p_limit IS NULL OR p_limit <= 0 OR p_limit > 200 THEN
    p_limit := 50;
  END IF;

  IF p_cursor IS NOT NULL THEN
    cursor_ts  := split_part(p_cursor, '|', 1)::timestamptz;
    cursor_txn := split_part(p_cursor, '|', 2)::uuid;
  END IF;

  RETURN QUERY
  WITH per_txn AS (
    SELECT
      e.transaction_id,
      MAX(e.created_at) AS created_at,
      (
        SUM(CASE WHEN e.dc = 'CREDIT' THEN e.amount_cents ELSE 0 END)
        - SUM(CASE WHEN e.dc = 'DEBIT'  THEN e.amount_cents ELSE 0 END)
      )::bigint AS net_cents,
      LEFT(
        COALESCE(
          NULLIF(string_agg(DISTINCT COALESCE(e.memo,''), ' | '), ''),
          'Transaction'
        ),
        240
      ) AS memo_base
    FROM ledger.ledger_entries e
    WHERE e.account_id = p_account_id
    GROUP BY e.transaction_id
  )
  SELECT
    p.transaction_id,
    p.created_at,
    CASE
      WHEN p.net_cents > 0 THEN 'IN'
      WHEN p.net_cents < 0 THEN 'OUT'
      ELSE 'FLAT'
    END AS direction,
    ABS(p.net_cents)::bigint AS amount_cents,
    p.net_cents,
    COALESCE(NULLIF(tm.display_text,''), p.memo_base) AS memo
  FROM per_txn p
  LEFT JOIN app.transaction_meta tm
    ON tm.transaction_id = p.transaction_id
  WHERE
    p_cursor IS NULL
    OR (p.created_at, p.transaction_id) < (cursor_ts, cursor_txn)
  ORDER BY p.created_at DESC, p.transaction_id DESC
  LIMIT p_limit;
END;
$$;


--
-- Name: get_wallet_activity_secure(uuid, integer, text); Type: FUNCTION; Schema: ledger; Owner: -
--

CREATE FUNCTION ledger.get_wallet_activity_secure(p_account_id uuid, p_limit integer DEFAULT 50, p_cursor text DEFAULT NULL::text) RETURNS TABLE(transaction_id uuid, created_at timestamp with time zone, direction text, amount_cents bigint, net_cents bigint, memo text)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'ledger', 'app', 'public'
    AS $$
DECLARE
  v_user_id uuid;
BEGIN
  v_user_id := ledger.actor_user_id();

  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'UNAUTHORIZED' USING ERRCODE = '28000';
  END IF;

  -- ✅ DB-level ownership guarantee
  PERFORM ledger.assert_wallet_owned_by_user(p_account_id, v_user_id);

  RETURN QUERY
  SELECT * FROM ledger.get_wallet_activity(p_account_id, p_limit, p_cursor);
END;
$$;


--
-- Name: get_wallet_transactions(uuid, integer, text); Type: FUNCTION; Schema: ledger; Owner: -
--

CREATE FUNCTION ledger.get_wallet_transactions(p_account_id uuid, p_limit integer DEFAULT 50, p_cursor text DEFAULT NULL::text) RETURNS TABLE(entry_id uuid, transaction_id uuid, dc text, amount_cents bigint, memo text, created_at timestamp with time zone)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'ledger', 'public'
    AS $$
DECLARE
  cursor_ts  timestamptz;
  cursor_id  uuid;
BEGIN
  IF p_limit IS NULL OR p_limit <= 0 OR p_limit > 200 THEN
    p_limit := 50;
  END IF;

  IF p_cursor IS NOT NULL THEN
    cursor_ts := split_part(p_cursor, '|', 1)::timestamptz;
    cursor_id := split_part(p_cursor, '|', 2)::uuid;
  END IF;

  RETURN QUERY
  SELECT
    e.id AS entry_id,                -- ✅ FIX
    e.transaction_id,
    e.dc::text,
    e.amount_cents,
    e.memo,
    e.created_at
  FROM ledger.ledger_entries e
  WHERE e.account_id = p_account_id
    AND (
      p_cursor IS NULL
      OR (e.created_at, e.id) < (cursor_ts, cursor_id)   -- ✅ cursor uses id too
    )
  ORDER BY e.created_at DESC, e.id DESC
  LIMIT p_limit;
END;
$$;


--
-- Name: get_wallet_transactions_secure(uuid, integer, text); Type: FUNCTION; Schema: ledger; Owner: -
--

CREATE FUNCTION ledger.get_wallet_transactions_secure(p_account_id uuid, p_limit integer DEFAULT 50, p_cursor text DEFAULT NULL::text) RETURNS TABLE(entry_id uuid, transaction_id uuid, dc text, amount_cents bigint, memo text, created_at timestamp with time zone)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'ledger', 'app', 'public'
    AS $$
DECLARE
  v_user_id uuid;
BEGIN
  v_user_id := ledger.actor_user_id();

  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'UNAUTHORIZED' USING ERRCODE = '28000';
  END IF;

  PERFORM ledger.assert_wallet_owned_by_user(p_account_id, v_user_id);

  RETURN QUERY
  SELECT * FROM ledger.get_wallet_transactions(p_account_id, p_limit, p_cursor);
END;
$$;


--
-- Name: post_cash_in_momo(uuid, uuid, bigint, ledger.country_code, text, text, uuid); Type: FUNCTION; Schema: ledger; Owner: -
--

CREATE FUNCTION ledger.post_cash_in_momo(p_user_account_id uuid, p_user_id uuid, p_amount_cents bigint, p_country ledger.country_code, p_idempotency_key text, p_provider_ref text, p_system_owner_id uuid DEFAULT '00000000-0000-0000-0000-000000000001'::uuid) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'ledger', 'public'
    AS $$
DECLARE
  txn_id UUID;
  settlement_acct UUID;
BEGIN
  IF p_amount_cents <= 0 THEN
    RAISE EXCEPTION 'Amount must be > 0';
  END IF;

  -- ✅ DB-level ownership check FIRST
  PERFORM ledger.assert_wallet_owned_by_user(p_user_account_id, p_user_id);

  -- Idempotency
  SELECT id INTO txn_id
  FROM ledger.ledger_transactions
  WHERE idempotency_key = p_idempotency_key
  LIMIT 1;

  IF txn_id IS NOT NULL THEN
    RETURN txn_id;
  END IF;

  settlement_acct := ledger.get_system_account(p_system_owner_id, p_country, 'SETTLEMENT', 'XOF');

  INSERT INTO ledger.ledger_transactions(
    type, status, country, currency, amount_cents,
    description, idempotency_key, rail, external_ref, created_by
  )
  VALUES (
    'CASHIN','POSTED',p_country,'XOF',p_amount_cents,
    'MoMo cash-in', p_idempotency_key,'MOBILE_MONEY',p_provider_ref,p_user_id
  )
  RETURNING id INTO txn_id;

  INSERT INTO ledger.ledger_entries(transaction_id, account_id, dc, amount_cents, memo)
  VALUES
    (txn_id, settlement_acct,   'DEBIT',  p_amount_cents, 'Settlement debit (provider owes)'),
    (txn_id, p_user_account_id, 'CREDIT', p_amount_cents, 'Wallet credit');

  PERFORM ledger.apply_balance_delta(p_user_account_id, +(p_amount_cents));

  INSERT INTO audit.audit_logs(actor_user_id, action, entity_type, entity_id, metadata)
  VALUES (
    p_user_id, 'CASHIN_POSTED', 'ledger_transaction', txn_id,
    jsonb_build_object('amount_cents',p_amount_cents,'provider_ref',p_provider_ref)
  );

  INSERT INTO app.transaction_meta(
    transaction_id, tx_type, sender_user_id, provider_ref, description, display_text
  )
  VALUES (
    txn_id,
    'CASH_IN_MOMO',
    p_user_id,
    p_provider_ref,
    'Cash in',
    CASE
      WHEN p_provider_ref IS NOT NULL AND length(trim(p_provider_ref)) > 0
        THEN 'Cash in (' || p_provider_ref || ')'
      ELSE 'Cash in (MoMo)'
    END
  )
  ON CONFLICT (transaction_id) DO NOTHING;

  RETURN txn_id;

EXCEPTION
  WHEN unique_violation THEN
    SELECT id INTO txn_id
    FROM ledger.ledger_transactions
    WHERE idempotency_key = p_idempotency_key
    LIMIT 1;
    RETURN txn_id;
END;
$$;


--
-- Name: post_cash_out_momo(uuid, uuid, bigint, ledger.country_code, text, text, uuid); Type: FUNCTION; Schema: ledger; Owner: -
--

CREATE FUNCTION ledger.post_cash_out_momo(p_user_account_id uuid, p_user_id uuid, p_amount_cents bigint, p_country ledger.country_code, p_idempotency_key text, p_provider_ref text, p_system_owner_id uuid DEFAULT '00000000-0000-0000-0000-000000000001'::uuid) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'ledger', 'public'
    AS $$
DECLARE
  txn_id UUID;
  fee_cents BIGINT;
  user_bal BIGINT;
  tier INT;
  lim RECORD;
  today_start TIMESTAMPTZ := date_trunc('day', now());
  used_today BIGINT;
  settlement_acct UUID;
  fee_acct UUID;
  v_actor_user_id uuid;
BEGIN
  PERFORM set_config('search_path', 'ledger,public', true);
  v_actor_user_id := ledger.current_user_id();

  IF p_amount_cents <= 0 THEN
    RAISE EXCEPTION 'Amount must be > 0';
  END IF;

  -- ✅ DB-level enforcement
  PERFORM ledger.assert_wallet_owned_by_session_user(p_user_account_id);

  -- Idempotency
  SELECT id INTO txn_id
  FROM ledger.ledger_transactions
  WHERE idempotency_key = p_idempotency_key
  LIMIT 1;

  IF txn_id IS NOT NULL THEN
    RETURN txn_id;
  END IF;

  fee_cents := limits.compute_fee('CASHOUT', p_country, p_amount_cents);
  user_bal := ledger.get_available_balance(p_user_account_id);

  IF user_bal < (p_amount_cents + fee_cents) THEN
    RAISE EXCEPTION 'Insufficient funds';
  END IF;

  -- Cash-out limit check
  tier := kyc.get_user_tier(v_actor_user_id);
  SELECT * INTO lim FROM limits.get_limits_for_tier(tier);
  IF lim.daily_cashout_cents IS NULL THEN
    RAISE EXCEPTION 'No cashout limit configured for KYC tier %', tier;
  END IF;

  used_today := limits.sum_debits_for_period(
    p_user_account_id,
    ARRAY['CASHOUT']::TEXT[],
    today_start,
    today_start + interval '1 day'
  );

  IF used_today + p_amount_cents > lim.daily_cashout_cents THEN
    RAISE EXCEPTION 'Daily cashout limit exceeded';
  END IF;

  settlement_acct := ledger.get_system_account(p_system_owner_id, p_country, 'SETTLEMENT', 'XOF');

  INSERT INTO ledger.ledger_transactions(
    type, status, country, currency, amount_cents,
    description, idempotency_key, rail, external_ref, created_by
  )
  VALUES (
    'CASHOUT','POSTED',p_country,'XOF',p_amount_cents,
    'MoMo cash-out', p_idempotency_key,'MOBILE_MONEY',p_provider_ref, v_actor_user_id
  )
  RETURNING id INTO txn_id;

  -- Entries
  INSERT INTO ledger.ledger_entries(transaction_id, account_id, dc, amount_cents, memo)
  VALUES
    (txn_id, p_user_account_id,'DEBIT',  p_amount_cents + fee_cents, 'Wallet debit incl fee'),
    (txn_id, settlement_acct,  'CREDIT', p_amount_cents,            'Settlement credit (payout due)');

  -- Fee
  IF fee_cents > 0 THEN
    fee_acct := ledger.get_system_account(p_system_owner_id, p_country, 'FEE_REVENUE', 'XOF');

    INSERT INTO ledger.ledger_entries(transaction_id, account_id, dc, amount_cents, memo)
    VALUES (txn_id, fee_acct, 'CREDIT', fee_cents, 'Cashout fee');

    PERFORM ledger.apply_balance_delta(fee_acct, +(fee_cents));
  END IF;

  -- Cache balances
  PERFORM ledger.apply_balance_delta(p_user_account_id, -(p_amount_cents + fee_cents));

  -- Audit
  INSERT INTO audit.audit_logs(actor_user_id, action, entity_type, entity_id, metadata)
  VALUES (
    v_actor_user_id, 'CASHOUT_POSTED', 'ledger_transaction', txn_id,
    jsonb_build_object('amount_cents',p_amount_cents,'fee_cents',fee_cents,'provider_ref',p_provider_ref)
  );

  -- Meta
  INSERT INTO app.transaction_meta(
    transaction_id, tx_type, sender_user_id, provider_ref, description, display_text
  )
  VALUES (
    txn_id,
    'CASH_OUT_MOMO',
    v_actor_user_id,
    p_provider_ref,
    'Cash out',
    CASE
      WHEN p_provider_ref IS NOT NULL AND length(trim(p_provider_ref)) > 0
        THEN 'Cash out (' || p_provider_ref || ')'
      ELSE 'Cash out (MoMo)'
    END
  )
  ON CONFLICT (transaction_id) DO NOTHING;

  RETURN txn_id;

EXCEPTION
  WHEN unique_violation THEN
    SELECT id INTO txn_id FROM ledger.ledger_transactions WHERE idempotency_key=p_idempotency_key LIMIT 1;
  RETURN txn_id;
END;
$$;

--
-- Name: post_cash_in_mobile_money(uuid, uuid, bigint, ledger.country_code, text, text, text, text, uuid); Type: FUNCTION; Schema: ledger; Owner: -
--

CREATE FUNCTION ledger.post_cash_in_mobile_money(
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

--
-- Name: post_cash_out_mobile_money(uuid, uuid, bigint, ledger.country_code, text, text, text, text, uuid); Type: FUNCTION; Schema: ledger; Owner: -
--

CREATE FUNCTION ledger.post_cash_out_mobile_money(
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


--
-- Name: post_merchant_pay(uuid, uuid, uuid, bigint, ledger.country_code, text, text, uuid); Type: FUNCTION; Schema: ledger; Owner: -
--

CREATE FUNCTION ledger.post_merchant_pay(p_payer_account_id uuid, p_payer_user_id uuid, p_merchant_account_id uuid, p_amount_cents bigint, p_country ledger.country_code, p_idempotency_key text, p_note text DEFAULT NULL::text, p_system_owner_id uuid DEFAULT '00000000-0000-0000-0000-000000000001'::uuid) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'ledger', 'public'
    AS $$
DECLARE
  txn_id UUID;
  fee_cents BIGINT;
  payer_bal BIGINT;
  tier INT;
  lim RECORD;
  today_start TIMESTAMPTZ := date_trunc('day', now());
  month_start TIMESTAMPTZ := date_trunc('month', now());
  used_today BIGINT;
  used_month BIGINT;
  fee_acct UUID;

  v_actor_user_id uuid;
  merchant_name text;
BEGIN
  PERFORM set_config('search_path', 'ledger,public', true);
  v_actor_user_id := ledger.current_user_id();

  IF p_amount_cents <= 0 THEN
    RAISE EXCEPTION 'Amount must be > 0';
  END IF;

  -- ✅ DB-level enforcement
  PERFORM ledger.assert_wallet_owned_by_session_user(p_payer_account_id);
  PERFORM ledger.assert_merchant_wallet(p_merchant_account_id);

  -- Idempotency
  SELECT id INTO txn_id
  FROM ledger.ledger_transactions
  WHERE idempotency_key = p_idempotency_key
  LIMIT 1;

  IF txn_id IS NOT NULL THEN
    RETURN txn_id;
  END IF;

  fee_cents := limits.compute_fee('MERCHANT_PAY', p_country, p_amount_cents);
  payer_bal := ledger.get_available_balance(p_payer_account_id);

  IF payer_bal < (p_amount_cents + fee_cents) THEN
    RAISE EXCEPTION 'Insufficient funds';
  END IF;

  -- Limits (counts as send)
  tier := kyc.get_user_tier(v_actor_user_id);
  SELECT * INTO lim FROM limits.get_limits_for_tier(tier);
  IF lim.daily_send_cents IS NULL THEN
    RAISE EXCEPTION 'No limits configured for KYC tier %', tier;
  END IF;

  used_today := limits.sum_debits_for_period(
    p_payer_account_id,
    ARRAY['P2P','MERCHANT_PAY']::TEXT[],
    today_start,
    today_start + interval '1 day'
  );

  used_month := limits.sum_debits_for_period(
    p_payer_account_id,
    ARRAY['P2P','MERCHANT_PAY']::TEXT[],
    month_start,
    month_start + interval '1 month'
  );

  IF used_today + p_amount_cents > lim.daily_send_cents THEN
    RAISE EXCEPTION 'Daily send limit exceeded';
  END IF;

  IF used_month + p_amount_cents > lim.monthly_send_cents THEN
    RAISE EXCEPTION 'Monthly send limit exceeded';
  END IF;

  -- Create transaction
  INSERT INTO ledger.ledger_transactions(
    type, status, country, currency, amount_cents, description,
    idempotency_key, rail, created_by
  )
  VALUES (
    'MERCHANT_PAY','POSTED',p_country,'XOF',p_amount_cents,
    COALESCE(p_note,'Merchant payment'),
    p_idempotency_key,'INTERNAL', v_actor_user_id
  )
  RETURNING id INTO txn_id;

  -- Entries
  INSERT INTO ledger.ledger_entries(transaction_id, account_id, dc, amount_cents, memo)
  VALUES
    (txn_id, p_payer_account_id,     'DEBIT',  p_amount_cents + fee_cents, 'Merchant pay debit incl fee'),
    (txn_id, p_merchant_account_id,  'CREDIT', p_amount_cents,            'Merchant pay credit');

  -- Fee entry
  IF fee_cents > 0 THEN
    fee_acct := ledger.get_system_account(p_system_owner_id, p_country, 'FEE_REVENUE', 'XOF');

    INSERT INTO ledger.ledger_entries(transaction_id, account_id, dc, amount_cents, memo)
    VALUES (txn_id, fee_acct, 'CREDIT', fee_cents, 'Merchant pay fee');

    PERFORM ledger.apply_balance_delta(fee_acct, +(fee_cents));
  END IF;

  -- Cache balances
  PERFORM ledger.apply_balance_delta(p_payer_account_id,    -(p_amount_cents + fee_cents));
  PERFORM ledger.apply_balance_delta(p_merchant_account_id, +(p_amount_cents));

  -- Optional: merchant display name from a merchants table/view (you have a "merchants" view)
  SELECT name INTO merchant_name
  FROM merchants.merchants
  WHERE wallet_id = p_merchant_account_id
  LIMIT 1;

  -- Audit
  INSERT INTO audit.audit_logs(actor_user_id, action, entity_type, entity_id, metadata)
  VALUES (
    v_actor_user_id, 'MERCHANT_PAY_POSTED', 'ledger_transaction', txn_id,
    jsonb_build_object('amount_cents',p_amount_cents,'fee_cents',fee_cents)
  );

  -- Meta
  INSERT INTO app.transaction_meta(
    transaction_id, tx_type, description, sender_user_id,
    merchant_wallet_id, merchant_name, display_text
  )
  VALUES (
    txn_id,
    'MERCHANT_PAY',
    COALESCE(p_note,'Merchant payment'),
    v_actor_user_id,
    p_merchant_account_id,
    merchant_name,
    CASE
      WHEN merchant_name IS NOT NULL AND length(trim(merchant_name)) > 0
        THEN 'Paid ' || merchant_name
      ELSE 'Paid merchant'
    END
  )
  ON CONFLICT (transaction_id) DO NOTHING;

  RETURN txn_id;

EXCEPTION
  WHEN unique_violation THEN
    SELECT id INTO txn_id FROM ledger.ledger_transactions WHERE idempotency_key=p_idempotency_key LIMIT 1;
    RETURN txn_id;
END;
$$;


--
-- Name: post_p2p_transfer(uuid, uuid, uuid, bigint, ledger.country_code, text, text, uuid); Type: FUNCTION; Schema: ledger; Owner: -
--

CREATE FUNCTION ledger.post_p2p_transfer(p_sender_account_id uuid, p_sender_user_id uuid, p_receiver_account_id uuid, p_amount_cents bigint, p_country ledger.country_code, p_idempotency_key text, p_description text DEFAULT NULL::text, p_system_owner_id uuid DEFAULT '00000000-0000-0000-0000-000000000001'::uuid) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'ledger', 'public'
    AS $$
DECLARE
  txn_id UUID;
  fee_cents BIGINT;
  sender_bal BIGINT;
  tier INT;
  lim RECORD;
  today_start TIMESTAMPTZ := date_trunc('day', now());
  month_start TIMESTAMPTZ := date_trunc('month', now());
  used_today BIGINT;
  used_month BIGINT;
  fee_acct UUID;

  v_actor_user_id uuid;        -- from session
  receiver_user_id UUID;
BEGIN
  -- Ensure stable search_path even if caller changes it
  PERFORM set_config('search_path', 'ledger,public', true);

  -- DB-level actor (comes from set_config('app.user_id', ...))
  v_actor_user_id := ledger.current_user_id();

  IF p_amount_cents <= 0 THEN
    RAISE EXCEPTION 'Amount must be > 0';
  END IF;

  -- ✅ DB-level ownership enforcement
  PERFORM ledger.assert_wallet_owned_by_session_user(p_sender_account_id);
  PERFORM ledger.assert_is_wallet(p_receiver_account_id);

  -- Idempotency
  SELECT id INTO txn_id
  FROM ledger.ledger_transactions
  WHERE idempotency_key = p_idempotency_key
  LIMIT 1;

  IF txn_id IS NOT NULL THEN
    RETURN txn_id;
  END IF;

  fee_cents := limits.compute_fee('P2P', p_country, p_amount_cents);
  sender_bal := ledger.get_available_balance(p_sender_account_id);

  IF sender_bal < (p_amount_cents + fee_cents) THEN
    RAISE EXCEPTION 'Insufficient funds. Need %, have %', (p_amount_cents + fee_cents), sender_bal;
  END IF;

  -- Limits
  tier := kyc.get_user_tier(v_actor_user_id);
  SELECT * INTO lim FROM limits.get_limits_for_tier(tier);
  IF lim.daily_send_cents IS NULL THEN
    RAISE EXCEPTION 'No limits configured for KYC tier %', tier;
  END IF;

  used_today := limits.sum_debits_for_period(
    p_sender_account_id,
    ARRAY['P2P','MERCHANT_PAY']::TEXT[],
    today_start,
    today_start + interval '1 day'
  );

  used_month := limits.sum_debits_for_period(
    p_sender_account_id,
    ARRAY['P2P','MERCHANT_PAY']::TEXT[],
    month_start,
    month_start + interval '1 month'
  );

  IF used_today + p_amount_cents > lim.daily_send_cents THEN
    RAISE EXCEPTION 'Daily send limit exceeded';
  END IF;

  IF used_month + p_amount_cents > lim.monthly_send_cents THEN
    RAISE EXCEPTION 'Monthly send limit exceeded';
  END IF;

  -- Receiver user id (only if receiver wallet is a USER wallet)
  SELECT owner_id INTO receiver_user_id
  FROM ledger.ledger_accounts
  WHERE id = p_receiver_account_id;

  -- Create transaction (created_by must be actor)
  INSERT INTO ledger.ledger_transactions(
    type, status, country, currency, amount_cents, description,
    idempotency_key, rail, created_by
  )
  VALUES (
    'P2P','POSTED',p_country,'XOF',p_amount_cents,
    COALESCE(p_description,'P2P transfer'),
    p_idempotency_key, 'INTERNAL', v_actor_user_id
  )
  RETURNING id INTO txn_id;

  -- Entries
  INSERT INTO ledger.ledger_entries(transaction_id, account_id, dc, amount_cents, memo)
  VALUES
    (txn_id, p_sender_account_id,   'DEBIT',  p_amount_cents + fee_cents, 'P2P debit incl fee'),
    (txn_id, p_receiver_account_id, 'CREDIT', p_amount_cents,            'P2P credit');

  -- Fee entry
  IF fee_cents > 0 THEN
    fee_acct := ledger.get_system_account(p_system_owner_id, p_country, 'FEE_REVENUE', 'XOF');

    INSERT INTO ledger.ledger_entries(transaction_id, account_id, dc, amount_cents, memo)
    VALUES (txn_id, fee_acct, 'CREDIT', fee_cents, 'P2P fee');

    PERFORM ledger.apply_balance_delta(fee_acct, +(fee_cents));
  END IF;

  -- Cache balances
  PERFORM ledger.apply_balance_delta(p_sender_account_id,   -(p_amount_cents + fee_cents));
  PERFORM ledger.apply_balance_delta(p_receiver_account_id, +(p_amount_cents));

  -- Audit
  INSERT INTO audit.audit_logs(actor_user_id, action, entity_type, entity_id, metadata)
  VALUES (
    v_actor_user_id, 'P2P_POSTED', 'ledger_transaction', txn_id,
    jsonb_build_object('amount_cents',p_amount_cents,'fee_cents',fee_cents)
  );

  -- Transaction meta (assumes app.transaction_meta has these columns)
  INSERT INTO app.transaction_meta(
    transaction_id, tx_type, description, sender_user_id, receiver_user_id, display_text
  )
  VALUES (
    txn_id,
    'P2P',
    COALESCE(p_description,'P2P transfer'),
    v_actor_user_id,
    receiver_user_id,
    COALESCE(p_description,'P2P transfer')
  )
  ON CONFLICT (transaction_id) DO NOTHING;

  RETURN txn_id;

EXCEPTION
  WHEN unique_violation THEN
    SELECT id INTO txn_id
    FROM ledger.ledger_transactions
    WHERE idempotency_key = p_idempotency_key
    LIMIT 1;
    RETURN txn_id;
END;
$$;


--
-- Name: compute_fee(text, ledger.country_code, bigint); Type: FUNCTION; Schema: limits; Owner: -
--

CREATE FUNCTION limits.compute_fee(p_applies_to text, p_country ledger.country_code, p_amount_cents bigint) RETURNS bigint
    LANGUAGE plpgsql
    AS $$
DECLARE
  r RECORD;
  raw BIGINT;
  fee BIGINT;
BEGIN
  SELECT *
  INTO r
  FROM limits.fee_rules
  WHERE is_active = TRUE
    AND applies_to = p_applies_to
    AND (country = p_country OR country IS NULL)
  ORDER BY (country IS NULL) ASC, id ASC
  LIMIT 1;

  IF NOT FOUND THEN
    RETURN 0;
  END IF;

  raw := COALESCE(r.fixed_cents,0) + (p_amount_cents * COALESCE(r.pct_bps,0) / 10000);

  fee := GREATEST(raw, COALESCE(r.min_cents,0));

  IF r.max_cents IS NOT NULL THEN
    fee := LEAST(fee, r.max_cents);
  END IF;

  RETURN GREATEST(fee, 0);
END;
$$;


--
-- Name: get_limits_for_tier(integer); Type: FUNCTION; Schema: limits; Owner: -
--

CREATE FUNCTION limits.get_limits_for_tier(p_tier integer) RETURNS TABLE(daily_send_cents bigint, monthly_send_cents bigint, daily_cashout_cents bigint)
    LANGUAGE plpgsql
    AS $$
BEGIN
  RETURN QUERY
  SELECT a.daily_send_cents, a.monthly_send_cents, a.daily_cashout_cents
  FROM limits.account_limits a
  WHERE a.is_active = TRUE AND a.kyc_tier = p_tier
  LIMIT 1;
END;
$$;


--
-- Name: sum_debits_for_period(uuid, text[], timestamp with time zone, timestamp with time zone); Type: FUNCTION; Schema: limits; Owner: -
--

CREATE FUNCTION limits.sum_debits_for_period(p_account_id uuid, p_types text[], p_start timestamp with time zone, p_end timestamp with time zone) RETURNS bigint
    LANGUAGE plpgsql
    AS $$
DECLARE
  s BIGINT;
BEGIN
  SELECT COALESCE(SUM(e.amount_cents),0) INTO s
  FROM ledger.ledger_entries e
  JOIN ledger.ledger_transactions t ON t.id = e.transaction_id
  WHERE e.account_id = p_account_id
    AND e.dc = 'DEBIT'
    AND t.status = 'POSTED'
    AND t.type = ANY(p_types)
    AND t.created_at >= p_start
    AND t.created_at <  p_end;

  RETURN COALESCE(s,0);
END;
$$;

--
-- Name: register_user_secure(text, text, text, ledger.country_code, text); Type: FUNCTION; Schema: users; Owner: -
--

CREATE FUNCTION users.register_user_secure(
    p_email text,
    p_phone text,
    p_full_name text,
    p_country ledger.country_code,
    p_password_hash text
) RETURNS uuid
    LANGUAGE plpgsql
    AS $$
DECLARE
  v_user_id uuid;
  v_wallet_id uuid;
BEGIN
  INSERT INTO users.users (
    email,
    phone_e164,
    full_name,
    country,
    is_active,
    created_at,
    password_hash
  )
  VALUES (
    p_email,
    p_phone,
    p_full_name,
    p_country,
    TRUE,
    now(),
    p_password_hash
  )
  RETURNING id INTO v_user_id;

  INSERT INTO ledger.ledger_accounts (
    owner_type,
    owner_id,
    country,
    currency,
    account_type,
    is_active
  )
  VALUES (
    'USER',
    v_user_id,
    p_country,
    'XOF',
    'WALLET',
    TRUE
  )
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

--
-- Name: is_admin_secure(uuid); Type: FUNCTION; Schema: users; Owner: -
--

CREATE FUNCTION users.is_admin_secure(p_user_id uuid) RETURNS boolean
    LANGUAGE plpgsql
    AS $$
DECLARE
  v_role text;
BEGIN
  IF p_user_id IS NULL THEN
    RETURN FALSE;
  END IF;
  IF p_user_id = '00000000-0000-0000-0000-000000000001'::uuid THEN
    RETURN TRUE;
  END IF;
  SELECT role INTO v_role
  FROM users.user_roles
  WHERE user_id = p_user_id
  LIMIT 1;
  RETURN upper(coalesce(v_role, '')) = 'ADMIN';
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: transaction_meta; Type: TABLE; Schema: app; Owner: -
--

CREATE TABLE app.transaction_meta (
    transaction_id uuid NOT NULL,
    tx_type text NOT NULL,
    description text,
    provider_ref text,
    sender_user_id uuid,
    receiver_user_id uuid,
    merchant_account_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    display_text text NOT NULL,
    CONSTRAINT transaction_meta_tx_type_check CHECK ((tx_type = ANY (ARRAY['P2P'::text, 'MERCHANT_PAY'::text, 'CASH_IN_MOMO'::text, 'CASH_OUT_MOMO'::text])))
);


--
-- Name: users; Type: TABLE; Schema: app; Owner: -
--

CREATE TABLE app.users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    email text NOT NULL,
    password_hash text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

--
-- Name: mobile_money_payouts; Type: TABLE; Schema: app; Owner: -
--

CREATE TABLE app.mobile_money_payouts (
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
    attempt_count integer DEFAULT 0 NOT NULL,
    last_attempt_at timestamp with time zone,
    next_retry_at timestamp with time zone,
    retryable boolean DEFAULT true NOT NULL,
    provider_response jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: audit_logs; Type: TABLE; Schema: audit; Owner: -
--

CREATE TABLE audit.audit_logs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    actor_user_id uuid,
    action text NOT NULL,
    entity_type text,
    entity_id uuid,
    metadata jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: disputes; Type: TABLE; Schema: audit; Owner: -
--

CREATE TABLE audit.disputes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    ledger_transaction_id uuid NOT NULL,
    opened_by_user_id uuid,
    reason text NOT NULL,
    status text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: kyc_profiles; Type: TABLE; Schema: kyc; Owner: -
--

CREATE TABLE kyc.kyc_profiles (
    user_id uuid NOT NULL,
    tier integer DEFAULT 1 NOT NULL,
    id_type text,
    id_number text,
    verified_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: ledger_accounts; Type: TABLE; Schema: ledger; Owner: -
--

CREATE TABLE ledger.ledger_accounts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    owner_type ledger.party_type NOT NULL,
    owner_id uuid NOT NULL,
    country ledger.country_code NOT NULL,
    currency text DEFAULT 'XOF'::text NOT NULL,
    account_type text NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    merchant_id uuid,
    CONSTRAINT chk_merchant_wallet CHECK ((((owner_type = 'MERCHANT'::ledger.party_type) AND (merchant_id IS NOT NULL)) OR ((owner_type <> 'MERCHANT'::ledger.party_type) AND (merchant_id IS NULL))))
);


--
-- Name: ledger_entries; Type: TABLE; Schema: ledger; Owner: -
--

CREATE TABLE ledger.ledger_entries (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    transaction_id uuid NOT NULL,
    account_id uuid NOT NULL,
    dc ledger.entry_dc NOT NULL,
    amount_cents bigint NOT NULL,
    memo text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT amount_positive CHECK ((amount_cents > 0)),
    CONSTRAINT chk_amount_positive CHECK ((amount_cents > 0)),
    CONSTRAINT chk_dc CHECK ((dc = ANY (ARRAY['DEBIT'::ledger.entry_dc, 'CREDIT'::ledger.entry_dc]))),
    CONSTRAINT ledger_entries_amount_cents_check CHECK ((amount_cents > 0))
);

--
-- Name: wallet_entries; Type: VIEW; Schema: ledger; Owner: -
--

CREATE VIEW ledger.wallet_entries AS
SELECT
    account_id AS wallet_id,
    transaction_id,
    created_at
FROM ledger.ledger_entries;


--
-- Name: ledger_transactions; Type: TABLE; Schema: ledger; Owner: -
--

CREATE TABLE ledger.ledger_transactions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    type text NOT NULL,
    status ledger.txn_status DEFAULT 'PENDING'::ledger.txn_status NOT NULL,
    country ledger.country_code NOT NULL,
    currency text DEFAULT 'XOF'::text NOT NULL,
    amount_cents bigint NOT NULL,
    description text,
    idempotency_key text NOT NULL,
    rail rails.rail_type DEFAULT 'INTERNAL'::rails.rail_type NOT NULL,
    external_ref text,
    provider text,
    phone_e164 text,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    posted_at timestamp with time zone,
    CONSTRAINT ledger_transactions_amount_cents_check CHECK ((amount_cents > 0))
);


--
-- Name: wallet_balances; Type: TABLE; Schema: ledger; Owner: -
--

CREATE TABLE ledger.wallet_balances (
    account_id uuid NOT NULL,
    available_cents bigint DEFAULT 0 NOT NULL,
    pending_cents bigint DEFAULT 0 NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: account_limits; Type: TABLE; Schema: limits; Owner: -
--

CREATE TABLE limits.account_limits (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    kyc_tier integer NOT NULL,
    daily_send_cents bigint NOT NULL,
    monthly_send_cents bigint NOT NULL,
    daily_cashout_cents bigint NOT NULL,
    is_active boolean DEFAULT true NOT NULL
);


--
-- Name: fee_rules; Type: TABLE; Schema: limits; Owner: -
--

CREATE TABLE limits.fee_rules (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    applies_to text NOT NULL,
    country ledger.country_code,
    fixed_cents bigint DEFAULT 0 NOT NULL,
    pct_bps integer DEFAULT 0 NOT NULL,
    min_cents bigint DEFAULT 0 NOT NULL,
    max_cents bigint,
    is_active boolean DEFAULT true NOT NULL
);


--
-- Name: merchant_qr_codes; Type: TABLE; Schema: merchants; Owner: -
--

CREATE TABLE merchants.merchant_qr_codes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    merchant_id uuid NOT NULL,
    qr_payload text NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: merchants; Type: TABLE; Schema: merchants; Owner: -
--

CREATE TABLE merchants.merchants (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    owner_user_id uuid,
    legal_name text NOT NULL,
    display_name text NOT NULL,
    country ledger.country_code NOT NULL,
    category text,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: users; Type: TABLE; Schema: users; Owner: -
--

CREATE TABLE users.users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    phone_e164 text NOT NULL,
    email text,
    full_name text,
    country ledger.country_code NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    password_hash text
);

--
-- Name: user_roles; Type: TABLE; Schema: users; Owner: -
--

CREATE TABLE users.user_roles (
    user_id uuid NOT NULL,
    role text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

--
-- Name: user_sessions; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.user_sessions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    device_id uuid NOT NULL,
    refresh_token_hash text NOT NULL,
    biometric_enabled boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_used_at timestamp with time zone,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone
);


--
-- Name: transaction_meta transaction_meta_pkey; Type: CONSTRAINT; Schema: app; Owner: -
--

ALTER TABLE ONLY app.transaction_meta
    ADD CONSTRAINT transaction_meta_pkey PRIMARY KEY (transaction_id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: app; Owner: -
--

ALTER TABLE ONLY app.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: app; Owner: -
--

ALTER TABLE ONLY app.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);

--
-- Name: mobile_money_payouts mobile_money_payouts_pkey; Type: CONSTRAINT; Schema: app; Owner: -
--

ALTER TABLE ONLY app.mobile_money_payouts
    ADD CONSTRAINT mobile_money_payouts_pkey PRIMARY KEY (id);

--
-- Name: mobile_money_payouts mobile_money_payouts_transaction_id_key; Type: CONSTRAINT; Schema: app; Owner: -
--

ALTER TABLE ONLY app.mobile_money_payouts
    ADD CONSTRAINT mobile_money_payouts_transaction_id_key UNIQUE (transaction_id);


--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: disputes disputes_pkey; Type: CONSTRAINT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit.disputes
    ADD CONSTRAINT disputes_pkey PRIMARY KEY (id);


--
-- Name: kyc_profiles kyc_profiles_pkey; Type: CONSTRAINT; Schema: kyc; Owner: -
--

ALTER TABLE ONLY kyc.kyc_profiles
    ADD CONSTRAINT kyc_profiles_pkey PRIMARY KEY (user_id);


--
-- Name: ledger_accounts ledger_accounts_owner_type_owner_id_country_currency_accoun_key; Type: CONSTRAINT; Schema: ledger; Owner: -
--

ALTER TABLE ONLY ledger.ledger_accounts
    ADD CONSTRAINT ledger_accounts_owner_type_owner_id_country_currency_accoun_key UNIQUE (owner_type, owner_id, country, currency, account_type);


--
-- Name: ledger_accounts ledger_accounts_pkey; Type: CONSTRAINT; Schema: ledger; Owner: -
--

ALTER TABLE ONLY ledger.ledger_accounts
    ADD CONSTRAINT ledger_accounts_pkey PRIMARY KEY (id);


--
-- Name: ledger_entries ledger_entries_pkey; Type: CONSTRAINT; Schema: ledger; Owner: -
--

ALTER TABLE ONLY ledger.ledger_entries
    ADD CONSTRAINT ledger_entries_pkey PRIMARY KEY (id);


--
-- Name: ledger_transactions ledger_transactions_idempotency_key_key; Type: CONSTRAINT; Schema: ledger; Owner: -
--

ALTER TABLE ONLY ledger.ledger_transactions
    ADD CONSTRAINT ledger_transactions_idempotency_key_key UNIQUE (idempotency_key);


--
-- Name: ledger_transactions ledger_transactions_pkey; Type: CONSTRAINT; Schema: ledger; Owner: -
--

ALTER TABLE ONLY ledger.ledger_transactions
    ADD CONSTRAINT ledger_transactions_pkey PRIMARY KEY (id);


--
-- Name: wallet_balances wallet_balances_pkey; Type: CONSTRAINT; Schema: ledger; Owner: -
--

ALTER TABLE ONLY ledger.wallet_balances
    ADD CONSTRAINT wallet_balances_pkey PRIMARY KEY (account_id);


--
-- Name: account_limits account_limits_kyc_tier_key; Type: CONSTRAINT; Schema: limits; Owner: -
--

ALTER TABLE ONLY limits.account_limits
    ADD CONSTRAINT account_limits_kyc_tier_key UNIQUE (kyc_tier);


--
-- Name: account_limits account_limits_pkey; Type: CONSTRAINT; Schema: limits; Owner: -
--

ALTER TABLE ONLY limits.account_limits
    ADD CONSTRAINT account_limits_pkey PRIMARY KEY (id);


--
-- Name: fee_rules fee_rules_pkey; Type: CONSTRAINT; Schema: limits; Owner: -
--

ALTER TABLE ONLY limits.fee_rules
    ADD CONSTRAINT fee_rules_pkey PRIMARY KEY (id);


--
-- Name: merchant_qr_codes merchant_qr_codes_merchant_id_key; Type: CONSTRAINT; Schema: merchants; Owner: -
--

ALTER TABLE ONLY merchants.merchant_qr_codes
    ADD CONSTRAINT merchant_qr_codes_merchant_id_key UNIQUE (merchant_id);


--
-- Name: merchant_qr_codes merchant_qr_codes_pkey; Type: CONSTRAINT; Schema: merchants; Owner: -
--

ALTER TABLE ONLY merchants.merchant_qr_codes
    ADD CONSTRAINT merchant_qr_codes_pkey PRIMARY KEY (id);


--
-- Name: merchants merchants_pkey; Type: CONSTRAINT; Schema: merchants; Owner: -
--

ALTER TABLE ONLY merchants.merchants
    ADD CONSTRAINT merchants_pkey PRIMARY KEY (id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: users; Owner: -
--

ALTER TABLE ONLY users.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_phone_e164_key; Type: CONSTRAINT; Schema: users; Owner: -
--

ALTER TABLE ONLY users.users
    ADD CONSTRAINT users_phone_e164_key UNIQUE (phone_e164);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: users; Owner: -
--

ALTER TABLE ONLY users.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);

--
-- Name: user_roles user_roles_pkey; Type: CONSTRAINT; Schema: users; Owner: -
--

ALTER TABLE ONLY users.user_roles
    ADD CONSTRAINT user_roles_pkey PRIMARY KEY (user_id);

--
-- Name: user_sessions user_sessions_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.user_sessions
    ADD CONSTRAINT user_sessions_pkey PRIMARY KEY (id);


--
-- Name: idx_txmeta_receiver; Type: INDEX; Schema: app; Owner: -
--

CREATE INDEX idx_txmeta_receiver ON app.transaction_meta USING btree (receiver_user_id, created_at DESC);


--
-- Name: idx_txmeta_sender; Type: INDEX; Schema: app; Owner: -
--

CREATE INDEX idx_txmeta_sender ON app.transaction_meta USING btree (sender_user_id, created_at DESC);


--
-- Name: idx_audit_logs_actor; Type: INDEX; Schema: audit; Owner: -
--

CREATE INDEX idx_audit_logs_actor ON audit.audit_logs USING btree (actor_user_id);


--
-- Name: idx_audit_logs_created_at; Type: INDEX; Schema: audit; Owner: -
--

CREATE INDEX idx_audit_logs_created_at ON audit.audit_logs USING btree (created_at);


--
-- Name: idx_disputes_txn; Type: INDEX; Schema: audit; Owner: -
--

CREATE INDEX idx_disputes_txn ON audit.disputes USING btree (ledger_transaction_id);

--
-- Name: ux_user_sessions_refresh_token_hash; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX ux_user_sessions_refresh_token_hash ON auth.user_sessions USING btree (refresh_token_hash);


--
-- Name: idx_accounts_country; Type: INDEX; Schema: ledger; Owner: -
--

CREATE INDEX idx_accounts_country ON ledger.ledger_accounts USING btree (country);


--
-- Name: idx_accounts_owner; Type: INDEX; Schema: ledger; Owner: -
--

CREATE INDEX idx_accounts_owner ON ledger.ledger_accounts USING btree (owner_type, owner_id);


--
-- Name: idx_entries_account; Type: INDEX; Schema: ledger; Owner: -
--

CREATE INDEX idx_entries_account ON ledger.ledger_entries USING btree (account_id);


--
-- Name: idx_entries_txn; Type: INDEX; Schema: ledger; Owner: -
--

CREATE INDEX idx_entries_txn ON ledger.ledger_entries USING btree (transaction_id);


--
-- Name: idx_ledger_entries_account_txn_created; Type: INDEX; Schema: ledger; Owner: -
--

CREATE INDEX idx_ledger_entries_account_txn_created ON ledger.ledger_entries USING btree (account_id, transaction_id, created_at DESC);


--
-- Name: idx_ledger_txn_created_at; Type: INDEX; Schema: ledger; Owner: -
--

CREATE INDEX idx_ledger_txn_created_at ON ledger.ledger_transactions USING btree (created_at);


--
-- Name: idx_ledger_txn_external_ref; Type: INDEX; Schema: ledger; Owner: -
--

CREATE INDEX idx_ledger_txn_external_ref ON ledger.ledger_transactions USING btree (external_ref);


--
-- Name: idx_ledger_txn_status; Type: INDEX; Schema: ledger; Owner: -
--

CREATE INDEX idx_ledger_txn_status ON ledger.ledger_transactions USING btree (status);


--
-- Name: uq_cash_in_provider_ref; Type: INDEX; Schema: ledger; Owner: -
--

CREATE UNIQUE INDEX uq_cash_in_provider_ref ON ledger.ledger_transactions USING btree (external_ref) WHERE ((type = 'CASHIN'::text) AND (external_ref IS NOT NULL));


--
-- Name: ux_tx_idempotency; Type: INDEX; Schema: ledger; Owner: -
--

CREATE UNIQUE INDEX ux_tx_idempotency ON ledger.ledger_transactions USING btree (idempotency_key);


--
-- Name: idx_fee_rules_active; Type: INDEX; Schema: limits; Owner: -
--

CREATE INDEX idx_fee_rules_active ON limits.fee_rules USING btree (is_active);


--
-- Name: idx_merchants_owner; Type: INDEX; Schema: merchants; Owner: -
--

CREATE INDEX idx_merchants_owner ON merchants.merchants USING btree (owner_user_id);


--
-- Name: ix_users_email; Type: INDEX; Schema: users; Owner: -
--

CREATE INDEX ix_users_email ON users.users USING btree (email);


--
-- Name: users_users_email_uq; Type: INDEX; Schema: users; Owner: -
--

CREATE UNIQUE INDEX users_users_email_uq ON users.users USING btree (email);


--
-- Name: ledger_entries trg_balance_check; Type: TRIGGER; Schema: ledger; Owner: -
--

CREATE CONSTRAINT TRIGGER trg_balance_check AFTER INSERT OR DELETE OR UPDATE ON ledger.ledger_entries DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ledger.enforce_balanced_transaction();


--
-- Name: audit_logs audit_logs_actor_user_id_fkey; Type: FK CONSTRAINT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit.audit_logs
    ADD CONSTRAINT audit_logs_actor_user_id_fkey FOREIGN KEY (actor_user_id) REFERENCES users.users(id);


--
-- Name: disputes disputes_ledger_transaction_id_fkey; Type: FK CONSTRAINT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit.disputes
    ADD CONSTRAINT disputes_ledger_transaction_id_fkey FOREIGN KEY (ledger_transaction_id) REFERENCES ledger.ledger_transactions(id);


--
-- Name: disputes disputes_opened_by_user_id_fkey; Type: FK CONSTRAINT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit.disputes
    ADD CONSTRAINT disputes_opened_by_user_id_fkey FOREIGN KEY (opened_by_user_id) REFERENCES users.users(id);

--
-- Name: user_sessions user_sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.user_sessions
    ADD CONSTRAINT user_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES users.users(id);


--
-- Name: kyc_profiles kyc_profiles_user_id_fkey; Type: FK CONSTRAINT; Schema: kyc; Owner: -
--

ALTER TABLE ONLY kyc.kyc_profiles
    ADD CONSTRAINT kyc_profiles_user_id_fkey FOREIGN KEY (user_id) REFERENCES users.users(id);


--
-- Name: ledger_accounts ledger_accounts_merchant_id_fkey; Type: FK CONSTRAINT; Schema: ledger; Owner: -
--

ALTER TABLE ONLY ledger.ledger_accounts
    ADD CONSTRAINT ledger_accounts_merchant_id_fkey FOREIGN KEY (merchant_id) REFERENCES merchants.merchants(id);


--
-- Name: ledger_entries ledger_entries_account_id_fkey; Type: FK CONSTRAINT; Schema: ledger; Owner: -
--

ALTER TABLE ONLY ledger.ledger_entries
    ADD CONSTRAINT ledger_entries_account_id_fkey FOREIGN KEY (account_id) REFERENCES ledger.ledger_accounts(id);


--
-- Name: ledger_entries ledger_entries_transaction_id_fkey; Type: FK CONSTRAINT; Schema: ledger; Owner: -
--

ALTER TABLE ONLY ledger.ledger_entries
    ADD CONSTRAINT ledger_entries_transaction_id_fkey FOREIGN KEY (transaction_id) REFERENCES ledger.ledger_transactions(id) ON DELETE CASCADE;


--
-- Name: ledger_transactions ledger_transactions_created_by_fkey; Type: FK CONSTRAINT; Schema: ledger; Owner: -
--

ALTER TABLE ONLY ledger.ledger_transactions
    ADD CONSTRAINT ledger_transactions_created_by_fkey FOREIGN KEY (created_by) REFERENCES users.users(id);


--
-- Name: wallet_balances wallet_balances_account_id_fkey; Type: FK CONSTRAINT; Schema: ledger; Owner: -
--

ALTER TABLE ONLY ledger.wallet_balances
    ADD CONSTRAINT wallet_balances_account_id_fkey FOREIGN KEY (account_id) REFERENCES ledger.ledger_accounts(id);


--
-- Name: audit_log; Type: TABLE; Schema: app; Owner: -
--

CREATE TABLE IF NOT EXISTS app.audit_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id uuid NOT NULL,
    action text NOT NULL,
    target_id text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ledger_txn_created_by_type_created_at
    ON ledger.ledger_transactions (created_by, type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_mobile_money_payouts_created_at
    ON app.mobile_money_payouts (created_at);

CREATE INDEX IF NOT EXISTS idx_mobile_money_payouts_phone_created_at
    ON app.mobile_money_payouts (phone_e164, created_at DESC);

CREATE TABLE IF NOT EXISTS app.webhook_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider text NOT NULL,
    external_ref text,
    provider_ref text,
    status_raw text,
    payload jsonb NOT NULL,
    payload_json jsonb,
    payload_summary jsonb,
    headers jsonb,
    received_at timestamptz NOT NULL DEFAULT now(),
    signature_valid boolean
);

--
-- Name: webhook_events; Type: TABLE; Schema: public; Owner: -
--

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


--
-- Name: merchant_qr_codes merchant_qr_codes_merchant_id_fkey; Type: FK CONSTRAINT; Schema: merchants; Owner: -
--

ALTER TABLE ONLY merchants.merchant_qr_codes
    ADD CONSTRAINT merchant_qr_codes_merchant_id_fkey FOREIGN KEY (merchant_id) REFERENCES merchants.merchants(id);


--
-- Name: merchants merchants_owner_user_id_fkey; Type: FK CONSTRAINT; Schema: merchants; Owner: -
--

ALTER TABLE ONLY merchants.merchants
    ADD CONSTRAINT merchants_owner_user_id_fkey FOREIGN KEY (owner_user_id) REFERENCES users.users(id);


--
-- PostgreSQL database dump complete
--

\unrestrict M0CO4ow6DDcoG18gcgxTeXNzkBgWIJHJkWC100HLbxmF6phmyXXd0tyM4mVor4N



--
-- Name: idempotency_keys; Type: TABLE; Schema: app; Owner: -
--

CREATE TABLE app.idempotency_keys (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    idempotency_key text NOT NULL,
    route_key text NOT NULL,
    request_hash text,
    response_json jsonb NOT NULL,
    status_code integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE app.idempotency_keys
    ADD CONSTRAINT idempotency_keys_pkey PRIMARY KEY (id);

CREATE UNIQUE INDEX ux_idempotency_keys_user_route ON app.idempotency_keys USING btree (user_id, idempotency_key, route_key);

--
-- Name: admin_events; Type: TABLE; Schema: audit; Owner: -
--

CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE IF NOT EXISTS audit.admin_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    admin_user_id uuid NOT NULL,
    action text NOT NULL,
    entity_type text NOT NULL,
    entity_id text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    request_id text
);

ALTER TABLE audit.admin_events
    ADD CONSTRAINT admin_events_pkey PRIMARY KEY (id);
