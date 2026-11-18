"""Track identity and bounded-cardinality metrics for one API process."""

import os
import time
import logging
import hmac
import re

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from .observability import correlation_id, round_identity
from .integrations.contracts import configuration_fingerprint

TRACK = os.getenv("APP_TRACK", "stable")
if TRACK not in {"stable", "canary"}:
    raise ValueError("APP_TRACK must be stable or canary")
VERSION = "3.0.0" if TRACK == "canary" else "2.0.0"
REVISION = os.getenv("RENDER_GIT_COMMIT") or os.getenv("APP_REVISION", "development")
LABELS = ("track", "version", "method", "route")
REQUESTS = Counter("inventory_http_requests_total", "HTTP responses", (*LABELS, "status"))
LATENCY = Histogram(
    "inventory_http_duration_seconds", "HTTP duration", LABELS,
    buckets=(.005, .01, .025, .05, .1, .2, .3, .5, .75, 1, 1.5, 2, 3, 5, 10),
)
QUERIES = Counter("inventory_queries_total", "Successful inventory queries", ("track", "version"))
FLOWS = Counter("inventory_flow_requests_total", "Complete and failed three-entity flows", ("round", "outcome"))
FLOW_DURATION = Histogram(
    "inventory_flow_duration_seconds", "Three-entity flow duration, including failed flows",
    ("round", "outcome"), buckets=(.005, .01, .025, .05, .1, .2, .3, .5, .75, 1, 1.5, 2, 3, 5, 10),
)
logger = logging.getLogger(__name__)


def install_telemetry(app):
    @app.get("/metrics", include_in_schema=False)
    async def metrics(request: Request):
        token=os.getenv('METRICS_BEARER_TOKEN')
        if token and not hmac.compare_digest(request.headers.get('Authorization','').encode(),('Bearer '+token).encode()):
            return JSONResponse(status_code=401,content={'detail':'Metrics Bearer required'})
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
        if os.getenv('RENDER')=='true':
            response.headers['X-Deployment-Provider']='render'
            for name,header in (('RENDER_SERVICE_ID','X-Render-Service-Id'),('RENDER_INSTANCE_ID','X-Render-Instance-Id')):
                value=os.getenv(name,'')
                if re.fullmatch(r'[A-Za-z0-9_-]{1,128}',value):response.headers[header]=value
        elif os.getenv('CLOUD_PROVIDER')=='aws':
            response.headers['X-Deployment-Provider']='aws'
            instance=os.getenv('AWS_INSTANCE_ID','')
            if re.fullmatch(r'i-[a-f0-9]{8,17}',instance):
                response.headers['X-Cloud-Service-Id']=instance
                response.headers['X-Cloud-Instance-Id']=instance
        response.headers["X-Resilience-Mode"] = os.getenv("RESILIENCE_MODE", "baseline") if os.getenv("RESILIENCE_MODE", "baseline") in {"baseline", "protected"} else "invalid"
        current_round = round_identity()
        response.headers["X-Chaos-Round"] = current_round
        trace_id = getattr(request.state, "trace_id", None) or response.headers.get("X-Trace-Id")
        if not trace_id:
            trace_id = correlation_id(request.headers.get("X-Trace-Id"))
        response.headers["X-Trace-Id"] = trace_id
        elapsed = time.perf_counter() - start
        if request.url.path in {"/api/v2/integracion", "/api/v3/integracion"}:
            response.headers["X-Integration-Contract"] = configuration_fingerprint()
            outcome = "complete" if response.status_code == 200 and getattr(request.state, "flow_complete", False) else "error"
            FLOWS.labels(current_round, outcome).inc()
            FLOW_DURATION.labels(current_round, outcome).observe(elapsed)
            logger.info("Flujo finalizado", extra={"trace_id": trace_id, "event": "flow_response", "round": current_round, "status": response.status_code, "duration_ms": round(elapsed*1000, 3), "outcome": outcome})
        if request.url.path not in {"/metrics", "/health", "/api/v2/health", "/api/v3/health"}:
            route = request.scope.get("route")
            # Unmatched paths and denied auth do not become user-controlled labels.
            path = getattr(route, "path", "unmatched")
            labels = (TRACK, VERSION, request.method if request.method in {
                "GET", "POST", "PUT", "DELETE", "OPTIONS", "QUERY", "HEAD", "PATCH"
            } else "OTHER", path)
            REQUESTS.labels(*labels, str(response.status_code)).inc()
            LATENCY.labels(*labels).observe(elapsed)
            logger.info('Respuesta HTTP', extra={'trace_id':trace_id, 'path':path,
                'status':response.status_code, 'duration_ms':round(elapsed*1000,3)})
            if path.endswith(("/inventario/query", "/inventario")) and response.status_code == 200:
                QUERIES.labels(TRACK, VERSION).inc()
        return response
