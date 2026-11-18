"""Private publication of measured client results, including censored timings."""
import hashlib
import hmac
import json
import logging
import math
import os
import re

from fastapi import Request
from fastapi.responses import JSONResponse
from prometheus_client import Gauge

FIELDS=('mttd_seconds','mttc_seconds','detection_coverage_percent','false_positive_percent','adverse_acceptance_percent')
GAUGES={name:Gauge('inventory_security_'+name,'Measured E1 '+name,('round',)) for name in FIELDS}
OBSERVED={name:Gauge('inventory_security_'+name+'_observed','One when timing was actually observed; zero when censored',('round',)) for name in ('mttd_seconds','mttc_seconds')}
logger=logging.getLogger('app.security_results')


def install_security_results(app):
    if os.getenv('SECURITY_RESULTS_ENABLED')!='true':return
    key=os.getenv('RESOURCE_ADMIN_KEY','')
    if not key:raise ValueError('Security result publication requires a separate operator key')
    recorded={}
    @app.post('/api/v2/admin/security-result',include_in_schema=False)
    async def publish(request:Request):
        if not hmac.compare_digest(request.headers.get('X-Api-Key','').encode(),key.encode()):
            return JSONResponse(status_code=401,content={'detail':'Private operator credential required'})
        try:
            payload=await request.json();current=payload['round']
            if current not in ('R0','R1') or current!=os.getenv('CHAOS_ROUND'):raise ValueError('Round mismatch')
            if not re.fullmatch('[a-f0-9]{32}',payload['execution_id']) or not re.fullmatch('[a-f0-9]{64}',payload['scope_sha256']):raise ValueError('Invalid provenance')
            values={}
            for name in FIELDS:
                value=payload[name]
                if value is None and name in OBSERVED:values[name]=math.nan;continue
                maximum=120 if name in OBSERVED else 100
                if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=maximum:raise ValueError('Invalid measurement')
                values[name]=value
        except (ValueError,TypeError,KeyError):
            return JSONResponse(status_code=400,content={'detail':'Invalid measured E1 result'})
        digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
        if current in recorded and recorded[current]!=digest:
            return JSONResponse(status_code=409,content={'detail':'This round already has different measurements; preserve the original evidence'})
        for name,value in values.items():GAUGES[name].labels(current).set(value)
        for name,gauge in OBSERVED.items():gauge.labels(current).set(int(not math.isnan(values[name])))
        recorded[current]=digest
        logger.info('Measured security round published',extra={'event':'security_round_result',
            'round':current,'execution_id':payload['execution_id'],'trace_id':getattr(request.state,'trace_id','none')})
        return {'published':True,'round':current,'execution_id':payload['execution_id']}
