

# app/providers/mobile_money/mtn_momo.py
from __future__ import annotations

import base64
import time
from typing import Optional

import httpx

from app.providers.base import ProviderResult, MobileMoneyProvider
from app.providers.mobile_money.config import momo_config
from app.providers.mobile_money.http import HttpClient, is_retryable_http
from settings import settings


class MtnMomoProvider(MobileMoneyProvider):
    def __init__(self, http: Optional[HttpClient] = None):
        timeout = float(getattr(settings, "MOMO_HTTP_TIMEOUT_S", 20.0))
        self.http = http or HttpClient(timeout_s=timeout)
        self._token: Optional[str] = None
        self._token_exp: float = 0.0

    def send_cashout(self, payout: dict) -> ProviderResult:
        cfg = momo_config()
        token = self._get_token()
        if not token:
            return ProviderResult(status="FAILED", error="momo token error", retryable=True)

        phone = (payout.get("phone_e164") or "").strip()
        amount_cents = payout.get("amount_cents")
        currency = (payout.get("currency") or "").strip().upper()

        if not phone:
            return ProviderResult(status="FAILED", error="Missing phone_e164", retryable=False)
        if not currency:
            return ProviderResult(status="FAILED", error="Missing currency", retryable=False)
        if amount_cents is None or int(amount_cents) <= 0:
            return ProviderResult(status="FAILED", error="Missing/invalid amount_cents", retryable=False)

        amount = f"{int(amount_cents) / 100:.2f}"
        provider_ref = str(payout.get("provider_ref") or payout.get("id") or payout.get("transaction_id"))

        url = f"{cfg.base_url}/disbursement/v1_0/transfer"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Reference-Id": provider_ref,
            "X-Target-Environment": cfg.target_env,
            "Ocp-Apim-Subscription-Key": cfg.subscription_key,
            "Content-Type": "application/json",
        }
        if cfg.callback_url:
            headers["X-Callback-Url"] = cfg.callback_url

        body = {
            "amount": amount,
            "currency": currency,
            "externalId": str(payout.get("transaction_id") or provider_ref),
            "payee": {"partyIdType": "MSISDN", "partyId": phone.lstrip("+")},
            "payerMessage": payout.get("payer_message") or "NepXy cash-out",
            "payeeNote": payout.get("payee_note") or "NepXy cash-out",
        }

        try:
            resp = self.http.post(url, headers=headers, json_body=body, debug=True)
        except httpx.TimeoutException:
            return ProviderResult(status="FAILED", error="Gateway timeout", retryable=True)
        except Exception as e:
            return ProviderResult(status="FAILED", error=f"Provider error: {e}", retryable=True)

        if resp.status_code in (200, 201, 202):
            return ProviderResult(status="SENT", provider_ref=provider_ref, response=resp.json)

        return ProviderResult(
            status="FAILED",
            provider_ref=None,
            response={"http_status": resp.status_code, "body": resp.json, "text": resp.text},
            error=f"HTTP {resp.status_code}",
            retryable=is_retryable_http(resp.status_code),
        )

    def get_cashout_status(self, payout: dict) -> ProviderResult:
        cfg = momo_config()
        token = self._get_token()
        if not token:
            return ProviderResult(status="SENT", error="momo token error", retryable=True)

        provider_ref = str(payout.get("provider_ref") or payout.get("id") or payout.get("transaction_id"))
        url = f"{cfg.base_url}/disbursement/v1_0/transfer/{provider_ref}"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Target-Environment": cfg.target_env,
            "Ocp-Apim-Subscription-Key": cfg.subscription_key,
        }

        try:
            resp = self.http.get(url, headers=headers, debug=True)
        except httpx.TimeoutException:
            return ProviderResult(status="SENT", provider_ref=provider_ref, error="Gateway timeout", retryable=True)
        except Exception as e:
            return ProviderResult(status="SENT", provider_ref=provider_ref, error=f"Provider error: {e}", retryable=True)

        if resp.status_code == 200 and isinstance(resp.json, dict):
            st = (resp.json.get("status") or resp.json.get("financialTransactionStatus") or "").upper()
            if st in ("SUCCESSFUL", "SUCCESS", "COMPLETED"):
                return ProviderResult(status="CONFIRMED", provider_ref=provider_ref, response=resp.json)
            if st in ("FAILED", "REJECTED", "CANCELLED"):
                return ProviderResult(status="FAILED", provider_ref=provider_ref, response=resp.json, error=st, retryable=False)
            return ProviderResult(status="SENT", provider_ref=provider_ref, response=resp.json, retryable=True)

        return ProviderResult(
            status="SENT",
            provider_ref=provider_ref,
            response={"http_status": resp.status_code, "body": resp.json, "text": resp.text},
            error=f"HTTP {resp.status_code}",
            retryable=is_retryable_http(resp.status_code),
        )

    def _get_token(self) -> Optional[str]:
        cfg = momo_config()
        now = time.time()
        if self._token and now < (self._token_exp - 30):
            return self._token

        if not (cfg.base_url and cfg.api_user and cfg.api_key and cfg.subscription_key):
            return None

        basic = base64.b64encode(f"{cfg.api_user}:{cfg.api_key}".encode()).decode()
        url = f"{cfg.base_url}/disbursement/token/"
        headers = {
            "Authorization": f"Basic {basic}",
            "Ocp-Apim-Subscription-Key": cfg.subscription_key,
            "X-Target-Environment": cfg.target_env,
        }

        try:
            resp = self.http.post(url, headers=headers, json_body=None, debug=True)
        except Exception:
            return None

        if resp.status_code == 200 and isinstance(resp.json, dict) and resp.json.get("access_token"):
            self._token = resp.json["access_token"]
            expires_in = int(resp.json.get("expires_in") or 3600)
            self._token_exp = now + expires_in
            return self._token

        return None
