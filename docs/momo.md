# MoMo Sandbox Notes

This covers how MoMo sandbox tokens are generated, required env vars, and which subscription keys apply.

## Required env vars

- `MOMO_API_USER_ID`
- `MOMO_API_KEY`
- `MOMO_DISBURSE_SUB_KEY`
- `MOMO_ENV` (use `sandbox`)

The adapter uses the MoMo Disbursement sandbox base URL:
- `https://sandbox.momodeveloper.mtn.com`

## Token generation flow

1) Create an API user:
   - `POST https://sandbox.momodeveloper.mtn.com/v1_0/apiuser`
   - Headers:
     - `X-Reference-Id: <api_user_id>`
     - `Ocp-Apim-Subscription-Key: <collection subscription key>`
   - Body:
     - `{ "providerCallbackHost": "<your callback host>" }`

2) Create an API key:
   - `POST https://sandbox.momodeveloper.mtn.com/v1_0/apiuser/<api_user_id>/apikey`
   - Header:
     - `Ocp-Apim-Subscription-Key: <collection subscription key>`

The script `scripts/momo_bootstrap.py` runs this flow and prints the API user id + API key.

## Adapter behavior

- Token is cached in memory and refreshed with a 60s safety buffer.
- Transfer requests include `X-Reference-Id` set to the payout provider ref.
- Status mapping: `SUCCESSFUL` -> `CONFIRMED`, `FAILED/REJECTED` -> `FAILED`, `PENDING` -> `SENT`.

## Which subscription key to use

- Collection endpoints use `MOMO_COLLECTION_SUB_KEY`.
- Disbursement endpoints use `MOMO_DISBURSE_SUB_KEY`.

The API user + API key created with the collection key can be used to request tokens
for both product areas, but you must pass the correct subscription key per endpoint.
