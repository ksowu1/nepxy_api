

# schemas.py
from __future__ import annotations

from pydantic import BaseModel, Field, EmailStr
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Literal

RoleName = Literal["ADMIN", "SUPPORT", "USER"]


# -------- AUTH --------
class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: UUID


# (Optional: keep if you already use it somewhere)
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# -------- PAYMENTS --------
class P2PRequest(BaseModel):
    sender_account_id: UUID
    receiver_account_id: UUID
    amount_cents: int = Field(gt=0)
    country: str = Field(pattern="^(TG|BJ|BF|ML)$")
    description: Optional[str] = None


class MerchantPayRequest(BaseModel):
    payer_account_id: UUID
    merchant_account_id: UUID
    amount_cents: int = Field(gt=0)
    country: str = Field(pattern="^(TG|BJ|BF|ML)$")
    note: Optional[str] = None


class CashInRequest(BaseModel):
    user_account_id: UUID
    amount_cents: int = Field(gt=0)
    country: str = Field(pattern="^(TG|BJ|BF|ML)$")
    provider_ref: str = Field(min_length=3, max_length=100)


class CashOutRequest(BaseModel):
    user_account_id: UUID
    amount_cents: int = Field(gt=0)
    country: str = Field(pattern="^(TG|BJ|BF|ML)$")
    provider_ref: str = Field(min_length=3, max_length=100)


class TxnResponse(BaseModel):
    transaction_id: UUID


# -------- WALLETS --------
class WalletItem(BaseModel):
    wallet_id: UUID
    owner_id: UUID
    owner_type: str
    currency: str
    country: str
    account_type: str  # stored as account_type in DB, but represents WALLET here


class WalletListResponse(BaseModel):
    wallets: List[WalletItem]


class WalletBalanceResponse(BaseModel):
    wallet_id: UUID
    balance_cents: int


class WalletTxnItem(BaseModel):
    entry_id: UUID
    transaction_id: UUID
    dc: str
    amount_cents: int
    memo: Optional[str] = None
    created_at: datetime


class WalletTxnPage(BaseModel):
    wallet_id: UUID
    items: List[WalletTxnItem]
    next_cursor: Optional[str] = None


class WalletActivityItem(BaseModel):
    transaction_id: UUID
    created_at: datetime
    direction: str
    amount_cents: int
    net_cents: int
    memo: str


class WalletActivityPage(BaseModel):
    wallet_id: UUID
    items: List[WalletActivityItem]
    next_cursor: Optional[str] = None


class LedgerIntegrityCheckResponse(BaseModel):
    mismatches: int
    repaired: bool

class LedgerIntegrityCheckRequest(BaseModel):
    repair: bool = False
    account_id: Optional[UUID] = None


#
class AdminSetRoleRequest(BaseModel):
    target_user_id: UUID
    role: RoleName

class AdminClearRoleRequest(BaseModel):
    target_user_id: UUID

class UserRoleItem(BaseModel):
    user_id: UUID
    role: str
    created_at: datetime

class UserRoleListResponse(BaseModel):
    items: List[UserRoleItem]


class RegisterRequest(BaseModel):
    email: EmailStr
    phone_e164: str = Field(min_length=5)
    full_name: str | None = None
    country: str  # cast in SQL to ledger.country_code
    password: str = Field(min_length=8)

class RegisterResponse(BaseModel):
    user_id: UUID

class P2PTransferRequest(BaseModel):
    from_wallet_id: UUID
    to_wallet_id: UUID
    amount_cents: int = Field(..., gt=0)
    memo: Optional[str] = None
