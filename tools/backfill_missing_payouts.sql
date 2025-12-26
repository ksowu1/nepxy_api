-- Backfill payout rows for CASHOUT transactions that don't have a payout row yet.
-- Safe to run multiple times.

INSERT INTO app.mobile_money_payouts (
  transaction_id,
  provider,
  phone_e164,
  provider_ref,
  status,
  last_error
)
SELECT
  t.id AS transaction_id,
  COALESCE(m.provider, 'MOMO') AS provider,
  m.phone_e164,
  t.external_ref AS provider_ref,
  'PENDING' AS status,
  NULL AS last_error
FROM ledger.ledger_transactions t
LEFT JOIN app.transaction_meta m
  ON m.transaction_id = t.id
LEFT JOIN app.mobile_money_payouts p
  ON p.transaction_id = t.id
WHERE t.type = 'CASHOUT'
  AND t.status = 'POSTED'
  AND p.transaction_id IS NULL
RETURNING transaction_id;
