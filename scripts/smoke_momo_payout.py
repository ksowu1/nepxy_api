import os
import sys
import time
import uuid

import requests

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None


def _die(message, code=1):
    print(message)
    sys.exit(code)


def _require_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        _die(f"Missing env var: {name}")
    return value


def _staging_headers() -> dict[str, str]:
    key = (os.getenv("STAGING_GATE_KEY") or "").strip()
    if key:
        return {"X-Staging-Key": key}
    return {}


def _request(method: str, url: str, *, headers=None, json_body=None):
    merged = _staging_headers()
    if headers:
        merged.update(headers)
    try:
        resp = requests.request(method, url, headers=merged, json=json_body)
    except Exception as exc:
        _die(f"Request failed: {exc}")
    return resp


def _auth_headers(token: str, idem: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if idem:
        headers["Idempotency-Key"] = idem
    return headers


def _login(base_url: str, email: str, password: str) -> str:
    resp = _request(
        "POST",
        f"{base_url}/v1/auth/login",
        json_body={"email": email, "password": password},
    )
    if resp.status_code != 200:
        _die(f"Login failed: {resp.status_code} {resp.text}")
    token = resp.json().get("access_token")
    if not token:
        _die("Login response missing access_token")
    return token


def _pick_wallet(base_url: str, token: str) -> str:
    resp = _request("GET", f"{base_url}/v1/wallets", headers=_auth_headers(token))
    if resp.status_code != 200:
        _die(f"Wallet list failed: {resp.status_code} {resp.text}")
    payload = resp.json()
    wallets = payload.get("wallets") if isinstance(payload, dict) else payload
    if not wallets:
        _die("No wallets returned")
    wallet_id = wallets[0].get("wallet_id") or wallets[0].get("id")
    if not wallet_id:
        _die("Wallet id missing")
    return wallet_id


def _cash_in(base_url: str, token: str, wallet_id: str) -> None:
    provider_ref = f"smoke-cashin-{uuid.uuid4()}"
    payload = {
        "wallet_id": wallet_id,
        "amount_cents": 2000,
        "country": "TG",
        "provider_ref": provider_ref,
        "provider": "TMONEY",
    }
    resp = _request(
        "POST",
        f"{base_url}/v1/cash-in/mobile-money",
        headers=_auth_headers(token, idem=provider_ref),
        json_body=payload,
    )
    if resp.status_code not in (200, 201):
        _die(f"Cash-in failed: {resp.status_code} {resp.text}")


def _cash_out(base_url: str, token: str, wallet_id: str) -> str:
    provider_ref = f"smoke-cashout-{uuid.uuid4()}"
    payload = {
        "wallet_id": wallet_id,
        "amount_cents": 100,
        "destination_country": "GH",
        "provider_ref": provider_ref,
        "phone_e164": "+233201234567",
    }
    resp = _request(
        "POST",
        f"{base_url}/v1/cash-out/mobile-money",
        headers=_auth_headers(token, idem=provider_ref),
        json_body=payload,
    )
    if resp.status_code not in (200, 201):
        _die(f"Cash-out failed: {resp.status_code} {resp.text}")
    tx_id = resp.json().get("transaction_id")
    if not tx_id:
        _die("Cash-out response missing transaction_id")
    return tx_id


def _get_payout(base_url: str, token: str, tx_id: str) -> dict:
    resp = _request("GET", f"{base_url}/v1/payouts/{tx_id}", headers=_auth_headers(token))
    if resp.status_code != 200:
        _die(f"Payout fetch failed: {resp.status_code} {resp.text}")
    return resp.json()


def _retry_payout(base_url: str, token: str, tx_id: str) -> None:
    resp = _request(
        "POST",
        f"{base_url}/v1/admin/mobile-money/payouts/{tx_id}/retry",
        headers=_auth_headers(token),
        json_body={},
    )
    if resp.status_code == 200:
        print("retry triggered")
        return
    print(f"retry skipped: {resp.status_code} {resp.text}")


def main() -> None:
    if load_dotenv:
        load_dotenv()

    base_url = _require_env("BASE_URL")
    email = _require_env("USER_EMAIL")
    password = _require_env("USER_PASSWORD")

    token = _login(base_url, email, password)
    wallet_id = _pick_wallet(base_url, token)
    _cash_in(base_url, token, wallet_id)
    tx_id = _cash_out(base_url, token, wallet_id)

    payout = _get_payout(base_url, token, tx_id)
    provider = payout.get("provider")
    status = payout.get("status")
    print(f"provider={provider} status={status}")

    if provider == "THUNES":
        print("routing OK (thunes preferred)")
    elif provider == "MOMO":
        _retry_payout(base_url, token, tx_id)
        for _ in range(5):
            time.sleep(2)
            payout = _get_payout(base_url, token, tx_id)
            status = payout.get("status")
            print(f"status={status}")
            if status not in ("PENDING", "SENT", "RETRY"):
                return
        _die("Payout did not advance beyond PENDING/SENT", code=2)


if __name__ == "__main__":
    main()
