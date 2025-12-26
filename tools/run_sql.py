
# tools/run_sql.py
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor


def parse_params(kvs: List[str]) -> Dict[str, Any]:
    """
    Parse --params key=value key2=value2 into a dict.
    Values are passed as strings (Postgres casts in SQL via ::uuid, ::bigint, etc.)
    """
    out: Dict[str, Any] = {}
    for item in kvs:
        if "=" not in item:
            raise SystemExit(f"Invalid --params item '{item}'. Expected key=value")
        k, v = item.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not k:
            raise SystemExit(f"Invalid --params item '{item}'. Empty key")
        out[k] = v
    return out


def find_default_file() -> Path:
    """
    Optional default SQL file if user doesn't pass --file.
    """
    default = Path("db") / "migrations" / "004_mobile_money_generic.sql"
    return default


def format_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "(no rows)"
    cols = list(rows[0].keys())
    widths = {c: len(c) for c in cols}
    for r in rows:
        for c in cols:
            widths[c] = max(widths[c], len(str(r.get(c, ""))))
    sep = " | "
    header = sep.join(c.ljust(widths[c]) for c in cols)
    line = "-+-".join("-" * widths[c] for c in cols)
    body = "\n".join(sep.join(str(r.get(c, "")).ljust(widths[c]) for c in cols) for r in rows)
    return f"{header}\n{line}\n{body}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a SQL file against DATABASE_URL with optional params.")
    parser.add_argument(
        "--file",
        dest="sql_file",
        type=str,
        default=None,
        help="Path to SQL file (required unless a default migration exists).",
    )
    parser.add_argument(
        "--params",
        nargs="*",
        default=[],
        help="SQL params as key=value (used for :key placeholders). Example: --params tx_id=... ",
    )

    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL is not set. Set it in PowerShell: $env:DATABASE_URL='postgres://...'", file=sys.stderr)
        return 2

    sql_path: Path
    if args.sql_file:
        sql_path = Path(args.sql_file)
    else:
        sql_path = find_default_file()

    if not sql_path.exists():
        print(f"SQL file not found: {sql_path.resolve()}", file=sys.stderr)
        return 2

    sql_text = sql_path.read_text(encoding="utf-8")

    params = parse_params(args.params)

    # Convert :param style to psycopg2 %(param)s style for RealDictCursor execution
    # (simple safe replacement for named params)
    for k in params.keys():
        sql_text = sql_text.replace(f":{k}", f"%({k})s")

    try:
        with psycopg2.connect(db_url) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql_text, params)
                rows: List[Dict[str, Any]] = []
                if cur.description is not None:
                    rows = cur.fetchall()
                print(format_table(rows))
        return 0
    except Exception as e:
        print(f"SQL ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
