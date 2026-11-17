"""Check public read-only Prometheus API from a real Grafana backend, then clean up."""
import json
import time
from uuid import uuid4

import httpx

from scripts.local_team import RUNTIME, read_json, settings, grafana, write_json


def verify():
    values=settings(); base=read_json(RUNTIME/'session.json')['public_url']
    prefix=base+'/shared/prometheus/api/v1'
    headers={'Authorization':'Bearer '+values['METRICS_TOKEN']}
    with httpx.Client(timeout=15) as client:
        assert client.get(prefix+'/query',params={'query':'1+1'}).status_code==401
        result=client.get(prefix+'/query',headers=headers,params={'query':'1+1'})
        result.raise_for_status();assert result.json()['data']['result'][1]=='2'
        result=client.post(prefix+'/query',headers=headers,data={'query':'up{job="inventory"}'})
        result.raise_for_status();assert result.json()['data']['result']
        result=client.post(prefix+'/query_range',headers=headers,data={
            'query':'up{job="inventory"}','start':str(time.time()-60),'end':str(time.time()),'step':'5'})
        result.raise_for_status();assert result.json()['data']['result']
        assert client.delete(prefix+'/query',headers=headers).status_code==405
        for suffix in ('admin/tsdb/delete_series','write','read','status/config'):
            assert client.post(prefix+'/'+suffix,headers=headers).status_code==404
        assert client.post(base+'/shared/prometheus/-/reload',headers=headers).status_code==404
        assert client.get(prefix+'/status/buildinfo',headers=headers).json()['status']=='success'
    identifier='inventory-query-proof-'+uuid4().hex[:12]
    try:
        response=grafana(values,'/api/datasources','POST',{
            'uid':identifier,'name':identifier,'type':'prometheus','access':'proxy','url':base+'/shared/prometheus',
            'jsonData':{'httpMethod':'POST','httpHeaderName1':'Authorization','prometheusType':'Prometheus',
                        'prometheusVersion':'3.5.0','timeInterval':'5s'},
            'secureJsonData':{'httpHeaderValue1':'Bearer '+values['METRICS_TOKEN']}})
        response.raise_for_status()
        health=grafana(values,'/api/datasources/uid/'+identifier+'/health')
        health.raise_for_status();assert health.json()['status']=='OK'
        query=grafana(values,'/api/ds/query','POST',{
            'from':'now-15m','to':'now','queries':[{'refId':'A','datasource':{'type':'prometheus','uid':identifier},
                'expr':'up{job="inventory"}','instant':True}]})
        query.raise_for_status()
        assert not query.json()['results']['A'].get('error')
        assert query.json()['results']['A']['frames']
    finally:
        response=grafana(values,'/api/datasources/uid/'+identifier,'DELETE')
        assert response.status_code in (200,404)
    proof={'public_query_url':base+'/shared/prometheus','query_and_range':'passed','authentication':'passed',
        'admin_write_lifecycle_blocked':'passed','real_grafana_backend_health_and_query':'passed',
        'common_grafana_cloud_stack':'NOT CONFIGURED OR VERIFIED: requires stack access',
        'temporary_datasource_removed':True}
    write_json(RUNTIME/'prometheus-query-verification.json',proof)
    print(json.dumps(proof))


if __name__=='__main__':verify()
