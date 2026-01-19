import json
import os
import sys
import uuid

import requests


BASE_URL = "https://sandbox.momodeveloper.mtn.com"


def _die(message, code=1):
    print(message)
    sys.exit(code)


def _require_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        _die(f"Missing env var: {name}")
    return value


def _post_json(url: str, headers: dict, body: dict | None = None):
    try:
        resp = requests.post(url, headers=headers, json=body)
    except Exception as exc:
        _die(f"Request failed: {exc}")
    if resp.status_code not in (200, 201, 409):
        print(f"HTTP {resp.status_code} {resp.reason}")
        print(resp.text)
    return resp


def _create_api_user(api_user_id: str, subscription_key: str, callback_host: str) -> None:
    url = f"{BASE_URL}/v1_0/apiuser"
    headers = {
        "X-Reference-Id": api_user_id,
        "Ocp-Apim-Subscription-Key": subscription_key,
        "Content-Type": "application/json",
    }
    body = {"providerCallbackHost": callback_host}
    resp = _post_json(url, headers=headers, body=body)
    if resp.status_code in (200, 201, 409):
        return
    _die("Failed to create apiuser.")


def _create_api_key(api_user_id: str, subscription_key: str) -> str:
    url = f"{BASE_URL}/v1_0/apiuser/{api_user_id}/apikey"
    headers = {"Ocp-Apim-Subscription-Key": subscription_key}
    resp = _post_json(url, headers=headers, body=None)
    if resp.status_code not in (200, 201):
        _die("Failed to create api key.")
    try:
        payload = resp.json()
    except json.JSONDecodeError:
        _die("Invalid JSON response while creating api key.")
    api_key = payload.get("apiKey")
    if not api_key:
        _die("Missing apiKey in response.")
    return api_key


def main() -> None:
    callback_host = _require_env("MOMO_CALLBACK_HOST")
    collection_key = _require_env("MOMO_COLLECTION_SUB_KEY")
    _require_env("MOMO_DISBURSE_SUB_KEY")

    api_user_id = str(uuid.uuid4())
    print(f"Using api_user_id={api_user_id}")

    print("Creating apiuser (collection key)...")
    _create_api_user(api_user_id, collection_key, callback_host)
    api_key = _create_api_key(api_user_id, collection_key)
    print("API key created.")

    print("\nCredentials:")
    print(f"  api_user_id={api_user_id}")
    print(f"  api_key={api_key}")
    print("\nSnippet:")
    print(f"MOMO_API_USER_ID={api_user_id}")
    print(f"MOMO_API_KEY={api_key}")


if __name__ == "__main__":
    main()
