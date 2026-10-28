import argparse
import json
from .config import TENANTS
from .db import migrate
from .retrieval import seed
from .engine import ingest,run_id,worker,export,resume
from .approvals import list_pending,decide

def main():
    parser=argparse.ArgumentParser(prog='relay')
    sub=parser.add_subparsers(dest='command',required=True)
    for cmd in ['migrate','seed','worker','export']: sub.add_parser(cmd)
    run=sub.add_parser('run'); run.add_argument('--inbox',required=True,nargs='+')
    evaluate=sub.add_parser('eval'); evaluate.add_argument('--runs',type=int,default=5)
    for command in ['list','show','approve','reject','resume']:
        p=sub.add_parser(command); p.add_argument('--tenant',required=True,choices=TENANTS)
        if command!='list': p.add_argument('ticket_id')
        if command in ('approve','reject','resume'): p.add_argument('--by',required=True)
        if command=='reject': p.add_argument('--reason',required=True)
    args=parser.parse_args()
    if args.command=='migrate': migrate()
    elif args.command=='seed': seed()
    elif args.command=='run':
        run=run_id(); print('run:',run,flush=True); print('new tickets:',ingest(args.inbox,run),flush=True); worker(); export()
    elif args.command=='worker': worker(); export()
    elif args.command=='export': export()
    elif args.command in ('list','show'):
        for row in list_pending(args.tenant,ticket_id=getattr(args,'ticket_id',None)):
            print(json.dumps(row,default=str,ensure_ascii=False))
    elif args.command in ('approve','reject'):
        print(decide(args.tenant,args.ticket_id,args.by,args.command=='approve',getattr(args,'reason',None))); export()
    elif args.command=='resume': resume(args.tenant,args.ticket_id,args.by)
    elif args.command=='eval':
        from .evaluation import evaluate
        evaluate(args.runs)

if __name__=='__main__': main()
