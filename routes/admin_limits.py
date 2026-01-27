from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from db import get_conn
from deps.admin import require_admin
from deps.auth import CurrentUser
from services.audit_log import write_audit_log
from services.user_limits import (
    get_user_limit_override,
    upsert_user_limit_override,
    clear_user_limit_override,
)
from settings import settings


router = APIRouter(prefix="/v1/admin/limits", tags=["admin", "limits"])


class UserLimitOverrideRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_cashout_per_day_cents: int | None = Field(default=None, ge=0)
    max_cashout_per_month_cents: int | None = Field(default=None, ge=0)
    max_cashout_count_per_day: int | None = Field(default=None, ge=0)
    max_cashout_count_per_month: int | None = Field(default=None, ge=0)
    max_cashin_per_day_cents: int | None = Field(default=None, ge=0)
    max_cashin_per_month_cents: int | None = Field(default=None, ge=0)
    max_cashout_count_per_window: int | None = Field(default=None, ge=0)
    cashout_window_minutes: int | None = Field(default=None, ge=0)
    max_distinct_receivers_per_day: int | None = Field(default=None, ge=0)
    clear: bool | None = False


def _defaults() -> dict:
    return {
        "max_cashout_per_day_cents": int(getattr(settings, "MAX_CASHOUT_PER_DAY_CENTS", 0) or 0),
        "max_cashout_per_month_cents": int(getattr(settings, "MAX_CASHOUT_PER_MONTH_CENTS", 0) or 0),
        "max_cashout_count_per_day": int(getattr(settings, "MAX_CASHOUT_COUNT_PER_DAY", 0) or 0),
        "max_cashout_count_per_month": int(getattr(settings, "MAX_CASHOUT_COUNT_PER_MONTH", 0) or 0),
        "max_cashin_per_day_cents": int(getattr(settings, "MAX_CASHIN_PER_DAY_CENTS", 0) or 0),
        "max_cashin_per_month_cents": int(getattr(settings, "MAX_CASHIN_PER_MONTH_CENTS", 0) or 0),
        "max_cashout_count_per_window": int(getattr(settings, "MAX_CASHOUT_COUNT_PER_WINDOW", 0) or 0),
        "cashout_window_minutes": int(getattr(settings, "CASHOUT_WINDOW_MINUTES", 0) or 0),
        "max_distinct_receivers_per_day": int(getattr(settings, "MAX_DISTINCT_RECEIVERS_PER_DAY", 0) or 0),
    }


@router.get("/users/{user_id}")
def get_user_limits(user_id: UUID, _admin=Depends(require_admin)):
    with get_conn() as conn:
        overrides = get_user_limit_override(conn, str(user_id))
    return {"user_id": str(user_id), "defaults": _defaults(), "overrides": overrides or None}


@router.put("/users/{user_id}")
def set_user_limits(
    user_id: UUID,
    body: UserLimitOverrideRequest,
    admin: CurrentUser = Depends(require_admin),
):
    payload = body.model_dump(exclude={"clear"})
    with get_conn() as conn:
        if body.clear:
            clear_user_limit_override(conn, str(user_id))
            overrides = None
        else:
            overrides = upsert_user_limit_override(conn, str(user_id), payload)

        write_audit_log(
            conn,
            actor_user_id=str(admin.user_id),
            action="USER_LIMITS_UPDATED",
            target_id=str(user_id),
            metadata={"payload": payload, "clear": bool(body.clear)},
        )
        conn.commit()

    if body.clear:
        return {"ok": True, "user_id": str(user_id), "overrides": None}
    if not overrides:
        raise HTTPException(status_code=500, detail="FAILED_TO_UPDATE_LIMITS")
    return {"ok": True, "user_id": str(user_id), "overrides": overrides}
