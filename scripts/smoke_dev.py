import json
import os
import sys
import uuid
import hmac
import hashlib

import requests


def die(message, code=1):
    print(message)
    sys.exit(code)


def step(message):
    print("\n==> " + message)


def request(method, url, headers=None, json_body=None, data=None, allow_failure=False):
    try:
        resp = requests.request(method, url, headers=headers, json=json_body, data=data)
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


def sign_tmoney(payload_bytes, secret):
    mac = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return "sha256=" + mac


def _safe_json(resp):
    try:
        return resp.json()
    except ValueError:
        return {}


def _response_detail(resp):
    payload = _safe_json(resp)
    detail = payload.get("detail")
    if detail:
        return detail
    return payload.get("message")


def _build_registration_payload(email, password, phone, country, full_name):
    payload = {
        "email": email,
        "password": password,
        "phone_e164": phone,
        "country": (country or "").upper(),
    }
    if full_name:
        payload["full_name"] = full_name
    return payload


def _register_account(label, base_url, payload):
    step(f"Ensure {label} account")
    resp = request(
        "POST",
        base_url + "/v1/auth/register",
        json_body=payload,
        allow_failure=True,
    )
    status = resp.status_code
    if status in (200, 201):
        return
    if status == 400:
        detail = _response_detail(resp) or ""
        if "EMAIL_TAKEN" in detail or "PHONE_TAKEN" in detail:
            print(f"{label} already registered: {detail or 'EMAIL_TAKEN/PHONE_TAKEN'}")
            return
    die(f"Failed to register {label} account ({status}): {resp.text.strip()}" )


def _login_with_retry(label, base_url, email, password, register_payload):
    resp = request(
        "POST",
        base_url + "/v1/auth/login",
        json_body={"email": email, "password": password},
        allow_failure=True,
    )
    if resp.status_code == 200:
        payload = _safe_json(resp)
        token = payload.get("access_token")
        user_id = payload.get("user_id")
        if token and user_id:
            return token, user_id
        die(f"Missing access_token or user_id for {label} after login.")

    if resp.status_code == 401 and _response_detail(resp) == "INVALID_CREDENTIALS":
        _register_account(label, base_url, register_payload)
        resp = request(
            "POST",
            base_url + "/v1/auth/login",
            json_body={"email": email, "password": password},
            allow_failure=True,
        )
        if resp.status_code == 200:
            payload = _safe_json(resp)
            token = payload.get("access_token")
            user_id = payload.get("user_id")
            if token and user_id:
                return token, user_id
            die(f"Missing access_token or user_id for {label} after re-login.")
        detail = _response_detail(resp) or resp.text
        die(f"{label.capitalize()} login still failing after registration ({resp.status_code}): {detail}")

    die(f"{label.capitalize()} login failed ({resp.status_code}): {_response_detail(resp) or resp.text}")


def _is_bootstrap_allowed() -> bool:
    env = (os.getenv("ENV") or "dev").strip().lower()
    mode = (os.getenv("MM_MODE") or "sandbox").strip().lower()
    return mode == "sandbox" or env in {"dev", "staging"}


def _bootstrap_admin_role(base_url: str, secret: str, admin_email: str) -> None:
    step("Bootstrap admin role via debug endpoint")
    resp = request(
        "POST",
        base_url + "/debug/bootstrap-admin",
        headers={"X-Bootstrap-Secret": secret},
        json_body={"email": admin_email},
        allow_failure=True,
    )
    if resp.status_code == 200:
        return
    die(
        "Failed to bootstrap admin role via /debug/bootstrap-admin (%s): %s"
        % (resp.status_code, _response_detail(resp) or resp.text)
    )




def _ensure_admin_role(base_url, admin_token, admin_user_id, admin_email, allow_bootstrap=True):
    step("Ensure admin role")
    resp = request(
        "POST",
        base_url + "/v1/admin/roles/set",
        headers=auth_headers(admin_token),
        json_body={"target_user_id": admin_user_id, "role": "ADMIN"},
        allow_failure=True,
    )
    if resp.status_code in (200, 201):
        return

    detail = _response_detail(resp) or ""
    if resp.status_code == 403 and "ADMIN_REQUIRED" in detail:
        bootstrap_secret = os.getenv("BOOTSTRAP_ADMIN_SECRET")
        if allow_bootstrap and _is_bootstrap_allowed() and bootstrap_secret:
            _bootstrap_admin_role(base_url, bootstrap_secret, admin_email)
            return _ensure_admin_role(
                base_url,
                admin_token,
                admin_user_id,
                admin_email,
                allow_bootstrap=False,
            )
        die(
            "Admin endpoint requires ADMIN role. "
            "Ensure ADMIN_EMAIL has ADMIN role before running smoke_dev.py."
        )

    die(f"Failed to ensure admin role for {admin_email}: {resp.status_code} {detail or resp.text}")


