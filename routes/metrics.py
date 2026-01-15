from fastapi import APIRouter
from fastapi.responses import Response

from services.metrics import render_prometheus

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
def metrics():
    body = render_prometheus()
    return Response(content=body, media_type="text/plain; version=0.0.4")
