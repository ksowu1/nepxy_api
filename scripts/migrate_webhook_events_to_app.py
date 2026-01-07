


import os, sys
sys.path.insert(0, ".")
from db import get_conn

def main():
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Copy rows that don't already exist in app.
            # This assumes both tables have the same columns.
            cur.execute("""
                INSERT INTO app.webhook_events
                SELECT *
                FROM public.webhook_events
                ON CONFLICT DO NOTHING
            """)
        conn.commit()
    print("Done migrating public.webhook_events -> app.webhook_events")

if __name__ == "__main__":
    main()
