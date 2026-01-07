

import sys
sys.path.insert(0, ".")

from db import get_conn
from app.providers.mobile_money.factory import get_provider

TX = "1fb9655b-1a5c-43a4-9391-aaa6361b0991"

print("provider factory THUNES =", type(get_provider("THUNES")).__name__ if get_provider("THUNES") else None)

SQL_PAYOUT = """
select
  p.transaction_id::text,
  p.provider,
  p.status,
  p.attempt_count,
  p.retryable,
  p.next_retry_at,
  p.last_attempt_at,
  p.provider_ref,
  p.phone_e164,
  p.amount_cents,
  p.currency,
  tx.external_ref
from app.mobile_money_payouts p
join ledger.ledger_transactions tx on tx.id = p.transaction_id
where p.transaction_id = %s::uuid
"""

with get_conn() as conn:
    cur = conn.cursor()
    cur.execute(SQL_PAYOUT, (TX,))
    row = cur.fetchone()
    print("payout row =", row)

    cur.execute("""
      select count(*)
      from app.mobile_money_payouts
      where provider='THUNES'
        and status in ('PENDING','RETRY')
        and coalesce(retryable,false)=true
        and coalesce(next_retry_at, now()) <= now()
    """)
    print("THUNES ready-to-run count =", cur.fetchone()[0])
