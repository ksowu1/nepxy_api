

SELECT
  to_regclass('app.mobile_money_payouts') AS mobile_money_payouts,
  to_regclass('app.transaction_meta')     AS transaction_meta,
  to_regclass('ledger.ledger_transactions') AS ledger_transactions,
  to_regclass('ledger.ledger_entries')      AS ledger_entries;

