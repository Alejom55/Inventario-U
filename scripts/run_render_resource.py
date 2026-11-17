"""Sequential cloud rounds on one verified Render Free deployment."""
import json
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

import httpx

from deploy.render.free import ROOT,RUNTIME,api,read,write,credentials


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,help='Previously attested public deployment; no Render account key required in CI')
    args=parser.parse_args()
    state=read('deployment.json'); values=credentials(); base=state['api_url']
    if args.manifest:
        manifest=json.loads(args.manifest.read_text(encoding='utf-8'))
        assert manifest['plan']=='free' and manifest['provider']=='render'
        assert manifest['api_url']==base and manifest['service_id']==state['api_service_id']
        revision=manifest['application_revision'];deployment={'id':manifest['deployment_id']}
    else:
        service=api('GET','/services/'+state['api_service_id'])
        assert service['serviceDetails']['plan']=='free'
        deployments=api('GET','/services/'+state['api_service_id']+'/deploys?limit=1')
        deployment=deployments[0].get('deploy',deployments[0])
        assert deployment['status']=='live'
        revision=deployment['commit']['id']
    execution=uuid4().hex
    folder=ROOT/'chaos/results'/('render-'+execution);folder.mkdir(parents=True)
    write('cloud-run.json',{'execution_id':execution,'folder':str(folder),'deployment_id':deployment['id']})
    business={'X-Api-Key':values['TEAM_API_KEY']};control={'X-Api-Key':values['RESOURCE_ADMIN_KEY']}
    with httpx.Client(timeout=20) as client:
        response=client.get(base+'/api/v2/skus',headers=business);response.raise_for_status()
        assert response.headers['X-Render-Service-Id']==state['api_service_id']
        assert response.headers['X-App-Revision']==revision
        instance=response.headers['X-Render-Instance-Id']
        if not response.json():
            response=client.post(base+'/api/v2/skus',headers=business,json={
                'codigo':'RENDER-SYNTHETIC','nombre':'Synthetic cloud chaos fixture','stock_minimo':0})
            response.raise_for_status()
        reports=[]
        for current in ('BASELINE','R0','R1'):
            response=client.post(base+'/api/v2/admin/resource-round',headers=control,
                json={'round':current,'execution_id':execution})
            response.raise_for_status()
            assert response.headers['X-Render-Instance-Id']==instance
            env=dict(os.environ,CHAOS_ROUND=current,CHAOS_EXECUTION_ID=execution,RESOURCE_RENDER_URL=base,
                RESOURCE_PRIVATE_KEY=values['TEAM_API_KEY'],RESOURCE_CONTROL_KEY=values['RESOURCE_ADMIN_KEY'],
                RESOURCE_EXPECTED_SERVICE_ID=state['api_service_id'],RESOURCE_EXPECTED_INSTANCE_ID=instance,
                RESOURCE_RESULT_FILE=str(folder/(current+'.json')),APP_REVISION=revision)
            print(current+': 120 s in Render Free; execution '+execution,flush=True)
            with (folder/(current+'-toolkit.log')).open('w',encoding='utf-8') as output:
                result=subprocess.run([sys.executable,'-m','chaostoolkit','--no-version-check','--no-log-file','run',
                    'chaos/experiments/resource-concurrency.json','--journal-path',str(folder/(current+'-journal.json'))],
                    cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT)
            journal=json.loads((folder/(current+'-journal.json')).read_text(encoding='utf-8'))
            assert result.returncode==0 and journal['run'] and all(a['status']=='succeeded' for a in journal['run'])
            report=json.loads((folder/(current+'.json')).read_text(encoding='utf-8'))
            assert report['samples']==300 and report['total_requests']==600 and report['rollback_verified']
            reports.append(report)
            print(json.dumps({k:report[k] for k in ('round','p95_ms','success_percent','passed','guardrail_p95_passed')}),flush=True)
    summary={'provider':'render','scope':'real cloud single API; full three-API E2E and GKE/Chaos Mesh are separate requirements',
        'execution_id':execution,'service_id':state['api_service_id'],'deployment_id':deployment['id'],
        'instance_id':instance,'application_revision':revision,'plan':'free',
        'generator':{'environment':'GitHub-hosted Ubuntu' if os.getenv('GITHUB_ACTIONS')=='true' else 'operator PC',
            'run_id':os.getenv('GITHUB_RUN_ID'),'repository':os.getenv('GITHUB_REPOSITORY')},
        'same_profile':all(r['profile']==reports[0]['profile'] for r in reports),
        'measurements':[{k:v for k,v in r.items() if k!='requests'} for r in reports]}
    baseline=reports[0]['p95_ms']
    for report in summary['measurements']:
        report['p95_variation_vs_baseline_percent']=round((report['p95_ms']/baseline-1)*100,2)
        report['success_variation_percentage_points']=report['success_percent']-reports[0]['success_percent']
    (folder/'comparison.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    target=ROOT/'docs/evidence/render-cloud-results.json';target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    write('cloud-last.json',{'execution_id':execution,'folder':str(folder),'summary':str(target)})
    print('Cloud evidence saved: '+str(target),flush=True)


if __name__=='__main__':main()
