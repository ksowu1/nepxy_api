

# app/providers/mobile_money/thunes.py
from __future__ import annotations

from typing import Any, Dict, Optional
import logging
import requests

from settings import settings
from app.providers.base import ProviderResult


# --- Thunes "Money Transfer API v2" base path is: {API_ENDPOINT}/v2/money-transfer
# Docs: Base URL `/v2/money-transfer` and Basic Auth.  :contentReference[oaicite:10]{index=10}

logger = logging.getLogger("nexapay.thunes")


class ThunesProvider:
    """
    Thunes adapter for your worker contract:
      - send_cashout(payout_dict) -> ProviderResult(status=CONFIRMED|SENT|FAILED, provider_ref=..., response=..., error=..., retryable=...)
      - get_cashout_status(payout_dict) -> ProviderResult(...)
    """

    def __init__(self):
        self.mode = (settings.MM_MODE or "sandbox").strip().lower()

        api_endpoint = (
            settings.THUNES_SANDBOX_API_ENDPOINT
            if self.mode == "sandbox"
            else settings.THUNES_REAL_API_ENDPOINT
        )
        api_key = (
            settings.THUNES_SANDBOX_API_KEY
            if self.mode == "sandbox"
            else settings.THUNES_REAL_API_KEY
        )
        api_secret = (
            settings.THUNES_SANDBOX_API_SECRET
            if self.mode == "sandbox"
            else settings.THUNES_REAL_API_SECRET
        )

        self.api_endpoint = (api_endpoint or "").strip().rstrip("/")
        self.base_url = (self.api_endpoint + "/v2/money-transfer") if self.api_endpoint else ""
        self.api_key = (api_key or "").strip()
        self.api_secret = (api_secret or "").strip()

        self.use_simulation = bool(getattr(settings, "THUNES_USE_SIMULATION", True)) and self.mode == "sandbox"
        self.timeout_s = float(getattr(settings, "MM_HTTP_TIMEOUT_S", 20.0))

    def _auth(self):
        # Thunes uses Basic Authentication: -u API_KEY:API_SECRET  :contentReference[oaicite:11]{index=11}
        if not (self.api_key and self.api_secret):
            return None
        return (self.api_key, self.api_secret)

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.use_simulation:
            # Thunes supports x-simulated-transaction=true for sandbox simulation :contentReference[oaicite:12]{index=12}
            h["x-simulated-transaction"] = "true"
        return h

    def _build_headers(self) -> Dict[str, str]:
        if self.use_simulation:
            logger.info("thunes sandbox simulation headers enabled")
        return self._headers()

    @staticmethod
    def map_thunes_status(status_raw: str) -> tuple[str, bool, str | None]:
        """
        Map Thunes status string -> (internal_status, retryable, last_error).
        """
        st = (status_raw or "").strip().upper()
        if st in ("COMPLETED", "SUCCESS", "SUCCESSFUL", "CONFIRMED", "PAID"):
            return ("CONFIRMED", False, None)

        if st.startswith("DECLINED") or st.startswith("REJECTED") or st in (
            "FAILED",
            "CANCELLED",
            "CANCELED",
        ):
            return ("FAILED", False, st or "THUNES_FAILED")

        # In-flight/unknown => retryable
        return ("SENT", True, None)

    def _payer_id_for_country(self, country2: str) -> Optional[int]:
        c = (country2 or "").strip().upper()
        if c == "TG":
            v = (settings.THUNES_PAYER_ID_TG or "").strip()
        elif c == "BJ":
            v = (settings.THUNES_PAYER_ID_BJ or "").strip()
        else:
            v = ""
        if not v:
            return None
        try:
            return int(v)
        except Exception:
            return None

    def send_cashout(self, payout: dict) -> ProviderResult:
        """
        Called by worker when payout is PENDING.
        Implements: quotation -> transaction -> confirm. :contentReference[oaicite:13]{index=13}
        """
        if not self.base_url:
            return ProviderResult(
                status="FAILED",
                error="THUNES_API_ENDPOINT_NOT_SET",
                retryable=False,
            )
        if not self._auth():
            return ProviderResult(
                status="FAILED",
                error="THUNES_API_KEY_OR_SECRET_NOT_SET",
                retryable=False,
            )

        country2 = (payout.get("country") or "TG").strip().upper()
        payer_id = self._payer_id_for_country(country2)
        if payer_id is None:
            return ProviderResult(
                status="FAILED",
                error=f"THUNES_PAYER_ID_NOT_SET_FOR_{country2}",
                retryable=False,
            )

        # external_ref is our immutable reference; provider_ref is Thunes transaction id.
        external_id = (payout.get("external_ref") or "").strip()
        if not external_id:
            external_id = str(payout.get("transaction_id") or "")

        # Amount handling (your system uses cents; Thunes expects amount as decimal/number)
        amount_cents = int(payout.get("amount_cents") or 0)
        if amount_cents <= 0:
            return ProviderResult(status="FAILED", error="INVALID_AMOUNT", retryable=False)

        destination_currency = (payout.get("currency") or "XOF").strip().upper()
        destination_amount = round(amount_cents / 100.0, 2)

        tx_type = (getattr(settings, "THUNES_TX_TYPE", "C2C") or "C2C").strip().upper()
        quote_mode = (getattr(settings, "THUNES_QUOTE_MODE", "DESTINATION_AMOUNT") or "DESTINATION_AMOUNT").strip().upper()

        source_currency = (settings.THUNES_SOURCE_CURRENCY or "USD").strip().upper()
        source_country_iso3 = (settings.THUNES_SOURCE_COUNTRY_ISO3 or "USA").strip().upper()

        # 1) Create quotation  POST /quotations  :contentReference[oaicite:14]{index=14}
        q_payload = {
            "external_id": external_id,
            "payer_id": str(payer_id),
            "mode": quote_mode,
            "transaction_type": tx_type,
            "source": {
                "amount": None,  # depending on mode
                "currency": source_currency,
                "country_iso_code": source_country_iso3,
            },
            "destination": {
                "amount": None,
                "currency": destination_currency,
            },
        }

        if quote_mode == "DESTINATION_AMOUNT":
            q_payload["destination"]["amount"] = destination_amount
        else:
            # SOURCE_AMOUNT
            q_payload["source"]["amount"] = destination_amount

        try:
            q_url = f"{self.base_url}/quotations"
            q_resp = requests.post(
                q_url,
                json=q_payload,
                headers=self._headers(),
                auth=self._auth(),
                timeout=self.timeout_s,
            )
            q_data = _safe_json(q_resp)
            if q_resp.status_code not in (200, 201):
                return _map_thunes_http_failure(
                    "THUNES_QUOTATION_FAILED",
                    q_url,
                    q_resp.status_code,
                    q_data,
                )

            quotation_id = q_data.get("id")
            if not quotation_id:
                return ProviderResult(
                    status="FAILED",
                    error="THUNES_QUOTATION_MISSING_ID",
                    response={"http_status": q_resp.status_code, "data": q_data, "request_url": q_url},
                    retryable=False,
                )

            # 2) Create transaction  POST /quotations/{id}/transactions :contentReference[oaicite:15]{index=15}
            phone = (payout.get("phone_e164") or "").strip()
            if not phone:
                return ProviderResult(status="FAILED", error="MISSING_PHONE_E164", retryable=False)

            t_payload = {
                "credit_party_identifier": {
                    "msisdn": phone
                },
                "sender": {
                    "firstname": settings.THUNES_SENDER_FIRSTNAME,
                    "lastname": settings.THUNES_SENDER_LASTNAME,
                    "nationality_country_iso_code": settings.THUNES_SENDER_NATIONALITY_ISO3,
                    "date_of_birth": settings.THUNES_SENDER_DOB,
                    "country_of_birth_iso_code": settings.THUNES_SENDER_COUNTRY_OF_BIRTH_ISO3,
                    "gender": settings.THUNES_SENDER_GENDER,
                    "address": settings.THUNES_SENDER_ADDRESS,
                    "city": settings.THUNES_SENDER_CITY,
                    "postal_code": settings.THUNES_SENDER_POSTAL,
                    "country_iso_code": settings.THUNES_SENDER_COUNTRY_ISO3,
                },
            }

            t_url = f"{self.base_url}/quotations/{quotation_id}/transactions"
            t_resp = requests.post(
                t_url,
                json=t_payload,
                headers=self._headers(),
                auth=self._auth(),
                timeout=self.timeout_s,
            )
            t_data = _safe_json(t_resp)
            if t_resp.status_code not in (200, 201):
                return _map_thunes_http_failure(
                    "THUNES_CREATE_TX_FAILED",
                    t_url,
                    t_resp.status_code,
                    t_data,
                )

            transaction_id = t_data.get("id")
            if not transaction_id:
                return ProviderResult(
                    status="FAILED",
                    error="THUNES_TRANSACTION_MISSING_ID",
                    response={"http_status": t_resp.status_code, "data": t_data, "request_url": t_url},
                    retryable=False,
                )

            # 3) Confirm transaction  POST /transactions/{id}/confirm :contentReference[oaicite:16]{index=16}
            c_url = f"{self.base_url}/transactions/{transaction_id}/confirm"
            c_resp = requests.post(
                c_url,
                headers=self._headers(),
                auth=self._auth(),
                timeout=self.timeout_s,
            )
            c_data = _safe_json(c_resp)

            if c_resp.status_code not in (200, 201, 202):
                return _map_thunes_http_failure(
                    "THUNES_CONFIRM_FAILED",
                    c_url,
                    c_resp.status_code,
                    c_data,
                    provider_ref=str(transaction_id),
                )

            # After confirm, usually in-flight => SENT (worker will poll GET /transactions/{id})
            return ProviderResult(
                status="SENT",
                provider_ref=str(transaction_id),
                response={
                    "http_status": c_resp.status_code,
                    "quotation_id": quotation_id,
                    "transaction_id": transaction_id,
                    "data": c_data,
                    "request_url": c_url,
                    "quote_request": q_payload,
                    "quote_response": {
                        "http_status": q_resp.status_code,
                        "data": q_data,
                        "request_url": q_url,
                    },
                    "quote_meta": {
                        "fee": q_data.get("fee"),
                        "rate": q_data.get("rate"),
                    },
                    "transaction_create_request": t_payload,
                    "transaction_create_response": {
                        "http_status": t_resp.status_code,
                        "data": t_data,
                        "request_url": t_url,
                    },
                    "confirm_response": {
                        "http_status": c_resp.status_code,
                        "data": c_data,
                        "request_url": c_url,
                    },
                },
                error=None,
                retryable=True,
            )

        except requests.RequestException as e:
            return ProviderResult(
                status="FAILED",
                error=f"THUNES_NETWORK_ERROR: {e}",
                response={"http_status": 504, "request_url": self.base_url},
                retryable=True,
            )

    def get_cashout_status(self, payout: dict) -> ProviderResult:
        """
        Called by worker when payout is stale SENT.
        Uses GET /transactions/{transaction_id}. :contentReference[oaicite:17]{index=17}
        """
        if not self.base_url:
            return ProviderResult(status="FAILED", error="THUNES_API_ENDPOINT_NOT_SET", retryable=False)
        if not self._auth():
            return ProviderResult(status="FAILED", error="THUNES_API_KEY_OR_SECRET_NOT_SET", retryable=False)

        provider_ref = (payout.get("provider_ref") or "").strip()
        if not provider_ref:
            return ProviderResult(status="SENT", error="MISSING_PROVIDER_REF", retryable=True)

        url = f"{self.base_url}/transactions/{provider_ref}"

        try:
            resp = requests.get(
                url,
                headers=self._headers(),
                auth=self._auth(),
                timeout=self.timeout_s,
            )
            data = _safe_json(resp)

            if resp.status_code == 404:
                # Very commonly means wrong API endpoint/base URL. Treat as config error.
                return ProviderResult(
                    status="FAILED",
                    provider_ref=provider_ref,
                    error="THUNES_ENDPOINT_NOT_FOUND",
                    response={"http_status": 404, "data": data, "request_url": url},
                    retryable=False,
                )

            if resp.status_code in (408, 425, 429, 500, 502, 503, 504):
                return ProviderResult(
                    status="FAILED",
                    provider_ref=provider_ref,
                    error="THUNES_TEMP_ERROR",
                    response={"http_status": resp.status_code, "data": data, "request_url": url},
                    retryable=True,
                )

            if resp.status_code not in (200, 201):
                return ProviderResult(
                    status="FAILED",
                    provider_ref=provider_ref,
                    error="THUNES_STATUS_FAILED",
                    response={"http_status": resp.status_code, "data": data, "request_url": url},
                    retryable=False,
                )

            thunes_status = str(data.get("status") or "")
            mapped_status, retryable, last_error = self.map_thunes_status(thunes_status)

            return ProviderResult(
                status=mapped_status,
                provider_ref=provider_ref,
                response={"http_status": resp.status_code, "data": data, "request_url": url},
                error=last_error,
                retryable=retryable,
            )

        except requests.RequestException as e:
            return ProviderResult(
                status="FAILED",
                provider_ref=provider_ref,
                error=f"THUNES_NETWORK_ERROR: {e}",
                response={"http_status": 504, "request_url": url},
                retryable=True,
            )


