import json
import os
import sys
import uuid
import hashlib
from pathlib import Path

import requests

_session = requests.Session()

try:
    from _webhook_signing import canonical_json_bytes, tmoney_sig_header
except ModuleNotFoundError:
    scripts_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(scripts_dir))
    from _webhook_signing import canonical_json_bytes, tmoney_sig_header


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


def request(method, url, headers=None, json_body=None, data=None):
    try:
        resp = _session.request(method, url, headers=headers, json=json_body, data=data)
    except Exception as exc:
        die("Request failed: %s" % exc)
    if resp.status_code < 200 or resp.status_code >= 300:
        print("HTTP %s %s" % (resp.status_code, resp.reason))
        print(resp.text)
        sys.exit(1)
    return resp


def request_raw(method, url, headers=None, json_body=None, data=None):
    try:
        return _session.request(method, url, headers=headers, json=json_body, data=data)
    except Exception as exc:
        die("Request failed: %s" % exc)


def auth_headers(token, idem=None):
    h = {"Authorization": "Bearer %s" % token}
    if idem:
        h["Idempotency-Key"] = idem
    return h


def new_idem_key():
    return "idem-" + uuid.uuid4().hex


def _print_request_id(resp, label: str):
    try:
        req_id = resp.headers.get("X-Request-ID")
    except Exception:
        req_id = None
    if req_id:
        print("%s request_id=%s" % (label, req_id))


def _redact_email(value):
    if not value:
        return value
    parts = value.split("@", 1)
    if len(parts) != 2:
        return "***"
    name, domain = parts
    if not name:
        return "***@" + domain
    return name[0] + "***@" + domain


def _validate_openapi_paths(openapi, allow_bootstrap):
    paths = (openapi or {}).get("paths") or {}
    required = [
        "/v1/auth/login",
        "/v1/cash-in/mobile-money",
        "/v1/cash-out/mobile-money",
        "/v1/payouts/{transaction_id}",
        "/v1/webhooks/tmoney",
        "/v1/admin/mobile-money/payouts/{transaction_id}/webhook-events",
    ]
    missing = [p for p in required if p not in paths]
    if allow_bootstrap and "/debug/bootstrap-staging-users" not in paths:
        missing.append("/debug/bootstrap-staging-users")
    return missing, paths


def bootstrap_preflight(base_url, bootstrap_secret):
    if os.getenv("CANARY_ALLOW_BOOTSTRAP") != "1":
        return True
    if not bootstrap_secret:
        print("Bootstrap disabled: BOOTSTRAP_ADMIN_SECRET not set")
        return False
    resp = request_raw(
        "POST",
        base_url + "/debug/bootstrap-verify",
        headers={"X-Bootstrap-Admin-Secret": bootstrap_secret},
        json_body={"email": "bootstrap-check@nexapay.io", "password": "bootstrap-check"},
    )
    if resp.status_code == 404:
        print("Bootstrap endpoint not available; skipping.")
        return True
    if resp.status_code == 403:
        print("Bootstrap secret mismatch. Rotate BOOTSTRAP_ADMIN_SECRET in Fly and set it locally.")
        return False
    if resp.status_code >= 500:
        print("Bootstrap preflight failed: HTTP %s %s" % (resp.status_code, resp.reason))
        return False
    return True


def _login_once(base_url, email, password):
    resp = request_raw(
        "POST",
        base_url + "/v1/auth/login",
        json_body={"email": email, "password": password},
    )
    detail = ""
    if resp is not None:
        try:
            detail = resp.json().get("detail", "")
        except Exception:
            detail = resp.text or ""
    token = None
    if resp is not None and resp.status_code == 200:
        token = resp.json().get("access_token")
    return {"resp": resp, "token": token, "detail": detail}


def login_with_optional_bootstrap(
    base_url,
    email,
    password,
    bootstrap_secret,
    *,
    base_email=None,
    base_password=None,
):
    login = _login_once(base_url, email, password)
    if login["token"]:
        return login["token"]
    if not (
        login["resp"] is not None
        and login["resp"].status_code == 401
        and login["detail"] == "INVALID_CREDENTIALS"
    ):
        return None
    if os.getenv("CANARY_ALLOW_BOOTSTRAP") != "1":
        return None
    headers = {}
    if bootstrap_secret:
        headers["X-Bootstrap-Admin-Secret"] = bootstrap_secret
    staging_key = os.getenv("STAGING_GATE_KEY")
    if staging_key:
        headers["X-Staging-Key"] = staging_key
    maybe_bootstrap_users(base_url=base_url, headers=headers)
    retry_email = base_email or email
    retry_password = base_password or password
    retry = _login_once(base_url, retry_email, retry_password)
    return retry["token"]


