

# routes/admin_ledger.py
from fastapi import APIRouter, Depends
from typing import Optional
from uuid import UUID

from db import get_conn
from db_session import set_db_actor
from deps.admin import require_admin
from deps.auth import CurrentUser
from schemas import LedgerIntegrityCheckResponse

router = APIRouter(prefix="/v1/admin/ledger", tags=["admin-ledger"])

@router.post("/integrity-check", response_model=LedgerIntegrityCheckResponse)
def integrity_check(
    repair: bool = False,
    account_id: Optional[UUID] = None,
    admin: CurrentUser = Depends(require_admin),
):
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Optional: set actor for audit context (DB function uses NULL actor now)
            set_db_actor(cur, admin.user_id)

            cur.execute(
                "SELECT mismatches, repaired FROM ledger.check_and_log_balance_integrity(%s::bool, %s::uuid);",
                (repair, str(account_id) if account_id else None),
            )
            row = cur.fetchone()

    return LedgerIntegrityCheckResponse(mismatches=int(row[0]), repaired=bool(row[1]))
