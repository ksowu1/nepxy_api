
#main.py
from fastapi import FastAPI
from routes.wallet import router as wallet_router
from routes.payments import router as payments_router
import psycopg2
from fastapi import Request
from fastapi.responses import JSONResponse
from routes.debug import router as debug_router
from routes.auth import router as auth_router
from routes.fx import router as fx_router
from routes.admin_ledger import router as admin_ledger_router
from routes.admin_roles import router as admin_roles_router
from routes.p2p import router as p2p_router



app = FastAPI(title="NexaPay API", version="1.0.0")

# -----------------------------
# ROUTERS
# -----------------------------

app.include_router(wallet_router)
app.include_router(payments_router)
app.include_router(debug_router)
app.include_router(auth_router)
app.include_router(fx_router)
app.include_router(admin_ledger_router)
app.include_router(admin_roles_router)
app.include_router(p2p_router)


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


