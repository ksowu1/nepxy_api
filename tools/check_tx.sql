

SELECT *
FROM ledger.ledger_entries
WHERE transaction_id = %(tx_id)s::uuid
ORDER BY created_at;
