"""Explicitly enabled, authenticated canary-only regression switch."""

import asyncio
import hmac
import os
import random
import time
from uuid import uuid4

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .telemetry import TRACK


class Fault(BaseModel):
    error_rate: float = Field(default=0, ge=0, le=1)
    latency_ms: int = Field(default=0, ge=0, le=2000)
    duration_seconds: int = Field(default=180, ge=1, le=600)


def install_faults(app):
    if TRACK != "canary" or os.getenv("FAULT_INJECTION_ENABLED") != "true":
        return
    state = (Fault(), 0.0)

    def authorized(request):
        key = os.getenv("TEAM_API_KEY", "")
        return bool(key) and hmac.compare_digest(request.headers.get("X-Api-Key", ""), key)

    @app.post("/api/v3/admin/fault", tags=["controlled demo"])
    def configure(body: Fault, request: Request):
        nonlocal state
        if not authorized(request):
            raise HTTPException(status_code=401, detail="Valid API key required")
        state = (body, time.monotonic() + body.duration_seconds)
        return body.model_dump()

    @app.middleware("http")
    async def inject(request, call_next):
        if authorized(request) and request.url.path.startswith(("/api/v3/inventario/", "/api/v3/skus")):
            current, expires_at = state
            if time.monotonic() >= expires_at:
                return await call_next(request)
            if current.latency_ms:
                await asyncio.sleep(current.latency_ms / 1000)
            if random.random() < current.error_rate:
                trace_id = request.headers.get("X-Trace-Id") or str(uuid4())
                return JSONResponse(
                    status_code=500,
                    content={"detail": "Controlled canary regression", "trace_id": trace_id},
                    headers={"X-Trace-Id": trace_id},
                )
        return await call_next(request)
