"""Suspend only the two owned Free web services after the authorized practice."""
import ctypes
from datetime import datetime,timedelta,timezone
import json
import os
import subprocess
import sys
import time

from deploy.render.free import ROOT,RUNTIME,api,read,write


def suspend():
    state=read('deployment.json')
    for key,name in (('api_service_id','inventario-chaos-free'),('prometheus_service_id','inventario-chaos-prom-free')):
        service=api('GET','/services/'+state[key])
        if service['name']!=name or service['serviceDetails']['plan']!='free':
            raise RuntimeError('Ownership or Free plan mismatch; no other project will be changed')
        if service.get('suspended')!='suspended':api('POST','/services/'+state[key]+'/suspend')
    return True


def start(deadline=None):
    state=read('deployment.json')
    existing=read('guard.json',{})
    if existing.get('heartbeat_utc') and existing.get('status')=='watching':
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(existing['heartbeat_utc'])).total_seconds()
        if age<45:return
    if deadline is None:
        service=api('GET','/services/'+state['api_service_id'])
        created=datetime.fromisoformat(service['createdAt'].replace('Z','+00:00'))
        deadline=created+timedelta(hours=2)
    write('guard.json',{'deadline_utc':deadline.isoformat(),'status':'starting'})
    subprocess.Popen([sys.executable,'-m','scripts.render_free_guard'],cwd=ROOT,
        stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW)


def main():
    try:
        while True:
            state=read('guard.json');deadline=datetime.fromisoformat(state['deadline_utc'])
            awake=bool(ctypes.windll.kernel32.SetThreadExecutionState(0x80000001))
            now=datetime.now(timezone.utc)
            state.update(pid=os.getpid(),heartbeat_utc=now.isoformat(),keep_awake=awake)
            if now>=deadline:
                try:
                    suspend();state['status']='suspended';write('guard.json',state);return
                except Exception as error:
                    state.update(status='retry_required',error_type=type(error).__name__)
            else:state['status']='watching'
            write('guard.json',state)
            time.sleep(15)
    finally:ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


if __name__=='__main__':main()
