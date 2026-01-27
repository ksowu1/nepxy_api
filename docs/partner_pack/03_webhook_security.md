# NepXy Partner Pack - Webhook Security

## Webhook endpoints
- POST /v1/webhooks/tmoney
- POST /v1/webhooks/flooz
- POST /v1/webhooks/momo
- POST /v1/webhooks/thunes

## Signing
- NepXy verifies HMAC SHA-256 signatures.
- Signature header: X-Signature: sha256=<hex>
- Secret: provider-specific webhook secret (e.g., TMONEY_WEBHOOK_SECRET).

## Verification rules
- If a provider is disabled, NepXy returns HTTP 503 ProviderDisabled.
- If the signature is missing or invalid, NepXy returns HTTP 401.
- If the secret is not configured, NepXy returns HTTP 500 to signal misconfiguration.

## Replay protection
- NepXy stores every webhook event with request metadata.
- Idempotent processing: updates by provider_ref or external_ref; unknown refs are ignored with HTTP 200 to avoid retry storms.
- Admin replay endpoint exists for controlled reprocessing:
  POST /v1/admin/webhooks/events/{event_id}/replay

## Minimal payload requirements
- provider_ref or external_ref
- status

## Example (pseudo)
X-Signature: sha256=<hmac(body, secret)>
Body: { "provider_ref": "ref-123", "status": "SUCCESS" }
