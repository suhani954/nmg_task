import json
import random
import time
import uuid
from pathlib import Path
from datetime import datetime, timezone
from psycopg.types.json import Jsonb
from pydantic import ValidationError
from .config import Config, TENANTS
from .contracts import Ticket, DecisionRecord
from .db import session, audit, new_run, save_decision
from .gateway import Gateway, BudgetExceeded, InvalidModelOutput
from .agents import triage, route, draft
from .retrieval import retrieve
from .checker import check_database

def run_id():
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]

def ingest(paths, run, cfg=None):
    new_run(run,cfg)
    added=0
    for path in paths:
        with Path(path).open(encoding='utf-8') as source:
            for number,line in enumerate(source,1):
                if not line.strip(): continue
                try:
                    ticket=Ticket.model_validate_json(line)
                except ValidationError:
                    with session(cfg=cfg) as conn:
                        conn.execute('INSERT INTO rejected_inputs(run_id,line_number,reason) VALUES (%s,%s,%s)',(run,number,'invalid_input_or_unknown_tenant'))
                    continue
                with session(ticket.tenant,cfg) as conn:
                    row=conn.execute('INSERT INTO tickets(tenant,id,payload) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id',
                                     (ticket.tenant,ticket.id,Jsonb(ticket.model_dump(mode='json')))).fetchone()
                    if row:
                        conn.execute('INSERT INTO jobs(tenant,ticket_id,run_id) VALUES (%s,%s,%s)',(ticket.tenant,ticket.id,run))
                        audit(conn,ticket.tenant,ticket.id,'queued','validated input','ingest')
                        added+=1
    return added

def claim(tenant,cfg):
    with session(tenant,cfg) as conn:
        row=conn.execute("SELECT * FROM jobs WHERE (state='ready' AND available_at<=now()) OR (state='leased' AND lease_until<now()) ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1").fetchone()
        if not row: return None
        lease=uuid.uuid4().hex
        conn.execute("UPDATE jobs SET state='leased',attempts=attempts+1,lease_token=%s,lease_until=now()+(%s * interval '1 second') WHERE id=%s",(lease,cfg.lease_seconds,row['id']))
        audit(conn,tenant,row['ticket_id'],'leased','worker acquired or recovered lease')
        row.update(lease_token=lease,attempts=row['attempts']+1)
        return row

def case(conn,ticket,priority,reason):
    owner='on-duty dentist' if reason=='clinical_requires_dentist' else 'support lead'
    conn.execute('INSERT INTO cases(tenant,ticket_id,owner,severity,reason) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (tenant,ticket_id) DO UPDATE SET reason=excluded.reason,severity=excluded.severity',
                 (ticket.tenant,ticket.id,owner,priority,reason))

