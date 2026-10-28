import json
import uuid
import pytest
import psycopg
from relay.config import Config
from relay.db import session,new_run
from relay.engine import ingest,claim,process,export,retry
from relay.approvals import decide,list_pending
from relay.gateway import Gateway,BudgetExceeded,InvalidModelOutput
from relay.contracts import TriageResult,DraftResult

class FakeGateway(Gateway):
    def structured(self,task,system,user,contract):
        self._reserve(100)
        self._record(task,'fake-test',100,{'prompt_eval_count':10,'eval_count':5},1)
        if task=='triage':
            return TriageResult(category='shipping_delivery',priority='normal',action='draft_reply',injection_detected=False,reason='ordinary shipping',missing_details=[])
        return DraftResult(text='Standard delivery takes 4 to 6 business days in metro cities (NW-KB-02).',kb_refs=['NW-KB-02'])
    def embed(self,text):
        self._reserve(100); self._record('embedding','fake-embed',100,{'prompt_eval_count':5},1)
        return [1.0]+[0.0]*767

def add_ticket(tmp_path,cfg):
    identity='test-'+uuid.uuid4().hex
    path=tmp_path/'tickets.jsonl'
    path.write_text(json.dumps(dict(id=identity,tenant='northwind',customer_ref='C-4321',subject='Shipping',body='Delivery policy please',received_at='2026-10-28T10:00:00Z'))+'\n')
    run='test-'+uuid.uuid4().hex
    assert ingest([path],run,cfg)==1
    return path,identity,run

def test_rls_fail_closed_and_cross_tenant(db_cfg):
    with session(cfg=db_cfg) as conn:
        assert conn.execute('SELECT count(*) AS n FROM kb').fetchone()['n']==0
        role=conn.execute('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone()
        assert not role['rolsuper'] and not role['rolbypassrls']
    with session('northwind',db_cfg) as conn:
        assert conn.execute("SELECT count(*) AS n FROM kb WHERE tenant='harbor'").fetchone()['n']==0
        assert conn.execute('SELECT count(*) AS n FROM kb').fetchone()['n']==7
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("INSERT INTO kb SELECT 'harbor','invalid','x','x',false,embedding FROM kb LIMIT 1")
    with session(cfg=db_cfg) as conn:
        assert conn.execute('SELECT count(*) AS n FROM kb').fetchone()['n']==0
    with pytest.raises(ValueError):
        with session('unknown',db_cfg): pass

def test_idempotency_and_exactly_once_approval(tmp_path,db_cfg):
    path,identity,run=add_ticket(tmp_path,db_cfg)
    assert ingest([path],run,db_cfg)==0
    job=claim('northwind',db_cfg)
    result=process(job,db_cfg,FakeGateway)
    assert result.status=='pending_approval'
    assert len(list_pending('northwind',db_cfg,identity))==1
    assert decide('northwind',identity,'tester',True,cfg=db_cfg)=='approved'
    assert decide('northwind',identity,'tester',True,cfg=db_cfg)=='already approved'
    with session('northwind',db_cfg) as conn:
        assert conn.execute('SELECT count(*) AS n FROM outbox WHERE ticket_id=%s',(identity,)).fetchone()['n']==1
        assert conn.execute("SELECT count(*) AS n FROM audit WHERE ticket_id=%s AND event='approved'",(identity,)).fetchone()['n']==1

def test_reject_once_then_case(tmp_path,db_cfg):
    _,identity,_=add_ticket(tmp_path,db_cfg)
    process(claim('northwind',db_cfg),db_cfg,FakeGateway)
    with pytest.raises(ValueError): decide('northwind',identity,'tester',False,cfg=db_cfg)
    decide('northwind',identity,'tester',False,'Use clearer wording',db_cfg)
    process(claim('northwind',db_cfg),db_cfg,FakeGateway)
    decide('northwind',identity,'tester',False,'Still unclear',db_cfg)
    with session('northwind',db_cfg) as conn:
        assert conn.execute('SELECT reason FROM cases WHERE ticket_id=%s',(identity,)).fetchone()['reason']=='draft_rejected_twice'
        assert conn.execute('SELECT count(*) AS n FROM outbox WHERE ticket_id=%s',(identity,)).fetchone()['n']==0

def test_budget_holds_ticket(tmp_path,db_cfg):
    _,identity,_=add_ticket(tmp_path,db_cfg)
    cfg=Config(**{**db_cfg.__dict__,'ticket_budget':1})
    result=process(claim('northwind',cfg),cfg,FakeGateway)
    assert result.status=='held_budget'
    with session('northwind',cfg) as conn:
        assert conn.execute('SELECT count(*) AS n FROM approvals WHERE ticket_id=%s',(identity,)).fetchone()['n']==0

def test_lease_recovery_and_fencing(tmp_path,db_cfg):
    _,identity,_=add_ticket(tmp_path,db_cfg)
    old=claim('northwind',db_cfg)
    with session('northwind',db_cfg) as conn:
        conn.execute("UPDATE jobs SET lease_until=now()-interval '1 second' WHERE id=%s",(old['id'],))
    new=claim('northwind',db_cfg)
    assert new['lease_token']!=old['lease_token']
    assert process(old,db_cfg,FakeGateway) is None
    assert process(new,db_cfg,FakeGateway).status=='pending_approval'

def test_unknown_tenant_rejected(tmp_path,db_cfg):
    path=tmp_path/'unknown.jsonl'
    path.write_text(json.dumps(dict(id='unknown',tenant='not-a-client',customer_ref='x',subject='x',body='',received_at='2026-10-28T10:00:00Z')))
    run='reject-'+uuid.uuid4().hex
    assert ingest([path],run,db_cfg)==0
    with session(cfg=db_cfg) as conn:
        assert conn.execute('SELECT count(*) AS n FROM rejected_inputs WHERE run_id=%s',(run,)).fetchone()['n']==1

def test_structured_output_one_repair_then_classified_failure(monkeypatch,db_cfg):
    run='repair-'+uuid.uuid4().hex; new_run(run,db_cfg)
    gateway=Gateway('northwind',None,run,db_cfg); calls=[]
    def invalid(*args): calls.append(args); return {'message':{'content':'not json'}}
    monkeypatch.setattr(gateway,'_request',invalid)
    with pytest.raises(InvalidModelOutput): gateway.structured('triage','system','ticket',TriageResult)
    assert len(calls)==2
