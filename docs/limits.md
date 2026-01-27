# Limits and Corridors

This document describes the compliance limits and corridor allowlist controls.

## Environment variables
- `MAX_CASHOUT_PER_DAY_CENTS` (default: 0 = disabled)
- `MAX_CASHOUT_COUNT_PER_DAY` (default: 0 = disabled)
- `MAX_DISTINCT_RECEIVERS_PER_DAY` (default: 0 = disabled)
- `MAX_CASHIN_PER_DAY_CENTS` (default: 0 = disabled)
- `MAX_CASHOUT_PER_MONTH_CENTS` (default: 0 = disabled)
- `MAX_CASHOUT_COUNT_PER_MONTH` (default: 0 = disabled)
- `MAX_CASHIN_PER_MONTH_CENTS` (default: 0 = disabled)
- `MAX_CASHOUT_COUNT_PER_WINDOW` (default: 0 = disabled)
- `CASHOUT_WINDOW_MINUTES` (default: 0 = disabled)
- `CORRIDOR_ALLOWLIST` (default: "US:GH,US:BJ")

## Allowlist format
- Comma-separated `SEND:RECEIVE` pairs.
- Example: `US:GH,US:BJ`.
- Backward-compatible: `US->GH,US->BJ` also supported.

## Defaults
- All limits default to 0 (disabled).
- Corridor allowlist defaults to `US:GH,US:BJ`.

## Recommendations
- Staging: keep limits disabled unless testing throttles.
- Production: set daily + monthly caps and windowed velocity.

## Error codes
- `VELOCITY_LIMIT_EXCEEDED`
- `CASHOUT_VELOCITY_WINDOW_EXCEEDED`
- `UNSUPPORTED_CORRIDOR`
