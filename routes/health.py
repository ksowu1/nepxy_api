from __future__ import annotations

import os

from fastapi import APIRouter

from db import get_conn

router = APIRouter(tags=["health"])

MIGRATION_REVISION = "0001_baseline_schema"


def _check_db() -> tuple[bool, str | None]:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
        return True, None
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _check_migrations() -> bool:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.alembic_version');")
                exists = cur.fetchone()[0]
                if not exists:
                    return False
                cur.execute("SELECT version_num FROM alembic_version LIMIT 1;")
                row = cur.fetchone()
                if not row or not row[0]:
                    return False
                return True
    except Exception:
        return False


def _resolve_env() -> str:
    return (os.getenv("ENVIRONMENT") or os.getenv("ENV") or "").strip()


def _resolve_git_sha() -> str | None:
    return (
        (os.getenv("FLY_IMAGE_REF") or "").strip()
        or (os.getenv("GIT_SHA") or "").strip()
        or (os.getenv("FLY_APP_NAME") or "").strip()
        or None
    )


@router.get("/healthz")
def healthz():
    db_ok, db_error = _check_db()
    return {
        "ok": True,
        "version": os.getenv("APP_VERSION", "1.0.0"),
        "git_sha": _resolve_git_sha(),
        "db_ok": db_ok,
        "db_error": db_error,
    }


@router.get("/health")
def health():
    return {
        "ok": True,
        "env": _resolve_env(),
        "mm_mode": (os.getenv("MM_MODE") or "").strip(),
        "git_sha": _resolve_git_sha(),
    }


@router.get("/readyz")
def readyz():
    db_ok, db_error = _check_db()
    migrations_ok = _check_migrations()
    ready = bool(db_ok and migrations_ok)
    return {
        "ready": ready,
        "version": os.getenv("APP_VERSION", "1.0.0"),
        "git_sha": _resolve_git_sha(),
        "db_ok": db_ok,
        "db_error": db_error,
        "migrations_ok": migrations_ok,
        "migration_revision": MIGRATION_REVISION,
    }
