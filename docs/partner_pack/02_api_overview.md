# NepXy Partner Pack - API Overview

## Base URLs
- Staging: https://nepxy-staging.fly.dev
- Production: https://nepxy-prod.fly.dev

## Authentication
- Login: POST /v1/auth/login
- Response includes access_token (Bearer JWT)
- Use: Authorization: Bearer <token>

## Idempotency
- Send Idempotency-Key header on POST requests that create money movement.
- Example header: Idempotency-Key: <uuid>
- Safe retry behavior: identical payload + same key returns same result.

## Common endpoints
- POST /v1/auth/login
- POST /v1/auth/register
- GET /v1/wallets
- GET /v1/wallets/{wallet_id}/balance
- POST /v1/cash-in/mobile-money
- POST /v1/cash-out/mobile-money

## Request/response expectations
- All monetary values are in cents (integer).
- Provider names are uppercase: TMONEY, FLOOZ, MOMO, THUNES.
- Country codes use ISO2 (e.g., TG, GH, BJ).

## Error format
- HTTP status codes indicate error class.
- JSON error payload contains detail or error fields.

## Sample request (cash-out)
POST /v1/cash-out/mobile-money
Headers:
  Authorization: Bearer <token>
  Idempotency-Key: <uuid>
Body:
{
  "wallet_id": "<wallet_id>",
  "amount_cents": 1000,
  "country": "TG",
  "provider": "TMONEY",
  "provider_ref": "client-ref-123"
}
