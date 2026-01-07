BEGIN;

CREATE SCHEMA IF NOT EXISTS ledger;

-- Ensure compatibility view exists and points to the real table
CREATE OR REPLACE VIEW ledger.entries AS
SELECT
  transaction_id,
  account_id,
  account_id AS wallet_id
FROM ledger.ledger_entries;

-- Cleanup any leftovers from earlier repairs
DROP TABLE IF EXISTS ledger.entries_seed;
DROP TABLE IF EXISTS ledger.entries_bad_backup;
DROP VIEW  IF EXISTS ledger.entries_view;

COMMIT;
