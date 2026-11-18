"""Operate the isolated E1 lab without stopping the shared business service."""
import argparse
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

import httpx

from .deploy_aws_lab import ROOT,RUNTIME,AWS,HOST,INSTANCE,REVISION,remote,ssh_options
from security.prepare import refresh_honeytoken
from security.scope import validate_scope,scope_digest
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


def authorize_owner(path,minutes,now=None):
    if type(minutes) is not int or not 5<=minutes<=120:raise ValueError('Owner experiment window must be 5 to 120 minutes')
    now=now or datetime.now(timezone.utc)
    rules=json.loads((ROOT/'security/rules-of-engagement.example.json').read_text(encoding='utf-8'))
    rules.update(authorization_mode='owner_isolated_lab',isolated_lab=True,evidence_class='owner_authorized_aws_lab',
        api_origin='https://e1.'+HOST+'.sslip.io',prometheus_origin='https://e1.'+HOST+'.sslip.io/prometheus',
        application_revision=REVISION,instance_id=INSTANCE,account_id='536202634723',
        window_start_utc=(now-timedelta(seconds=1)).isoformat(),window_end_utc=(now+timedelta(minutes=minutes)).isoformat(),
        controller_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        acceptance_note='Explicit owner CLI authorization for isolated E1 only; not group signatures or a VM shutdown schedule.')
    rules['owner_authorization']={'name':'Alejandro Marín','accepted':True,'source':'owner_cli',
        'accepted_at_utc':now.isoformat(),'accepted_scope_sha256':scope_digest(rules)}
    Path(path).write_text(json.dumps(rules,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return validate_scope(path,now)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('state','R0','R1','stop','authorize'))
    parser.add_argument('--scope',type=Path,default=RUNTIME/'rules-owner.json')
    parser.add_argument('--minutes',type=int,default=60,help='Explicit owner authorization window; does not schedule VM shutdown')
    args=parser.parse_args()
    if args.action=='stop':
        print(stop());return
    credentials=json.loads((RUNTIME/'credentials.json').read_text(encoding='utf-8'))
    base='https://e1.'+HOST+'.sslip.io'
    token=credentials.get('prometheus_token',credentials['metrics_token'])
    if args.action=='state':
        print(json.dumps(check_live(base,token)));return
    if args.action=='authorize':
        check_live(base,token)
        rules=authorize_owner(args.scope,args.minutes)
        print('Owner E1 window until '+rules['window_end_utc']+'. No VM shutdown scheduled. STOP is preserved.');return
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
            check_live(base,token,phase)
            with httpx.Client(timeout=5) as client:
                query=client.get(base+'/prometheus/api/v1/query',params={'query':'ALERTS{alertname="InventoryMachineIdentityMisuse",alertstate="firing",round="'+phase+'"}'},
                    headers={'Authorization':'Bearer '+token})
                query.raise_for_status()
                assert not query.json()['data']['result'],'Previous round alert has not cleared yet'
            break
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
