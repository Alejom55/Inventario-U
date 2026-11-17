"""Importable Grafana dashboard for the actual Render Free experiment."""


def build(summary,api_url,prometheus_url):
    text=f'''# Inventario-U: ejecución real en Render Free

API: {api_url}
GET /api/v2/skus es terminal: consulta PostgreSQL, sin invocar a los compañeros.
Autenticación de negocio: X-Api-Key. Propagar X-Trace-Id.
Datasource Prometheus: {prometheus_url}; header Authorization: Bearer <token privado>.
No colocar claves en paneles, repositorios ni mensajes del grupo.

**Única métrica objetivo: éxito del cliente ≥99% durante el fallo.**
Guardarraíl separado: p95 del cliente <500 ms, incluyendo errores y timeouts.
Perfil: 5 peticiones/s, 120 s; fallo desde t=30 durante 60 s; timeout 2 s.
Estado estable, R0 y R1 usan la misma versión e instancia de la API y los mismos datos.
R0 comparte los seis permisos HTTP con seis tareas de fondo. R1 usa bulkhead y
admisión máxima de cuatro tareas de fondo, rechazando dos sin cola.
El interruptor requiere una clave administrativa distinta y tiene expiración de 60 s.

Las mediciones son de una API real en Render; no acreditan por sí solas el flujo
integrado de tres APIs ni Chaos Mesh/GKE. El grupo debe aceptar Render en lugar de OCI.
Aquí R0/R1 son rondas de caos; no son las versiones stable/canary del ejercicio anterior.

| Ronda | Éxito % | p95 ms | Variación p95 % | Objetivo | Guardarraíl |
|---|---:|---:|---:|---|---|
'''
    for r in summary['measurements']:
        text+=f"| {r['round']} | {r['success_percent']:.3f} | {r['p95_ms']:.3f} | {r['p95_variation_vs_baseline_percent']:.2f} | {'cumple' if r['objective_passed'] else 'refutada'} | {'cumple' if r['guardrail_p95_passed'] else 'no cumple'} |\n"
    text+=f"\nExecution ID: `{summary['execution_id']}`\n\nRevisión: `{summary['application_revision']}`\n\nDeployment: `{summary['deployment_id']}`\n\n"
    for r in summary['measurements']:
        fault=r['fault']
        text+=f"**{r['round']}**: {r['started_utc']} a {r['ended_utc']}; trace_id `{r['trace_id']}`. "
        text+=f"Inyección: {fault.get('injection_ack_utc','sin fallo')}; reversión: {fault.get('release_verified_utc','verificada al finalizar')}.\n\n"
    text+='Prometheus tiene almacenamiento temporal. Descargar el informe; un reinicio puede perder las series. Cero tráfico sin peticiones es normal. Los indicadores de éxito/p95 del cliente se publican al terminar cada ronda, a partir de las muestras reales del generador.'
    panels=[{'id':1,'type':'text','title':'Guía, resultados reales y trazabilidad',
        'gridPos':{'x':0,'y':0,'w':24,'h':22},'options':{'mode':'markdown','content':text}}]
    queries=[('Objetivo único: éxito del cliente por ronda ≥99%','inventory_resource_client_success_ratio{cloud="render"}','percentunit','stat'),
        ('Guardarraíl: p95 del cliente <500 ms','1000 * inventory_resource_client_p95_seconds{cloud="render"}','ms','stat'),
        ('Tráfico HTTP al endpoint y rechazos de admisión','sum(rate(inventory_http_requests_total{cloud="render",method="GET",route=~"/api/v2/skus|unmatched"}[1m]))','reqps','timeseries'),
        ('Tareas de fondo activas','inventory_resource_background_active{cloud="render"}','short','timeseries'),
        ('CPU del proceso respecto a 0,1 CPU asignada','rate(process_cpu_seconds_total{cloud="render"}[1m]) / 0.1','percentunit','timeseries'),
        ('Memoria del proceso respecto a 512 MiB','process_resident_memory_bytes{cloud="render"} / 536870912','percentunit','timeseries')]
    for index,(title,expression,unit,kind) in enumerate(queries):
        defaults={'unit':unit,'min':0}
        if unit=='percentunit':defaults['max']=1
        if index==0:defaults['thresholds']={'mode':'absolute','steps':[{'color':'red','value':None},{'color':'green','value':.99}]}
        if index==1:defaults['thresholds']={'mode':'absolute','steps':[{'color':'green','value':None},{'color':'red','value':500}]}
        panels.append({'id':index+2,'type':kind,'title':title,
            'gridPos':{'x':index%2*12,'y':22+index//2*8,'w':12,'h':8},
            'datasource':{'type':'prometheus','uid':'${DS_PROMETHEUS}'},
            'targets':[{'refId':'A','expr':expression,'legendFormat':'{{round}}','instant':kind=='stat'}],
            'fieldConfig':{'defaults':defaults,'overrides':[]},
            'options':{'reduceOptions':{'calcs':['lastNotNull'],'fields':'','values':False}} if kind=='stat' else {}})
    return {'uid':None,'title':'Inventario-U — Fallo c en Render Free','schemaVersion':41,'version':1,'refresh':'5s',
        'time':{'from':'now-3h','to':'now'},'panels':panels,
        '__inputs':[{'name':'DS_PROMETHEUS','label':'Prometheus Inventario-U Render','type':'datasource','pluginId':'prometheus','pluginName':'Prometheus'}]},text
