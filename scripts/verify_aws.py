"""Verify the real AWS HTTPS surface and export team artifacts without secrets."""
from datetime import datetime,timezone
import json
from urllib.parse import urlencode
from uuid import uuid4

import httpx

from deploy.local_team.content import postman
from scripts.run_aws_resource import ROOT,RUNTIME


def main():
    state=json.loads((ROOT/'deploy/aws/target.json').read_text())
    values=json.loads((RUNTIME/'credentials.json').read_text())
    summary=json.loads((ROOT/'docs/evidence/aws-cloud-results.json').read_text())
    assert summary['instance_id']==state['instance_id'] and summary['application_revision']==state['application_revision']
    base=state['api_url'];prom=state['prometheus_url']
    trace='aws-verification-'+uuid4().hex
    business={'X-Api-Key':values['TEAM_API_KEY'],'X-Trace-Id':trace}
    bearer={'Authorization':'Bearer '+values['METRICS_BEARER_TOKEN']}
    with httpx.Client(timeout=20) as client:
        def call(path,method='GET',body=None):return client.request(method,base+path,headers=business,json=body)
        response=call('/api/v2/skus');response.raise_for_status()
        assert response.headers['X-Deployment-Provider']=='aws' and response.headers['X-Cloud-Instance-Id']==state['instance_id']
        assert response.headers['X-Trace-Id']==trace
        synthetic=next(x for x in response.json() if x['codigo']=='AWS-SYNTHETIC')
        code='VERIFY-'+uuid4().hex
        temp=call('/api/v2/skus','POST',{'codigo':code,'nombre':'Disposable AWS check','stock_minimo':0})
        assert temp.status_code==201;identifier=temp.json()['id']
        try:
            assert call('/api/v2/skus/'+str(identifier)).status_code==200
            assert call('/api/v2/skus/'+str(identifier),'PUT',{'codigo':code,'nombre':'Updated AWS check','stock_minimo':1}).status_code==200
        finally:assert call('/api/v2/skus/'+str(identifier),'DELETE').status_code==204
        assert call('/api/v2/skus/'+str(identifier)).status_code==404
        warehouses=call('/api/v2/almacenes').json()
        fixture=next((w for w in warehouses if w['nombre']=='AWS synthetic practice'),None)
        if fixture is None:
            response=call('/api/v2/almacenes','POST',{'nombre':'AWS synthetic practice','ubicacion':'Synthetic data only'})
            response.raise_for_status();fixture=response.json()
            call('/api/v2/movimientos','POST',{'sku_id':synthetic['id'],'almacen_id':fixture['id'],
                'tipo':'entrada','cantidad':8,'motivo':'AWS synthetic fixture'}).raise_for_status()
        ids={'sku_id':synthetic['id'],'almacen_id':fixture['id']}
        response=call('/api/v2/inventario?'+urlencode(ids));legacy=call('/api/v2/inventario/query','QUERY',ids)
        assert response.status_code==200 and legacy.status_code==200 and response.json()==legacy.json()
        assert client.get(base+'/api/v2/skus').status_code==401
        assert call('/api/v2/admin/resource-round','POST',{'round':'BASELINE','execution_id':'a'*32}).status_code==401
        for path in ('/api/v2/storage','/api/v2/integracion','/metrics'):
            assert call(path).status_code==404
        assert client.get(prom+'/api/v1/query',params={'query':'1+1'}).status_code==401
        result=client.get(prom+'/api/v1/query',headers=bearer,params={'query':'up{job="inventory",cloud="aws"}'})
        result.raise_for_status();assert result.json()['data']['result'][0]['value'][1]=='1'
        for path in ('/api/v1/write','/api/v1/admin/tsdb/delete_series','/-/reload'):
            assert client.post(prom+path,headers=bearer).status_code==401
        queries=[('Objetivo único: éxito del cliente ≥99%','inventory_resource_client_success_ratio{cloud="aws"}','percentunit'),
            ('Guardarraíl: p95 del cliente <500 ms','1000 * inventory_resource_client_p95_seconds{cloud="aws"}','ms'),
            ('Tráfico HTTP','sum(rate(inventory_http_requests_total{cloud="aws",route="/api/v2/skus"}[1m]))','reqps'),
            ('Tareas de fondo activas','inventory_resource_background_active{cloud="aws"}','short'),
            ('CPU respecto al límite de 0,5 CPU','rate(process_cpu_seconds_total{cloud="aws"}[1m]) / 0.5','percentunit'),
            ('Memoria respecto al límite de 512 MiB','process_resident_memory_bytes{cloud="aws"} / 536870912','percentunit')]
        for title,expression,_ in queries:
            result=client.post(prom+'/api/v1/query_range',headers=bearer,data={'query':expression,
                'start':str(datetime.now(timezone.utc).timestamp()-1800),'end':str(datetime.now(timezone.utc).timestamp()),'step':'5'})
            result.raise_for_status();assert result.json()['data']['result'],title
    guide=f'''# Inventario-U: AWS con plan gratuito

API: {base}
Prometheus para Grafana Cloud: {prom}
Instancia: {state['instance_id']}; aplicación: {state['application_revision']}.
El plan FREE se verificó antes de crear recursos. No se habilitó un plan de pago.
Solo créditos gratuitos; el cálculo reservado de la práctica es USD 0,31.
Terminación automática: {state['deadline_utc']}. Se elimina el disco sintético.
La URL depende de esta IP y no se conserva para otro lanzamiento.

## Postman

GET {base}/api/v2/skus
Headers: X-Api-Key: {{{{inventario_api_key}}}} y X-Trace-Id: equipo-{{{{$guid}}}}.
Esperado: 200 con lista de SKU. Es un endpoint terminal, sin llamadas a los compañeros.
GET {base}/api/v2/inventario?sku_id={ids['sku_id']}&almacen_id={ids['almacen_id']}
Devuelve resultados[]. El método QUERY /api/v2/inventario/query sigue disponible.
Conserva CRUD de SKU, almacenes y movimientos. Usar exclusivamente datos sintéticos.

## Grafana Cloud

Crear datasource Prometheus con la URL anterior, método POST y header seguro
Authorization: Bearer <token privado de métricas>. Importar docs/aws-dashboard.json.
Las claves se entregan por privado; no ponerlas en paneles ni en el grupo.
Cero tráfico sin peticiones es normal. Una petición aislada apenas cambia una tasa.
Los indicadores del cliente se publican al terminar la ronda, contando timeouts.
Estos gráficos comparan BASELINE/R0/R1 de una API; no son dos versiones Canary.

## Resultados reales

Perfil: 5 peticiones/s, 120 s; agotamiento de concurrencia desde t=30 durante 60 s.
Único objetivo: éxito del cliente >=99%. Guardarraíl separado: p95 <500 ms.
R0 ocupa los seis trabajadores compartidos. R1 usa bulkhead y admite cuatro tareas
de fondo, rechazando dos sin cola. Reversión verificada en las tres rondas.
Generador: {summary['generator']['environment']}. Comparar únicamente rondas del mismo origen.
Execution ID: {summary['execution_id']}.

| Ronda | Éxito % | p95 ms | Variación p95 % |
|---|---:|---:|---:|
'''
    for row in summary['measurements']:
        guide+=f"| {row['round']} | {row['success_percent']:.3f} | {row['p95_ms']:.3f} | {row['p95_variation_vs_baseline_percent']:.2f} |\n"
    guide+='\nActions > Validacion local de caos > Run workflow > feat/aws-chaos > Run workflow. Coordinar R0 con el grupo antes de ejecutarla. Solo funciona durante la ventana autorizada.\n'
    guide+='\nPara las IA: consumir /api/v2/skus y las otras rutas propietarias; nunca llamar a /integracion desde una dependencia. Enviar X-Api-Key desde secretos, propagar X-Trace-Id, establecer timeouts y tratar respuestas no 2xx como errores.\n'
    guide+='\nEsta evidencia corresponde a una API en AWS. No acredita la integración de las tres APIs ni Chaos Mesh/GKE. El Grafana Cloud común requiere que su responsable agregue la fuente y el tablero.\n'
    if summary.get('github_run_url'):guide+='\nEjecución: '+summary['github_run_url']+'\n'
    panels=[{'id':1,'type':'text','title':'Guía del equipo y evidencia AWS','gridPos':{'x':0,'y':0,'w':24,'h':24},'options':{'mode':'markdown','content':guide}}]
    for index,(title,expression,unit) in enumerate(queries):
        panels.append({'id':index+2,'type':'timeseries','title':title,'gridPos':{'x':index%2*12,'y':24+index//2*8,'w':12,'h':8},
            'datasource':{'type':'prometheus','uid':'${DS_PROMETHEUS}'},
            'targets':[{'refId':'A','expr':expression,'legendFormat':'{{round}}'}],
            'fieldConfig':{'defaults':{'unit':unit,'min':0},'overrides':[]}})
    dashboard={'title':'Inventario-U — Guía y fallo c en AWS','schemaVersion':41,'version':1,'refresh':'5s',
        'time':{'from':'now-3h','to':'now'},'panels':panels,'__inputs':[{'name':'DS_PROMETHEUS','label':'Prometheus AWS Inventario-U','type':'datasource','pluginId':'prometheus','pluginName':'Prometheus'}]}
    docs=ROOT/'docs'
    (docs/'aws-guide.md').write_text(guide.rstrip()+'\n',encoding='utf-8')
    (docs/'aws-dashboard.json').write_text(json.dumps(dashboard,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    collection=postman(base,ids);collection['info']['name']='Inventario-U — AWS Free'
    (docs/'aws-postman.json').write_text(json.dumps(collection,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    proof={'verified_utc':datetime.now(timezone.utc).isoformat(),'provider':'aws','instance_id':state['instance_id'],
        'revision':state['application_revision'],'execution_id':summary['execution_id'],'synthetic_ids':ids,
        'crud_get_query_trace_auth':'passed','metrics_and_readonly_queries':'passed','dashboard_promql':'passed',
        'public_storage_coordinator_and_raw_metrics':'blocked','common_grafana_cloud':'not configured; owner must import'}
    (docs/'evidence/aws-verification.json').write_text(json.dumps(proof,indent=2)+'\n')
    (RUNTIME/'credenciales-companeros.txt').write_text('SOLO POR PRIVADO\nAPI: '+base+'\nX-Api-Key: '+values['TEAM_API_KEY']+'\nPrometheus: '+prom+'\nAuthorization: Bearer '+values['METRICS_BEARER_TOKEN']+'\n',encoding='utf-8')
    (RUNTIME/'postman-private-environment.json').write_text(json.dumps({'name':'Inventario-U AWS privado','_postman_variable_scope':'environment','values':[
        {'key':'base_url','value':base,'enabled':True,'type':'default'},{'key':'inventario_api_key','value':values['TEAM_API_KEY'],'enabled':True,'type':'secret'}]},indent=2)+'\n')
    for name in ('aws-guide.md','aws-dashboard.json','aws-postman.json','evidence/aws-verification.json'):
        content=(docs/name).read_text(encoding='utf-8')
        assert not any(values[key] in content for key in ('TEAM_API_KEY','RESOURCE_ADMIN_KEY','METRICS_BEARER_TOKEN','POSTGRES_PASSWORD'))
    print(json.dumps(proof))


if __name__=='__main__':main()
