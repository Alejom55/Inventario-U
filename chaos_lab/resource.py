"""Local synthetic resource experiment providers; credentials never enter journals."""
import asyncio
from datetime import datetime, timezone
import json
import math
import os
import re
from pathlib import Path
import time
from uuid import uuid4

import httpx

PROFILE = {'requests_per_second':5,'duration_seconds':120,'fault_start_seconds':30,
           'fault_duration_seconds':60,'timeout_seconds':2,'workers':6,
           'max_p95_ms':500,'min_success_percent':99,'window_seconds':60}
PORTS = {'BASELINE':18110,'R0':18111,'R1':18112}


def evaluate_objective(success_percent,p95_ms):
    objective=success_percent>=PROFILE['min_success_percent']
    guardrail=p95_ms<PROFILE['max_p95_ms']
    return {'objective_name':'success_percent','objective_threshold':99,
        'objective_passed':objective,'guardrail_p95_passed':guardrail,
        'passed':objective,'promotion_allowed':objective and guardrail}


def utc():
    return datetime.now(timezone.utc).isoformat()


def target():
    current=os.environ['CHAOS_ROUND']
    base=os.getenv('RESOURCE_RENDER_URL')
    if base:
        if not re.fullmatch(r'https://[a-z0-9-]+\.onrender\.com',base):
            raise ValueError('Expected one verified Render HTTPS origin')
        return current,base
    return current,'http://127.0.0.1:'+str(PORTS[current])


def headers(trace=None,control=False):
    key=os.getenv('RESOURCE_CONTROL_KEY') if control else None
    return {'X-Api-Key':key or os.environ['RESOURCE_PRIVATE_KEY'],'X-Trace-Id':trace or uuid4().hex}


def healthy():
    _,base=target()
    response=httpx.get(base+'/api/v2/skus',headers=headers(),timeout=3)
    valid=response.status_code==200 and isinstance(response.json(),list)
    if os.getenv('RESOURCE_RENDER_URL'):
        valid=valid and response.headers.get('X-Deployment-Provider')=='render' and response.headers.get('X-Render-Service-Id')==os.environ['RESOURCE_EXPECTED_SERVICE_ID'] and response.headers.get('X-App-Revision')==os.environ['APP_REVISION']
    return valid


def rollback():
    _,base=target()
    response=httpx.delete(base+'/api/v2/admin/resource-fault',headers=headers(control=True),timeout=7)
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
                trace=uuid4().hex; beginning=time.perf_counter(); code=0; identity=False; sent_utc=utc(); instance=None
                try:
                    response=await client.get(base+'/api/v2/skus',headers=headers(trace))
                    code=response.status_code
                    identity=response.headers.get('X-Trace-Id')==trace and response.headers.get('X-Chaos-Round')==current
                    if os.getenv('RESOURCE_RENDER_URL'):
                        instance=response.headers.get('X-Render-Instance-Id')
                        identity=identity and response.headers.get('X-Deployment-Provider')=='render' and response.headers.get('X-Render-Service-Id')==os.environ['RESOURCE_EXPECTED_SERVICE_ID'] and response.headers.get('X-App-Revision')==os.environ['APP_REVISION'] and instance==os.environ['RESOURCE_EXPECTED_INSTANCE_ID']
                except httpx.TransportError:
                    pass
                rows.append({'index':index,'scheduled_seconds':scheduled,'sent_utc':sent_utc,
                    'scheduler_lag_ms':round((beginning-started-scheduled)*1000,3),
                    'duration_ms':round((time.perf_counter()-beginning)*1000,3),
                    'status':code,'success':code==200 and identity,'trace_id':trace,'server_instance_id':instance})
            async def inject():
                await asyncio.sleep(max(0,30-(time.perf_counter()-started)))
                if current=='BASELINE':return
                events['injection_request_utc']=utc()
                response=await client.post(base+'/api/v2/admin/resource-fault',headers=headers(control=True),
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
            report={'scope':'RENDER cloud single API; not three-API E2E' if os.getenv('RESOURCE_RENDER_URL') else 'LOCAL single API replica; not cloud or three-API E2E',
                'assignment_status':'confirmed resource c: concurrency exhaustion',
                'round':current,'execution_id':execution,'profile':PROFILE,'revision':os.environ['APP_REVISION'],
                'started_utc':started_utc,'ended_utc':utc(),'fault':events,'samples':len(window),
                'total_requests':len(rows),'p95_ms':p95,'success_percent':success,'error_percent':100-success,
                'max_scheduler_lag_ms':max(r['scheduler_lag_ms'] for r in rows),
                **evaluate_objective(success,p95),'rollback_verified':released,
                'trace_id':next((r['trace_id'] for r in window if r['success']),window[0]['trace_id']),
                'requests':sorted(rows,key=lambda r:r['index'])}
            if os.getenv('RESOURCE_RENDER_URL'):
                report['deployment']={'provider':'render','url':base,'service_id':os.environ['RESOURCE_EXPECTED_SERVICE_ID'],
                    'instance_id':os.environ['RESOURCE_EXPECTED_INSTANCE_ID'],'application_revision':os.environ['APP_REVISION']}
                result=await client.post(base+'/api/v2/admin/resource-result',headers=headers(control=True),json={
                    'round':current,'execution_id':execution,'samples':len(window),'successes':sum(r['success'] for r in window),'p95_ms':p95})
                result.raise_for_status()
            destination.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
            return {key:value for key,value in report.items() if key!='requests'}
    return asyncio.run(run())
