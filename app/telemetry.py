"""Track identity and bounded-cardinality metrics for one API process."""

import os
import time

from fastapi import Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

TRACK = os.getenv("APP_TRACK", "stable")
if TRACK not in {"stable", "canary"}:
    raise ValueError("APP_TRACK must be stable or canary")
VERSION = "3.0.0" if TRACK == "canary" else "2.0.0"
REVISION = os.getenv("APP_REVISION", "development")
LABELS = ("track", "version", "method", "route")
REQUESTS = Counter("inventory_http_requests_total", "HTTP responses", (*LABELS, "status"))
LATENCY = Histogram(
    "inventory_http_duration_seconds", "HTTP duration", LABELS,
    buckets=(.005, .01, .025, .05, .1, .2, .3, .5, .75, 1, 1.5, 2, 3, 5, 10),
)
QUERIES = Counter("inventory_queries_total", "Successful inventory queries", ("track", "version"))


def install_telemetry(app):
    @app.get("/metrics", include_in_schema=False)
    def metrics():
        return Response(generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})

    @app.middleware("http")
    async def measure(request, call_next):
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Preserve identity and count unhandled failures without exposing internals.
            response = JSONResponse(status_code=500, content={"detail": "Internal server error"})
        response.headers["X-App-Version"] = VERSION
        response.headers["X-App-Track"] = TRACK
        response.headers["X-App-Revision"] = REVISION
        if request.url.path not in {"/metrics", "/health", "/api/v2/health", "/api/v3/health"}:
            route = request.scope.get("route")
            # Unmatched paths and denied auth do not become user-controlled labels.
            path = getattr(route, "path", "unmatched")
            labels = (TRACK, VERSION, request.method if request.method in {
                "GET", "POST", "PUT", "DELETE", "OPTIONS", "QUERY", "HEAD", "PATCH"
            } else "OTHER", path)
            REQUESTS.labels(*labels, str(response.status_code)).inc()
            LATENCY.labels(*labels).observe(time.perf_counter() - start)
            if path.endswith("/inventario/query") and response.status_code == 200:
                QUERIES.labels(TRACK, VERSION).inc()
        return response
