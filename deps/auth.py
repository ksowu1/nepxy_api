

# deps/auth.py
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from uuid import UUID

from security import decode_token

bearer = HTTPBearer(auto_error=False)

class CurrentUser:
    def __init__(self, user_id: UUID):
        self.user_id = user_id

def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
) -> CurrentUser:
    if not creds:
        raise HTTPException(status_code=401, detail="UNAUTHORIZED")

    # must be "Bearer"
    if (creds.scheme or "").lower() != "bearer":
        raise HTTPException(status_code=401, detail="UNAUTHORIZED")

    try:
        payload = decode_token(creds.credentials)
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail="UNAUTHORIZED")
        return CurrentUser(user_id=UUID(sub))
    except Exception:
        raise HTTPException(status_code=401, detail="UNAUTHORIZED")
