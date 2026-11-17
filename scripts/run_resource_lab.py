"""Run reproducible local BASELINE/R0/R1 without faulting the shared API."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

import httpx

from scripts.local_team import ROOT, RUNTIME, FOLDER, read_json, settings, write_json


def compose(*arguments):
    subprocess.run(['docker','compose','--project-name','inventario-resource-lab','--env-file',str(RUNTIME/'resource.env'),
        '-f',str(FOLDER/'resource-compose.yml'),*arguments],cwd=ROOT,check=True)


def main():
    values=settings(); execution=uuid4().hex
    subprocess.run(['docker','build','-t','inventario-resource:local','.'],cwd=ROOT,check=True)
    values['CANARY_IMAGE']=subprocess.check_output(['docker','image','inspect','--format','{{.Id}}','inventario-resource:local'],text=True).strip()
    values['APP_REVISION']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    values['CHAOS_EXECUTION_ID']=execution
    (RUNTIME/'resource.env').write_text(''.join(k+'='+json.dumps(v)+'\n' for k,v in values.items()),encoding='utf-8')
    folder=ROOT/'chaos/results'/('resource-'+execution)
    folder.mkdir(parents=True)
    compose('up','-d','--wait','--wait-timeout','180')
    # All three replicas query the same isolated synthetic database.
    response=httpx.get('http://127.0.0.1:18110/api/v2/skus',headers={'X-Api-Key':values['TEAM_API_KEY']})
    response.raise_for_status()
    if not response.json():
        response=httpx.post('http://127.0.0.1:18110/api/v2/skus',headers={'X-Api-Key':values['TEAM_API_KEY']},
            json={'codigo':'RESOURCE-SYNTHETIC','nombre':'Resource experiment fixture','stock_minimo':0})
        response.raise_for_status()
    reports=[]
    for current in ('BASELINE','R0','R1'):
        print(current+': running identical 120 s profile; experiment '+execution,flush=True)
        env=dict(os.environ,CHAOS_ROUND=current,CHAOS_EXECUTION_ID=execution,
            RESOURCE_PRIVATE_KEY=values['TEAM_API_KEY'],RESOURCE_RESULT_FILE=str(folder/(current+'.json')),
            APP_REVISION=values['APP_REVISION'])
        with (folder/(current+'-toolkit.log')).open('w',encoding='utf-8') as log:
            result=subprocess.run([sys.executable,'-m','chaostoolkit','--no-version-check','--no-log-file',
                'run',str(ROOT/'chaos/experiments/resource-concurrency.json'),'--journal-path',
                str(folder/(current+'-journal.json'))],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(current+' Chaos Toolkit failed; inspect private result log')
        report=read_json(folder/(current+'.json'))
        journal=read_json(folder/(current+'-journal.json'))
        if not report or any(activity.get('status')!='succeeded' for activity in journal.get('run',[])):
            raise RuntimeError(current+' experiment action failed; inspect journal; no approved evidence')
        assert report['total_requests']==600 and report['samples']==300 and report['rollback_verified']
        reports.append(report)
        print(json.dumps({k:report[k] for k in ('round','p95_ms','error_percent','passed')}),flush=True)
    comparison={'execution_id':execution,'profile_identical':all(r['profile']==reports[0]['profile'] for r in reports),
        'revision_identical':len({r['revision'] for r in reports})==1,
        'scope':'local isolated single-API replica; assignment c pending group confirmation',
        'measurements':[{k:v for k,v in report.items() if k!='requests'} for report in reports]}
    baseline=reports[0]['p95_ms']
    for report in comparison['measurements']:
        report['p95_variation_vs_baseline_percent']=round((report['p95_ms']/baseline-1)*100,2)
        report['error_variation_percentage_points']=round(report['error_percent']-reports[0]['error_percent'],3)
    write_json(folder/'comparison.json',comparison)
    write_json(RUNTIME/'resource-last.json',{'folder':str(folder),'execution_id':execution})
    lines=['# Inventario-U: evidencia local de agotamiento de concurrencia','',
        'Asignación c propuesta; el grupo debe confirmar el cambio desde latencia saliente.',
        'Réplica local aislada; no demuestra tres APIs en tres nubes. La API compartida no recibió este fallo.','',
        'Hipótesis: con 5 GET /api/v2/skus por segundo durante 120 s, al solicitar 6 tareas bloqueantes durante 60 s desde t=30, p95 <500 ms y éxito >=99% en la ventana [30,90).',
        'Carga de llegada constante: 600 peticiones, timeout 2 s; 300 muestras en cada ventana. Las respuestas fallidas y timeouts se incluyen en p95.',
        'R0: las tareas ocupan los 6 permisos del pool HTTP. R1: bulkhead con limiter separado y admisión máxima de 4 tareas de fondo sin cola; se rechazan 2. Misma solicitud de fallo, distinta protección.',
        'La hipótesis de disponibilidad de Chaos Toolkit verifica antes/después; passed en la tabla evalúa el objetivo DURANTE el fallo.','',
        '| Medición | p95 ms | Error % | Variación p95 vs estable % | Objetivo |',
        '|---|---:|---:|---:|---|']
    for r in comparison['measurements']:
        lines.append(f"| {r['round']} | {r['p95_ms']:.3f} | {r['error_percent']:.3f} | {r['p95_variation_vs_baseline_percent']:.2f} | {'cumple' if r['passed'] else 'refutada'} |")
    lines.extend(['','Variación de error se expresa en puntos porcentuales: una variación relativa desde 0% no está definida.',
        '',f'Execution ID: `{execution}`',f"Revisión: `{values['APP_REVISION']}`",''])
    for r in reports:
        lines.extend([f"## {r['round']}",f"Inicio UTC: {r['started_utc']}",
            f"Fin UTC: {r['ended_utc']}",f"Trace de ejemplo: `{r['trace_id']}`",
            'Inyección y reversión UTC: `'+json.dumps(r['fault'])+'`',
            f"Mayor retraso del generador: {r['max_scheduler_lag_ms']} ms. Reversión comprobada: {r['rollback_verified']}.",''])
    report_text='\n'.join(lines)+'\n'
    (ROOT/'docs/resource-local-results.md').write_text(report_text,encoding='utf-8')
    (RUNTIME/'exports/resource-results.md').write_text(report_text,encoding='utf-8')
    from deploy.local_team.resource_dashboard import build
    write_json(RUNTIME/'dashboards/resource.json',build(report_text))
    # App logs carry trace_id, round and execution_id; capture genuine logs after each run.
    command=['docker','compose','--project-name','inventario-resource-lab','--env-file',str(RUNTIME/'resource.env'),'-f',str(FOLDER/'resource-compose.yml'),'logs','--no-color']
    with (folder/'application.log').open('w',encoding='utf-8') as output:
        subprocess.run(command,stdout=output,stderr=subprocess.STDOUT,check=True,cwd=ROOT)
    print('Results: '+str(ROOT/'docs/resource-local-results.md'),flush=True)


if __name__=='__main__':main()
