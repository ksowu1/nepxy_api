# MoMo Sandbox Bootstrap + Tokens

This note covers how to bootstrap sandbox credentials and fetch access tokens.

## Bootstrap credentials

Run the bootstrap script with the required env vars:

```bash
set MOMO_ENV=sandbox
set MOMO_CALLBACK_HOST=https://nepxy-staging.fly.dev
set MOMO_COLLECTION_SUB_KEY=your_collection_sub_key
set MOMO_DISBURSE_SUB_KEY=your_disbursement_sub_key
python scripts/momo_bootstrap.py
```

It prints the api user id and keys and writes `.env.momo.sandbox`.

## Get tokens

Use the `MOMO_API_USER` and API keys from `.env.momo.sandbox`.

### Collection token

```bash
set MOMO_API_USER=your_api_user_id
set MOMO_COLLECTION_API_KEY=your_collection_api_key
set MOMO_COLLECTION_SUB_KEY=your_collection_sub_key
curl -sS -X POST ^
  https://sandbox.momodeveloper.mtn.com/collection/token/ ^
  -u %MOMO_API_USER%:%MOMO_COLLECTION_API_KEY% ^
  -H "Ocp-Apim-Subscription-Key: %MOMO_COLLECTION_SUB_KEY%"
```

### Disbursement token

```bash
set MOMO_API_USER=your_api_user_id
set MOMO_DISBURSE_API_KEY=your_disbursement_api_key
set MOMO_DISBURSE_SUB_KEY=your_disbursement_sub_key
curl -sS -X POST ^
  https://sandbox.momodeveloper.mtn.com/disbursement/token/ ^
  -u %MOMO_API_USER%:%MOMO_DISBURSE_API_KEY% ^
  -H "Ocp-Apim-Subscription-Key: %MOMO_DISBURSE_SUB_KEY%"
```
