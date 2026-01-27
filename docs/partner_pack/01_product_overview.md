# NepXy Partner Pack - Product One-Pager

## Summary
NepXy is a programmable wallet and payout platform for African markets. It provides API-first cash-in and cash-out flows, settlement-ready ledgers, and audit-grade observability.

## What it does
- Wallets and balances with ledger-backed transactions
- Mobile money cash-in and cash-out with provider abstraction
- Idempotent transaction creation and payout submission
- Webhook-based status updates with audit trails

## Core capabilities
- Unified API for multiple mobile money providers
- Deterministic idempotency for safe retries
- Webhook verification and replay protection
- Operational controls (rate limits, velocity limits, staging gate)

## Typical integration flow
1) Create user and wallet
2) Cash-in to fund a wallet
3) Cash-out to a mobile money recipient
4) Listen for webhook status updates
5) Reconcile status and audit trail

## Environments
- Staging: pre-production testing behind a gate header
- Production: locked-down, debug routes disabled

## Support
See Incident Response + Contacts in this pack.
