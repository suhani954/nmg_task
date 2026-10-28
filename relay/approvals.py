from psycopg.types.json import Jsonb
from .db import session,audit
from .contracts import Ticket, DraftResult, Passage
from .checker import check_database
from .engine import case

def list_pending(tenant,cfg=None,ticket_id=None):
    with session(tenant,cfg) as conn:
        return conn.execute("SELECT ticket_id,revision,text,kb_refs,created_at FROM approvals WHERE state='pending' AND (%s::text IS NULL OR ticket_id=%s) ORDER BY created_at",(ticket_id,ticket_id)).fetchall()

def decide(tenant,ticket_id,actor,approve,reason=None,cfg=None):
    if not actor.strip(): raise ValueError('approver is required')
    if not approve and not (reason and reason.strip()): raise ValueError('rejection reason is required')
    # All approval mutations lock the ticket first, serializing repeated approvals.
    with session(tenant,cfg) as conn:
        stored=conn.execute('SELECT * FROM tickets WHERE tenant=%s AND id=%s FOR UPDATE',(tenant,ticket_id)).fetchone()
        if not stored: raise ValueError('unknown ticket')
        approval=conn.execute("SELECT * FROM approvals WHERE tenant=%s AND ticket_id=%s AND state='pending' ORDER BY revision DESC LIMIT 1 FOR UPDATE",(tenant,ticket_id)).fetchone()
        if not approval:
            existing=conn.execute('SELECT ticket_id FROM outbox WHERE tenant=%s AND ticket_id=%s',(tenant,ticket_id)).fetchone()
            if existing and approve: return 'already approved'
            raise ValueError('no pending approval')
        if approve:
            ticket=Ticket.model_validate(stored['payload'])
            candidate=DraftResult(text=approval['text'],kb_refs=approval['kb_refs'])
            passages=[Passage(kb_id=ref,text='',score=1) for ref in candidate.kb_refs]
            failures=check_database(ticket,candidate,passages,cfg)
            if failures: raise ValueError('approval blocked by checker: '+','.join(failures))
            conn.execute('INSERT INTO outbox(tenant,ticket_id,text,approved_by,idempotency_key) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                         (tenant,ticket_id,approval['text'],actor,tenant+':'+ticket_id))
            new_state='approved'
            conn.execute("UPDATE tickets SET status='approved' WHERE tenant=%s AND id=%s",(tenant,ticket_id))
        else:
            new_state='rejected'
            if approval['revision']==0:
                conn.execute("UPDATE tickets SET status='queued',revision=revision+1 WHERE tenant=%s AND id=%s",(tenant,ticket_id))
                conn.execute("UPDATE jobs SET state='ready',attempts=0,lease_token=NULL,available_at=now() WHERE tenant=%s AND ticket_id=%s",(tenant,ticket_id))
            else:
                case(conn,Ticket.model_validate(stored['payload']),'high','draft_rejected_twice')
                conn.execute("UPDATE tickets SET status='escalated' WHERE tenant=%s AND id=%s",(tenant,ticket_id))
        conn.execute('UPDATE approvals SET state=%s,feedback=%s,decided_by=%s,decided_at=now() WHERE tenant=%s AND ticket_id=%s AND revision=%s',
                     (new_state,reason,actor,tenant,ticket_id,approval['revision']))
        audit(conn,tenant,ticket_id,new_state,'human approval' if approve else reason,actor)
    return new_state
