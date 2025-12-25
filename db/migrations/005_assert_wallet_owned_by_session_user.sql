
-- Adds helper used by post_cash_out_mobile_money

CREATE OR REPLACE FUNCTION ledger.assert_wallet_owned_by_session_user(
  p_account_id uuid
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ledger, public
AS $$
DECLARE
  v_user_id uuid;
  v_owner_id uuid;
BEGIN
  v_user_id := ledger.current_user_id();

  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'DB_ERROR: UNAUTHORIZED_WALLET_ACCESS';
  END IF;

  SELECT owner_id INTO v_owner_id
  FROM ledger.ledger_accounts
  WHERE id = p_account_id;

  IF v_owner_id IS NULL THEN
    RAISE EXCEPTION 'DB_ERROR: WALLET_NOT_FOUND';
  END IF;

  IF v_owner_id <> v_user_id THEN
    RAISE EXCEPTION 'DB_ERROR: WALLET_NOT_OWNED';
  END IF;

  RETURN;
END;
$$;

ALTER FUNCTION ledger.assert_wallet_owned_by_session_user(uuid) OWNER TO postgres;
