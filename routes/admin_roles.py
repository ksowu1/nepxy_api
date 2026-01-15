

# routes/admin_roles.py
from fastapi import APIRouter, Depends
from db import get_conn
from db_session import set_db_actor
from deps.admin import require_admin
from deps.auth import CurrentUser
from schemas import (
    AdminSetRoleRequest,
    AdminClearRoleRequest,
    UserRoleListResponse,
    UserRoleItem,
)
from services.audit_log import write_audit_log

router = APIRouter(prefix="/v1/admin/roles", tags=["admin-roles"])


@router.get("", response_model=UserRoleListResponse)
def list_roles(admin: CurrentUser = Depends(require_admin)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            set_db_actor(cur, admin.user_id)
            cur.execute("SELECT * FROM users.list_user_roles_secure();")
            rows = cur.fetchall()

    items = [UserRoleItem(user_id=r[0], role=r[1], created_at=r[2]) for r in rows]
    return UserRoleListResponse(items=items)


@router.post("/set")
def set_role(payload: AdminSetRoleRequest, admin: CurrentUser = Depends(require_admin)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            set_db_actor(cur, admin.user_id)
            cur.execute(
                "SELECT users.set_user_role_secure(%s::uuid, %s::text);",
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
                "SELECT users.clear_user_role_secure(%s::uuid);",
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
