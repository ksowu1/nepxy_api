

# schemas.py

from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, ConfigDict

# -----------------------------
# Shared Types / Enums
# -----------------------------

CountryCode = Literal["TG", "BJ", "BF", "ML", "GH"]
RoleName = Literal["ADMIN", "SUPPORT", "USER"]


class MobileMoneyProvider(str, Enum):
    """Mobile money providers supported in West Africa (extensible)."""
    MOMO = "MOMO"        # MTN MoMo (or generic MoMo rail)
    TMONEY = "TMONEY"    # Togo TMoney
    FLOOZ = "FLOOZ"      # Moov Flooz
    THUNES = "THUNES"    # Thunes (licensed partner / aggregator)


E164_REGEX = r"^\+[1-9]\d{4,14}$"  # basic E.164 validation


# -----------------------------
# Auth
# -----------------------------

class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    access_token: str
    token_type: str = "bearer"
    user_id: UUID


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    phone_e164: str = Field(min_length=5, pattern=E164_REGEX)
    full_name: Optional[str] = None
    country: CountryCode
    password: str = Field(min_length=8)


class RegisterResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: UUID


# -----------------------------
# Payments
# -----------------------------

class TxnResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transaction_id: UUID


class CashOutQuote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    send_amount_cents: int
    fee_cents: int
    fx_rate: str
    receive_amount_minor: int
    corridor: str
    provider: str


class CashOutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transaction_id: UUID
    external_ref: str | None = None
    fee_cents: int | None = None
    fx_rate: str | None = None
    receive_amount_minor: int | None = None
    corridor: str | None = None


class PayoutQuoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    destination_country: CountryCode
    amount_cents: int = Field(gt=0)
    preferred_method: Optional[str] = None


class PayoutQuoteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    destination_country: str
    currency: str | None = None
    available_methods: List[str]
    recommended_method: str | None = None
    providers_per_method: dict[str, list[str]]
    fee_cents: int
    notes: Optional[str] = None


class P2PTransferRequest(BaseModel):
    """Current API schema used by /v1/p2p/transfer."""
    model_config = ConfigDict(extra="forbid")
    from_wallet_id: UUID
    to_wallet_id: UUID
    amount_cents: int = Field(gt=0)
    memo: Optional[str] = None


class MerchantPayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payer_account_id: UUID
    merchant_account_id: UUID
    amount_cents: int = Field(gt=0)
    country: CountryCode
    note: Optional[str] = None


class CashInRequest(BaseModel):
    """
    Wallet-only cash-in contract.
    """
    model_config = ConfigDict(extra="forbid")
    wallet_id: UUID
    amount_cents: int = Field(gt=0)
    country: CountryCode
    provider_ref: Optional[str] = Field(default=None, min_length=3, max_length=100)
    provider: MobileMoneyProvider = MobileMoneyProvider.MOMO
    phone_e164: Optional[str] = Field(default=None, pattern=E164_REGEX)


class CashOutRequest(BaseModel):
    """
    Wallet-only cash-out contract.
    """
    model_config = ConfigDict(extra="forbid")
    wallet_id: UUID
    amount_cents: int = Field(gt=0)
    country: CountryCode | None = None
    destination_country: CountryCode | None = None
    delivery_method: Optional[str] = None
    provider_ref: Optional[str] = Field(default=None, min_length=3, max_length=100)
    provider: Optional[MobileMoneyProvider] = None
    phone_e164: Optional[str] = Field(default=None, pattern=E164_REGEX)


# -----------------------------
# Wallets
# -----------------------------

class WalletItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    wallet_id: UUID
    owner_id: UUID
    owner_type: str
    currency: str
    country: str
    account_type: str


class WalletListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    wallets: List[WalletItem]


class WalletBalanceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    wallet_id: UUID
    balance_cents: int


class WalletTxnItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entry_id: UUID
    transaction_id: UUID
    dc: str
    amount_cents: int
    memo: Optional[str] = None
    created_at: datetime


class WalletTxnPage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    wallet_id: UUID
    items: List[WalletTxnItem]
    next_cursor: Optional[str] = None


class WalletActivityItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transaction_id: UUID
    created_at: datetime
    direction: str
    amount_cents: int
    net_cents: int
    memo: str


class WalletActivityPage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    wallet_id: UUID
    items: List[WalletActivityItem]
    next_cursor: Optional[str] = None


# -----------------------------
# Admin / Ledger Tools
# -----------------------------

class LedgerIntegrityCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repair: bool = False
    account_id: Optional[UUID] = None


class LedgerIntegrityCheckResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mismatches: int
    repaired: bool


class WalletInvariantItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    wallet_id: UUID
    balance_cents: int
    ledger_cents: int
    diff_cents: int
    ok: bool
    balance_source: str


class WalletInvariantResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool
    wallet: WalletInvariantItem


class WalletInvariantListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool
    count: int
    mismatches: int
    items: List[WalletInvariantItem]


class AdminSetRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_user_id: UUID
    role: RoleName


class AdminClearRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_user_id: UUID


class UserRoleItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: UUID
    role: str
    created_at: datetime


class UserRoleListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: List[UserRoleItem]


class PayoutStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transaction_id: UUID
    provider: str | None = None
    status: str
    attempt_count: int = 0
    retryable: bool | None = None
    provider_ref: str | None = None
    last_error: str | None = None
    last_attempt_at: datetime | None = None
    next_retry_at: datetime | None = None
    provider_response: dict | None = None
    amount_cents: int | None = None
    currency: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
