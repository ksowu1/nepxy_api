

SELECT
  p.id AS payout_id,
  p.transaction_id,
  t.type AS ledger_type,
  t.status AS ledger_status,
  t.amount_cents,
  p.provider,
  p.phone_e164,
  p.provider_ref,
  p.status AS payout_status,
  p.last_error,
  p.created_at,
  p.updated_at
FROM app.mobile_money_payouts p
JOIN ledger.ledger_transactions t
  ON t.id = p.transaction_id
WHERE p.transaction_id = %(tx_id)s::uuid
ORDER BY p.created_at DESC;