def bootstrap_and_verify_credentials(
    base_url,
    bootstrap_secret,
    staging_key,
    user_email,
    user_password,
    admin_email,
    admin_password,
):
    if os.getenv("CANARY_ALLOW_BOOTSTRAP") != "1" or not bootstrap_secret:
        return False
    step("Bootstrap staging users")
    headers = {"X-Bootstrap-Admin-Secret": bootstrap_secret}
    if staging_key:
        headers["X-Staging-Key"] = staging_key
    resp = request_raw(
        "POST",
        base_url + "/debug/bootstrap-staging-users",
        headers=headers,
    )
    if resp.status_code == 404:
        print("Bootstrap endpoint not available; skipping")
        return False
    if resp.status_code == 403:
        print(resp.text)
        die("Bootstrap forbidden (403)")
    if resp.status_code != 200:
        print("Bootstrap failed: HTTP %s %s" % (resp.status_code, resp.reason))
        print(resp.text)
        die("Bootstrap failed")
    print("Bootstrap succeeded via /debug/bootstrap-staging-users")

    user_login = _login_once(base_url, user_email, user_password)
    if user_login["resp"] is not None:
        _print_request_id(user_login["resp"], "Login user (post-bootstrap)")
    if (
        user_login["resp"] is not None
        and user_login["resp"].status_code == 401
        and user_login["detail"] == "INVALID_CREDENTIALS"
    ):
        die("Invalid credentials for STAGING_USER_EMAIL/STAGING_USER_PASSWORD")

    admin_login = _login_once(base_url, admin_email, admin_password)
    if admin_login["resp"] is not None:
        _print_request_id(admin_login["resp"], "Login admin (post-bootstrap)")
    if (
        admin_login["resp"] is not None
        and admin_login["resp"].status_code == 401
        and admin_login["detail"] == "INVALID_CREDENTIALS"
    ):
        die("Invalid credentials for STAGING_ADMIN_EMAIL/STAGING_ADMIN_PASSWORD")

    return True


def maybe_bootstrap_users(*, base_url: str, headers: dict) -> dict | None:
    """
    Back-compat shim for tests/tools that patch maybe_bootstrap_users.
    Returns a dict on success, None if skipped.
    """
    safe_headers = headers or {}
    bootstrap_secret = safe_headers.get("X-Bootstrap-Admin-Secret") or os.getenv(
        "BOOTSTRAP_ADMIN_SECRET"
    )
    staging_key = safe_headers.get("X-Staging-Key") or os.getenv("STAGING_GATE_KEY")
    user_email = os.getenv("STAGING_USER_EMAIL")
    user_password = os.getenv("STAGING_USER_PASSWORD")
    admin_email = os.getenv("STAGING_ADMIN_EMAIL")
    admin_password = os.getenv("STAGING_ADMIN_PASSWORD")
    bootstrapped = bootstrap_and_verify_credentials(
        base_url,
        bootstrap_secret,
        staging_key,
        user_email,
        user_password,
        admin_email,
        admin_password,
    )
    if not bootstrapped:
        return None
    return {"mode": "staging-users", "info": {}}


