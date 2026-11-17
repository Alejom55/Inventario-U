"""Public contract, teammate prompt and Grafana panel share one source."""
import json
import re
from urllib.parse import urlencode, urlsplit


def public_gateway(values):
    for name in ('TEAM_API_KEY','PEER_API_KEY','METRICS_TOKEN'):
        if not re.fullmatch(r'[a-f0-9]{48,64}',values[name]):
            raise ValueError('Invalid generated credential: '+name)
    metrics_query = urlencode({'match[]':'{job="inventory",__name__=~"inventory_.*|process_cpu_seconds_total|process_resident_memory_bytes|up"}'})
    return r'''map_hash_bucket_size 256;
map $http_x_api_key $peer_ok { default 0; "PEER_KEY" 1; }
map $http_authorization $metrics_ok { default 0; "Bearer METRICS_KEY" 1; }
server {
    listen 8080;
    server_tokens off;
    client_max_body_size 2m;
    proxy_connect_timeout 3s;
    proxy_read_timeout 15s;
    proxy_next_upstream off;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;
    proxy_set_header X-Trace-Id $http_x_trace_id;
    location = / { root /srv/team; try_files /index.html =404; }
    location = /shared/metrics {
        if ($request_method != GET) { return 405; }
        if ($metrics_ok = 0) { return 401; }
        proxy_pass http://prometheus:9090/federate?METRICS_QUERY;
    }
    location ~ ^/api/v2/(skus|almacenes|movimientos)(/[1-9][0-9]*)?$ {
        if ($peer_ok = 0) { return 401; }
        proxy_set_header X-Api-Key "INTERNAL_KEY";
        proxy_set_header X-Trace-Id $http_x_trace_id;
        proxy_pass http://stable:8000;
    }
    location ~ ^/api/v2/(health|inventario|inventario/query)$ {
        if ($peer_ok = 0) { return 401; }
        proxy_set_header X-Api-Key "INTERNAL_KEY";
        proxy_set_header X-Trace-Id $http_x_trace_id;
        proxy_pass http://stable:8000;
    }
    location ~ ^/shared/(guia\.md|contrato\.json|postman\.json|prometheus\.yml|dashboard\.json)$ {
        alias /srv/team/$1;
    }
    location ~ ^/grafana/api/admin(?:/|$) { return 404; }
    location ~ ^/grafana/(login|logout|api/ds/query)$ {
        proxy_pass http://grafana:3000;
    }
    location /grafana/ {
        if ($request_method !~ ^(GET|HEAD)$) { return 403; }
        proxy_pass http://grafana:3000;
    }
    location / { return 404; }
}
'''.replace('PEER_KEY',values['PEER_API_KEY']).replace('METRICS_KEY',values['METRICS_TOKEN']).replace('INTERNAL_KEY',values['TEAM_API_KEY']).replace('METRICS_QUERY',metrics_query)


def contract(base, ids):
    return {
        'service':'Inventario-U','scope':'Local synthetic practice, not three cloud deployments',
        'base_url':base,'api_auth':{'header':'X-Api-Key','environment_variable':'INVENTARIO_API_KEY'},
        'trace':{'header':'X-Trace-Id','format':'1..128 ASCII letters, digits, underscore or hyphen; generated when absent or invalid'},
        'inventory':{'method':'GET','path':'/api/v2/inventario','query':ids,'response':{'resultados':[{'sku_id':ids.get('sku_id'),'almacen_id':ids.get('almacen_id'),'stock_disponible':8}]}},
        'legacy_query':{'method':'QUERY','path':'/api/v2/inventario/query','body':ids},
        'crud':{name:base+'/api/v2/'+name for name in ('skus','almacenes','movimientos')},
        'metrics':{'url':base+'/shared/metrics','authentication':'Bearer token from INVENTARIO_METRICS_TOKEN; distinct from API key','instrument':'Prometheus federation, not JSON business API'},
        'grafana':{'url':base+'/grafana/d/inventory-team/','role':'Viewer','username':'companeros'},
        'limitations':['URL changes when the tunnel restarts','Available only while this PC, Docker and tunnel run','Peer API URLs are still required for the full coordinator flow'],
    }


