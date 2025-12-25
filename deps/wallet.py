

from fastapi import Depends, HTTPException
from uuid import UUID

from db import get_conn
from deps.auth import get_current_user, CurrentUser

def require_wallet_owner(
    wallet_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 1
                FROM ledger.ledger_accounts
                WHERE id = %s::uuid
                  AND owner_type = 'USER'
                  AND owner_id = %s::uuid
                  AND account_type = 'WALLET';
            """, (str(wallet_id), str(user.user_id)))
            ok = cur.fetchone()

    if not ok:
        raise HTTPException(status_code=403, detail="WALLET_NOT_OWNED")

    return user
