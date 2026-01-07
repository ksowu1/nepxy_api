

from db import get_conn
import pprint

with get_conn() as conn:
    cur = conn.cursor()
    cur.execute("""
        select schemaname, tablename
        from pg_tables
        where schemaname not in ('pg_catalog','information_schema')
          and tablename ilike '%webhook%'
        order by schemaname, tablename
    """)
    pprint.pp(cur.fetchall())