def main():
    base_url = os.getenv("STAGING_BASE_URL")
    _configure_session()

    staging_user_email = os.getenv("STAGING_USER_EMAIL")
    staging_user_password = os.getenv("STAGING_USER_PASSWORD")
    staging_admin_email = os.getenv("STAGING_ADMIN_EMAIL")
    staging_admin_password = os.getenv("STAGING_ADMIN_PASSWORD")

    user_email = staging_user_email
    user_password = staging_user_password
    admin_email = staging_admin_email
    admin_password = staging_admin_password
    user_source = "STAGING_*"
    admin_source = "STAGING_*"
    bootstrap_secret = os.getenv("BOOTSTRAP_ADMIN_SECRET")
    webhook_secret = os.getenv("TMONEY_WEBHOOK_SECRET")
    if not webhook_secret:
        staging_webhook_secret = os.getenv("STAGING_TMONEY_WEBHOOK_SECRET")
        if staging_webhook_secret:
            webhook_secret = staging_webhook_secret
            os.environ["TMONEY_WEBHOOK_SECRET"] = staging_webhook_secret
            print("Using TMONEY_WEBHOOK_SECRET from STAGING_TMONEY_WEBHOOK_SECRET")
    if webhook_secret:
        webhook_secret = webhook_secret.strip()

    missing = []
    if not base_url:
        missing.append("STAGING_BASE_URL")
    if not user_email or not user_password:
        missing.append("STAGING_USER_EMAIL/STAGING_USER_PASSWORD")
    if not admin_email or not admin_password:
        missing.append("STAGING_ADMIN_EMAIL/STAGING_ADMIN_PASSWORD")
    if missing:
        die("Missing env vars: %s" % ", ".join(missing), code=2)

    require_webhook_secret = os.getenv("CANARY_REQUIRE_WEBHOOK_SECRET") == "1"
    skip_webhook = False
    if not webhook_secret:
        message = "Missing TMONEY_WEBHOOK_SECRET; skipping TMONEY webhook."
        if require_webhook_secret:
            die(message + " Set CANARY_REQUIRE_WEBHOOK_SECRET=1 only when required.")
        print(message + " Set CANARY_REQUIRE_WEBHOOK_SECRET=1 to fail instead.")
        skip_webhook = True

    staging_key_set = bool(os.getenv("STAGING_GATE_KEY"))
    webhook_len = len(webhook_secret) if webhook_secret else 0
    print("X-Staging-Key enabled=%s" % staging_key_set)
    print("TMONEY_WEBHOOK_SECRET set=%s len=%s" % (bool(webhook_secret), webhook_len))

    step("Preflight debug version")
    version_resp = request_raw("GET", base_url + "/debug/version")
    if version_resp.status_code != 200:
        die("Debug version check failed: HTTP %s %s" % (version_resp.status_code, version_resp.reason))
    try:
        version_payload = version_resp.json()
    except Exception:
        die("Debug version check failed: invalid JSON")
    env_value = version_payload.get("env") or version_payload.get("environment")
    if env_value != "staging":
        die("Debug version env mismatch: %s" % env_value)
    if version_payload.get("mm_mode") != "sandbox":
        die("Debug version mm_mode mismatch: %s" % version_payload.get("mm_mode"))

    step("Preflight health")
    health_resp = request_raw("GET", base_url + "/health")
    if health_resp.status_code == 404:
        health_resp = request_raw("GET", base_url + "/v1/health")
        if health_resp.status_code == 404:
            print("No health route available; skipping.")
        elif health_resp.status_code < 200 or health_resp.status_code >= 300:
            die("Health check failed: HTTP %s %s" % (health_resp.status_code, health_resp.reason))
    elif health_resp.status_code < 200 or health_resp.status_code >= 300:
        die("Health check failed: HTTP %s %s" % (health_resp.status_code, health_resp.reason))

    step("Validate OpenAPI routes")
    openapi_resp = request_raw("GET", base_url + "/openapi.json")
    if openapi_resp.status_code != 200:
        die("OpenAPI fetch failed: HTTP %s %s" % (openapi_resp.status_code, openapi_resp.reason))
    try:
        openapi = openapi_resp.json()
    except Exception:
        die("OpenAPI fetch failed: invalid JSON")

    allow_bootstrap = os.getenv("CANARY_ALLOW_BOOTSTRAP") == "1"
    missing, paths = _validate_openapi_paths(openapi, allow_bootstrap)
    if missing:
        die("Missing required OpenAPI paths: %s" % ", ".join(missing))
    if allow_bootstrap and "/debug/bootstrap-staging-users" not in paths:
        print("Bootstrap skipped: /debug/bootstrap-staging-users missing from OpenAPI")

    print("Using user credentials from %s" % user_source)
    print("Using admin credentials from %s" % admin_source)
    print("User email=%s" % _redact_email(user_email))
    print("Admin email=%s" % _redact_email(admin_email))

    bootstrap_ready = bootstrap_preflight(base_url, bootstrap_secret)
    allow_bootstrap = os.getenv("CANARY_ALLOW_BOOTSTRAP") == "1"
    staging_key = os.getenv("STAGING_GATE_KEY")
    bootstrap_headers = {}
    if bootstrap_secret:
        bootstrap_headers["X-Bootstrap-Admin-Secret"] = bootstrap_secret
    if staging_key:
        bootstrap_headers["X-Staging-Key"] = staging_key

    step("Login user")
    user_login = _login_once(base_url, user_email, user_password)
    if user_login["resp"] is not None:
        _print_request_id(user_login["resp"], "Login user")
    token = user_login["token"]
    if not token:
        if (
            user_login["resp"] is not None
            and user_login["resp"].status_code == 401
            and user_login["detail"] == "INVALID_CREDENTIALS"
            and allow_bootstrap
            and bootstrap_ready
            and bootstrap_secret
        ):
            print("Login failed with INVALID_CREDENTIALS; attempting bootstrap")
            maybe_bootstrap_users(base_url=base_url, headers=bootstrap_headers)
            user_login = _login_once(base_url, user_email, user_password)
            if user_login["resp"] is not None:
                _print_request_id(user_login["resp"], "Login user (retry)")
            token = user_login["token"]
        if not token:
            if user_login["resp"] is not None:
                print("HTTP %s %s" % (user_login["resp"].status_code, user_login["resp"].reason))
                print(user_login["resp"].text)
            die("Missing access_token for user.")

    step("Login admin")
    admin_login = _login_once(base_url, admin_email, admin_password)
    if admin_login["resp"] is not None:
        _print_request_id(admin_login["resp"], "Login admin")
    admin_token = admin_login["token"]
    if not admin_token:
        if (
            admin_login["resp"] is not None
            and admin_login["resp"].status_code == 401
            and admin_login["detail"] == "INVALID_CREDENTIALS"
            and allow_bootstrap
            and bootstrap_ready
            and bootstrap_secret
        ):
            print("Login failed with INVALID_CREDENTIALS; attempting bootstrap")
            maybe_bootstrap_users(base_url=base_url, headers=bootstrap_headers)
            admin_login = _login_once(base_url, admin_email, admin_password)
            if admin_login["resp"] is not None:
                _print_request_id(admin_login["resp"], "Login admin (retry)")
            admin_token = admin_login["token"]
        if not admin_token:
            if admin_login["resp"] is not None:
                print("HTTP %s %s" % (admin_login["resp"].status_code, admin_login["resp"].reason))
                print(admin_login["resp"].text)
            die("Missing access_token for admin.")

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
    cash_in_resp = request(
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
    _print_request_id(cash_in_resp, "Cash-in")

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
    _print_request_id(r, "Cash-out")
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

    if not skip_webhook:
        step("Post TMONEY webhook")
        payload_obj = {"external_ref": external_ref, "status": "SUCCESS"}
        payload_bytes = canonical_json_bytes(payload_obj)
        sig_header = tmoney_sig_header(webhook_secret, payload_bytes)
        if os.getenv("WEBHOOK_DEBUG") == "1":
            digest = hashlib.sha256(payload_bytes).hexdigest()[:12]
            sig_preview = sig_header["X-Signature"][:12]
            print("TMONEY webhook debug body_len=%s sha=%s sig=%s" % (len(payload_bytes), digest, sig_preview))
        webhook_resp = request_raw(
            "POST",
            base_url + "/v1/webhooks/tmoney",
            headers={"Content-Type": "application/json", **sig_header},
            data=payload_bytes,
        )
        _print_request_id(webhook_resp, "TMONEY webhook")
        if (
            webhook_resp.status_code == 401
            and os.getenv("CANARY_DEBUG_WEBHOOK_SIG") == "1"
        ):
            detail = ""
            try:
                detail = webhook_resp.json().get("detail", "")
            except Exception:
                detail = webhook_resp.text or ""
            if detail == "INVALID_SIGNATURE":
                digest = hashlib.sha256(payload_bytes).hexdigest()[:12]
                sig_preview = sig_header["X-Signature"][:10]
                req_id = webhook_resp.headers.get("X-Request-ID")
                print(
                    "TMONEY webhook signature debug body_len=%s sha=%s sig=%s secret_len=%s request_id=%s"
                    % (
                        len(payload_bytes),
                        digest,
                        sig_preview,
                        len(webhook_secret),
                        req_id,
                    )
                )
        if webhook_resp.status_code < 200 or webhook_resp.status_code >= 300:
            print("HTTP %s %s" % (webhook_resp.status_code, webhook_resp.reason))
            print(webhook_resp.text)
            sys.exit(1)

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

    step("Canary smoke completed")
    print("transaction_id=%s" % tx_id)
    print("external_ref=%s" % external_ref)


if __name__ == "__main__":
    main()
