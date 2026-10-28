"""One documented command from a clean clone; requires Docker and Ollama."""
import os
import shutil
import subprocess
import sys
import json
import time
from datetime import datetime, timezone
from pathlib import Path

def main():
    root=Path(__file__).resolve().parents[1]
    os.chdir(root)
    started=time.perf_counter()
    timings={'started_at':datetime.now(timezone.utc).isoformat(),'stages':[]}
    report=root/'tmp'/'demo-timing.json'
    report.parent.mkdir(exist_ok=True)

    def stage(name,command,**kwargs):
        print(f'[{name}] starting',flush=True)
        stage_started=time.perf_counter()
        try:
            result=subprocess.run(command,check=True,**kwargs)
        except BaseException:
            timings['stages'].append({'name':name,'seconds':round(time.perf_counter()-stage_started,3),'success':False})
            timings['success']=False
            timings['total_seconds']=round(time.perf_counter()-started,3)
            report.write_text(json.dumps(timings,indent=2),encoding='utf-8')
            raise
        elapsed=round(time.perf_counter()-stage_started,3)
        timings['stages'].append({'name':name,'seconds':elapsed,'success':True})
        print(f'[{name}] completed in {elapsed:.2f}s',flush=True)
        return result
    docker=shutil.which('docker')
    if not docker and os.name=='nt': docker=r'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
    if not docker: raise SystemExit('Start Docker Desktop and put docker on PATH.')
    # The brief's preflight may already own port 5432. Reuse its healthy setup
    # container; a clean machine follows the compose path instead.
    existing=subprocess.run([docker,'ps','--filter','name=^relay-pg$','--format','{{.Names}}'],capture_output=True,text=True,check=True)
    if existing.stdout.strip()=='relay-pg' and os.getenv('PG_PORT','5432')=='5432':
        stage('database',[docker,'exec','relay-pg','pg_isready','-U','postgres'])
    else:
        stage('database',[docker,'compose','up','-d','--wait'])
    venv=root/'.venv'
    python=venv/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not python.exists(): stage('virtual_environment',[sys.executable,'-m','venv',str(venv)])
    stage('dependencies',[str(python),'-m','pip','install','--disable-pip-version-check','-r','requirements.txt'])
    env=os.environ.copy()
    env['PYTHONUTF8']='1'
    for name,args in [('migrations',['migrate']),('embeddings',['seed']),('inboxes',['run','--inbox','data/northwind/tickets.jsonl','data/harbor/tickets.jsonl']),('approval_queue_northwind',['list','--tenant','northwind']),('approval_queue_harbor',['list','--tenant','harbor'])]:
        stage(name,[str(python),'-m','relay',*args],env=env)
    timings['success']=True
    timings['finished_at']=datetime.now(timezone.utc).isoformat()
    timings['total_seconds']=round(time.perf_counter()-started,3)
    report.write_text(json.dumps(timings,indent=2),encoding='utf-8')
    print(f'Demo completed in {timings["total_seconds"]:.2f}s. Timing: {report}',flush=True)

if __name__=='__main__': main()
