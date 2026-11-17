"""Verify the new Free cloud deployment and export credential-free team artifacts."""
from datetime import datetime,timezone
import json
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

import httpx

from deploy.render.free import ROOT,RUNTIME,api,read,write,credentials,OWNER
from deploy.render.dashboard import build
from deploy.local_team.content import postman


def main():
    state=read('deployment.json');values=credentials();base=state['api_url'];prom=state['prometheus_url']
    summary=json.loads((ROOT/'docs/evidence/render-cloud-results.json').read_text(encoding='utf-8'))
    business={'X-Api-Key':values['TEAM_API_KEY'],'X-Trace-Id':'render-verification-'+uuid4().hex}
    bearer={'Authorization':'Bearer '+values['METRICS_BEARER_TOKEN']}
    with httpx.Client(timeout=20) as client:
        def call(path,method='GET',body=None):
            return client.request(method,base+path,headers=business,json=body)
        response=call('/api/v2/skus');response.raise_for_status()
        assert response.headers['X-Trace-Id']==business['X-Trace-Id']
        assert response.headers['X-App-Revision']==summary['application_revision']
        assert response.headers['X-Render-Service-Id']==state['api_service_id']
        synthetic=next(x for x in response.json() if x['codigo']=='RENDER-SYNTHETIC')
        temp=call('/api/v2/skus','POST',{'codigo':'VERIFY-'+uuid4().hex,'nombre':'Disposable verification SKU','stock_minimo':0})
        assert temp.status_code==201;identifier=temp.json()['id']
        try:
            assert call('/api/v2/skus/'+str(identifier)).status_code==200
            assert call('/api/v2/skus/'+str(identifier),'PUT',{'codigo':temp.json()['codigo'],'nombre':'Updated synthetic SKU','stock_minimo':1}).status_code==200
        finally:assert call('/api/v2/skus/'+str(identifier),'DELETE').status_code==204
        assert call('/api/v2/skus/'+str(identifier)).status_code==404
        warehouses=call('/api/v2/almacenes');warehouses.raise_for_status()
        fixtures=[w for w in warehouses.json() if w['nombre']=='Render synthetic practice']
        if not fixtures:
            place=call('/api/v2/almacenes','POST',{'nombre':'Render synthetic practice','ubicacion':'Cloud synthetic data only'})
            place.raise_for_status();fixtures=[place.json()]
            movement=call('/api/v2/movimientos','POST',{'sku_id':synthetic['id'],'almacen_id':fixtures[0]['id'],
                'tipo':'entrada','cantidad':8,'motivo':'Render cloud synthetic fixture'})
            movement.raise_for_status()
        assert len(fixtures)==1
        ids={'sku_id':synthetic['id'],'almacen_id':fixtures[0]['id']}
        query=call('/api/v2/inventario?'+urlencode(ids));legacy=call('/api/v2/inventario/query','QUERY',ids)
        assert query.status_code==200 and legacy.status_code==200 and query.json()==legacy.json()
        assert client.get(base+'/api/v2/skus').status_code==401
        assert call('/api/v2/admin/resource-round','POST',{'round':'BASELINE','execution_id':'a'*32}).status_code==401
        assert call('/api/v2/storage').status_code==404 and call('/api/v2/integracion').status_code==404
        assert client.get(base+'/metrics').status_code==401
        response=client.get(base+'/metrics',headers=bearer);response.raise_for_status()
        assert 'inventory_resource_client_success_ratio' in response.text
        assert client.get(prom+'/api/v1/query',params={'query':'1+1'}).status_code==401
        assert client.get(prom+'/api/v1/query',headers=bearer,params={'query':'1+1'}).json()['data']['result'][1]=='2'
        for path in ('/api/v1/write','/api/v1/admin/tsdb/delete_series','/-/reload'):
            assert client.post(prom+path,headers=bearer).status_code==404
        dashboard,guide=build(summary,base,prom)
        for panel in dashboard['panels']:
            for target in panel.get('targets',[]):
                response=client.post(prom+'/api/v1/query_range',headers=bearer,data={
                    'query':target['expr'],'start':str(datetime.now(timezone.utc).timestamp()-1200),
                    'end':str(datetime.now(timezone.utc).timestamp()),'step':'5'})
                response.raise_for_status();assert response.json()['status']=='success'
                assert response.json()['data']['result'],panel['title']
    trace_proof=[]
    for report in summary['measurements']:
        logs=api('GET','/logs?'+urlencode({'ownerId':OWNER,'resource':state['api_service_id'],'text':report['trace_id'],'limit':20}))
        matched=[]
        for row in logs.get('logs',[]):
            try:message=json.loads(row['message'])
            except (ValueError,KeyError):continue
            if message.get('trace_id')==report['trace_id'] and message.get('round')==report['round'] and message.get('execution_id')==summary['execution_id']:
                matched.append(message)
        assert matched,'Missing real correlated cloud logs for '+report['round']
        trace_proof.extend(matched[:2])
    plans={}
    for kind in ('api','prometheus'):
        service=api('GET','/services/'+state[kind+'_service_id']);assert service['serviceDetails']['plan']=='free'
        plans[kind]='free'
    db=api('GET','/postgres/'+state['database_id']);assert db['plan']=='free'
    plans['postgres']='free'
    proof={'verified_utc':datetime.now(timezone.utc).isoformat(),'provider':'render','plans':plans,
        'application_revision':summary['application_revision'],'execution_id':summary['execution_id'],
        'public_crud_get_query_trace_auth':'passed','private_controls_and_metrics':'passed',
        'storage_coordinator_and_prometheus_write_blocked':'passed','dashboard_promql':'passed',
        'actual_application_log_examples':trace_proof,'synthetic_ids':ids,
        'common_grafana_cloud_stack':'not configured; owner must import datasource/dashboard'}
    docs=ROOT/'docs'
    (docs/'render-free-guide.md').write_text(guide+'\n',encoding='utf-8')
    (docs/'render-free-dashboard.json').write_text(json.dumps(dashboard,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    collection=postman(base,ids);collection['info']['name']='Inventario-U — Render Free'
    (docs/'render-free-postman.json').write_text(json.dumps(collection,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (docs/'evidence/render-verification.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (RUNTIME/'credenciales-companeros.txt').write_text('SOLO POR PRIVADO\nAPI: '+base+'\nX-Api-Key: '+values['TEAM_API_KEY']+'\nPrometheus datasource: '+prom+'\nAuthorization: Bearer '+values['METRICS_BEARER_TOKEN']+'\nIDs: '+json.dumps(ids)+'\nNo contiene la clave administrativa ni la clave de Render.\n',encoding='utf-8')
    write('postman-private-environment.json',{'name':'Inventario-U Render privado','_postman_variable_scope':'environment',
        'values':[{'key':'base_url','value':base,'enabled':True,'type':'default'},
                  {'key':'inventario_api_key','value':values['TEAM_API_KEY'],'enabled':True,'type':'secret'}]})
    for name in ('render-free-guide.md','render-free-dashboard.json','render-free-postman.json','evidence/render-verification.json'):
        content=(docs/name).read_text(encoding='utf-8')
        assert not any(value in content for value in values.values())
    write('verification.json',proof)
    print(json.dumps({k:v for k,v in proof.items() if k!='actual_application_log_examples'}))


if __name__=='__main__':main()