def process(job,cfg=None,gateway_factory=Gateway,evaluation=False):
    cfg=cfg or Config()
    if job['attempts']>cfg.max_attempts:
        raise RuntimeError('lease_recovery_exhausted_attempt_limit')
    start=time.monotonic()
    tenant=job['tenant']
    with session(tenant,cfg) as conn:
        stored=conn.execute('SELECT * FROM tickets WHERE tenant=%s AND id=%s',(tenant,job['ticket_id'])).fetchone()
        feedback=conn.execute("SELECT feedback FROM approvals WHERE tenant=%s AND ticket_id=%s AND state='rejected' ORDER BY revision DESC LIMIT 1",(tenant,job['ticket_id'])).fetchone()
    ticket=Ticket.model_validate(stored['payload'])
    gateway=gateway_factory(tenant,ticket.id,job['run_id'],cfg)
    category,priority,action,injection='other','normal','escalate',False
    passages=[]; refs=[]; output=None; failure_reason=None
    try:
        result=triage(ticket,gateway)
        # Retrieval also runs for escalations, yielding auditable public context.
        passages=retrieve(ticket,gateway,cfg)
        result=route(ticket,result,passages)
        category,priority,action,injection=result.category,result.priority,result.action,result.injection_detected
        refs=[passages[0].kb_id] if passages else []
        if action=='escalate':
            status='escalated'
            failure_reason='prompt_injection' if injection else ('clinical_requires_dentist' if category=='clinical' else 'human_judgment_or_unsupported_request')
        elif evaluation:
            status='pending_approval'
        else:
            output=draft(ticket,result,passages,gateway,feedback['feedback'] if feedback else None)
            reasons=check_database(ticket,output,passages,cfg)
            if reasons:
                output=None; status='failed'; failure_reason='checker:'+','.join(reasons)
            else:
                status='pending_approval'; refs=output.kb_refs
    except BudgetExceeded:
        status='held_budget'; failure_reason='budget_exhausted'
    except InvalidModelOutput:
        status='failed'; failure_reason='invalid_model_output'
    models,ti,to=gateway.metrics()
    decision=DecisionRecord(ticket_id=ticket.id,tenant=tenant,run_id=job['run_id'],category=category,priority=priority,
                            action=action,injection_detected=injection,kb_refs=refs,draft_reply=output.text if output else None,
                            status=status,model=models,tokens_in=ti,tokens_out=to,latency_ms=int((time.monotonic()-start)*1000))
    with session(tenant,cfg) as conn:
        locked=conn.execute('SELECT * FROM jobs WHERE id=%s FOR UPDATE',(job['id'],)).fetchone()
        if locked['lease_token']!=job['lease_token']:
            return None # A newer worker owns the job; discard this worker's output.
        save_decision(conn,decision)
        conn.execute('UPDATE tickets SET status=%s WHERE tenant=%s AND id=%s',(status,tenant,ticket.id))
        if output:
            conn.execute('INSERT INTO approvals(tenant,ticket_id,revision,text,kb_refs) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                         (tenant,ticket.id,stored['revision'],output.text,Jsonb(output.kb_refs)))
        if failure_reason and status in ('escalated','failed'):
            case(conn,ticket,priority,failure_reason)
        conn.execute("UPDATE jobs SET state='done',lease_until=NULL WHERE id=%s",(job['id'],))
        audit(conn,tenant,ticket.id,status,failure_reason or 'validated draft awaiting human approval')
    return decision

def retry(job,exc,cfg):
    with session(job['tenant'],cfg) as conn:
        locked=conn.execute('SELECT * FROM jobs WHERE id=%s FOR UPDATE',(job['id'],)).fetchone()
        if locked['lease_token']!=job['lease_token']: return
        if job['attempts']>=cfg.max_attempts:
            conn.execute("UPDATE jobs SET state='dead',lease_until=NULL WHERE id=%s",(job['id'],))
            row=conn.execute('SELECT payload FROM tickets WHERE tenant=%s AND id=%s',(job['tenant'],job['ticket_id'])).fetchone()
            ticket=Ticket.model_validate(row['payload'])
            case(conn,ticket,'high','attempts_exhausted:'+type(exc).__name__)
            gateway=Gateway(job['tenant'],job['ticket_id'],job['run_id'],cfg)
            # Read usage on this connection instead of nesting a budget transaction.
            calls=conn.execute('SELECT model,tokens_in,tokens_out FROM model_calls WHERE ticket_id=%s',(job['ticket_id'],)).fetchall()
            decision=DecisionRecord(ticket_id=ticket.id,tenant=ticket.tenant,run_id=job['run_id'],category='other',priority='high',action='escalate',injection_detected=False,kb_refs=[],draft_reply=None,status='failed',model='+'.join(sorted({r['model'] for r in calls})),tokens_in=sum(r['tokens_in'] for r in calls),tokens_out=sum(r['tokens_out'] for r in calls),latency_ms=0)
            save_decision(conn,decision)
            conn.execute("UPDATE tickets SET status='failed' WHERE tenant=%s AND id=%s",(ticket.tenant,ticket.id))
            audit(conn,ticket.tenant,ticket.id,'dead_letter',type(exc).__name__)
        else:
            delay=cfg.retry_base*2**(job['attempts']-1)+random.uniform(0,cfg.retry_base)
            conn.execute("UPDATE jobs SET state='ready',lease_until=NULL,available_at=now()+(%s*interval '1 second') WHERE id=%s",(delay,job['id']))
            audit(conn,job['tenant'],job['ticket_id'],'retry_scheduled',type(exc).__name__)

def worker(cfg=None):
    cfg=cfg or Config()
    while True:
        progressed=False
        for tenant in TENANTS:
            job=claim(tenant,cfg)
            if not job: continue
            progressed=True
            try:
                decision=process(job,cfg)
                if decision: print(f'{tenant}/{job["ticket_id"]}: {decision.status}',flush=True)
            except Exception as exc:
                retry(job,exc,cfg)
                print(f'{tenant}/{job["ticket_id"]}: retry or dead letter ({type(exc).__name__})',flush=True)
        if not progressed:
            remaining=0
            for tenant in TENANTS:
                with session(tenant,cfg) as conn:
                    remaining+=conn.execute("SELECT count(*) AS n FROM jobs WHERE state IN ('ready','leased')").fetchone()['n']
            if not remaining: break
            time.sleep(1)

def resume(tenant,ticket_id,actor,cfg=None):
    """Explicit operator recovery; preserve previous usage and audit history."""
    identifier=run_id(); new_run(identifier,cfg)
    with session(tenant,cfg) as conn:
        ticket=conn.execute('SELECT status FROM tickets WHERE tenant=%s AND id=%s FOR UPDATE',(tenant,ticket_id)).fetchone()
        if not ticket or ticket['status'] not in ('queued','failed','held_budget'):
            raise ValueError('only unfinished, failed or held tickets can be resumed')
        conn.execute("UPDATE jobs SET state='ready',attempts=0,lease_token=NULL,lease_until=NULL,available_at=now(),run_id=%s WHERE tenant=%s AND ticket_id=%s",(identifier,tenant,ticket_id))
        conn.execute("UPDATE tickets SET status='queued' WHERE tenant=%s AND id=%s",(tenant,ticket_id))
        audit(conn,tenant,ticket_id,'operator_resume','explicit retry with preserved usage counters',actor)

def export(cfg=None):
    decisions=[]; messages=[]
    for tenant in TENANTS:
        with session(tenant,cfg) as conn:
            decisions.extend(r['record'] for r in conn.execute('SELECT record FROM decisions ORDER BY ticket_id'))
            messages.extend(dict(r) for r in conn.execute('SELECT tenant,ticket_id,text,approved_by,approved_at,idempotency_key FROM outbox ORDER BY ticket_id'))
    Path('out').mkdir(exist_ok=True)
    for name,rows in [('decisions',decisions),('outbox',messages)]:
        path=Path('out')/(name+'.jsonl')
        temporary=path.with_suffix('.tmp')
        temporary.write_text(''.join(json.dumps(row,default=str,ensure_ascii=False)+'\n' for row in rows),encoding='utf-8')
        temporary.replace(path)
