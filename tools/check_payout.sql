

-- Latest mobile money payouts, with ledger amount/status and tx meta display text
SELECT
  p.id                  AS payout_id,
  p.transaction_id,
  t.type                AS ledger_type,
  t.status              AS ledger_status,
  t.country,
  t.currency,
  t.amount_cents,
  p.provider,
  p.phone_e164,
  p.provider_ref,
  p.status              AS payout_status,
  p.last_error,
  tm.display_text,
  p.created_at,
  p.updated_at
FROM app.mobile_money_payouts p
JOIN ledger.ledger_transactions t
  ON t.id = p.transaction_id
LEFT JOIN app.transaction_meta tm
  ON tm.transaction_id = p.transaction_id
ORDER BY p.created_at DESC
LIMIT 25;