def prometheus_config(base):
    host = urlsplit(base).netloc
    return f'''# Mount the private metrics token file; never commit its contents.
scrape_configs:
  - job_name: inventario-u-remoto
    scrape_interval: 5s
    scrape_timeout: 4s
    honor_labels: true
    scheme: {urlsplit(base).scheme}
    metrics_path: /shared/metrics
    authorization:
      type: Bearer
      credentials_file: /run/secrets/inventario_metrics_token
    static_configs:
      - targets: ['{host}']
'''


def guide(base, ids):
    query = urlencode(ids)
    return f'''# Inventario-U: integración del equipo

Entorno **local con datos sintéticos**. URL temporal: **{base}**.
La base es compartida: los cambios y eliminaciones afectan a la práctica del grupo.
Las credenciales se entregan por separado; no escribirlas en paneles ni repositorios.

## API de negocio y Postman

`GET {base}/api/v2/inventario?{query}`

Headers: `X-Api-Key: {{{{inventario_api_key}}}}` y `X-Trace-Id: practica-companero-001`.
La respuesta es `{{"resultados":[...]}}`, con `sku_id`, `almacen_id` y `stock_disponible`.
IDs iniciales: SKU **{ids.get('sku_id','pendiente')}**, almacén **{ids.get('almacen_id','pendiente')}**.
Los IDs se pueden eliminar mediante CRUD; si cambian, consultar SKU y almacenes existentes.

También funciona `QUERY /api/v2/inventario/query`, body JSON con los dos IDs.
CRUD en `/api/v2/skus`, `/api/v2/almacenes`, `/api/v2/movimientos`:
GET/POST sobre la colección; GET/PUT/DELETE sobre `/<id>`.
No hay acceso público al coordinador `/integracion`, Object Storage ni controles de fallos.
La consulta propietaria evita una dependencia circular entre las tres APIs.

Ejemplo SKU POST: `{{"codigo":"MI-PRUEBA-001","nombre":"Prueba del equipo","stock_minimo":10}}`.
Ejemplo almacén POST: `{{"nombre":"Prueba equipo","ubicacion":"Sintetica"}}`.
Ejemplo movimiento POST: `{{"sku_id":1,"almacen_id":1,"tipo":"entrada","cantidad":8,"motivo":"Prueba sintetica"}}`.
Sustituir los IDs del último ejemplo por los devueltos al crear las entidades.
Una clave inválida devuelve 401; validaciones pueden devolver 400/422 y una entidad inexistente 404.

[Colección Postman]({base}/shared/postman.json) · [Contrato JSON]({base}/shared/contrato.json)

## Sus Prometheus y Grafana

Las métricas están en `{base}/shared/metrics`; requieren un **token Bearer distinto**.
No conectar el JSON de inventario como datasource Prometheus.
Descargar [prometheus.yml]({base}/shared/prometheus.yml), montar el token en el archivo indicado
y añadir ese scrape a su Prometheus. Usar `honor_labels: true`.
Después conectar su Grafana a **su Prometheus**, e importar [el tablero]({base}/shared/dashboard.json).
Al importar, seleccionar su datasource Prometheus. Las etiquetas `track` distinguen stable y canary.
La federación solo entrega métricas de Inventario-U; no permite consultar ni administrar nuestro Prometheus.

## Cómo leer las gráficas

**Azul = stable; naranja = canary.** Peticiones/s mide tráfico; 4xx/5xx errores de la API;
p95 es la latencia bajo la cual termina el 95% de las solicitudes medidas.
CPU es fracción de un core y memoria fracción del límite de 512 MiB.
Cero peticiones sin tráfico es normal. Un único Send puede ser apenas visible: ejecutar 20–60
peticiones y esperar dos scrapes (10–15 s). Usar últimos 15 minutos y refresco de 5 s.
Las peticiones rechazadas por el proxy no llegan a los contadores de la aplicación.
Los paneles R0/R1 necesitan tráfico real al flujo completo y su etiqueta de ronda; no se inventan datos.
El canary solo recibe tráfico cuando el operador lo prueba o cambia el reparto local.

## Prompt para la IA de tu proyecto

```text
Integra nuestro proyecto con Inventario-U como API propietaria de inventario.
Base URL: {base}
Usa INVENTARIO_API_BASE_URL e INVENTARIO_API_KEY desde variables de entorno.
No guardes claves en Git, logs, dashboards ni código frontend.
Consulta GET /api/v2/inventario con sku_id y almacen_id positivos; procesa resultados[].
Propaga el mismo X-Trace-Id de la solicitud entrante; si falta, genera uno válido.
No llames /integracion desde nuestros endpoints propietarios: causaría una dependencia circular.
Usa timeout y errores controlados; no conviertas una respuesta incompleta en éxito.
Para métricas, usa la configuración de /shared/prometheus.yml y un token separado.
No uses el JSON de negocio como datasource de Grafana.
Implementa y prueba un cliente real; documenta URL, método, headers, IDs y respuesta.
No afirmes que esta práctica local demuestra despliegue en tres nubes o rondas R0/R1.
```

El acceso permanece hasta que el operador lo detenga. Reiniciar el túnel cambia la URL;
actualizar entonces las variables de ambos proyectos y sus targets Prometheus.
'''


