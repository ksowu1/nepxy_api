from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from db import get_conn
from db_session import set_db_actor
from deps.auth import CurrentUser
from deps.admin import require_admin
from schemas import (
    AdminSetRoleRequest,
    AdminClearRoleRequest,
    UserRoleListResponse,
    UserRoleItem,
)
from services.audit_log import write_audit_log

router = APIRouter(prefix="/v1/admin/roles", tags=["admin-roles"])

logger = logging.getLogger("nexapay")


@router.get("", response_model=UserRoleListResponse)
def list_roles(admin: CurrentUser = Depends(require_admin)):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                set_db_actor(cur, admin.user_id)
                cur.execute(
                    """
                    SELECT user_id, role, created_at
                    FROM users.user_roles
                    ORDER BY created_at DESC NULLS LAST, user_id;
                    """
                )
                rows = cur.fetchall()
    except Exception as exc:
        logger.exception(
            "admin_roles.list_roles failed admin_id=%s error=%s",
            getattr(admin, "user_id", None),
            exc,
        )
        raise HTTPException(status_code=500, detail="Unable to list admin roles")

    items = [UserRoleItem(user_id=r[0], role=r[1], created_at=r[2]) for r in rows]
    return UserRoleListResponse(items=items)


@router.post("/set")
def set_role(payload: AdminSetRoleRequest, admin: CurrentUser = Depends(require_admin)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            set_db_actor(cur, admin.user_id)
            cur.execute(
                """
                INSERT INTO users.user_roles (user_id, role)
                VALUES (%s::uuid, %s::text)
                ON CONFLICT (user_id) DO UPDATE SET role = EXCLUDED.role;
                """,
                (str(payload.target_user_id), payload.role),
            )
        write_audit_log(
            conn,
            actor_user_id=str(admin.user_id),
            action="ROLE_SET",
            target_id=str(payload.target_user_id),
            metadata={"role": payload.role},
        )
    return {"ok": True}


@router.post("/clear")
def clear_role(payload: AdminClearRoleRequest, admin: CurrentUser = Depends(require_admin)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            set_db_actor(cur, admin.user_id)
            cur.execute(
                """
                DELETE FROM users.user_roles
                WHERE user_id = %s::uuid;
                """,
                (str(payload.target_user_id),),
            )
        write_audit_log(
            conn,
            actor_user_id=str(admin.user_id),
            action="ROLE_CLEAR",
            target_id=str(payload.target_user_id),
            metadata={},
        )
    return {"ok": True}
