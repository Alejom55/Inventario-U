"""Explicitly enabled, authenticated canary-only regression switch."""

import asyncio
import hmac
import os
import random

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .telemetry import TRACK


class Fault(BaseModel):
    error_rate: float = Field(default=0, ge=0, le=1)
    latency_ms: int = Field(default=0, ge=0, le=2000)


def install_faults(app):
    if TRACK != "canary" or os.getenv("FAULT_INJECTION_ENABLED") != "true":
        return
    fault = Fault()

    def authorized(request):
        key = os.getenv("TEAM_API_KEY", "")
        return bool(key) and hmac.compare_digest(request.headers.get("X-Api-Key", ""), key)

    @app.post("/api/v3/admin/fault", tags=["controlled demo"])
    def configure(body: Fault, request: Request):
        nonlocal fault
        if not authorized(request):
            raise HTTPException(status_code=401, detail="Valid API key required")
        fault = body
        return fault.model_dump()

    @app.middleware("http")
    async def inject(request, call_next):
        if authorized(request) and request.url.path.startswith(("/api/v3/inventario/", "/api/v3/skus")):
            current = fault
            if current.latency_ms:
                await asyncio.sleep(current.latency_ms / 1000)
            if random.random() < current.error_rate:
                return JSONResponse(status_code=500, content={"detail": "Controlled canary regression"})
        return await call_next(request)
