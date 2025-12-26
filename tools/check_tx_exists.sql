

SELECT
  id,
  type,
  status,
  country,
  currency,
  amount_cents,
  external_ref,
  created_at
FROM ledger.ledger_transactions
WHERE id = %(tx_id)s::uuid;
