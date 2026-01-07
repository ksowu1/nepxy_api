

# routes/debug.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from deps.auth import get_current_user, CurrentUser
import os
import socket
from uuid import UUID

from fastapi import APIRouter, HTTPException

from db import get_conn
from settings import settings

router = APIRouter(tags=["debug"])


'''@router.get("/debug/whoami")
def whoami():
    # Do not leak passwords. Only show host:port/db part.
    safe_db = settings.DATABASE_URL.split("@")[-1] if hasattr(settings, "DATABASE_URL") else "unknown"
    return {
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "db_url": safe_db,
    }
'''

@router.get("/debug/source")
def debug_source():
    return {"file": os.path.abspath(__file__)}


'''@router.get("/debug/dbinfo")
def debug_dbinfo():
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database(), current_user, inet_server_addr(), inet_server_port();")
                db, usr, addr, port = cur.fetchone()
        return {"db": db, "user": usr, "addr": str(addr), "port": port}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB_ERROR: {str(e)}")
'''

'''@router.get("/debug/activity/{wallet_id}")
def debug_activity(wallet_id: UUID):
    """
    Debug helper: returns raw rows from ledger.get_wallet_activity(wallet_id, 10, NULL)
    """
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM ledger.get_wallet_activity(%s::uuid, 10, NULL);",
                    (str(wallet_id),),
                )
                rows = cur.fetchall()
        return {"rows": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB_ERROR: {str(e)}")
'''

# routes/debug.py
from fastapi import APIRouter
from uuid import UUID
from db import get_conn

router = APIRouter(prefix="/debug", tags=["debug"])

@router.get("/merchant-check/{wallet_id}")
def merchant_check(wallet_id: UUID):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, owner_type, account_type, country::text, currency
                FROM ledger.ledger_accounts
                WHERE id=%s::uuid;
            """, (str(wallet_id),))
            row = cur.fetchone()
    return {"row": row}

@router.get("/balance/{wallet_id}")
def balance(wallet_id: UUID):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT ledger.get_available_balance(%s::uuid);", (str(wallet_id),))
            bal = cur.fetchone()[0]
    return {"wallet_id": str(wallet_id), "balance_cents": int(bal)}


import sys, os
from fastapi import APIRouter

router = APIRouter(prefix="/debug", tags=["debug"])

@router.get("/python")
def debug_python():
    return {
        "executable": sys.executable,
        "version": sys.version,
        "venv": os.environ.get("VIRTUAL_ENV"),
    }

from fastapi import APIRouter
from db import get_conn

router = APIRouter(tags=["debug"])

@router.get("/health")
def health():
    return {"status": "ok"}

@router.get("/ready")
def ready():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            cur.fetchone()
    return {"status": "ready"}


@router.get("/debug/jwt")
def debug_jwt():
    return {"alg": settings.JWT_ALG, "secret_len": len(settings.JWT_SECRET)}


@router.get("/debug/me")
def debug_me(user: CurrentUser = Depends(get_current_user)):
    return {"user_id": str(user.user_id)}


from fastapi import APIRouter
router = APIRouter(prefix="/v1", tags=["debug"])

@router.get("/health")
def health():
    return {"ok": True}

