# Ledger Funding Contract

This document defines how future funding rails (ACH/Card) should map into ledger transactions and entries.

## Ledger transaction mapping
- Create a ledger transaction with type `CASHIN`.
- `external_ref`: provider’s unique reference for the funding event (must be immutable).
- `idempotency_key`: client-supplied key; if provider delivers a duplicate event, do not create a second ledger transaction.

## Entries
- Debit: external funding source (virtual account)
- Credit: user wallet account
- Amount: `amount_cents` in the wallet currency

## Required invariants
- `external_ref` must be globally unique per provider.
- `idempotency_key` must be required on API create.
- If an event with the same `external_ref` arrives, the system must return the existing transaction and not create new entries.
- Ledger balance must equal sum of entries at all times.

## Reconciliation
- Store `provider_ref` and `external_ref` on the ledger transaction for audit.
- Reconcile funding events by `external_ref` first, falling back to provider-specific reference if present.
- If provider sends a correction (chargeback/refund), create a compensating ledger transaction; do not mutate historical entries.
