"""Opt-in, private concurrency exhaustion lab. Disabled in the shared API."""
import asyncio
import hmac
import logging
import os
from threading import Event
import time

import anyio
from fastapi import HTTPException, Request
from prometheus_client import Counter, Gauge

logger = logging.getLogger(__name__)
ACTIVE = Gauge('inventory_resource_background_active', 'Active background workers', ('round',))
REJECTED = Counter('inventory_resource_background_rejected_total', 'Background jobs rejected without queuing', ('round',))


class ResourceFault:
    def __init__(self, protected, current_round):
        self.protected = protected
        self.current_round = current_round
        self.tasks = set()
        self.stop_event = Event()
        self.limiter = anyio.CapacityLimiter(4)
        self.expires = 0.0

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
    # Fixed small capacity makes the fault reproducible without consuming host resources.
    state = ResourceFault(os.getenv('RESILIENCE_MODE') == 'protected', os.getenv('CHAOS_ROUND','none'))
    app.state.resource_fault = state

    @app.on_event('startup')
    async def capacity():
        anyio.to_thread.current_default_thread_limiter().total_tokens = 6

    @app.on_event('shutdown')
    async def release():
        await state.release()

    def authorize(request):
        key = os.getenv('TEAM_API_KEY','')
        if not key or not hmac.compare_digest(key, request.headers.get('X-Api-Key','')):
            raise HTTPException(401, 'Private lab key required')

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
