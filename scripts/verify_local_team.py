"""Exercise the real public surface using disposable synthetic entities."""
import json
import time
from uuid import uuid4

import httpx

from scripts.local_team import OPERATOR, RUNTIME, api, grafana, read_json, settings


def verify():
    values=settings();session=read_json(RUNTIME/'session.json');base=session['public_url']
    report={'url':base,'revision':session['revision']}
    def request(path,method='GET',body=None):
        return api(values,path,method,body,public=True,base=base)
    suffix=uuid4().hex[:10]
    created=[]
    with httpx.Client(timeout=25) as client:
        assert client.get(base+'/api/v2/skus').status_code==401
        assert client.get(base+'/shared/metrics',headers={'Authorization':'Bearer '+values['PEER_API_KEY']}).status_code==401
        assert client.get(base+'/api/v2/skus',headers={'X-Api-Key':values['TEAM_API_KEY']}).status_code==401
        for path in ('/metrics','/api/v2/storage','/api/v2/integracion','/api/v3/admin/fault','/api/v2/skus/1/../../storage','/grafana/api/admin/users'):
            response=client.get(base+path,headers={'X-Api-Key':values['PEER_API_KEY']})
            assert response.status_code in (403,404), (path,response.status_code)
        assert client.post(base+'/shared/metrics',headers={'Authorization':'Bearer '+values['METRICS_TOKEN']}).status_code==405
        for origin,key in ((base,values['PEER_API_KEY']),(OPERATOR,values['TEAM_API_KEY'])):
            response=client.get(origin+'/api/v2/health',headers={'X-Api-Key':key,'X-Trace-Id':'peer-correlation-123'})
            assert response.status_code==200 and response.headers['X-Trace-Id']=='peer-correlation-123'
            assert response.headers['X-App-Revision']==session['revision']
        try:
            sku=request('/api/v2/skus','POST',{'codigo':'TEAM-VERIFY-'+suffix,'nombre':'Temporal prueba','stock_minimo':3})
            assert sku.status_code==201,sku.text
            sku=sku.json();created.append(('skus',sku['id']))
            assert request('/api/v2/skus/'+str(sku['id']),'PUT',{'codigo':sku['codigo'],'nombre':'Prueba editada','stock_minimo':3}).status_code==200
            warehouse=request('/api/v2/almacenes','POST',{'nombre':'Temporal '+suffix,'ubicacion':'Sintetica'})
            assert warehouse.status_code==201
            warehouse=warehouse.json();created.append(('almacenes',warehouse['id']))
            assert request('/api/v2/almacenes/'+str(warehouse['id']),'PUT',{'nombre':warehouse['nombre'],'ubicacion':'Editada'}).status_code==200
            ids={'sku_id':sku['id'],'almacen_id':warehouse['id']}
            movement=request('/api/v2/movimientos','POST',{**ids,'tipo':'entrada','cantidad':8,'motivo':'Prueba publica'})
            assert movement.status_code==201,movement.text
            movement=movement.json();created.append(('movimientos',movement['id']))
            assert request('/api/v2/movimientos/'+str(movement['id']),'PUT',{**ids,'tipo':'entrada','cantidad':9,'motivo':'Prueba editada'}).status_code==200
            query='?sku_id='+str(sku['id'])+'&almacen_id='+str(warehouse['id'])
            response=request('/api/v2/inventario'+query)
            assert response.status_code==200 and response.json()['resultados'][0]['stock_disponible']==9
            assert response.json()==request('/api/v2/inventario/query','QUERY',ids).json()
            assert request('/api/v2/inventario?sku_id=0&almacen_id=1').status_code==422
            report['public_crud_query_trace']='passed'
        finally:
            for resource,identifier in reversed(created):
                response=request('/api/v2/'+resource+'/'+str(identifier),'DELETE')
                assert response.status_code==204,(resource,response.status_code)
        response=client.get(base+'/api/v2/health',headers={'X-Api-Key':values['PEER_API_KEY'],'X-Trace-Id':'invalid.trace'})
        assert response.headers['X-Trace-Id']!='invalid.trace'
        for _ in range(12):
            response=client.get(base+'/shared/metrics',headers={'Authorization':'Bearer '+values['METRICS_TOKEN']})
            if response.status_code==200 and 'inventory_http_requests_total' in response.text:
                break
            time.sleep(2)
        else:
            raise AssertionError('Public Prometheus federation has no actual inventory samples')
        assert 'prometheus_build_info' not in response.text
        assert 'job="inventory"' in response.text
        report['protected_federation']='passed'
        for name in ('guia.md','contrato.json','postman.json','prometheus.yml','dashboard.json'):
            response=client.get(base+'/shared/'+name);assert response.status_code==200,(name,response.status_code)
            assert all(values[k] not in response.text for k in ('TEAM_API_KEY','PEER_API_KEY','METRICS_TOKEN','POSTGRES_PASSWORD','GRAFANA_PASSWORD','VIEWER_PASSWORD'))
        response=client.get(base+'/grafana/api/user',auth=('companeros',values['VIEWER_PASSWORD']))
        assert response.status_code==200 and not response.json()['isGrafanaAdmin']
        response=client.get(base+'/grafana/api/user/orgs',auth=('companeros',values['VIEWER_PASSWORD']))
        assert response.status_code==200 and any(org['role']=='Viewer' for org in response.json())
        assert client.post(base+'/grafana/api/dashboards/db',json={},auth=('companeros',values['VIEWER_PASSWORD'])).status_code==403
        for _ in range(15):
            response=client.get(base+'/grafana/api/dashboards/uid/inventory-team',auth=('companeros',values['VIEWER_PASSWORD']))
            if response.status_code==200 and base in response.json()['dashboard']['panels'][0]['options']['content']:
                break
            time.sleep(2)
        else:raise AssertionError('Provisioned guide does not match the current tunnel URL')
        report['viewer_guide_and_exports']='passed'
        query=client.post(base+'/grafana/api/ds/query',auth=('companeros',values['VIEWER_PASSWORD']),json={'from':'now-15m','to':'now','queries':[{'refId':'A','datasource':{'type':'prometheus','uid':'prometheus'},'expr':'sum(inventory_http_requests_total)','instant':True}]})
        assert query.status_code==200,query.text[:200]
        assert query.json()['results']['A']['frames']
        report['grafana_real_prometheus_query']='passed'
    write=RUNTIME/'verification.json'
    write.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':verify()