def main():
    base_url = os.getenv("BASE_URL", "http://127.0.0.1:8001")
    user_email = os.getenv("USER_EMAIL")
    user_password = os.getenv("USER_PASSWORD")
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    user_phone = os.getenv("USER_PHONE", "+15550000002")
    user_country = os.getenv("USER_COUNTRY", "TG")
    user_full_name = os.getenv("USER_FULL_NAME", "Smoke User")
    admin_phone = os.getenv("ADMIN_PHONE", "+15550000003")
    admin_country = os.getenv("ADMIN_COUNTRY", "TG")
    admin_full_name = os.getenv("ADMIN_FULL_NAME", "Smoke Admin")
    webhook_secret = os.getenv("TMONEY_WEBHOOK_SECRET", "dev_secret_tmoney")

    missing = [name for name in ("USER_EMAIL", "USER_PASSWORD", "ADMIN_EMAIL", "ADMIN_PASSWORD") if not os.getenv(name)]
    if missing:
        die("Missing env vars: %s" % ", ".join(missing), code=2)

    user_register = _build_registration_payload(
        user_email, user_password, user_phone, user_country, user_full_name
    )
    admin_register = _build_registration_payload(
        admin_email, admin_password, admin_phone, admin_country, admin_full_name
    )

    step("Login user")
    token, _ = _login_with_retry("user", base_url, user_email, user_password, user_register)

    step("Login admin")
    admin_token, admin_user_id = _login_with_retry(
        "admin", base_url, admin_email, admin_password, admin_register
    )
    _ensure_admin_role(base_url, admin_token, admin_user_id, admin_email)

    step("Fetch wallet")
    r = request("GET", base_url + "/v1/wallets", headers=auth_headers(token))
    wallets = []
    payload = r.json()
    if isinstance(payload, dict) and "wallets" in payload:
        wallets = payload.get("wallets") or []
    elif isinstance(payload, list):
        wallets = payload
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

    step("Cash-out 100")
    r = request(
        "POST",
        base_url + "/v1/cash-out/mobile-money",
        headers=auth_headers(token, new_idem_key()),
        json_body={
            "wallet_id": wallet_id,
            "amount_cents": 100,
            "country": "BJ",
            "provider": "TMONEY",
            "phone_e164": "+22890009911",
        },
    )
    tx_id = r.json().get("transaction_id")
    if not tx_id:
        die("Missing transaction_id from cash-out.")

    step("Get payout and check status")
    r = request("GET", base_url + "/v1/payouts/%s" % tx_id, headers=auth_headers(token))
    payout = r.json()
    status = payout.get("status")
    if status not in ("PENDING", "SENT"):
        die("Unexpected payout status: %s" % status)

    external_ref = payout.get("external_ref")
    if not external_ref:
        die("Missing external_ref on payout.")

    step("Post TMONEY webhook")
    payload_obj = {"external_ref": external_ref, "status": "SUCCESS"}
    payload_json = json.dumps(payload_obj, separators=(",", ":"), ensure_ascii=False)
    payload_bytes = payload_json.encode("utf-8")
    sig = sign_tmoney(payload_bytes, webhook_secret)
    request(
        "POST",
        base_url + "/v1/webhooks/tmoney",
        headers={"Content-Type": "application/json", "X-Signature": sig},
        data=payload_bytes,
    )

    step("Confirm payout updated")
    r = request("GET", base_url + "/v1/payouts/%s" % tx_id, headers=auth_headers(token))
    payout = r.json()
    if payout.get("status") != "CONFIRMED":
        die("Payout not confirmed. Current status: %s" % payout.get("status"))

    step("Check admin payout webhook events")
    r = request(
        "GET",
        base_url + "/v1/admin/mobile-money/payouts/%s/webhook-events?limit=50" % tx_id,
        headers=auth_headers(admin_token),
    )
    data = r.json()
    events = []
    if isinstance(data, dict):
        events = data.get("items") or data.get("events") or []
    elif isinstance(data, list):
        events = data
    if not events:
        die("No webhook events found for payout.")
    refs = [e.get("external_ref") or e.get("provider_ref") for e in events]
    if external_ref not in refs:
        die("Webhook events missing expected external_ref: %s" % external_ref)

    step("Smoke test completed")
    print("transaction_id=%s" % tx_id)
    print("external_ref=%s" % external_ref)


if __name__ == "__main__":
    main()
