

import sys
sys.path.insert(0, ".")
from db import get_conn

with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute("select count(*) from app.webhook_events")
        print("app.webhook_events =", cur.fetchone()[0])
        cur.execute("select count(*) from public.webhook_events")
        print("public.webhook_events =", cur.fetchone()[0])
