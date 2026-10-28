import argparse
import json
from .config import TENANTS
from .db import migrate,session
from .retrieval import seed
from .engine import ingest,run_id,worker,export,resume
from .approvals import list_pending,decide

def main():
    parser=argparse.ArgumentParser(prog='relay')
    sub=parser.add_subparsers(dest='command',required=True)
    for cmd in ['migrate','seed','worker','export']: sub.add_parser(cmd)
    run=sub.add_parser('run'); run.add_argument('--inbox',required=True,nargs='+')
    evaluate=sub.add_parser('eval'); evaluate.add_argument('--runs',type=int,default=5)
    evaluate.add_argument('--output-dir',default='eval/runs')
    evaluate.add_argument('--report',default='docs/EVAL.md')
    for command in ['list','show','approve','reject','resume','decision','cases']:
        p=sub.add_parser(command); p.add_argument('--tenant',required=True,choices=TENANTS)
        if command not in ('list','cases'): p.add_argument('ticket_id')
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
    elif args.command=='decision':
        with session(args.tenant) as conn:
            row=conn.execute('SELECT record FROM decisions WHERE tenant=%s AND ticket_id=%s',(args.tenant,args.ticket_id)).fetchone()
            if not row: raise SystemExit('No decision for this tenant/ticket')
            print(json.dumps(row['record'],ensure_ascii=False,indent=2))
    elif args.command=='cases':
        with session(args.tenant) as conn:
            for row in conn.execute('SELECT ticket_id,owner,severity,reason,created_at FROM cases ORDER BY created_at'):
                print(json.dumps(row,default=str,ensure_ascii=False))
    elif args.command=='eval':
        from .evaluation import evaluate
        evaluate(args.runs,output_dir=args.output_dir,report_path=args.report)

if __name__=='__main__': main()
