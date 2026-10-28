"""Golden labels are read only here, after predictions have been produced."""
import json
import time
from pathlib import Path
from psycopg.types.json import Jsonb
from .contracts import Ticket,DecisionRecord
from .db import session,new_run,load_jsonl
from .engine import run_id
from .gateway import Gateway,BudgetExceeded
from .agents import triage,route
from .retrieval import retrieve

def evaluate(runs=5,cfg=None,output_dir='eval/runs',report_path='docs/EVAL.md'):
    if runs<1: raise ValueError('runs must be positive')
    tickets=[Ticket.model_validate(row) for tenant in ('northwind','harbor') for row in load_jsonl(f'data/{tenant}/tickets.jsonl')]
    Path(output_dir).mkdir(parents=True,exist_ok=True)
    all_runs=[]; started=time.monotonic(); retrieved={}
    for number in range(1,runs+1):
        identifier=run_id(); new_run(identifier,cfg); results=[]
        for ticket in tickets:
            identity='eval:'+identifier+':'+ticket.id
            with session(ticket.tenant,cfg) as conn:
                conn.execute('INSERT INTO tickets(tenant,id,payload) VALUES (%s,%s,%s)',(ticket.tenant,identity,Jsonb(ticket.model_dump(mode='json'))))
            gateway=Gateway(ticket.tenant,identity,identifier,cfg)
            t0=time.monotonic(); error=None
            category,priority,action,injection,refs,status='other','normal','escalate',False,[],'failed'
            try:
                proposal=triage(ticket,gateway)
                # Only immutable public retrieval context is reused. Every run
                # still makes a fresh triage model call and reruns routing.
                key=(ticket.tenant,ticket.subject,ticket.body)
                if key not in retrieved:
                    retrieved[key]=retrieve(ticket,gateway,cfg)
                passages=retrieved[key]
                result=route(ticket,proposal,passages)
                category,priority,action,injection=result.category,result.priority,result.action,result.injection_detected
                refs=[passages[0].kb_id] if passages else []
                status='escalated' if action=='escalate' else 'pending_approval'
            except Exception as exc:
                error=type(exc).__name__
                status='held_budget' if isinstance(exc,BudgetExceeded) else 'failed'
            model,ti,to=gateway.metrics()
            record=DecisionRecord(ticket_id=ticket.id,tenant=ticket.tenant,run_id=identifier,category=category,priority=priority,action=action,
                                  injection_detected=injection,kb_refs=refs,draft_reply=None,status=status,model=model,tokens_in=ti,tokens_out=to,latency_ms=int((time.monotonic()-t0)*1000)).model_dump()
            results.append(record)
            print(f'eval {number}/{runs} {ticket.id}: {action} {error or ""}',flush=True)
        path=Path(output_dir)/f'run_{number}.jsonl'
        path.write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in results),encoding='utf-8')
        all_runs.append(results)
    # Measurement-only code below. Never imported by triage/routing.
    golden={r['id']:r for r in load_jsonl('data/golden.jsonl')}
    rows=[r for run in all_runs for r in run]; n=len(rows)
    action_correct=sum(r['action']==golden[r['ticket_id']]['action'] and r['status'] not in ('failed','held_budget') for r in rows)
    category_correct=sum(r['category']==golden[r['ticket_id']]['category'] for r in rows)
    positives=sum(golden[r['ticket_id']]['injection'] for r in rows)
    true_positives=sum(r['injection_detected'] and golden[r['ticket_id']]['injection'] for r in rows)
    false_positives=sum(r['injection_detected'] and not golden[r['ticket_id']]['injection'] for r in rows)
    stable=sum(len({run[i]['action'] for run in all_runs})==1 for i in range(len(tickets)))
    lines=['# Evaluation','',f'Generated from {runs} real local-model runs over {len(tickets)} tickets. Temperature 0, seed 7. No drafting in evaluation.',
           'Every run executes fresh triage inference and routing. Immutable public retrieval passages are reused after the first run; model responses and decisions are never cached. Usage records reflect calls actually made.','',
           f'- Action accuracy: {action_correct}/{n} ({action_correct/n:.1%})',f'- Category accuracy: {category_correct}/{n} ({category_correct/n:.1%})',
           f'- Injection recall: {true_positives}/{positives} ({true_positives/positives:.1%})',
           f'- Injection false positives: {false_positives}/{n-positives}',f'- Action stability: {stable}/{len(tickets)} ({stable/len(tickets):.1%})',
           f'- Input tokens: {sum(r["tokens_in"] for r in rows)}',f'- Output tokens: {sum(r["tokens_out"] for r in rows)}',
           f'- Wall time: {time.monotonic()-started:.2f} seconds','',
           '## Errors per ticket','', '| Run | Ticket | Differences |','|---|---|---|']
    errors=0
    for index,run in enumerate(all_runs,1):
        for row in run:
            g=golden[row['ticket_id']]; differences=[]
            for actual,expected in [('action','action'),('category','category'),('priority','priority'),('injection_detected','injection')]:
                if row[actual]!=g[expected]: differences.append(f'{actual}: {row[actual]} expected {g[expected]}')
            if row['status'] in ('failed','held_budget'): differences.append('execution status: '+row['status'])
            if differences: lines.append(f'| {index} | {row["ticket_id"]} | '+ '; '.join(differences)+' |'); errors+=1
    if not errors: lines.append('| all | all | none |')
    lines += ['', '## Interpretation','',
              'These results cover the visible synthetic seed set, not unseen-ticket accuracy. Repeated local inference may vary between machines. Priority and KB retrieval are diagnostic, not folded into action accuracy.',
              'Next improvements: larger paraphrased injection and benign-control sets, evidence extraction for ambiguous missing details, and measured retrieval relevance. No result was manually edited.']
    Path(report_path).parent.mkdir(parents=True,exist_ok=True)
    Path(report_path).write_text('\n'.join(lines)+'\n',encoding='utf-8')
