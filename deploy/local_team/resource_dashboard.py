"""Resource lab charts use real Prometheus series, with an explicit scope label."""
def build(report='Las mediciones todavía no han terminado; no hay resultados aprobados.'):
    panels=[{'id':1,'type':'text','title':'Fallo c confirmado: práctica LOCAL, no evidencia cloud',
        'gridPos':{'x':0,'y':0,'w':24,'h':16},'options':{'mode':'markdown','content':'Métrica objetivo única: éxito ≥99%. Guardarraíl: p95 <500 ms. El grupo exige repetir estado estable/R0/R1 en OCI.\n\n'+report}}]
    selector='track=~"resource-.*",route="/api/v2/skus",method="GET"'
    total='sum by (track) (rate(inventory_http_requests_total{track=~"resource-.*"}[30s]))'
    errors='sum by (track) (rate(inventory_http_requests_total{track=~"resource-.*",status!~"2.."}[30s]))'
    queries=[('Peticiones por segundo',f'sum by (track) (rate(inventory_http_requests_total{{{selector}}}[30s]))','reqps'),
        ('p95 HTTP observado por la API',f'histogram_quantile(0.95,sum by (le,track) (rate(inventory_http_duration_seconds_bucket{{{selector}}}[30s])))','s'),
        ('Errores HTTP; timeouts del cliente en informe superior',f'({errors} or on (track) (0 * {total})) / clamp_min({total},0.000001)','percentunit'),
        ('Tareas de fondo activas: R0 comparte pool HTTP, R1 aislado','inventory_resource_background_active','short')]
    for index,(title,expression,unit) in enumerate(queries):
        panels.append({'id':index+2,'type':'timeseries','title':title,
            'gridPos':{'x':(index%2)*12,'y':16+(index//2)*8,'w':12,'h':8},
            'datasource':{'type':'prometheus','uid':'prometheus'},
            'targets':[{'refId':'A','expr':expression,'legendFormat':'{{track}} {{round}}'}],
            'fieldConfig':{'defaults':{'unit':unit,'min':0,**({'max':1} if unit=='percentunit' else {})},'overrides':[]}})
    return {'uid':'inventory-resource','title':'Inventario-U — Fallo c: concurrencia LOCAL',
        'schemaVersion':41,'version':1,'refresh':'5s','time':{'from':'now-30m','to':'now'},'panels':panels,
        'links':[{'title':'Guía del equipo','type':'link','url':'/grafana/d/inventory-team/'}]}
