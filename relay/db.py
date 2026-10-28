import json
from contextlib import contextmanager
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from .config import Config, TENANTS

@contextmanager
def session(tenant=None, cfg=None):
    cfg = cfg or Config()
    if tenant is not None and tenant not in TENANTS:
        raise ValueError('unknown tenant')
    with psycopg.connect(cfg.database_url, row_factory=dict_row, connect_timeout=10) as conn:
        if tenant:
            conn.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant,))
        yield conn

def migrate(cfg=None):
    cfg = cfg or Config()
    with psycopg.connect(cfg.admin_url, connect_timeout=10) as conn:
        conn.execute(Path(__file__).with_name('schema.sql').read_text())

def audit(conn, tenant, ticket_id, event, reason, actor='worker'):
    conn.execute('INSERT INTO audit(tenant,ticket_id,actor,event,reason) VALUES (%s,%s,%s,%s,%s)',
                 (tenant,ticket_id,actor,event,reason))

def new_run(run_id, cfg=None):
    cfg = cfg or Config()
    with session(cfg=cfg) as conn:
        conn.execute('INSERT INTO runs(id,token_limit) VALUES (%s,%s) ON CONFLICT DO NOTHING', (run_id,cfg.run_budget))

def load_jsonl(path):
    with Path(path).open(encoding='utf-8') as file:
        for line in file:
            if line.strip():
                yield json.loads(line)

def save_decision(conn, decision):
    conn.execute('INSERT INTO decisions VALUES (%s,%s,%s) ON CONFLICT (tenant,ticket_id) DO UPDATE SET record=excluded.record',
                 (decision.tenant,decision.ticket_id,Jsonb(decision.model_dump())))
