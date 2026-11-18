"""Opt-in, private concurrency exhaustion lab. Disabled in the shared API."""
import asyncio
import hmac
import logging
import math
import os
import re
from threading import Event
import time

import anyio
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Gauge

logger = logging.getLogger(__name__)
ACTIVE = Gauge('inventory_resource_background_active', 'Active background workers', ('round',))
REJECTED = Counter('inventory_resource_background_rejected_total', 'Background jobs rejected without queuing', ('round',))
CLIENT_SUCCESS = Gauge('inventory_resource_client_success_ratio', 'Observed client success ratio during the fault window', ('round',))
CLIENT_P95 = Gauge('inventory_resource_client_p95_seconds', 'Observed client p95 including timeouts during the fault window', ('round',))


class ResourceFault:
    def __init__(self, protected, current_round):
        self.protected = protected
        self.current_round = current_round
        self.tasks = set()
        self.stop_event = Event()
        self.limiter = anyio.CapacityLimiter(4)
        self.expires = 0.0
        self.http_active = 0

    async def occupy(self, duration):
        ACTIVE.labels(self.current_round).inc()
        try:
            await anyio.to_thread.run_sync(self.stop_event.wait, duration,
                limiter=self.limiter if self.protected else None)
        finally:
            ACTIVE.labels(self.current_round).dec()

    async def inject(self, workers, duration):
        if self.tasks:
            raise HTTPException(409, 'A resource experiment is already active')
        self.stop_event = Event()
        admitted = min(workers, 4) if self.protected else workers
        REJECTED.labels(self.current_round).inc(workers-admitted)
        self.expires = time.monotonic()+duration
        for _ in range(admitted):
            task = asyncio.create_task(self.occupy(duration))
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)
        await asyncio.sleep(.05)
        return {'requested':workers, 'admitted':admitted, 'rejected':workers-admitted,
                'duration_seconds':duration, 'protected':self.protected}

    async def release(self):
        self.stop_event.set()
        if self.tasks:
            await asyncio.wait_for(asyncio.gather(*tuple(self.tasks)), timeout=5)
        return {'active':len(self.tasks), 'rollback_verified':not self.tasks}


def install_resource_lab(app):
    if os.getenv('RESOURCE_LAB_ENABLED') != 'true':
        return
    if (os.getenv('RENDER') == 'true' or os.getenv('CLOUD_PROVIDER') == 'aws') and (not os.getenv('RESOURCE_ADMIN_KEY') or not os.getenv('METRICS_BEARER_TOKEN')):
        raise ValueError('Cloud deployment requires separate private control and metrics credentials')
    # Fixed small capacity makes the fault reproducible without consuming host resources.
    state = ResourceFault(os.getenv('RESILIENCE_MODE') == 'protected', os.getenv('CHAOS_ROUND','none'))
    app.state.resource_fault = state

    @app.middleware('http')
    async def bound_business_queue(request,call_next):
        # Keep private rollback and metrics reachable even when business workers are exhausted.
        if request.url.path != '/api/v2/skus':
            return await call_next(request)
        if state.http_active >= 32:
            return JSONResponse(status_code=503,content={'detail':'Lab business concurrency capacity reached'})
        state.http_active += 1
        try:
            return await call_next(request)
        finally:
            state.http_active -= 1

    @app.on_event('startup')
    async def capacity():
        anyio.to_thread.current_default_thread_limiter().total_tokens = 6

    @app.on_event('shutdown')
    async def release():
        await state.release()

    def authorize(request):
        key = os.getenv('RESOURCE_ADMIN_KEY') or os.getenv('TEAM_API_KEY','')
        if not key or not hmac.compare_digest(key.encode(), request.headers.get('X-Api-Key','').encode()):
            raise HTTPException(401, 'Private lab key required')

    @app.post('/api/v2/admin/resource-round', include_in_schema=False)
    async def select_round(request: Request):
        authorize(request)
        data=await request.json()
        current=data.get('round'); execution=data.get('execution_id')
        if current not in {'BASELINE','R0','R1'} or not isinstance(execution,str) or not re.fullmatch(r'[a-f0-9]{32}',execution):
            raise HTTPException(400,'Expected BASELINE/R0/R1 and a 32-character execution_id')
        if state.tasks or state.http_active:
            raise HTTPException(409,'Wait for rollback and outstanding business requests before changing round')
        state.protected=current=='R1'
        state.current_round=current
        os.environ.update(CHAOS_ROUND=current,CHAOS_EXECUTION_ID=execution,
            RESILIENCE_MODE='protected' if state.protected else 'baseline')
        logger.info('Ronda seleccionada',extra={'trace_id':request.state.trace_id,'event':'resource_round'})
        return {'round':current,'execution_id':execution,'protected':state.protected}

    @app.post('/api/v2/admin/resource-result', include_in_schema=False)
    async def publish_result(request: Request):
        authorize(request)
        data=await request.json()
        successes=data.get('successes'); samples=data.get('samples'); p95=data.get('p95_ms')
        if data.get('round')!=state.current_round or data.get('execution_id')!=os.getenv('CHAOS_EXECUTION_ID'):
            raise HTTPException(409,'Result must belong to the active execution and round')
        if (type(samples) is not int or samples!=300 or type(successes) is not int or not 0<=successes<=samples
                or type(p95) not in (float,int) or not math.isfinite(p95) or not 0<=p95<=120000):
            raise HTTPException(400,'Expected 300 samples, successes 0..300 and a finite p95 in milliseconds')
        CLIENT_SUCCESS.labels(state.current_round).set(successes/samples)
        CLIENT_P95.labels(state.current_round).set(p95/1000)
        return {'recorded':True,'source':'client load measurement; raw evidence retained by controller'}

    @app.post('/api/v2/admin/resource-fault', include_in_schema=False)
    async def inject(request: Request):
        authorize(request)
        data = await request.json()
        workers, duration = data.get('workers'), data.get('duration_seconds')
        if type(workers) is not int or not 1 <= workers <= 6 or type(duration) is not int or not 1 <= duration <= 60:
            raise HTTPException(400, 'workers: integer 1..6; duration_seconds: integer 1..60')
        result = await state.inject(workers, duration)
        logger.info('Fallo de concurrencia inyectado', extra={'trace_id':request.state.trace_id,'event':'resource_injection'})
        return result

    @app.delete('/api/v2/admin/resource-fault', include_in_schema=False)
    async def rollback(request: Request):
        authorize(request)
        result = await state.release()
        logger.info('Concurrencia liberada', extra={'trace_id':request.state.trace_id,'event':'resource_rollback'})
        return result

    @app.get('/api/v2/admin/resource-fault', include_in_schema=False)
    async def inspect(request: Request):
        authorize(request)
        return {'active':len(state.tasks),'remaining_seconds':max(0,state.expires-time.monotonic())}
