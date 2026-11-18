"""Operate the isolated E1 lab without stopping the shared business service."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

import httpx

from .deploy_aws_lab import ROOT,RUNTIME,AWS,HOST,INSTANCE,REVISION,remote,ssh_options
from security.prepare import refresh_honeytoken
from security.scope import validate_scope
from security.stop_e1 import stop


def check_live(base,token,phase=None):
    with httpx.Client(timeout=5) as client:
        health=client.get(base+'/api/v2/health');health.raise_for_status()
        assert health.headers.get('X-Cloud-Instance-Id')==INSTANCE
        assert health.headers.get('X-App-Revision')==REVISION
        if phase:
            assert health.headers.get('X-Chaos-Round')==phase
            assert health.headers.get('X-Identity-Policy')==('legacy' if phase=='R0' else 'workload')
        result=client.get(base+'/prometheus/api/v1/query',params={'query':'up{job="inventory"}'},
            headers={'Authorization':'Bearer '+token})
        result.raise_for_status()
        assert result.json()['data']['result'] and all(x['value'][1]=='1' for x in result.json()['data']['result'])
    return {'checked_at_utc':datetime.now(timezone.utc).isoformat(),'health':200,'telemetry_up':1,
        'round':health.headers.get('X-Chaos-Round'),'policy':health.headers.get('X-Identity-Policy')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('state','R0','R1','stop'))
    parser.add_argument('--scope',type=Path,default=RUNTIME/'rules-owner.json')
    args=parser.parse_args()
    if args.action=='stop':
        print(stop());return
    credentials=json.loads((RUNTIME/'credentials.json').read_text(encoding='utf-8'))
    base='https://e1.'+HOST+'.sslip.io'
    token=credentials.get('prometheus_token',credentials['metrics_token'])
    if args.action=='state':
        print(json.dumps(check_live(base,token)));return
    rules=validate_scope(args.scope)
    assert rules['api_origin']==base and rules['instance_id']==INSTANCE and rules['application_revision']==REVISION
    assert not (RUNTIME/'STOP').exists(),'STOP is active; review the reason before clearing it'
    phase=args.action;execution=uuid4().hex
    if phase=='R1':refresh_honeytoken(RUNTIME)
    env=RUNTIME/(phase+'.env')
    lines=env.read_text(encoding='utf-8').splitlines()
    lines=[x for x in lines if not x.startswith('CHAOS_EXECUTION_ID=')]
    env.write_text('\n'.join(lines)+'\nCHAOS_EXECUTION_ID='+execution+'\n',encoding='utf-8')
    upload='/home/ec2-user/e1-round.env'
    subprocess.run(['scp',*ssh_options(),str(env),'ec2-user@'+HOST+':'+upload],check=True)
    code="""
from pathlib import Path
import subprocess
root=Path('/opt/inventario-e1');phase='__PHASE__'
source=Path('/home/ec2-user/e1-round.env');text=source.read_text()
assert 'CHAOS_ROUND='+phase+'\\n' in text and 'CHAOS_EXECUTION_ID=__EXECUTION__\\n' in text
target=root/'security/runtime'/('active.env');target.write_text(text);target.chmod(0o600)
subprocess.run(['docker','compose','--env-file',str(target),'-f',str(root/'deploy/security/compose.aws.yml'),
    'up','-d','--no-deps','--force-recreate','e1-api'],check=True)
print('ISOLATED_E1_ROUND_READY')
""".replace('__PHASE__',phase).replace('__EXECUTION__',execution)
    print(remote(code).stdout.strip())
    for attempt in range(25):
        try:
            check_live(base,token,phase);break
        except (httpx.HTTPError,AssertionError):
            if attempt==24:raise
            time.sleep(1)
    folder=ROOT/'security/results'/execution
    try:
        subprocess.run([sys.executable,'-m','security.run_e1','--scope',str(args.scope),
            '--credentials',str(RUNTIME/'credentials.json'),'--round',phase,'--execution-id',execution],cwd=ROOT,check=True)
        # Wait for a native scrape before replacing this process in the next round.
        with httpx.Client(timeout=5) as client:
            for attempt in range(15):
                query=client.get(base+'/prometheus/api/v1/query',params={'query':'inventory_security_detection_coverage_percent{round="'+phase+'"}'},
                    headers={'Authorization':'Bearer '+token})
                query.raise_for_status()
                if query.json()['data']['result']:break
                if attempt==14:raise RuntimeError('Published round results have not been scraped')
                time.sleep(1)
    finally:
        if folder.exists():
            code="""import subprocess
command=['docker','compose','--env-file','/opt/inventario-e1/security/runtime/active.env','-f',
 '/opt/inventario-e1/deploy/security/compose.aws.yml','logs','--no-color','--no-log-prefix','e1-api']
print(subprocess.check_output(command,text=True))
"""
            logs=remote(code).stdout
            (folder/'api.log').write_text(logs,encoding='utf-8')
    report=json.loads((folder/'report.json').read_text())
    if phase=='R1' and not report['objective']['passed']:raise SystemExit('E1 R1 objective failed')
    print('E1_RESULTS='+str(folder))


if __name__=='__main__':main()
