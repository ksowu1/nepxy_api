


# inspect_payouts.py
import os
import psycopg2, psycopg2.extras
from settings import settings

dsn = os.getenv("DATABASE_URL") or settings.DATABASE_URL
conn = psycopg2.connect(dsn)
conn.autocommit = True
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

print("\n--- Total rows ---")
cur.execute("select count(*) as n from app.mobile_money_payouts")
print("TOTAL =", cur.fetchone()["n"])

print("\n--- Status counts ---")
cur.execute("""
  select status, count(*) as n
  from app.mobile_money_payouts
  group by status
  order by n desc
""")
for r in cur.fetchall():
    print(r)

print("\n--- Latest 10 rows ---")
cur.execute("""
  select transaction_id, provider, provider_ref, status, attempt_count, retryable, last_error, created_at, updated_at
  from app.mobile_money_payouts
  order by created_at desc
  limit 10
""")
for r in cur.fetchall():
    print(r)

conn.close()
