from __future__ import annotations

import os
import time
import uuid
from typing import Any, Optional

import requests

from app.providers.base import ProviderResult


BASE_URL = "https://sandbox.momodeveloper.mtn.com"
TOKEN_SAFETY_BUFFER_S = 60


class MomoProvider:
    def __init__(self) -> None:
        momo_env = (os.getenv("MOMO_ENV") or "sandbox").strip().lower()
        self.base_url = BASE_URL
        self.target_env = "sandbox" if momo_env == "sandbox" else "sandbox"
        self.api_user_id = (os.getenv("MOMO_API_USER_ID") or "").strip()
        self.api_key = (os.getenv("MOMO_API_KEY") or "").strip()
        self.subscription_key = (os.getenv("MOMO_DISBURSE_SUB_KEY") or "").strip()
        self.callback_host = (os.getenv("MOMO_CALLBACK_HOST") or "").strip()
        self._token: Optional[str] = None
        self._token_exp: float = 0.0

    def initiate_payout(self, payout: dict) -> ProviderResult:
        missing = _missing_env(self.api_user_id, self.api_key, self.subscription_key)
        if missing:
            return ProviderResult(status="FAILED", error="MOMO_CONFIG_MISSING", response={"missing": missing})

        phone = (payout.get("phone_e164") or "").strip()
        currency = (payout.get("currency") or "").strip().upper()
        amount_cents = payout.get("amount_cents")
        if not phone:
            return ProviderResult(status="FAILED", error="Missing phone_e164", retryable=False)
        if not currency:
            return ProviderResult(status="FAILED", error="Missing currency", retryable=False)
        if amount_cents is None or int(amount_cents) <= 0:
            return ProviderResult(status="FAILED", error="Missing/invalid amount_cents", retryable=False)

        provider_ref = str(payout.get("provider_ref") or payout.get("id") or payout.get("transaction_id") or uuid.uuid4())
        external_ref = str(payout.get("external_ref") or payout.get("transaction_id") or provider_ref)

        amount = f"{int(amount_cents) / 100:.2f}"
        resp = self.create_transfer(
            amount=amount,
            currency=currency,
            external_id=external_ref,
            phone_e164=phone,
            reference_id=provider_ref,
            note=payout.get("payee_note") or "NepXy cash-out",
        )
        if isinstance(resp, ProviderResult):
            return resp

        if resp.status_code in (200, 201, 202):
            return ProviderResult(status="SENT", provider_ref=provider_ref, response=_safe_json(resp))

        retryable = _is_retryable_http(resp.status_code)
        return ProviderResult(
            status="FAILED",
            provider_ref=provider_ref,
            response=_response_payload(resp),
            error=f"HTTP {resp.status_code}",
            retryable=retryable,
        )

    def get_status(self, payout: dict) -> ProviderResult:
        provider_ref = (payout.get("provider_ref") or "").strip()
        if not provider_ref:
            return ProviderResult(status="SENT", error="MISSING_PROVIDER_REF", retryable=True)

        missing = _missing_env(self.api_user_id, self.api_key, self.subscription_key)
        if missing:
            return ProviderResult(status="SENT", error="MOMO_CONFIG_MISSING", response={"missing": missing})

        token = self.get_access_token_disbursement()
        if not token:
            return ProviderResult(status="SENT", provider_ref=provider_ref, error="MOMO_TOKEN_ERROR", retryable=True)

        resp = self.get_transfer_status(provider_ref)
        if isinstance(resp, ProviderResult):
            return resp

        payload = _safe_json(resp)
        if resp.status_code == 200 and isinstance(payload, dict):
            status = (payload.get("status") or payload.get("financialTransactionStatus") or "").upper()
            if status in ("SUCCESSFUL", "SUCCESS", "COMPLETED"):
                return ProviderResult(status="CONFIRMED", provider_ref=provider_ref, response=payload)
            if status in ("FAILED", "REJECTED"):
                return ProviderResult(
                    status="FAILED",
                    provider_ref=provider_ref,
                    response=payload,
                    error=status,
                    retryable=False,
                )
            if status == "PENDING":
                return ProviderResult(status="SENT", provider_ref=provider_ref, response=payload, retryable=True)
            return ProviderResult(status="SENT", provider_ref=provider_ref, response=payload, retryable=True)

        retryable = _is_retryable_http(resp.status_code)
        return ProviderResult(
            status="SENT",
            provider_ref=provider_ref,
            response=_response_payload(resp),
            error=f"HTTP {resp.status_code}",
            retryable=retryable,
        )

    def get_access_token_disbursement(self) -> str | None:
        now = time.time()
        if self._token and now < (self._token_exp - TOKEN_SAFETY_BUFFER_S):
            return self._token

        url = f"{self.base_url}/disbursement/token/"
        headers = {"Ocp-Apim-Subscription-Key": self.subscription_key}
        try:
            resp = requests.post(url, headers=headers, auth=(self.api_user_id, self.api_key))
        except Exception:
            return None

        if resp.status_code == 200:
            payload = _safe_json(resp)
            token = payload.get("access_token") if isinstance(payload, dict) else None
            if token:
                expires_in = int(payload.get("expires_in") or 3600)
                self._token = token
                self._token_exp = now + max(0, expires_in)
                return self._token
        return None

    def create_transfer(
        self,
        *,
        amount: str,
        currency: str,
        external_id: str,
        phone_e164: str,
        reference_id: str,
        note: str,
    ):
        token = self.get_access_token_disbursement()
        if not token:
            return ProviderResult(status="FAILED", error="MOMO_TOKEN_ERROR", retryable=True)

        url = f"{self.base_url}/disbursement/v1_0/transfer"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Reference-Id": reference_id,
            "X-Target-Environment": self.target_env,
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "Content-Type": "application/json",
        }
        body = {
            "amount": amount,
            "currency": currency,
            "externalId": external_id,
            "payee": {"partyIdType": "MSISDN", "partyId": phone_e164.lstrip("+")},
            "payerMessage": note,
            "payeeNote": note,
        }

        try:
            return requests.post(url, headers=headers, json=body)
        except Exception as exc:
            return ProviderResult(status="FAILED", provider_ref=reference_id, error=str(exc), retryable=True)

    def get_transfer_status(self, reference_id: str):
        token = self.get_access_token_disbursement()
        if not token:
            return ProviderResult(status="SENT", provider_ref=reference_id, error="MOMO_TOKEN_ERROR", retryable=True)

        url = f"{self.base_url}/disbursement/v1_0/transfer/{reference_id}"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Target-Environment": self.target_env,
            "Ocp-Apim-Subscription-Key": self.subscription_key,
        }

        try:
            return requests.get(url, headers=headers)
        except Exception as exc:
            return ProviderResult(status="SENT", provider_ref=reference_id, error=str(exc), retryable=True)

    def get_token(self) -> str | None:
        return self.get_access_token_disbursement()

    def get_payout_status(self, payout: dict) -> ProviderResult:
        return self.get_status(payout)

    def send_cashout(self, payout: dict) -> ProviderResult:
        return self.initiate_payout(payout)

    def get_cashout_status(self, payout: dict) -> ProviderResult:
        return self.get_status(payout)


def _safe_json(resp) -> Any:
    try:
        return resp.json()
    except Exception:
        return None


def _response_payload(resp) -> dict[str, Any]:
    return {
        "http_status": resp.status_code,
        "body": _safe_json(resp),
        "text": getattr(resp, "text", None),
    }


def _is_retryable_http(status_code: int) -> bool:
    if 500 <= status_code <= 599:
        return True
    if status_code in (408, 429):
        return True
    return False


def _missing_env(api_user_id: str, api_key: str, subscription_key: str) -> list[str]:
    missing: list[str] = []
    if not api_user_id:
        missing.append("MOMO_API_USER_ID")
    if not api_key:
        missing.append("MOMO_API_KEY")
    if not subscription_key:
        missing.append("MOMO_DISBURSE_SUB_KEY")
    return missing
