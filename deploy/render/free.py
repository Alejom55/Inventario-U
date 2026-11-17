"""Render API access restricted to this practice's explicitly Free resources."""
import json
from pathlib import Path
import secrets
import re

import httpx

ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT/'deploy/render/runtime'
OWNER='tea-da2msdpt0dsc73aoq87g'


def read(name,default=None):
    path=RUNTIME/name
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def write(name,value):
    RUNTIME.mkdir(parents=True,exist_ok=True)
    (RUNTIME/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def api(method,path,body=None):
    if not path.startswith('/') or '://' in path:
        raise ValueError('Only Render API paths are allowed')
    if method not in ('GET','POST','PATCH','PUT','DELETE'):
        raise ValueError('Unexpected API method')
    if method!='GET' and path not in ('/services','/postgres'):
        state=read('deployment.json',{})
        owned={state.get(k) for k in ('api_service_id','prometheus_service_id','database_id')}
        match=re.match(r'^/(?:services|postgres)/([^/?]+)(?:/|$)',path)
        if not match or match[1] not in owned:
            raise ValueError('Refusing to modify a resource outside this isolated practice')
        if body and body.get('serviceDetails',{}).get('plan','free')!='free':
            raise ValueError('Paid plan changes are forbidden')
    if method=='POST' and path in ('/services','/postgres'):
        details=body if path=='/postgres' else body.get('serviceDetails',{})
        if details.get('plan')!='free' or body.get('ownerId')!=OWNER:
            raise ValueError('Refusing a non-Free or different-workspace resource')
        if any(details.get(k) for k in ('disk','autoscaling','enableHighAvailability','enableDiskAutoscaling','readReplicas')):
            raise ValueError('Optional paid resources are forbidden')
    token=(RUNTIME/'api-token.txt').read_text(encoding='utf-8-sig').strip()
    if not token or any(ord(c)<33 or ord(c)>126 for c in token):
        raise ValueError('Expected one private API token without whitespace')
    with httpx.Client(base_url='https://api.render.com/v1',headers={'Authorization':'Bearer '+token},timeout=45) as client:
        result=client.request(method,path,json=body)
    if result.status_code>=400:
        # API responses can echo environment values: do not emit them in logs.
        raise RuntimeError(f'Render {method} {path} HTTP {result.status_code}; inspect the dashboard')
    return result.json() if result.content else None


def credentials():
    value=read('credentials.json')
    if value:return value
    value={k:secrets.token_hex(32) for k in ('TEAM_API_KEY','RESOURCE_ADMIN_KEY','METRICS_BEARER_TOKEN')}
    write('credentials.json',value)
    return value
