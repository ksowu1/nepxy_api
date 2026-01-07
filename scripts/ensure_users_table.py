


# scripts/ensure_users_table.py
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path BEFORE importing "db"
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import get_conn  # now this should import your project's db.py

DDL = """
CREATE TABLE IF NOT EXISTS users (
  id uuid PRIMARY KEY,
  email text UNIQUE NOT NULL,
  full_name text NULL,
  phone_e164 text NULL,
  country text NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
"""

def main() -> None:
    # Your get_conn() is a context manager that yields a psycopg2 connection
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(DDL)
        conn.commit()
        cur.close()

    print("OK: users table ensured")

if __name__ == "__main__":
    main()
