


# app/providers/mobile_money/flooz.py
from __future__ import annotations

from typing import Optional

import httpx

from app.providers.base import ProviderResult, MobileMoneyProvider
from app.providers.mobile_money.config import flooz_config
from app.providers.mobile_money.http import HttpClient, is_retryable_http
from settings import settings


class FloozProvider(MobileMoneyProvider):
    def __init__(self, http: Optional[HttpClient] = None):
        timeout = float(getattr(settings, "MM_HTTP_TIMEOUT_S", 20.0))
        self.http = http or HttpClient(timeout_s=timeout)

    def send_cashout(self, payout: dict) -> ProviderResult:
        cfg = flooz_config()
        url = cfg.cashout_url

        print("[FLOOZ] mode     =", repr(cfg.mode))
        print("[FLOOZ] cashout  =", repr(url))
        print("[FLOOZ] auth_mode=", repr(cfg.auth_mode))
        print("[FLOOZ] api_key? =", bool(cfg.api_key))

        if not url:
            return ProviderResult(status="FAILED", error="FLOOZ_CASHOUT_URL not configured", retryable=False)

        auth_mode = (cfg.auth_mode or "bearer").strip().lower()
        api_key = (cfg.api_key or "").strip()
        if auth_mode in ("bearer", "x-api-key") and not api_key:
            return ProviderResult(status="FAILED", error="FLOOZ_API_KEY not configured", retryable=False)

        phone = (payout.get("phone_e164") or "").strip()
        amount_cents = payout.get("amount_cents")
        currency = payout.get("currency")

        if not phone:
            return ProviderResult(status="FAILED", error="Missing phone_e164", retryable=False)
        if not currency:
            return ProviderResult(status="FAILED", error="Missing currency", retryable=False)
        if amount_cents is None or int(amount_cents) <= 0:
            return ProviderResult(status="FAILED", error="Missing/invalid amount_cents", retryable=False)

        provider_ref = str(payout.get("provider_ref") or payout.get("id") or payout.get("transaction_id"))

        headers = _auth_headers(auth_mode, api_key)
        headers["Content-Type"] = "application/json"

        body = {
            "external_id": provider_ref,
            "amount_cents": int(amount_cents),
            "currency": currency,
            "msisdn": phone,
        }

        try:
            resp = self.http.post(url, headers=headers, json_body=body, debug=True)
        except httpx.TimeoutException:
            return ProviderResult(status="FAILED", error="Gateway timeout", retryable=True)
        except Exception as e:
            return ProviderResult(status="FAILED", error=f"Provider error: {e}", retryable=True)

        if resp.status_code in (200, 201, 202):
            returned_ref = provider_ref
            if isinstance(resp.json, dict):
                returned_ref = (
                    resp.json.get("provider_ref")
                    or resp.json.get("provider_tx_id")
                    or resp.json.get("id")
                    or resp.json.get("reference")
                    or returned_ref
                )
            return ProviderResult(status="SENT", provider_ref=returned_ref, response=resp.json)

        err_msg = None
        if isinstance(resp.json, dict):
            err_msg = resp.json.get("message") or resp.json.get("error")

        return ProviderResult(
            status="FAILED",
            provider_ref=None,
            response={"http_status": resp.status_code, "body": resp.json, "text": resp.text},
            error=err_msg or f"HTTP {resp.status_code}",
            retryable=is_retryable_http(resp.status_code),
        )

    def get_cashout_status(self, payout: dict) -> ProviderResult:
        cfg = flooz_config()
        tpl = cfg.status_url_template
        provider_ref = payout.get("provider_ref")

        if not tpl or not provider_ref:
            return ProviderResult(status="SENT", provider_ref=provider_ref, error="Missing status url/provider_ref", retryable=True)

        auth_mode = (cfg.auth_mode or "bearer").strip().lower()
        api_key = (cfg.api_key or "").strip()
        if auth_mode in ("bearer", "x-api-key") and not api_key:
            return ProviderResult(status="SENT", provider_ref=provider_ref, error="FLOOZ_API_KEY not configured", retryable=True)

        url = tpl.format(provider_ref=provider_ref)
        headers = _auth_headers(auth_mode, api_key)

        try:
            resp = self.http.get(url, headers=headers, debug=True)
        except httpx.TimeoutException:
            return ProviderResult(status="SENT", provider_ref=provider_ref, error="Gateway timeout", retryable=True)
        except Exception as e:
            return ProviderResult(status="SENT", provider_ref=provider_ref, error=f"Provider error: {e}", retryable=True)

        if resp.status_code == 200 and isinstance(resp.json, dict):
            st = (resp.json.get("status") or "").upper()
            if st in ("SUCCESS", "SUCCESSFUL", "CONFIRMED", "COMPLETED"):
                return ProviderResult(status="CONFIRMED", provider_ref=provider_ref, response=resp.json)
            if st in ("FAILED", "CANCELLED", "REJECTED"):
                return ProviderResult(status="FAILED", provider_ref=provider_ref, response=resp.json, error=st, retryable=False)
            return ProviderResult(status="SENT", provider_ref=provider_ref, response=resp.json, retryable=True)

        return ProviderResult(
            status="SENT",
            provider_ref=provider_ref,
            response={"http_status": resp.status_code, "body": resp.json, "text": resp.text},
            error=f"HTTP {resp.status_code}",
            retryable=is_retryable_http(resp.status_code),
        )


def _auth_headers(mode: str, api_key: str) -> dict[str, str]:
    mode = (mode or "bearer").lower()
    api_key = (api_key or "").strip()

    if mode in ("none", "noauth") or not api_key:
        return {}
    if mode == "x-api-key":
        return {"X-Api-Key": api_key}
    return {"Authorization": f"Bearer {api_key}"}
