import os
import sys
import time
import uuid

import requests
from dotenv import load_dotenv


BASE_URL = "https://sandbox.momodeveloper.mtn.com"
DEFAULT_CURRENCIES = ["EUR", "GHS", "XOF", "USD"]


def _die(message, code=1):
    print(message)
    sys.exit(code)


def _require_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        _die(f"Missing env var: {name}")
    return value


def _retry(func, *, attempts: int = 3, delay_s: float = 1.0):
    last_exc = None
    for idx in range(attempts):
        try:
            return func()
        except Exception as exc:
            last_exc = exc
            if idx < attempts - 1:
                time.sleep(delay_s)
    raise last_exc


def _get_token(api_user_id: str, api_key: str, sub_key: str) -> str:
    url = f"{BASE_URL}/disbursement/token/"
    headers = {"Ocp-Apim-Subscription-Key": sub_key}

    def _call():
        resp = requests.post(url, headers=headers, auth=(api_user_id, api_key))
        if resp.status_code != 200:
            raise RuntimeError(f"Token request failed: HTTP {resp.status_code} {resp.text}")
        payload = resp.json() if resp.text else {}
        token = payload.get("access_token")
        if not token:
            raise RuntimeError("Token response missing access_token")
        return token

    return _retry(_call, attempts=3, delay_s=1.0)


def _parse_csv(value: str) -> list[str]:
    items = []
    for part in (value or "").split(","):
        clean = part.strip().upper()
        if clean:
            items.append(clean)
    return items


def _create_transfer(
    token: str,
    sub_key: str,
    reference_id: str,
    *,
    currency: str,
    amount: str,
    external_id: str,
    payee_msisdn: str,
) -> None:
    url = f"{BASE_URL}/disbursement/v1_0/transfer"
    headers = {
        "Authorization": f"Bearer {token}",

        "X-Reference-Id": reference_id,
        "Ocp-Apim-Subscription-Key": sub_key,
        "X-Target-Environment": "sandbox",
        "Content-Type": "application/json",
    }
    body = {
        "amount": amount,
        "currency": currency,
        "externalId": external_id,
        "payee": {"partyIdType": "MSISDN", "partyId": payee_msisdn},
        "payerMessage": "NepXy test",
        "payeeNote": "NepXy test",
    }

    def _call():
        resp = requests.post(url, headers=headers, json=body)
        if resp.status_code not in (200, 201, 202):
            raise RuntimeError(f"Transfer request failed: HTTP {resp.status_code} {resp.text}")
        return None

    _retry(_call, attempts=3, delay_s=1.0)


def _get_transfer_status(token: str, sub_key: str, reference_id: str) -> str:
    url = f"{BASE_URL}/disbursement/v1_0/transfer/{reference_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Ocp-Apim-Subscription-Key": sub_key,
        "X-Target-Environment": "sandbox",
    }

    def _call():
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"Status request failed: HTTP {resp.status_code} {resp.text}")
        payload = resp.json() if resp.text else {}
        status = (payload.get("status") or payload.get("financialTransactionStatus") or "").strip()
        if not status:
            raise RuntimeError("Status response missing status")
        return status

    return _retry(_call, attempts=3, delay_s=1.0)


def main() -> None:
    load_dotenv()
    momo_env = (os.getenv("MOMO_ENV") or "").strip().lower()
    if momo_env != "sandbox":
        _die("MOMO_ENV must be set to 'sandbox'.")

    api_user_id = _require_env("MOMO_API_USER_ID")
    api_key = _require_env("MOMO_API_KEY")
    sub_key = _require_env("MOMO_DISBURSE_SUB_KEY")
    currencies_env = os.getenv("MOMO_CURRENCIES", "")
    currencies = _parse_csv(currencies_env) or list(DEFAULT_CURRENCIES)
    payee_msisdn = os.getenv("MOMO_PAYEE_MSISDN", "233200000000").strip()
    amount = os.getenv("MOMO_AMOUNT", "1").strip() or "1"
    external_id = os.getenv("MOMO_EXTERNAL_ID", "nepxy-test").strip() or "nepxy-test"

    token = _get_token(api_user_id, api_key, sub_key)
    print("token ok")

    last_error = None
    for currency in currencies:
        reference_id = str(uuid.uuid4())
        try:
            _create_transfer(
                token,
                sub_key,
                reference_id,
                currency=currency,
                amount=amount,
                external_id=external_id,
                payee_msisdn=payee_msisdn,
            )
            status = _get_transfer_status(token, sub_key, reference_id)
            print(f"currency={currency} status={status}")
            return
        except Exception as exc:
            last_error = exc
            print(f"currency={currency} failed: {exc}")

    _die(f"All currencies failed. Last error: {last_error}")


if __name__ == "__main__":
    main()
