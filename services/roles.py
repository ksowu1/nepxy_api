

# services/roles.py
from __future__ import annotations

import os
from fastapi import Depends, HTTPException

from db import get_conn
from deps.auth import get_current_user, CurrentUser  # adjust import if your project path differs


SYSTEM_OWNER_ID = os.getenv("SYSTEM_OWNER_ID", "00000000-0000-0000-0000-000000000001")


def _user_id(u: CurrentUser) -> str:
    # support different CurrentUser shapes
    return str(getattr(u, "user_id", None) or getattr(u, "id", None) or getattr(u, "sub", None))


def is_admin_user(conn, user_id: str) -> bool:
    if not user_id:
        return False

    # system owner bypass
    if user_id == SYSTEM_OWNER_ID:
        return True

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT role
            FROM users.user_roles
            WHERE user_id = %s::uuid
            """,
            (user_id,),
        )
        row = cur.fetchone()

    if not row:
        return False

    role = (row[0] or "").strip().upper()
    return role == "ADMIN"


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT role FROM users.user_roles WHERE user_id=%s::uuid",
                (user.user_id,),
            )
            row = cur.fetchone()

    role = (row[0] if row else None)
    if (role or "").upper() != "ADMIN":
        raise HTTPException(status_code=403, detail="FORBIDDEN")

    return user
