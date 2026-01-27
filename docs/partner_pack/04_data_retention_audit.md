# NepXy Partner Pack - Data Retention and Audit Logging

## Data retention (summary)
- Transaction and payout records are stored in Postgres.
- Webhook events are stored with headers, payload, and signature validation results.
- Audit log entries are recorded for privileged actions (admin-only operations).

## Audit logging
- Each webhook is recorded in both:
  - app.webhook_events (admin API view)
  - public.webhook_events (detailed audit)
- Admin actions (e.g., webhook replay) are logged in app.audit_log.

## Access and exports
- Admin endpoints allow viewing webhook events and audit trails.
- Data exports are access-controlled and logged.

## Retention policy
- Retention windows should be set by the operator based on regulatory needs.
- NepXy supports configurable archival via database policy or external ETL.
