# NepXy Partner Pack - Staging Access

## Base URL
- https://nepxy-staging.fly.dev

## Staging gate
- Header: X-Staging-Key: <staging_gate_key>
- Required for protected routes.

## Test credentials
User:
- Email: <staging_user_email>
- Password: <staging_user_password>

Admin:
- Email: <staging_admin_email>
- Password: <staging_admin_password>

## Quick start
1) Login
   POST /v1/auth/login
2) Use Bearer token in Authorization header
3) Use Idempotency-Key on write endpoints
4) Trigger a cash-out and wait for webhook callback
