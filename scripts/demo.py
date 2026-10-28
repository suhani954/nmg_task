"""One documented command from a clean clone; requires Docker and Ollama."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

def main():
    root=Path(__file__).resolve().parents[1]
    os.chdir(root)
    docker=shutil.which('docker')
    if not docker and os.name=='nt': docker=r'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
    if not docker: raise SystemExit('Start Docker Desktop and put docker on PATH.')
    # The brief's preflight may already own port 5432. Reuse its healthy setup
    # container; a clean machine follows the compose path instead.
    existing=subprocess.run([docker,'ps','--filter','name=^relay-pg$','--format','{{.Names}}'],capture_output=True,text=True,check=True)
    if existing.stdout.strip()=='relay-pg' and os.getenv('PG_PORT','5432')=='5432':
        subprocess.run([docker,'exec','relay-pg','pg_isready','-U','postgres'],check=True)
    else:
        subprocess.run([docker,'compose','up','-d','--wait'],check=True)
    venv=root/'.venv'
    python=venv/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not python.exists(): subprocess.run([sys.executable,'-m','venv',str(venv)],check=True)
    subprocess.run([str(python),'-m','pip','install','-r','requirements.txt'],check=True)
    env=os.environ.copy()
    env['PYTHONUTF8']='1'
    for args in [['migrate'],['seed'],['run','--inbox','data/northwind/tickets.jsonl','data/harbor/tickets.jsonl'],['list','--tenant','northwind'],['list','--tenant','harbor']]:
        subprocess.run([str(python),'-m','relay',*args],check=True,env=env)

if __name__=='__main__': main()
