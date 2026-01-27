# Funding Rails (Stub)

NepXy includes placeholder funding rails for ACH, Card, and Wire. These endpoints are defined but return 501 until a real provider is integrated.

## Feature flags
Each rail is gated by a feature flag (all default to false):
- `FUNDING_ACH_ENABLED`
- `FUNDING_CARD_ENABLED`
- `FUNDING_WIRE_ENABLED`

When a flag is false, the endpoint returns HTTP 503 with `FEATURE_DISABLED`.
When true, the endpoint returns HTTP 501 with `NOT_IMPLEMENTED`.

## Endpoints
- POST `/v1/funding/ach`
- POST `/v1/funding/card`
- POST `/v1/funding/wire`

## Request body (common)
```
{
  "wallet_id": "<uuid>",
  "amount_cents": 1000,
  "currency": "USD",
  "external_ref": "client-ref-123",
  "memo": "optional memo"
}
```

## Internal request model
Each endpoint builds an internal `FundingRequest` object for consistency and logging.
This request_id will later be used for reconciliation and webhook updates when funding is implemented.

## Ledger integration points (future)
Once funding rails are wired:
- Post a ledger cash-in transaction after validation.
- Store `request_id` and `external_ref` on the ledger transaction for reconciliation.
- Update funding status via webhook or provider polling.
