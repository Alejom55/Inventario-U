"""Bounded credential-scope experiment. Requires the group's accepted private scope."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import time
from uuid import uuid4

import httpx

from .identity_tokens import issue
from .scope import validate_scope

ROOT=Path(__file__).resolve().parents[1]


def summarize(normal,adverse,mttd,mttc,observed_seconds):
    if not normal or not adverse:raise ValueError('Measured normal and adverse samples are required')
    # A first rejection alone does not establish sustained containment.
    if any(row['status'] not in (401,403) for row in adverse):mttc=None
    return {'objective':{'name':'mttd_seconds','maximum':30,'value':mttd,'passed':mttd is not None and mttd<=30},
        'mttd_seconds':mttd,'mttd_censored':mttd is None,
        'mttc_seconds':mttc,'mttc_censored':mttc is None,
        'observation_seconds':observed_seconds,'detection_coverage_percent':100 if mttd is not None else 0,
        'techniques_emulated':1,'techniques_detected':int(mttd is not None),
        'false_positive_percent':sum(row['status'] in (401,403) for row in normal)/len(normal)*100,
        'adverse_acceptance_percent':sum(200<=row['status']<300 for row in adverse)/len(adverse)*100,
        'containment_guardrail_passed':mttc is not None and mttc<=5 and all(row['status'] in (401,403) for row in adverse)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scope',type=Path,required=True)
    parser.add_argument('--credentials',type=Path,required=True)
    parser.add_argument('--round',choices=('R0','R1'),required=True)
    args=parser.parse_args()
    rules=validate_scope(args.scope)
    stop=ROOT/rules['stop_file']
    if stop.exists():raise InterruptedError('Stop switch is set; no network request was made')
    secrets=json.loads(args.credentials.read_text(encoding='utf-8'))
    base=rules['api_origin'].rstrip('/');prom=rules['prometheus_origin'].rstrip('/')
    execution=uuid4().hex;folder=ROOT/'security/results'/execution;folder.mkdir(parents=True)
    current=args.round
    if current=='R0':
        business={'X-Api-Key':secrets['legacy_key']};operator=business
    else:
        private=Path(secrets['issuer_private_key'])
        business={'Authorization':'Bearer '+issue(private,subject='coordinator-demo')}
        operator={'Authorization':'Bearer '+issue(private,subject='security-operator',scope='inventory:read inventory:write')}
    metrics={'Authorization':'Bearer '+secrets['metrics_token']}
    rows=[];created=[];requests=0;last_request=0.0;rollback=False
    started=datetime.now(timezone.utc).isoformat();mttd=None;mttc=None;adverse_start=None;alert_evidence=None;honey_evidence=None;observed_seconds=0
    end=datetime.fromisoformat(rules['window_end_utc'].replace('Z','+00:00'))
    expected_headers={'X-App-Revision':rules['application_revision'],
        'X-Deployment-Provider':'aws','X-Cloud-Instance-Id':rules['instance_id'],
        'X-Chaos-Round':current,'X-Identity-Policy':'legacy' if current=='R0' else 'workload'}
    with httpx.Client(timeout=3,follow_redirects=False) as client:
        def send(method,url,headers,body=None,rollback_request=False):
            nonlocal requests,last_request
            if requests>=rules['maximum_requests']:raise RuntimeError('Accepted request budget exhausted')
            if not rollback_request and stop.exists():raise InterruptedError('Stop switch observed')
            reserve=3 if rollback_request else 40
            if (end-datetime.now(timezone.utc)).total_seconds()<reserve:raise RuntimeError('Accepted window is ending')
            time.sleep(max(0,.5-(time.monotonic()-last_request)))
            last_request=time.monotonic();requests+=1
            trace=uuid4().hex;headers={**headers,'X-Trace-Id':trace}
            response=client.request(method,url,headers=headers,json=body)
            if response.status_code in (301,302,303,307,308):raise RuntimeError('Redirect outside the exact accepted endpoint is forbidden')
            if url.startswith(base+'/api/'):
                for key,expected in expected_headers.items():
                    if response.headers.get(key)!=expected:raise RuntimeError('Deployed identity or round mismatch: '+key)
            return response,trace

        def query(expression):
            from urllib.parse import urlencode
            response,_=send('GET',prom+'/api/v1/query?'+urlencode({'query':expression}),metrics)
            response.raise_for_status();payload=response.json()
            if payload.get('status')!='success':raise RuntimeError('Monitoring query failed')
            return payload['data']['result']

        try:
            response,_=send('GET',base+'/api/v2/health',{})
            response.raise_for_status()
            heartbeat=query('up{job="inventory"}')
            if not heartbeat or not all(row['value'][1]=='1' for row in heartbeat):raise RuntimeError('Measured telemetry baseline is not healthy')
            if query('ALERTS{alertname="InventoryMachineIdentityMisuse",alertstate="firing",round="'+current+'"}'):
                raise RuntimeError('A previous alert is still active; start the round with a fresh process')
            for index in range(rules['normal_requests']):
                response,trace=send('GET',base+'/api/v2/skus',business)
                rows.append({'kind':'normal','status':response.status_code,'trace_id':trace,'at_utc':datetime.now(timezone.utc).isoformat()})
                if response.status_code!=200 or response.headers.get('X-Trace-Id')!=trace:
                    raise RuntimeError('Normal flow baseline failed before injection')
            if query('ALERTS{alertname="InventoryMachineIdentityMisuse",alertstate="firing",round="'+current+'"}'):
                raise RuntimeError('Security alert fired on measured normal traffic')
            adverse_start=time.monotonic();injected_utc=datetime.now(timezone.utc).isoformat()
            for index in range(rules['adverse_requests']):
                code='CYBER-E1-'+execution[:12]+'-'+str(index)
                response,trace=send('POST',base+'/api/v2/skus',business,{'codigo':code,'nombre':'Synthetic E1 scope probe','stock_minimo':0})
                entry={'kind':'adverse','status':response.status_code,'trace_id':trace,'at_utc':datetime.now(timezone.utc).isoformat()}
                if response.headers.get('X-Trace-Id')!=trace:raise RuntimeError('Trace correlation failed')
                rows.append(entry)
                if response.status_code==201:
                    identifier=response.json()['id']
                    if type(identifier) is not int or identifier<=0:raise RuntimeError('Invalid synthetic SKU identity')
                    created.append((identifier,code))
                if response.status_code in (401,403) and mttc is None:mttc=time.monotonic()-adverse_start
                if response.status_code not in (201,401,403):raise RuntimeError('Unexpected response; abort rather than infer control efficacy')
            while time.monotonic()-adverse_start<rules['observation_seconds']:
                results=query('ALERTS{alertname="InventoryMachineIdentityMisuse",alertstate="firing",round="'+current+'",reason="scope_violation"}')
                if results and mttd is None:
                    mttd=time.monotonic()-adverse_start
                    alert_evidence={'observed_utc':datetime.now(timezone.utc).isoformat(),'prometheus_result':results}
                time.sleep(1)
            observed_seconds=time.monotonic()-adverse_start
            if current=='R1':
                honey=secrets.get('honey_token')
                if not honey:raise RuntimeError('Fresh private honeytoken required to verify the second improvement')
                honey_start=time.monotonic()
                response,trace=send('GET',base+'/api/v2/skus',{'Authorization':'Bearer '+honey})
                if response.status_code!=401 or response.json().get('reason')!='honeytoken':
                    raise RuntimeError('The decoy must never grant access')
                while time.monotonic()-honey_start<15:
                    found=query('ALERTS{alertname="InventoryMachineIdentityMisuse",alertstate="firing",round="R1",reason="honeytoken"}')
                    if found:
                        honey_evidence={'trace_id':trace,'observed_utc':datetime.now(timezone.utc).isoformat(),
                            'detection_upper_bound_seconds':time.monotonic()-honey_start,'prometheus_result':found}
                        break
                    time.sleep(1)
                if honey_evidence is None:raise RuntimeError('Honeytoken alert not observed')
        finally:
            # Cleanup is limited to records returned by this execution, even after STOP.
            cleanup_error=None
            try:
                for identity,expected_code in created:
                    response,_=send('GET',base+'/api/v2/skus/'+str(identity),operator,rollback_request=True)
                    if response.status_code!=200 or response.json().get('codigo')!=expected_code:
                        raise RuntimeError('Refusing to delete a SKU outside this execution')
                    response,_=send('DELETE',base+'/api/v2/skus/'+str(identity),operator,rollback_request=True)
                    if response.status_code!=204:raise RuntimeError('Synthetic fixture rollback failed')
                    response,_=send('GET',base+'/api/v2/skus/'+str(identity),operator,rollback_request=True)
                    if response.status_code!=404:raise RuntimeError('Synthetic fixture still exists after rollback')
                health,_=send('GET',base+'/api/v2/health',{},rollback_request=True)
                rollback=health.status_code==200
            except Exception as error:
                cleanup_error=error
            partial={'provider':'aws','experiment':'E1','round':current,'execution_id':execution,
                'started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),
                'scope_sha256':rules['scope_sha256'],'application_revision':rules['application_revision'],
                'instance_id':rules['instance_id'],'requests':rows,'rollback_verified':rollback,
                'cleanup_error_type':type(cleanup_error).__name__ if cleanup_error else None,
                'synthetic_records':[{'id':identity,'codigo':code} for identity,code in created]}
            (folder/'raw.json').write_text(json.dumps(partial,indent=2)+'\n')
            if cleanup_error is not None:raise RuntimeError('Rollback incomplete; inspect raw.json and perform scoped cleanup') from cleanup_error
        normal=[row for row in rows if row['kind']=='normal'];adverse=[row for row in rows if row['kind']=='adverse']
        if len(normal)!=10 or len(adverse)!=10 or not rollback:raise RuntimeError('Incomplete round; no final measurements published')
        report={k:v for k,v in partial.items() if k!='requests'}
        report.update(summarize(normal,adverse,mttd,mttc,observed_seconds),
            injected_utc=injected_utc,method={'normal_requests':10,'adverse_requests':10,'observation_seconds':30,'maximum_rps':2},
            timing_note='MTTD is the measured upper bound until the controller observes the native monitoring alert. Missing detection is censored, never zero.',
            attack='T1078',request_count=requests,alert_evidence=alert_evidence,honeytoken_evidence=honey_evidence)
        payload={name:report[name] for name in ('round','execution_id','scope_sha256','mttd_seconds','mttc_seconds',
            'detection_coverage_percent','false_positive_percent','adverse_acceptance_percent')}
        response,_=send('POST',base+'/api/v2/admin/security-result',{'X-Api-Key':secrets['results_key']},payload,rollback_request=True)
        response.raise_for_status()
        report['result_published']=True
        report['request_count']=requests
        report['raw_sha256']=__import__('hashlib').sha256((folder/'raw.json').read_bytes()).hexdigest()
        (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report))


if __name__=='__main__':main()
