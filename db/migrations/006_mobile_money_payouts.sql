

-- db/migrations/006_mobile_money_payouts.sql
CREATE TABLE IF NOT EXISTS app.mobile_money_payouts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  transaction_id uuid NOT NULL UNIQUE,
  provider text NOT NULL,
  phone_e164 text,
  provider_ref text,
  status text NOT NULL DEFAULT 'PENDING',  -- PENDING | SENT | CONFIRMED | FAILED
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mm_payouts_status ON app.mobile_money_payouts(status);
