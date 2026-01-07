

import sys
sys.path.insert(0, ".")

from db import get_conn

SQL = """
select id::text, provider, external_ref, provider_ref, status_raw, signature_valid, received_at
from app.webhook_events
order by received_at desc
limit 10
"""

with get_conn() as conn:
    cur = conn.cursor()
    cur.execute(SQL)
    for row in cur.fetchall():
        print(row)
