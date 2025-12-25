

\# NexaPay API (MVP)



FastAPI backend for wallets + ledger-backed transfers.



\## Features

\- Auth (JWT)

\- Wallet listing / balance

\- Wallet activity / transactions

\- P2P transfers with idempotency

\- DB error -> HTTP mapping (403/404/409 etc.)

\- Pytest suite (14 passing)



\## Run

```powershell

python -m uvicorn main:app --port 8001 --reload --reload-exclude .venv



