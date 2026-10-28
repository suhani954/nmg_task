import json
from pathlib import Path
from .db import session, new_run, load_jsonl
from .config import TENANTS
from .gateway import Gateway
from .contracts import Passage

def seed(cfg=None):
    run_id = 'seed-v1'
    new_run(run_id,cfg)
    for tenant in TENANTS:
        gateway = Gateway(tenant,None,run_id,cfg)
        for article in load_jsonl(Path('data')/tenant/'kb.jsonl'):
            with session(tenant,cfg) as conn:
                exists = conn.execute('SELECT id FROM kb WHERE id=%s',(article['id'],)).fetchone()
            if exists:
                continue
            vector = gateway.embed(article['title']+'\n'+article['body'])
            with session(tenant,cfg) as conn:
                conn.execute('INSERT INTO kb(tenant,id,title,body,internal,embedding) VALUES (%s,%s,%s,%s,%s,%s::vector) ON CONFLICT DO NOTHING',
                             (tenant,article['id'],article['title'],article['body'],article['internal'],json.dumps(vector)))

def retrieve(ticket, gateway, cfg=None):
    vector = gateway.embed(ticket.subject+'\n'+ticket.body)
    with session(ticket.tenant,cfg) as conn:
        # RLS enforces the tenant. Internal text never enters a drafter context.
        rows = conn.execute('SELECT id,title,body,1-(embedding <=> %s::vector) AS score FROM kb WHERE NOT internal ORDER BY embedding <=> %s::vector LIMIT 3',
                            (json.dumps(vector),json.dumps(vector))).fetchall()
    return [Passage(kb_id=r['id'],text=r['title']+': '+r['body'],score=r['score']) for r in rows]
