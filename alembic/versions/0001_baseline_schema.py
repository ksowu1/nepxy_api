"""baseline schema

Revision ID: 0001_baseline_schema
Revises:
Create Date: 2026-01-12 00:00:00.000000

"""

from __future__ import annotations

from pathlib import Path

from alembic import op


revision = "0001_baseline_schema"
down_revision = None
branch_labels = None
depends_on = None


def _load_schema_sql() -> str:
    root = Path(__file__).resolve().parents[2]
    schema_path = root / "db" / "schema_v1.sql"
    raw = schema_path.read_text(encoding="utf-8")

    skip_prefixes = (
        "SET statement_timeout",
        "SET lock_timeout",
        "SET idle_in_transaction_session_timeout",
        "SET transaction_timeout",
        "SET client_encoding",
        "SET standard_conforming_strings",
        "SET check_function_bodies",
        "SET xmloption",
        "SET client_min_messages",
        "SET row_security",
    )

    lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("--"):
            continue
        if stripped.startswith("\\"):
            continue
        if stripped.startswith(skip_prefixes):
            continue
        if stripped == "SELECT pg_catalog.set_config('search_path', '', false);":
            continue
        lines.append(line)
    return "\n".join(lines)


def upgrade() -> None:
    sql = _load_schema_sql()
    op.execute(sql)


def downgrade() -> None:
    pass
