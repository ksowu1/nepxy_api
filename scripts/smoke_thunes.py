import json
import os
import sys
import time
import uuid

import requests

from _webhook_signing import canonical_json_bytes, hmac_sha256_hex

_session = requests.Session()


def die(message, code=1):
    print(message)
    sys.exit(code)


def step(message):
    print("\n==> " + message)


def request(method, url, headers=None, json_body=None, data=None, allow_failure=False):
    try:
        resp = _session.request(method, url, headers=headers, json=json_body, data=data)
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


def _sign_thunes(secret, body_bytes):
    return {"X-Signature": "sha256=" + hmac_sha256_hex(secret, body_bytes)}


def _poll_payout(base_url, token, tx_id, max_attempts=8, sleep_s=2):
    for _ in range(max_attempts):
        r = request("GET", base_url + "/v1/payouts/%s" % tx_id, headers=auth_headers(token))
        payout = r.json()
        status = payout.get("status")
        if status in ("CONFIRMED", "FAILED"):
            return payout
        time.sleep(sleep_s)
    return payout


def _process_payouts_once(base_url, admin_token):
    try:
        resp = _session.request(
            "POST",
            base_url + "/v1/admin/mobile-money/payouts/process-once",
            headers=auth_headers(admin_token),
            json={"batch_size": 1, "stale_seconds": 0},
            timeout=10,
        )
    except Exception as exc:
        print("Admin process-once error: %s" % exc)
        return False
    if resp.status_code in (200, 201):
        return True
    print("Admin process-once failed (%s): %s" % (resp.status_code, resp.text))
    return False


def main():
    base_url = os.getenv("BASE_URL", "http://127.0.0.1:8001")
    user_email = os.getenv("USER_EMAIL")
    user_password = os.getenv("USER_PASSWORD")
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    thunes_secret = os.getenv("THUNES_WEBHOOK_SECRET", "")
    thunes_country = os.getenv("THUNES_DESTINATION_COUNTRY", "GH")

    missing = [name for name in ("USER_EMAIL", "USER_PASSWORD", "ADMIN_EMAIL", "ADMIN_PASSWORD") if not os.getenv(name)]
    if missing:
        die("Missing env vars: %s" % ", ".join(missing), code=2)

    step("Login user")
    r = request("POST", base_url + "/v1/auth/login", json_body={"email": user_email, "password": user_password})
    token = r.json().get("access_token")
    if not token:
        die("Missing access_token for user.")

    step("Login admin")
    r = request("POST", base_url + "/v1/auth/login", json_body={"email": admin_email, "password": admin_password})
    admin_token = r.json().get("access_token")
    if not admin_token:
        die("Missing access_token for admin.")

    step("Fetch wallet")
    r = request("GET", base_url + "/v1/wallets", headers=auth_headers(token))
    wallets = r.json().get("wallets") or r.json()
    if not wallets:
        die("No wallets returned.")
    wallet_id = wallets[0].get("wallet_id") or wallets[0].get("id")
    if not wallet_id:
        die("Could not determine wallet_id.")

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

    step("Cash-out 100 (THUNES)")
    r = request(
        "POST",
        base_url + "/v1/cash-out/mobile-money",
        headers=auth_headers(token, new_idem_key()),
        json_body={
            "wallet_id": wallet_id,
            "amount_cents": 100,
            "country": thunes_country,
            "provider": "THUNES",
            "phone_e164": "+22890009911",
        },
    )
    tx_id = r.json().get("transaction_id")
    if not tx_id:
        die("Missing transaction_id from cash-out.")

    step("Get payout and check status")
    r = request("GET", base_url + "/v1/payouts/%s" % tx_id, headers=auth_headers(token))
    payout = r.json()
    external_ref = payout.get("external_ref")
    if not external_ref:
        die("Missing external_ref on payout.")

    if thunes_secret:
        step("Post THUNES webhook")
        payload_obj = {"external_ref": external_ref, "status": "SUCCESSFUL"}
        payload_bytes = canonical_json_bytes(payload_obj)
        headers = {"Content-Type": "application/json", **_sign_thunes(thunes_secret, payload_bytes)}
        if os.getenv("WEBHOOK_DEBUG") == "1":
            print("THUNES webhook body_len=%s sig=%s" % (len(payload_bytes), headers["X-Signature"][:12]))
        request(
            "POST",
            base_url + "/v1/webhooks/thunes",
            headers=headers,
            data=payload_bytes,
        )

    step("Poll payout")
    for _ in range(12):
        _process_payouts_once(base_url, admin_token)
        payout = _poll_payout(base_url, token, tx_id, max_attempts=1, sleep_s=2)
        if payout.get("status") in ("CONFIRMED", "FAILED"):
            break
    if payout.get("status") not in ("CONFIRMED", "FAILED"):
        die("Payout not terminal. Current status: %s" % payout.get("status"))

    if thunes_secret:
        step("Check admin payout webhook events")
        r = request(
            "GET",
            base_url + "/v1/admin/mobile-money/payouts/%s/webhook-events?limit=50" % tx_id,
            headers=auth_headers(admin_token),
        )
        data = r.json()
        events = data.get("items") or data.get("events") or data if isinstance(data, list) else []
        if not events:
            die("No webhook events found for payout.")
        refs = [e.get("external_ref") or e.get("provider_ref") for e in events]
        if external_ref not in refs:
            die("Webhook events missing expected external_ref: %s" % external_ref)
    else:
        print("Skipping admin webhook events check; THUNES_WEBHOOK_SECRET not set.")

    step("Thunes smoke completed")
    print("transaction_id=%s" % tx_id)
    print("external_ref=%s" % external_ref)


if __name__ == "__main__":
    main()
