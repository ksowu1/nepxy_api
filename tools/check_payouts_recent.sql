

SELECT
  p.id AS payout_id,
  p.transaction_id,
  p.provider,
  p.phone_e164,
  p.provider_ref,
  p.status,
  p.last_error,
  p.created_at,
  p.updated_at
FROM app.mobile_money_payouts p
ORDER BY p.created_at DESC
LIMIT 25;
