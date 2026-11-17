"""Start, inspect, exercise or stop the isolated local team practice."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import time

import httpx

from deploy.canary.dashboard import build as canary_dashboard
from deploy.canary.gateway import render
from chaos.dashboard import build as chaos_dashboard
from deploy.local_team.content import contract, guide, postman, prometheus_config, public_gateway, team_dashboard, grafana_cloud_guide
from deploy.local_team.resource_dashboard import build as resource_dashboard

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT/'deploy/local_team'
RUNTIME = FOLDER/'runtime'
PROJECT = 'inventario-team-local'
OPERATOR = 'http://127.0.0.1:18100'
SHARED = 'http://127.0.0.1:18180'


def run(arguments, **kwargs):
    return subprocess.run(arguments,check=True,**kwargs)


def read_json(path,default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def write_json(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def settings():
    target=RUNTIME/'settings.json'
    if target.exists():
        return read_json(target)
    existing=subprocess.run(['docker','volume','inspect',PROJECT+'_postgres_data'],capture_output=True)
    if existing.returncode==0:
        raise RuntimeError('Existing database without its credentials: recover runtime/settings.json; do not rotate passwords')
    RUNTIME.mkdir(parents=True,exist_ok=True)
    values={name:secrets.token_hex(24) for name in ('POSTGRES_PASSWORD','TEAM_API_KEY','PEER_API_KEY','GRAFANA_PASSWORD','VIEWER_PASSWORD')}
    values.update(METRICS_TOKEN=secrets.token_hex(32),GATEWAY_BIND='127.0.0.1',GATEWAY_PORT='18100',PROMETHEUS_PORT='19190',
                  COMPOSE_PROJECT_NAME=PROJECT,CHAOS_ROUND='none',RESILIENCE_MODE='baseline')
    # PostgreSQL password has no format restriction in this local Compose stack.
    write_json(target,values)
    target.chmod(0o600)
    return values


def compose(*arguments,capture=False):
    return run(['docker','compose','--project-name',PROJECT,'--env-file',str(RUNTIME/'local.env'),'-f',str(FOLDER/'compose.yml'),*arguments],
               cwd=ROOT,capture_output=capture,text=True)


def configure(values,base,ids):
    if base!=SHARED and not re.fullmatch(r'https://[a-z0-9-]+\.trycloudflare\.com',base):
        raise ValueError('Only the local origin or a validated Quick Tunnel URL is accepted')
    for name in ('private','public','exports','dashboards'):
        (RUNTIME/name).mkdir(parents=True,exist_ok=True)
    values['PUBLIC_BASE_URL']=base
    values['COOKIE_SECURE']='true' if base.startswith('https://') else 'false'
    (RUNTIME/'grafana-cloud-privado.txt').write_text('SOLO POR PRIVADO AL RESPONSABLE DE GRAFANA\nDatasource Prometheus URL: '+base+'/shared/prometheus\nHTTP header Authorization: Bearer '+values['METRICS_TOKEN']+'\nNo enviar al grupo ni subir a Git. Guardar el header como secreto en Grafana.\n',encoding='utf-8')
    (RUNTIME/'local.env').write_text(''.join(k+'='+json.dumps(v)+'\n' for k,v in values.items()),encoding='utf-8')
    write_json(RUNTIME/'settings.json',values)
    (RUNTIME/'private/proxy.conf').write_text(render(0,values['TEAM_API_KEY']),encoding='utf-8')
    (RUNTIME/'public/proxy.conf').write_text(public_gateway(values),encoding='utf-8')
    (RUNTIME/'exports/index.html').write_text('<!doctype html><meta charset="utf-8"><title>Inventario-U</title><h1>Inventario-U: práctica del equipo</h1><a href="/grafana/d/inventory-team/">Abrir Grafana</a> · <a href="/shared/guia.md">Guía de integración e IA</a>',encoding='utf-8')
    (RUNTIME/'exports/guia.md').write_text(guide(base,ids),encoding='utf-8')
    (RUNTIME/'exports/grafana-cloud.md').write_text(grafana_cloud_guide(base),encoding='utf-8')
    write_json(RUNTIME/'exports/datasource-template.json',{'name':'Inventario-U','type':'prometheus',
        'access':'proxy','url':base+'/shared/prometheus','jsonData':{'httpMethod':'POST','httpHeaderName1':'Authorization',
        'prometheusType':'Prometheus','prometheusVersion':'3.5.0','timeInterval':'5s'},
        'secureJsonData':{'httpHeaderValue1':'Bearer <INSERT_PRIVATE_METRICS_TOKEN_IN_GRAFANA>'}})
    (RUNTIME/'exports/prometheus.yml').write_text(prometheus_config(base),encoding='utf-8')
    write_json(RUNTIME/'exports/contrato.json',contract(base,ids))
    write_json(RUNTIME/'exports/postman.json',postman(base,ids))
    write_json(RUNTIME/'dashboards/team.json',team_dashboard(base,ids))
    write_json(RUNTIME/'dashboards/canary.json',canary_dashboard())
    write_json(RUNTIME/'dashboards/chaos.json',chaos_dashboard())
    report=ROOT/'docs/resource-local-results.md'
    write_json(RUNTIME/'dashboards/resource.json',resource_dashboard(report.read_text(encoding='utf-8') if report.exists() else 'Fallo c confirmado. Rondas OCI pendientes; no usar datos locales como evidencia cloud.'))
    resource_import=resource_dashboard(report.read_text(encoding='utf-8') if report.exists() else 'Rondas OCI pendientes; no usar datos locales como evidencia cloud.')
    resource_import['uid']=None
    resource_import['__inputs']=[{'name':'DS_PROMETHEUS','label':'Prometheus Inventario-U','type':'datasource','pluginId':'prometheus','pluginName':'Prometheus'}]
    for panel in resource_import['panels']:
        if panel.get('targets'):panel['datasource']={'type':'prometheus','uid':'${DS_PROMETHEUS}'}
    write_json(RUNTIME/'exports/resource-dashboard.json',resource_import)
    if report.exists():
        (RUNTIME/'exports/resource-results.md').write_text(report.read_text(encoding='utf-8'),encoding='utf-8')
    (RUNTIME/'prometheus.yml').write_text((ROOT/'deploy/canary/prometheus.yml').read_text(encoding='utf-8')+'''
      - targets: ['resource-baseline:8000']
        labels: {track: resource-baseline, version: 2.0.0}
      - targets: ['resource-r0:8000']
        labels: {track: resource-r0, version: 2.0.0}
      - targets: ['resource-r1:8000']
        labels: {track: resource-r1, version: 2.0.0}
''',encoding='utf-8')
    imported=canary_dashboard()
    imported['uid']=None
    imported['title']='Inventario-U remoto: stable y canary'
    imported['__inputs']=[{'name':'DS_PROMETHEUS','label':'Su Prometheus','type':'datasource','pluginId':'prometheus','pluginName':'Prometheus'}]
    for panel in imported['panels']:
        panel['datasource']={'type':'prometheus','uid':'${DS_PROMETHEUS}'}
    write_json(RUNTIME/'exports/dashboard.json',imported)
    sensitive=[values[k] for k in ('TEAM_API_KEY','PEER_API_KEY','METRICS_TOKEN','POSTGRES_PASSWORD','GRAFANA_PASSWORD','VIEWER_PASSWORD')]
    for folder in ('exports','dashboards'):
        for file in (RUNTIME/folder).glob('*'):
            if any(secret in file.read_text(encoding='utf-8') for secret in sensitive):
                raise RuntimeError('Credentials detected in a public artifact')


def api(values,path,method='GET',body=None,public=False,base=None):
    with httpx.Client(timeout=20) as client:
        return client.request(method,(base or (SHARED if public else OPERATOR))+path,
                              headers={'X-Api-Key':values['PEER_API_KEY' if public else 'TEAM_API_KEY'],'X-Trace-Id':'local-team-check'},json=body)


def seed(values):
    skus=api(values,'/api/v2/skus');skus.raise_for_status()
    warehouses=api(values,'/api/v2/almacenes');warehouses.raise_for_status()
    found=[s for s in skus.json() if s['codigo']=='TEAM-DEMO']
    created=not found
    if not found:
        response=api(values,'/api/v2/skus','POST',{'codigo':'TEAM-DEMO','nombre':'Inventario equipo sintetico','stock_minimo':10});response.raise_for_status();found=[response.json()]
    places=[w for w in warehouses.json() if w['nombre']=='Practica compartida']
    if not places:
        response=api(values,'/api/v2/almacenes','POST',{'nombre':'Practica compartida','ubicacion':'Local sintetico'});response.raise_for_status();places=[response.json()];created=True
    if len(found)!=1 or len(places)!=1:
        raise RuntimeError('Ambiguous demo entities; inspect before seeding')
    ids={'sku_id':found[0]['id'],'almacen_id':places[0]['id']}
    if created:
        response=api(values,'/api/v2/movimientos','POST',{**ids,'tipo':'entrada','cantidad':8,'motivo':'Demo del equipo'});response.raise_for_status()
    return ids


def grafana(values,path,method='GET',body=None,viewer=False):
    auth=('companeros',values['VIEWER_PASSWORD']) if viewer else ('admin',values['GRAFANA_PASSWORD'])
    with httpx.Client(timeout=15) as client:
        return client.request(method,OPERATOR+'/grafana'+path,auth=auth,json=body)


def ensure_viewer(values):
    response=grafana(values,'/api/users/lookup?loginOrEmail=companeros')
    if response.status_code==404:
        response=grafana(values,'/api/admin/users','POST',{'name':'Companeros Inventario-U','login':'companeros','password':values['VIEWER_PASSWORD'],'OrgId':1})
    response.raise_for_status()
    identifier=response.json()['id']
    response=grafana(values,f'/api/org/users/{identifier}','PATCH',{'role':'Viewer'});response.raise_for_status()
    response=grafana(values,'/api/user',viewer=True);response.raise_for_status()
    assert not response.json()['isGrafanaAdmin']
    response=grafana(values,'/api/user/orgs',viewer=True);response.raise_for_status()
    assert any(org['role']=='Viewer' for org in response.json())


def tunnel_process(action):
    """Windows validates PID, creation time and executable before any stop."""
    path=RUNTIME/'tunnel.json'
    env=dict(os.environ,LOCAL_TEAM_RUNTIME=str(RUNTIME),LOCAL_TEAM_CLOUDFLARED=shutil.which('cloudflared') or '')
    if not env['LOCAL_TEAM_CLOUDFLARED']:
        raise RuntimeError('Install cloudflared from its official source')
    probe=r'''
$file=Join-Path $env:LOCAL_TEAM_RUNTIME 'tunnel.json'
if (!(Test-Path -LiteralPath $file)) { exit 4 }
$saved=Get-Content -LiteralPath $file -Raw | ConvertFrom-Json
$process=Get-Process -Id $saved.pid -ErrorAction SilentlyContinue
if (!$process -or $process.StartTime.ToUniversalTime().Ticks.ToString() -ne $saved.started_ticks -or $process.Path -ne $saved.executable) { exit 4 }
'''
    if action in ('status','stop'):
        script=probe+('\nStop-Process -Id $process.Id -ErrorAction Stop' if action=='stop' else '\nWrite-Output "running"')
        result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],env=env,capture_output=True,text=True)
        if result.returncode not in (0,4):
            raise RuntimeError('Unable to verify owned tunnel process: '+result.stderr[:200])
        return result.returncode==0
    if tunnel_process('status'):
        return
    script=r'''
$out=Join-Path $env:LOCAL_TEAM_RUNTIME 'tunnel.stdout.log'
$err=Join-Path $env:LOCAL_TEAM_RUNTIME 'tunnel.stderr.log'
$process=Start-Process -FilePath $env:LOCAL_TEAM_CLOUDFLARED -ArgumentList @('--no-autoupdate','tunnel','--protocol','http2','--url','http://127.0.0.1:18180') -WindowStyle Hidden -PassThru -RedirectStandardOutput $out -RedirectStandardError $err
$process=Get-Process -Id $process.Id -ErrorAction Stop
$value=@{pid=$process.Id; started_ticks=$process.StartTime.ToUniversalTime().Ticks.ToString(); executable=$process.Path} | ConvertTo-Json -Compress
[System.IO.File]::WriteAllText((Join-Path $env:LOCAL_TEAM_RUNTIME 'tunnel.json'),$value)
'''
    # The detached child can inherit pipe handles; do not wait for captured EOF.
    run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)
    if not path.exists():
        raise RuntimeError('Owned tunnel process metadata was not saved')


def tunnel_url():
    for _ in range(90):
        text=(RUNTIME/'tunnel.stderr.log').read_text(encoding='utf-8',errors='replace') if (RUNTIME/'tunnel.stderr.log').exists() else ''
        match=re.search(r'https://[a-z0-9-]+\.trycloudflare\.com\b',text)
        if match:
            return match[0]
        time.sleep(1)
    raise RuntimeError('Quick Tunnel URL not available; inspect private runtime/tunnel.stderr.log')


def start():
    values=settings()
    print('Building the API image for the dedicated team project...',flush=True)
    run(['docker','build','-t','inventario-team:local','.'],cwd=ROOT)
    values['CANARY_IMAGE']=run(['docker','image','inspect','--format','{{.Id}}','inventario-team:local'],capture_output=True,text=True).stdout.strip()
    values['APP_REVISION']=run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True).stdout.strip()
    session=read_json(RUNTIME/'session.json',{})
    base=session.get('public_url',SHARED) if tunnel_process('status') else SHARED
    configure(values,base,session.get('ids',{}))
    compose('config','--quiet')
    compose('up','-d','--wait','--wait-timeout','240','db','stable','canary','prometheus','grafana')
    # Refresh upstream DNS after recreating API containers; clear old unhealthy state.
    compose('up','-d','--force-recreate','--wait','--wait-timeout','120','gateway','share-gateway')
    ensure_viewer(values)
    ids=seed(values)
    print('Starting/reusing the owned HTTPS tunnel...',flush=True)
    tunnel_process('start')
    base=tunnel_url()
    configure(values,base,ids)
    if session.get('public_url') and session['public_url']!=base:
        notice='URL CAMBIO: '+session['public_url']+' -> '+base+'\nActualizar las variables del equipo y sus Prometheus.\n'
        (RUNTIME/'URL-CAMBIO.txt').write_text(notice,encoding='utf-8')
        print(notice,flush=True)
    compose('up','-d','grafana')
    for _ in range(45):
        try:
            if grafana(values,'/api/health').status_code==200:
                break
        except httpx.TransportError:
            pass
        time.sleep(1)
    else:
        raise RuntimeError('Grafana did not recover after public URL configuration')
    for service in ('gateway','share-gateway'):
        compose('exec','-T',service,'nginx','-t')
        compose('exec','-T',service,'nginx','-s','reload')
    for _ in range(60):
        try:
            response=api(values,'/api/v2/health',public=True,base=base)
            if response.status_code==200 and response.headers.get('X-App-Revision')==values['APP_REVISION']:
                break
        except httpx.TransportError:
            pass
        time.sleep(2)
    else:
        raise RuntimeError('Public HTTPS did not verify; keep credentials private and inspect tunnel logs')
    ensure_viewer(values)
    write_json(RUNTIME/'session.json',{'public_url':base,'ids':ids,'revision':values['APP_REVISION'],'started_at_utc':datetime.now(timezone.utc).isoformat()})
    (RUNTIME/'credenciales-companeros.txt').write_text(f'URL: {base}\nGrafana: {base}/grafana/d/inventory-team/\nUsuario Grafana: companeros\nClave Grafana: {values["VIEWER_PASSWORD"]}\nX-Api-Key: {values["PEER_API_KEY"]}\nBearer de metricas: {values["METRICS_TOKEN"]}\nIDs sinteticos: {json.dumps(ids)}\nCompartir este archivo solo con los companeros; no subir a Git.\n',encoding='utf-8')
    (RUNTIME/'inventario_metrics_token').write_text(values['METRICS_TOKEN'],encoding='utf-8')
    from scripts.local_team_watch import start as start_watch
    start_watch()
    if (RUNTIME/'resource.env').exists():
        run(['docker','compose','--project-name','inventario-resource-lab','--env-file',str(RUNTIME/'resource.env'),
             '-f',str(FOLDER/'resource-compose.yml'),'up','-d','--wait','--wait-timeout','180'])
    print(json.dumps({'ready':True,'public_url':base,'grafana':base+'/grafana/d/inventory-team/','credentials_file':str(RUNTIME/'credenciales-companeros.txt')}),flush=True)


def demo():
    values=settings();ids=read_json(RUNTIME/'session.json')['ids']
    for _ in range(30):
        for path in ('/api/v2/inventario','/api/v3/inventario'):
            response=api(values,path+'?sku_id='+str(ids['sku_id'])+'&almacen_id='+str(ids['almacen_id']))
            response.raise_for_status()
        time.sleep(.5)
    print('60 actual requests completed; allow 10–15 seconds for Prometheus/Grafana')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('start','status','demo','stop'))
    action=parser.parse_args().action
    if action=='start':start()
    elif action=='demo':demo()
    elif action=='stop':
        from scripts.local_team_watch import stop as stop_watch
        stop_watch()
        if (RUNTIME/'resource.env').exists():
            run(['docker','compose','--project-name','inventario-resource-lab','--env-file',str(RUNTIME/'resource.env'),'-f',str(FOLDER/'resource-compose.yml'),'stop'])
        tunnel_process('stop')
        if (RUNTIME/'local.env').exists():compose('stop')
        print('Owned tunnel and team containers stopped; data volumes retained')
    else:
        print(json.dumps({'tunnel_running':tunnel_process('status'),'session':read_json(RUNTIME/'session.json',{}),
                         'watch':read_json(RUNTIME/'watch.json',{})},indent=2))
        if (RUNTIME/'local.env').exists():compose('ps')
        if (RUNTIME/'resource.env').exists():
            run(['docker','compose','--project-name','inventario-resource-lab','--env-file',str(RUNTIME/'resource.env'),
                 '-f',str(FOLDER/'resource-compose.yml'),'ps'])


if __name__=='__main__':
    main()
