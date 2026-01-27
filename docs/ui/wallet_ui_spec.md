# NepXy UI Spec (Production-like, Minimal)

This spec mirrors the current API surface and mobile flows (see `mobile/nepxy`), but is simplified for a Next.js web onboarding + wallet experience.

## Global UX rules
- Always show a request_id in error toasts when available.
- Use idempotency keys for all write operations (cash-in, cash-out).
- Disable actions if the backing provider or funding rail is disabled.
- Prefer concise, operator-grade copy (clear and actionable).

## Routes (Next.js)
- `/` or `/login`
- `/signup`
- `/wallet`
- `/activity`
- `/send`
- `/add-money`

---

# 1) Sign up / Login

## Login
**Fields**
- Email
- Password

**Primary CTA**
- “Log in”

**Secondary**
- “Create account” (link to /signup)

**Errors**
- Invalid credentials: “We couldn’t log you in. Check your email and password.”
- Network: “Network error. Try again.”

**API**
- POST `/v1/auth/login`

---

## Sign up
**Fields**
- Email
- Phone (E.164)
- Full name
- Country (select)
- Password

**Primary CTA**
- “Create account”

**Secondary**
- “Already have an account? Log in”

**Errors**
- Email taken: “Email already registered. Log in instead.”
- Phone taken: “Phone already registered. Use a different number.”

**API**
- POST `/v1/auth/register`

---

# 2) Wallet (Home)

## Layout
- Header: “Wallet”
- Balance card
- Primary actions: “Add money”, “Send”
- Status strip (corridor + provider availability)

## Data
- GET `/v1/wallets`
- GET `/v1/wallets/{wallet_id}/balance`

## States
**Loading**
- Skeleton balance card

**Empty**
- “No wallet yet.”
- Subtext: “Finish onboarding to activate your wallet.”

**Error**
- “We couldn’t load your wallet. Try again.”

---

# 3) Add money (Funding)

## Behavior
- If all funding rails are disabled, show disabled state.
- If a specific rail is disabled, show the option but disabled with reason.

**Funding rails (placeholders)**
- ACH
- Card
- Wire

**Disabled state copy**
- Title: “Funding is not available yet”
- Body: “We’ll enable ACH, card, and wire deposits soon. You can still send funds from your wallet balance.”

**Enabled state (future)**
- Form: amount, memo, funding method
- CTA: “Add money”

**API**
- POST `/v1/funding/ach`
- POST `/v1/funding/card`
- POST `/v1/funding/wire`

**Error mapping**
- 503 FEATURE_DISABLED: “This funding method is not available yet.”
- 501 NOT_IMPLEMENTED: “Funding is coming soon. We’ll notify you when it’s ready.”

---

# 4) Send / Cash-out

## Flow
- Select wallet
- Amount
- Destination country
- Provider (if multiple)
- Recipient phone
- Review + submit

## Provider availability
- Use `/v1/catalog/destinations` or `/v1/catalog/delivery-methods` to show provider status.
- Disable provider options if status != AVAILABLE.

**Disabled state copy**
- “Provider unavailable”
- “This provider is not enabled right now. Choose another option.”

**Submit CTA**
- “Send now”

**API**
- POST `/v1/cash-out/mobile-money`

**Errors**
- PROVIDER_DISABLED: “This provider is currently disabled.”
- UNSUPPORTED_CORRIDOR: “This corridor is not supported yet.”
- VELOCITY_LIMIT_EXCEEDED: “You’ve reached today’s limit. Try again later.”
- CASHOUT_VELOCITY_WINDOW_EXCEEDED: “Too many transfers in a short time. Try again soon.”

---

# 5) Activity feed

## Layout
- Tabs: “Wallet activity” and “Payouts”
- Each item shows: amount, direction, status, time, provider

## Data
- GET `/v1/wallets/{wallet_id}/activity?limit=30`
- GET `/v1/wallets/{wallet_id}/payouts?limit=30`
  (fallback: `/v1/payouts?wallet_id=...`)

## States
**Empty**
- “No activity yet.”
- Subtext: “Your transfers and top-ups will appear here.”

**Error**
- “We couldn’t load activity. Try again.”

---

# Error handling (global)

## Toast messages
- “Something went wrong. Please try again.”
- “Network error. Check your connection.”
- “Request failed. Reference: <request_id>”

## Inline form errors
- “Enter a valid phone number.”
- “Amount must be greater than 0.”
- “Select a destination country.”

---

# Implementation notes (Next.js)
- Use a shared API client that injects `Authorization` and `Idempotency-Key`.
- Persist JWT in an HttpOnly cookie or secure storage.
- Keep provider availability in app state (from catalog endpoint), refreshed on page load.
- For disabled funding rails, render buttons disabled + tooltip with reason.
