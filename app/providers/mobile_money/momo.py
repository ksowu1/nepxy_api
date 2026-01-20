from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any, Optional

import requests

from app.providers.base import ProviderResult


BASE_URL = "https://sandbox.momodeveloper.mtn.com"
TOKEN_SAFETY_BUFFER_S = 60
logger = logging.getLogger("nexapay")
DESTINATION_CURRENCY = {
    "GH": "GHS",
}


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
        dest_country = (payout.get("destination_country") or payout.get("country") or "").strip().upper()
        currency = DESTINATION_CURRENCY.get(dest_country) or (payout.get("currency") or "").strip().upper()
        request_currency = _resolve_currency(currency)
        amount_cents = payout.get("amount_cents")
        if not phone:
            return ProviderResult(status="FAILED", error="Missing phone_e164", retryable=False)
        if not currency and self.target_env != "sandbox":
            return ProviderResult(status="FAILED", error="Missing currency", retryable=False)
        if amount_cents is None or int(amount_cents) <= 0:
            return ProviderResult(status="FAILED", error="Missing/invalid amount_cents", retryable=False)

        provider_ref = str(payout.get("provider_ref") or payout.get("id") or payout.get("transaction_id") or uuid.uuid4())
        external_ref = str(payout.get("external_ref") or payout.get("transaction_id") or provider_ref)

        amount = f"{int(amount_cents) / 100:.2f}"
        return self.create_transfer(
            amount=amount,
            currency=request_currency,
            external_id=external_ref,
            phone_e164=phone,
            reference_id=provider_ref,
            note=payout.get("payee_note") or "NepXy cash-out",
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
                return ProviderResult(status="CONFIRMED", provider_ref=provider_ref, response=_response_payload(resp, stage="poll"))
            if status in ("FAILED", "REJECTED"):
                return ProviderResult(
                    status="FAILED",
                    provider_ref=provider_ref,
                    response=_response_payload(resp, stage="poll"),
                    error=status,
                    retryable=False,
                )
            if status == "PENDING":
                return ProviderResult(status="SENT", provider_ref=provider_ref, response=_response_payload(resp, stage="poll"), retryable=True)
            return ProviderResult(status="SENT", provider_ref=provider_ref, response=_response_payload(resp, stage="poll"), retryable=True)

        if _is_currency_error(payload):
            return ProviderResult(
                status="FAILED",
                provider_ref=provider_ref,
                response=_response_payload(resp, stage="poll"),
                error=_currency_error_code(payload),
                retryable=False,
            )

        retryable = _is_retryable_http(resp.status_code)
        return ProviderResult(
            status="SENT",
            provider_ref=provider_ref,
            response=_response_payload(resp, stage="poll"),
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
        request_currency = _resolve_currency(currency)
        body = {
            "amount": amount,
            "currency": request_currency,
            "externalId": external_id,
            "payee": {"partyIdType": "MSISDN", "partyId": phone_e164.lstrip("+")},
            "payerMessage": note,
            "payeeNote": note,
        }

        try:
            resp = requests.post(url, headers=headers, json=body)
            logger.info(
                "momo transfer create status=%s reference_id=%s",
                resp.status_code,
                reference_id,
            )
            payload = _safe_json(resp)
            if isinstance(payload, dict):
                code = (payload.get("code") or "").upper()
                if code == "INVALID_CURRENCY":
                    return ProviderResult(
                        status="FAILED",
                        provider_ref=reference_id,
                        response=_response_payload(
                            resp,
                            stage="create",
                            request_meta=_request_meta(
                                currency=request_currency,
                                amount=amount,
                                payee_id=body["payee"]["partyId"],
                            ),
                        ),
                        error=code,
                        retryable=False,
                    )

            if resp.status_code in (200, 201, 202):
                ref = _extract_reference_id(payload) or reference_id
                return ProviderResult(
                    status="SENT",
                    provider_ref=ref,
                    response=_response_payload(
                        resp,
                        stage="create",
                        request_meta=_request_meta(
                            currency=request_currency,
                            amount=amount,
                            payee_id=body["payee"]["partyId"],
                        ),
                    ),
                    retryable=True,
                )

            retryable = _is_retryable_http(resp.status_code)
            return ProviderResult(
                status="FAILED",
                provider_ref=reference_id,
                response=_response_payload(
                    resp,
                    stage="create",
                    request_meta=_request_meta(
                        currency=request_currency,
                        amount=amount,
                        payee_id=body["payee"]["partyId"],
                    ),
                ),
                error=f"HTTP {resp.status_code}",
                retryable=retryable,
            )
        except Exception as exc:
            logger.warning("momo transfer create error reference_id=%s err=%s", reference_id, exc)
            return ProviderResult(
                status="FAILED",
                provider_ref=reference_id,
                response={"stage": "create", "error": str(exc)},
                error=str(exc),
                retryable=True,
            )

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
            resp = requests.get(url, headers=headers)
            logger.info(
                "momo transfer status status=%s reference_id=%s",
                resp.status_code,
                reference_id,
            )
            return resp
        except Exception as exc:
            logger.warning("momo transfer status error reference_id=%s err=%s", reference_id, exc)
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


def _response_payload(resp, *, stage: str, request_meta: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "stage": stage,
        "http_status": resp.status_code,
        "body": _safe_json(resp),
        "text": getattr(resp, "text", None),
    }
    if request_meta:
        payload["request"] = request_meta
    return payload


def _extract_reference_id(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in ("referenceId", "reference_id", "transactionReference", "providerReference", "reference"):
        value = payload.get(key)
        if value:
            return str(value)
    return None


def _resolve_currency(payout_currency: str | None) -> str:
    momo_env = (os.getenv("MOMO_ENV") or "sandbox").strip().lower()
    if momo_env == "sandbox":
        return (os.getenv("MOMO_SANDBOX_CURRENCY") or "EUR").strip().upper()
    return (payout_currency or "").strip().upper()


def _request_meta(*, currency: str, amount: str, payee_id: str) -> dict[str, Any]:
    return {
        "currency": currency,
        "amount": amount,
        "payee_party_id": payee_id,
    }


def _currency_error_code(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    raw = payload.get("code") or payload.get("errorCode") or payload.get("error") or payload.get("message")
    if not raw:
        return None
    value = str(raw).upper()
    if "INVALID_CURRENCY" in value:
        return "INVALID_CURRENCY"
    if "CURRENCY_NOT_SUPPORTED" in value:
        return "CURRENCY_NOT_SUPPORTED"
    return None


def _is_currency_error(payload: Any) -> bool:
    return _currency_error_code(payload) is not None


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
