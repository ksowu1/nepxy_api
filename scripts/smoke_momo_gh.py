import os
import sys
import time
import uuid

import requests


_session = requests.Session()


def die(message, code=1):
    print(message)
    sys.exit(code)


def step(message):
    print("\n==> " + message)


def _configure_session():
    key = os.getenv("STAGING_GATE_KEY")
    if key:
        _session.headers.update({"X-Staging-Key": key})
        print("Using staging gate header")


def request(method, url, headers=None, json_body=None, allow_failure=False):
    try:
        resp = _session.request(method, url, headers=headers, json=json_body)
    except Exception as exc:
        die("Request failed: %s" % exc)
    if resp.status_code < 200 or resp.status_code >= 300:
        if not allow_failure:
            print("HTTP %s %s" % (resp.status_code, resp.reason))
            print(resp.text)
            sys.exit(1)
    return resp


def auth_headers(token, idem=None):
    h = {"Authorization": "Bearer %s" % token}
    if idem:
        h["Idempotency-Key"] = idem
    return h


def new_idem_key():
    return "idem-" + uuid.uuid4().hex


def _safe_json(resp):
    try:
        return resp.json()
    except ValueError:
        return {}


def _login(base_url, email, password):
    resp = request(
        "POST",
        base_url + "/v1/auth/login",
        json_body={"email": email, "password": password},
        allow_failure=True,
    )
    if resp.status_code != 200:
        detail = _safe_json(resp).get("detail") or resp.text
        die("Login failed (%s): %s" % (resp.status_code, detail))
    payload = _safe_json(resp)
    token = payload.get("access_token")
    user_id = payload.get("user_id")
    if not token or not user_id:
        die("Missing access_token or user_id in login response.")
    return token, user_id


def _wallet_id(base_url, token):
    resp = request("GET", base_url + "/v1/wallets", headers=auth_headers(token))
    payload = _safe_json(resp)
    wallets = []
    if isinstance(payload, dict) and "wallets" in payload:
        wallets = payload.get("wallets") or []
    elif isinstance(payload, list):
        wallets = payload
    if not wallets:
        die("No wallets returned.")
    wallet_id = wallets[0].get("wallet_id") or wallets[0].get("id")
    if not wallet_id:
        die("Could not determine wallet_id.")
    return wallet_id


def _retry_payout(base_url, admin_token, tx_id):
    resp = request(
        "POST",
        base_url + "/v1/admin/mobile-money/payouts/%s/retry" % tx_id,
        headers=auth_headers(admin_token),
        json_body={"force": True, "reason": "smoke_momo_gh"},
        allow_failure=True,
    )
    if resp.status_code in (200, 201):
        return True
    detail = _safe_json(resp).get("detail") or resp.text
    print("Admin retry failed (%s): %s" % (resp.status_code, detail))
    return False


def main():
    base_url = os.getenv("BASE_URL", "http://127.0.0.1:8001")
    _configure_session()

    user_email = os.getenv("USER_EMAIL")
    user_password = os.getenv("USER_PASSWORD")
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    user_phone = os.getenv("USER_PHONE", "+233200000000")

    missing = [name for name in ("USER_EMAIL", "USER_PASSWORD") if not os.getenv(name)]
    if missing:
        die("Missing env vars: %s" % ", ".join(missing), code=2)

    step("Login user")
    token, _ = _login(base_url, user_email, user_password)

    step("Fetch wallet")
    wallet_id = _wallet_id(base_url, token)

    step("Cash-in 2000")
    request(
        "POST",
        base_url + "/v1/cash-in/mobile-money",
        headers=auth_headers(token, new_idem_key()),
        json_body={
            "wallet_id": wallet_id,
            "amount_cents": 2000,
            "country": "TG",
            "provider": "TMONEY",
            "phone_e164": "+22890009911",
        },
    )

    step("Cash-out 100 to GH (provider omitted)")
    resp = request(
        "POST",
        base_url + "/v1/cash-out/mobile-money",
        headers=auth_headers(token, new_idem_key()),
        json_body={
            "wallet_id": wallet_id,
            "amount_cents": 100,
            "destination_country": "GH",
            "phone_e164": user_phone,
        },
    )
    tx_id = _safe_json(resp).get("transaction_id")
    if not tx_id:
        die("Missing transaction_id from cash-out.")

    step("Fetch payout")
    resp = request("GET", base_url + "/v1/payouts/%s" % tx_id, headers=auth_headers(token))
    payout = _safe_json(resp)
    provider = (payout.get("provider") or "").upper()
    status = payout.get("status")
    print("provider=%s status=%s" % (provider, status))
    if provider != "MOMO":
        die("Expected MOMO provider but got %s" % provider)

    if admin_email and admin_password:
        step("Login admin")
        admin_token, _ = _login(base_url, admin_email, admin_password)
        step("Trigger payout retry")
        _retry_payout(base_url, admin_token, tx_id)
    else:
        print("Skipping admin retry; ADMIN_EMAIL/ADMIN_PASSWORD not set.")

    step("Poll payout status")
    final_status = status
    for _ in range(10):
        time.sleep(1)
        resp = request("GET", base_url + "/v1/payouts/%s" % tx_id, headers=auth_headers(token))
        payout = _safe_json(resp)
        final_status = payout.get("status")
        print("status=%s provider=%s" % (final_status, payout.get("provider")))
        if final_status == "CONFIRMED":
            break

    if final_status != "CONFIRMED":
        die("Payout did not confirm (status=%s)" % final_status)

    print("Smoke test completed: tx_id=%s" % tx_id)


if __name__ == "__main__":
    main()
