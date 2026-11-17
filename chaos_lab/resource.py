"""Local synthetic resource experiment providers; credentials never enter journals."""
import asyncio
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import time
from uuid import uuid4

import httpx

PROFILE = {'requests_per_second':5,'duration_seconds':120,'fault_start_seconds':30,
           'fault_duration_seconds':60,'timeout_seconds':2,'workers':6,
           'max_p95_ms':500,'min_success_percent':99,'window_seconds':60}
PORTS = {'BASELINE':18110,'R0':18111,'R1':18112}


def utc():
    return datetime.now(timezone.utc).isoformat()


def target():
    current=os.environ['CHAOS_ROUND']
    return current,'http://127.0.0.1:'+str(PORTS[current])


def headers(trace=None):
    return {'X-Api-Key':os.environ['RESOURCE_PRIVATE_KEY'],'X-Trace-Id':trace or uuid4().hex}


def healthy():
    _,base=target()
    response=httpx.get(base+'/api/v2/skus',headers=headers(),timeout=3)
    return response.status_code==200 and isinstance(response.json(),list)


def rollback():
    _,base=target()
    response=httpx.delete(base+'/api/v2/admin/resource-fault',headers=headers(),timeout=7)
    response.raise_for_status()
    return response.json()['rollback_verified']


def measure():
    current,base=target()
    execution=os.environ['CHAOS_EXECUTION_ID']
    destination=Path(os.environ['RESOURCE_RESULT_FILE'])
    async def run():
        rows=[]; events={}; tasks=[]
        async with httpx.AsyncClient(timeout=PROFILE['timeout_seconds'],limits=httpx.Limits(max_connections=40)) as client:
            started=time.perf_counter(); started_utc=utc()
            async def request(index,scheduled):
                trace=uuid4().hex; beginning=time.perf_counter(); code=0; identity=False
                try:
                    response=await client.get(base+'/api/v2/skus',headers=headers(trace))
                    code=response.status_code
                    identity=response.headers.get('X-Trace-Id')==trace and response.headers.get('X-Chaos-Round')==current
                except httpx.TransportError:
                    pass
                rows.append({'index':index,'scheduled_seconds':scheduled,'sent_utc':utc(),
                    'scheduler_lag_ms':round((beginning-started-scheduled)*1000,3),
                    'duration_ms':round((time.perf_counter()-beginning)*1000,3),
                    'status':code,'success':code==200 and identity,'trace_id':trace})
            async def inject():
                await asyncio.sleep(max(0,30-(time.perf_counter()-started)))
                if current=='BASELINE':return
                events['injection_request_utc']=utc()
                response=await client.post(base+'/api/v2/admin/resource-fault',headers=headers(),
                    json={'workers':6,'duration_seconds':60})
                response.raise_for_status()
                events.update(injection_ack_utc=utc(),injection=response.json())
                await asyncio.sleep(60)
                events['release']=await asyncio.to_thread(rollback)
                events['release_verified_utc']=utc()
            injection=asyncio.create_task(inject())
            try:
                for index in range(600):
                    scheduled=index/5
                    await asyncio.sleep(max(0,started+scheduled-time.perf_counter()))
                    tasks.append(asyncio.create_task(request(index,scheduled)))
                await asyncio.gather(*tasks)
                await injection
            finally:
                if not injection.done():
                    injection.cancel()
                    await asyncio.gather(injection,return_exceptions=True)
                released=await asyncio.to_thread(rollback)
            window=[r for r in rows if 30<=r['scheduled_seconds']<90]
            p95=sorted(r['duration_ms'] for r in window)[math.ceil(len(window)*.95)-1]
            success=sum(r['success'] for r in window)/len(window)*100
            report={'scope':'LOCAL single API replica; not cloud or three-API E2E',
                'assignment_status':'proposed resource c; group confirmation pending',
                'round':current,'execution_id':execution,'profile':PROFILE,'revision':os.environ['APP_REVISION'],
                'started_utc':started_utc,'ended_utc':utc(),'fault':events,'samples':len(window),
                'total_requests':len(rows),'p95_ms':p95,'success_percent':success,'error_percent':100-success,
                'max_scheduler_lag_ms':max(r['scheduler_lag_ms'] for r in rows),
                'passed':p95<500 and success>=99,'rollback_verified':released,
                'trace_id':next((r['trace_id'] for r in window if r['success']),window[0]['trace_id']),
                'requests':sorted(rows,key=lambda r:r['index'])}
            destination.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
            return {key:value for key,value in report.items() if key!='requests'}
    return asyncio.run(run())
