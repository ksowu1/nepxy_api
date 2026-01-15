from fastapi import APIRouter, Depends

from deps.auth import get_current_user, CurrentUser
from services.corridors import payout_provider_catalog

router = APIRouter(prefix="/v1/catalog", tags=["catalog"])


@router.get("/payout-providers")
def list_payout_providers(user: CurrentUser = Depends(get_current_user)):
    return payout_provider_catalog()
