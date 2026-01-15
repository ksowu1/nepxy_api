from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID

from deps.auth import get_current_user, CurrentUser
from deps.admin import require_admin
from schemas import WalletInvariantListResponse, WalletInvariantResponse
from services.ledger_invariants import (
    assert_wallet_balance_matches_ledger,
    list_wallet_balance_invariants,
)
from settings import settings

router = APIRouter(prefix="/debug", tags=["debug"])


def _require_dev() -> None:
    if (settings.ENV or "dev").lower() != "dev":
        raise HTTPException(status_code=404, detail="Not found")


@router.get("/me")
def debug_me(user: CurrentUser = Depends(get_current_user)):
    # CurrentUser in your project carries user_id; keep response minimal for tests
    return {"user_id": str(user.user_id)}


@router.get("/invariants/wallet/{wallet_id}", response_model=WalletInvariantResponse)
def debug_wallet_invariant(
    wallet_id: UUID,
    admin: CurrentUser = Depends(require_admin),
):
    _require_dev()
    result = assert_wallet_balance_matches_ledger(wallet_id)
    return WalletInvariantResponse(ok=bool(result["ok"]), wallet=result)


@router.get("/invariants/wallets", response_model=WalletInvariantListResponse)
def debug_wallet_invariants(admin: CurrentUser = Depends(require_admin)):
    _require_dev()
    items = list_wallet_balance_invariants()
    mismatches = sum(1 for item in items if not item["ok"])
    return WalletInvariantListResponse(
        ok=mismatches == 0,
        count=len(items),
        mismatches=mismatches,
        items=items,
    )
