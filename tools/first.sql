


-- tools/first.sql

-- Impersonate the same “session user” the API sets
SELECT set_config('app.user_id', %(user_id)s, true);

-- Optional: prove the actor is set
SELECT ledger.actor_user_id() AS actor_user_id, ledger.current_user_id() AS current_user_id;

-- Now run the real cash-out function (same as API would)
SELECT ledger.post_cash_out_mobile_money(
  %(wallet_id)s::uuid,
  %(user_id)s::uuid,
  %(amount_cents)s::bigint,
  %(country)s::ledger.country_code,
  %(idempotency_key)s::text,
  %(provider_ref)s::text,
  %(provider)s::text,
  %(phone_e164)s::text,
  %(system_owner_id)s::uuid
);
