

UPDATE app.mobile_money_payouts
SET status = 'CONFIRMED',
    updated_at = now(),
    last_error = NULL
WHERE transaction_id = %(tx_id)s::uuid
RETURNING
  id AS payout_id,
  transaction_id,
  status,
  updated_at;
