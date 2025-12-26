

-- tools/check_tx_entries.sql
-- Params:
--   :tx_id  (uuid)

SELECT
  e.transaction_id,
  e.account_id,
  a.owner_id,
  a.owner_type,
  a.account_type,
  a.country,
  a.currency,
  e.dc,
  e.amount_cents,
  e.memo,
  e.created_at
FROM ledger.ledger_entries e
JOIN ledger.ledger_accounts a
  ON a.id = e.account_id
WHERE e.transaction_id = :tx_id::uuid
ORDER BY e.created_at ASC, e.dc ASC, e.amount_cents DESC;


