"""Delete only this disposable practice Droplet; power-off does not stop billing."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener


def timestamp(value):
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None:
        raise ValueError('Explicit timezone required')
    return result


def validate(state):
    if type(state.get('droplet_id')) is not int or state['droplet_id']<=0:
        raise ValueError('One explicit Droplet ID is required')
    if not re.fullmatch(r'inventario-chaos-[a-f0-9]{12}',state.get('name','')):
        raise ValueError('Unexpected practice name')
    if state.get('ownership_tag')!=state['name']:
        raise ValueError('Ownership tag must match the dedicated practice name')
    created=timestamp(state['created_at'])
    deadline=timestamp(state['delete_at'])
    hours=(deadline-created).total_seconds()/3600
    rate=state['price_hourly_usd']
    # Keep substantial headroom for taxes and API retry time; no optional resources.
    if not math.isfinite(rate) or not 0<rate<=.1 or not 0<hours<=2 or rate*2*1.3+.05>1:
        raise ValueError('Outside USD 1 / two-hour authorization')
    return deadline


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise RuntimeError('Refusing to forward the API credential to another endpoint')


def request(token,method,identifier):
    if type(identifier) is not int or identifier<=0:
        raise ValueError('Invalid Droplet ID')
    operation=Request('https://api.digitalocean.com/v2/droplets/'+str(identifier),
        method=method,headers={'Authorization':'Bearer '+token,'Accept':'application/json'})
    try:
        with build_opener(NoRedirect()).open(operation,timeout=15) as response:
            body=response.read()
            return json.loads(body) if body else None
    except HTTPError as error:
        if error.code==404:return {'not_found':True}
        raise RuntimeError('DigitalOcean API HTTP '+str(error.code)) from None


def step(state,token,now=None,api=request):
    deadline=validate(state)
    now=now or datetime.now(timezone.utc)
    if now<deadline:
        return 'waiting'
    result=api(token,'GET',state['droplet_id'])
    if result.get('not_found'):return 'destroyed'
    droplet=result['droplet']
    if (droplet['id']!=state['droplet_id'] or droplet['name']!=state['name']
            or state['ownership_tag'] not in droplet.get('tags',[])
            or timestamp(droplet['created_at'])!=timestamp(state['created_at'])):
        raise RuntimeError('Ownership mismatch: refusing to delete another resource')
    api(token,'DELETE',state['droplet_id'])
    return 'delete_requested'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',required=True,type=Path)
    parser.add_argument('--token-file',required=True,type=Path)
    parser.add_argument('--once',action='store_true')
    args=parser.parse_args()
    state=json.loads(args.state.read_text(encoding='utf-8'))
    validate(state)
    token=args.token_file.read_text(encoding='utf-8').strip()
    if not token:raise ValueError('Missing private API token')
    while True:
        try:
            status=step(state,token)
        except (OSError,RuntimeError) as error:
            status='retry_required'
            print(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),'status':status,
                'error_type':type(error).__name__}),flush=True)
        else:
            print(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),'status':status}),flush=True)
        if args.once or status=='destroyed':return
        time.sleep(15)


if __name__=='__main__':main()
