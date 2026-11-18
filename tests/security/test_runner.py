"""In-memory contract fixtures, never cloud or personal-acceptance evidence."""
from datetime import datetime,timedelta,timezone
import json
import sys

import httpx
import pytest

from security.identity_tokens import create_keypair
from security import run_e1


@pytest.mark.parametrize('phase,fail_cleanup',[('R0',False),('R1',False),('R0',True)])
def test_bounded_runner_measures_and_preserves_failed_rollback(tmp_path,monkeypatch,phase,fail_cleanup):
    private,_=create_keypair(tmp_path)
    credentials=tmp_path/'credentials.json'
    credentials.write_text(json.dumps({'legacy_key':'unit-only','issuer_private_key':str(private),
        'metrics_token':'unit-metrics','results_key':'unit-operator','honey_token':'unit-decoy'}))
    rules={'api_origin':'https://unit.invalid','prometheus_origin':'https://unit.invalid/prometheus',
        'stop_file':'security/runtime/STOP','maximum_requests':100,'normal_requests':10,
        'adverse_requests':10,'observation_seconds':30,'application_revision':'a'*40,
        'instance_id':'i-0123456789abcdef0','scope_sha256':'b'*64,
        'window_end_utc':(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat()}
    # The acceptance gate has separate tests. This bypass exists only in this unit fixture.
    monkeypatch.setattr(run_e1,'validate_scope',lambda _:rules)
    monkeypatch.setattr(run_e1,'ROOT',tmp_path)
    monkeypatch.setattr(sys,'argv',['run_e1','--scope','unit-fixture','--credentials',str(credentials),'--round',phase])
    clock=[0.0]
    monkeypatch.setattr(run_e1.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(run_e1.time,'sleep',lambda seconds:clock.__setitem__(0,clock[0]+seconds))
    records={};adverse=[0];decoy=[False]
    headers={'X-App-Revision':'a'*40,'X-Deployment-Provider':'aws','X-Cloud-Instance-Id':rules['instance_id'],
        'X-Chaos-Round':phase,'X-Identity-Policy':'legacy' if phase=='R0' else 'workload'}

    def respond(request):
        response_headers={**headers,'X-Trace-Id':request.headers['X-Trace-Id']}
        path=request.url.path
        if path.startswith('/prometheus'):
            expression=request.url.params['query']
            active=expression.startswith('up') or (phase=='R1' and adverse[0] and ('honeytoken' not in expression or decoy[0]))
            return httpx.Response(200,json={'status':'success','data':{'result':[{'metric':{},'value':[0,'1']}] if active else []}})
        if path.endswith('/health') or path.endswith('/security-result'):
            return httpx.Response(200,json={'ok':True},headers=response_headers)
        if request.headers.get('Authorization')=='Bearer unit-decoy':
            decoy[0]=True
            return httpx.Response(401,json={'reason':'honeytoken'},headers=response_headers)
        if request.method=='POST':
            adverse[0]+=1
            if phase=='R1':return httpx.Response(403,json={'reason':'scope_violation'},headers=response_headers)
            identifier=adverse[0];records[identifier]={**json.loads(request.content),'id':identifier}
            return httpx.Response(201,json=records[identifier],headers=response_headers)
        if path.endswith('/skus'):return httpx.Response(200,json=[],headers=response_headers)
        identifier=int(path.rsplit('/',1)[1])
        if request.method=='DELETE':
            if fail_cleanup:raise httpx.ConnectError('Unit rollback failure')
            records.pop(identifier)
            return httpx.Response(204,headers=response_headers)
        return httpx.Response(200 if identifier in records else 404,json=records.get(identifier,{}),headers=response_headers)

    original_client=httpx.Client
    monkeypatch.setattr(run_e1.httpx,'Client',lambda **kwargs:original_client(transport=httpx.MockTransport(respond),**kwargs))
    if fail_cleanup:
        with pytest.raises(RuntimeError,match='Rollback incomplete'):run_e1.main()
    else:run_e1.main()
    folders=list((tmp_path/'security/results').iterdir());assert len(folders)==1
    raw=json.loads((folders[0]/'raw.json').read_text())
    assert len(raw['requests'])==20
    if fail_cleanup:
        assert not raw['rollback_verified'] and raw['cleanup_error_type']=='ConnectError'
        assert raw['synthetic_records'] and not (folders[0]/'report.json').exists()
    else:
        report=json.loads((folders[0]/'report.json').read_text())
        assert not records and report['rollback_verified'] and report['request_count']<=100
        assert 30<=report['observation_seconds']<32
        assert report['objective']['passed']==(phase=='R1')
        assert report['mttd_censored']==(phase=='R0')
        assert bool(report['honeytoken_evidence'])==(phase=='R1')
