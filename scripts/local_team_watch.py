"""Owned keep-awake and URL notice helper; never restarts a Quick Tunnel."""
import ctypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

from scripts.local_team import RUNTIME, read_json, write_json


def start():
    current=read_json(RUNTIME/'watch.json',{})
    if current.get('heartbeat_utc'):
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(current['heartbeat_utc'])).total_seconds()
        if age<45 and current.get('desired')=='running':return
    state={'token':uuid4().hex,'desired':'running'}
    (RUNTIME/'watch.stop').unlink(missing_ok=True)
    write_json(RUNTIME/'watch.json',state)
    subprocess.Popen([sys.executable,'-m','scripts.local_team_watch',state['token']],
        cwd=Path(__file__).resolve().parents[1],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    time.sleep(1)


def stop():
    (RUNTIME/'watch.stop').touch()
    state=read_json(RUNTIME/'watch.json',{})
    state['desired']='stopped'
    write_json(RUNTIME/'watch.json',state)


def worker(token):
    previous=read_json(RUNTIME/'session.json',{}).get('public_url')
    try:
        while True:
            state=read_json(RUNTIME/'watch.json',{})
            if (RUNTIME/'watch.stop').exists() or state.get('token')!=token or state.get('desired')!='running':return
            awake=bool(ctypes.windll.kernel32.SetThreadExecutionState(0x80000001))
            current=read_json(RUNTIME/'session.json',{}).get('public_url')
            if previous and current and current!=previous:
                (RUNTIME/'URL-CAMBIO.txt').write_text(f'URL anterior: {previous}\nURL nueva: {current}\nActualizar proyectos y Prometheus del equipo.\n',encoding='utf-8')
                ctypes.windll.user32.MessageBeep(0x30)
            previous=current
            state.update(pid=os.getpid(),heartbeat_utc=datetime.now(timezone.utc).isoformat(),
                system_required=awake,public_url=current)
            write_json(RUNTIME/'watch-next.json',state)
            (RUNTIME/'watch-next.json').replace(RUNTIME/'watch.json')
            time.sleep(10)
    finally:
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


if __name__=='__main__':
    worker(sys.argv[1])
