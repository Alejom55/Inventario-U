"""Run real cloud rounds against one attested, temporary AWS instance."""
import json
import os
from datetime import datetime,timezone,timedelta
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import httpx

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'deploy/aws/runtime'


def main():
    state=json.loads((ROOT/'deploy/aws/target.json').read_text())
    values=json.loads((RUNTIME/'credentials.json').read_text())
    assert state['provider']=='aws' and state['free_account_verified'] is True
    assert datetime.fromisoformat(state['deadline_utc'])>datetime.now(timezone.utc)+timedelta(minutes=10),'Not enough authorized time to measure'
    base=state['api_url'];revision=state['application_revision'];instance=state['instance_id']
    execution=uuid4().hex
    folder=ROOT/'chaos/results'/('aws-'+execution);folder.mkdir(parents=True)
    business={'X-Api-Key':values['TEAM_API_KEY']};control={'X-Api-Key':values['RESOURCE_ADMIN_KEY']}
    reports=[]
    with httpx.Client(timeout=20) as client:
        response=client.get(base+'/api/v2/skus',headers=business);response.raise_for_status()
        assert response.headers['X-Deployment-Provider']=='aws'
        assert response.headers['X-Cloud-Instance-Id']==instance and response.headers['X-App-Revision']==revision
        if not response.json():
            client.post(base+'/api/v2/skus',headers=business,json={'codigo':'AWS-SYNTHETIC','nombre':'AWS synthetic cloud fixture','stock_minimo':0}).raise_for_status()
        for current in ('BASELINE','R0','R1'):
            response=client.post(base+'/api/v2/admin/resource-round',headers=control,json={'round':current,'execution_id':execution})
            response.raise_for_status();assert response.headers['X-Cloud-Instance-Id']==instance
            env=dict(os.environ,CHAOS_ROUND=current,CHAOS_EXECUTION_ID=execution,RESOURCE_AWS_URL=base,
                RESOURCE_PRIVATE_KEY=values['TEAM_API_KEY'],RESOURCE_CONTROL_KEY=values['RESOURCE_ADMIN_KEY'],
                RESOURCE_EXPECTED_SERVICE_ID=instance,RESOURCE_EXPECTED_INSTANCE_ID=instance,
                RESOURCE_RESULT_FILE=str(folder/(current+'.json')),APP_REVISION=revision)
            env.pop('RESOURCE_RENDER_URL',None)
            print(current+': 120 s on AWS; execution '+execution,flush=True)
            with (folder/(current+'-toolkit.log')).open('w',encoding='utf-8') as output:
                result=subprocess.run([sys.executable,'-m','chaostoolkit','--no-version-check','--no-log-file','run',
                    'chaos/experiments/resource-concurrency.json','--journal-path',str(folder/(current+'-journal.json'))],
                    cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT)
            journal=json.loads((folder/(current+'-journal.json')).read_text())
            assert result.returncode==0 and journal['run'] and all(a['status']=='succeeded' for a in journal['run'])
            report=json.loads((folder/(current+'.json')).read_text())
            assert report['samples']==300 and report['total_requests']==600 and report['rollback_verified']
            reports.append(report)
            print(json.dumps({k:report[k] for k in ('round','success_percent','p95_ms','objective_passed','guardrail_p95_passed')}),flush=True)
    summary={'provider':'aws','scope':'real cloud single API; not full three-API E2E or GKE/Chaos Mesh',
        'execution_id':execution,'instance_id':instance,'application_revision':revision,'api_url':base,
        'generator':{'environment':'GitHub-hosted Ubuntu' if os.getenv('GITHUB_ACTIONS')=='true' else 'operator PC',
            'run_id':os.getenv('GITHUB_RUN_ID'),'repository':os.getenv('GITHUB_REPOSITORY')},
        'same_profile':all(r['profile']==reports[0]['profile'] for r in reports),
        'measurements':[{k:v for k,v in r.items() if k!='requests'} for r in reports]}
    for row in summary['measurements']:
        row['p95_variation_vs_baseline_percent']=round((row['p95_ms']/reports[0]['p95_ms']-1)*100,2)
        row['success_variation_percentage_points']=row['success_percent']-reports[0]['success_percent']
    (folder/'comparison.json').write_text(json.dumps(summary,indent=2)+'\n')
    (ROOT/'docs/evidence/aws-cloud-results.json').write_text(json.dumps(summary,indent=2)+'\n')
    (RUNTIME/'cloud-last.json').write_text(json.dumps({'execution_id':execution,'folder':str(folder)},indent=2)+'\n')


if __name__=='__main__':main()