def team_dashboard(base, ids):
    return {'uid':'inventory-team','title':'Inventario-U — Guía del equipo','schemaVersion':41,'version':1,'refresh':'5s',
            'time':{'from':'now-15m','to':'now'},'panels':[{'id':1,'type':'text','title':'API, métricas y prompt para sus IA',
            'gridPos':{'x':0,'y':0,'w':24,'h':42},'options':{'mode':'markdown','content':guide(base,ids)}}],
            'links':[{'title':'Canary: stable y canary','type':'link','url':'/grafana/d/inventory-canary/'},
                     {'title':'Caos R0/R1','type':'link','url':'/grafana/d/inventory-chaos/'}]}


def postman(base, ids):
    def item(name,method,path,body=None):
        request={'method':method,'header':[{'key':'X-Api-Key','value':'{{inventario_api_key}}'},{'key':'X-Trace-Id','value':'peer-{{$guid}}'}],
                 'url':{'raw':'{{base_url}}'+path,'host':['{{base_url}}'],'path':path.split('?',1)[0].strip('/').split('/')}}
        if '?' in path:
            from urllib.parse import parse_qsl
            request['url']['query']=[{'key':k,'value':v} for k,v in parse_qsl(path.split('?',1)[1])]
        if body is not None:
            request['header'].append({'key':'Content-Type','value':'application/json'})
            raw=json.dumps(body)
            for variable in ('test_sku_id','test_almacen_id'):
                raw=raw.replace('"{{'+variable+'}}"','{{'+variable+'}}')
            request['body']={'mode':'raw','raw':raw,'options':{'raw':{'language':'json'}}}
        return {'name':name,'request':request}
    collection={'info':{'name':'Inventario-U equipo local','schema':'https://schema.getpostman.com/json/collection/v2.1.0/collection.json'},
            'variable':[{'key':'base_url','value':base},{'key':'inventario_api_key','value':''}],
            'item':[item('Health','GET','/api/v2/health'),item('Inventario GET','GET','/api/v2/inventario?'+urlencode(ids)),
                    item('Inventario QUERY','QUERY','/api/v2/inventario/query',ids),item('Listar SKU','GET','/api/v2/skus'),
                    item('Crear SKU','POST','/api/v2/skus',{'codigo':'MI-PRUEBA-001','nombre':'Prueba equipo','stock_minimo':10}),
                    item('Listar almacenes','GET','/api/v2/almacenes'),item('Listar movimientos','GET','/api/v2/movimientos')]}
    definitions=[('skus','test_sku_id',{'codigo':'PEER-{{$guid}}','nombre':'Prueba equipo','stock_minimo':10}),
                 ('almacenes','test_almacen_id',{'nombre':'Prueba {{$guid}}','ubicacion':'Sintetica'}),
                 ('movimientos','test_movimiento_id',{'sku_id':'{{test_sku_id}}','almacen_id':'{{test_almacen_id}}','tipo':'entrada','cantidad':8,'motivo':'Prueba equipo'})]
    for resource,variable,body in definitions:
        collection['variable'].append({'key':variable,'value':''})
        create=item('Crear '+resource,'POST','/api/v2/'+resource,body)
        create['event']=[{'listen':'test','script':{'type':'text/javascript','exec':[f'if (pm.response.code === 201) pm.collectionVariables.set("{variable}", pm.response.json().id);']}}]
        collection['item'].append({'name':'CRUD '+resource+' — datos propios','item':[create,
            item('Consultar '+resource,'GET','/api/v2/'+resource+'/{{'+variable+'}}'),
            item('Actualizar '+resource,'PUT','/api/v2/'+resource+'/{{'+variable+'}}',body),
            item('Eliminar '+resource,'DELETE','/api/v2/'+resource+'/{{'+variable+'}}')]})
    return collection
