# Provider Onboarding Tracker

| Provider | Creds status | Webhook spec received | IP allowlist | Signature method | Sandbox tested | Production approved | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Thunes | Pending (no sandbox creds yet) | No | Unknown | HMAC SHA-256 (planned) | No | No | Waiting on Thunes sandbox credentials; payer IDs pending. |
| TMONEY | Staging OK | Yes | Unknown | HMAC SHA-256 (X-Signature) | Yes | No | Staging canary passes; prod readiness depends on enabled flag + secrets. |
| MTN MoMo | Unknown | Unknown | Unknown | Unknown | Unknown | No | MoMo integration exists; confirm sandbox credentials and webhook/allowlist requirements. |
| Flooz | Unknown | Unknown | Unknown | Unknown | Unknown | No | Flooz integration exists; verify keys, webhook spec, and sandbox behavior. |