def _map_thunes_http_failure(
    code: str,
    request_url: str,
    http_status: int,
    data: dict,
    *,
    provider_ref: Optional[str] = None,
) -> ProviderResult:
    # Retry for common transient statuses
    if http_status in (408, 425, 429, 500, 502, 503, 504):
        return ProviderResult(
            status="FAILED",
            provider_ref=provider_ref,
            error=code,
            response={"http_status": http_status, "data": data, "request_url": request_url},
            retryable=True,
        )

    # 404 usually means wrong endpoint path or wrong base URL
    if http_status == 404:
        return ProviderResult(
            status="FAILED",
            provider_ref=provider_ref,
            error="THUNES_ENDPOINT_NOT_FOUND",
            response={"http_status": 404, "data": data, "request_url": request_url},
            retryable=False,
        )

    # Other 4xx => likely non-retryable (bad request / missing fields)
    return ProviderResult(
        status="FAILED",
        provider_ref=provider_ref,
        error=code,
        response={"http_status": http_status, "data": data, "request_url": request_url},
        retryable=False,
    )


def _safe_json(resp) -> Dict[str, Any]:
    try:
        j = resp.json()
        return j if isinstance(j, dict) else {"raw": j}
    except Exception:
        return {"raw_text": getattr(resp, "text", "")}
