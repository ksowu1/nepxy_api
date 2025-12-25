

# deps/admin.py
from fastapi import Depends, HTTPException, status
from deps.auth import get_current_user, CurrentUser
from db import get_conn
from db_session import set_db_actor

def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    with get_conn() as conn:
        with conn.cursor() as cur:
            # keep ownership model consistent
            set_db_actor(cur, user.user_id)

            cur.execute("SELECT users.is_admin_secure(%s::uuid);", (str(user.user_id),))
            is_admin = cur.fetchone()[0]

    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ADMIN_REQUIRED",
        )
    return user
