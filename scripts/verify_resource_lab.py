"""Verify real local results, public federation and Viewer dashboard queries."""
import json
from pathlib import Path

import httpx

from scripts.local_team import ROOT, RUNTIME, read_json, settings


def verify():
    values=settings(); session=read_json(RUNTIME/'session.json')
    last=read_json(RUNTIME/'resource-last.json'); folder=Path(last['folder'])
    comparison=read_json(folder/'comparison.json')
    reports=comparison['measurements']
    assert comparison['profile_identical'] and comparison['revision_identical']
    assert [r['round'] for r in reports]==['BASELINE','R0','R1']
    assert all(r['samples']==300 and r['total_requests']==600 and r['rollback_verified'] for r in reports)
    assert reports[1]['fault']['injection']=={'requested':6,'admitted':6,'rejected':0,'duration_seconds':60,'protected':False}
    assert reports[2]['fault']['injection']=={'requested':6,'admitted':4,'rejected':2,'duration_seconds':60,'protected':True}
    logs=(folder/'application.log').read_text(encoding='utf-8')
    for report in reports:
        assert report['trace_id'] in logs
        assert '"round": "'+report['round']+'"' in logs
        assert report['execution_id'] in logs
    base=session['public_url']
    with httpx.Client(timeout=20) as client:
        metrics=client.get(base+'/shared/metrics',headers={'Authorization':'Bearer '+values['METRICS_TOKEN']})
        metrics.raise_for_status()
        assert all('track="resource-'+r+'"' in metrics.text for r in ('baseline','r0','r1'))
        assert client.get(base+'/shared/metrics').status_code==401
        assert client.post(base+'/api/v2/admin/resource-fault',headers={'X-Api-Key':values['PEER_API_KEY']}).status_code==404
        report=client.get(base+'/shared/resource-results.md');report.raise_for_status()
        assert last['execution_id'] in report.text
        auth=('companeros',values['VIEWER_PASSWORD'])
        dashboard=client.get(base+'/grafana/api/dashboards/uid/inventory-resource',auth=auth)
        dashboard.raise_for_status()
        assert last['execution_id'] in json.dumps(dashboard.json())
        for panel in dashboard.json()['dashboard']['panels']:
            for target in panel.get('targets',[]):
                result=client.post(base+'/grafana/api/ds/query',auth=auth,json={
                    'from':'now-30m','to':'now','queries':[{'refId':'A','datasource':{'type':'prometheus','uid':'prometheus'},
                    'expr':target['expr'],'range':True,'intervalMs':5000,'maxDataPoints':1000}]})
                result.raise_for_status()
                assert not result.json()['results']['A'].get('error')
                assert result.json()['results']['A']['frames']
        skus=client.get(base+'/api/v2/skus',headers={'X-Api-Key':values['PEER_API_KEY'],'X-Trace-Id':'resource-public-still-up'})
        skus.raise_for_status()
        assert skus.headers['X-Trace-Id']=='resource-public-still-up'
    proof={'execution_id':last['execution_id'],'public_url':base,'comparison_and_logs':'passed',
        'public_metrics_and_auth':'passed','viewer_dashboard_and_promql':'passed','shared_api_unaffected':'passed'}
    (RUNTIME/'resource-verification.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(proof))


if __name__=='__main__':verify()
