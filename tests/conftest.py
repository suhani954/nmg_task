import uuid
import pytest
import psycopg
from psycopg.types.json import Jsonb
from relay.config import Config
from relay.db import migrate,session,load_jsonl

@pytest.fixture(scope='session')
def db_cfg():
    cfg=Config()
    database='relay_test_'+uuid.uuid4().hex[:12]
    try:
        admin=psycopg.connect(cfg.admin_url,autocommit=True,connect_timeout=5)
    except psycopg.OperationalError:
        pytest.skip('PostgreSQL required for integration tests; no Ollama required')
    from psycopg import sql
    admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database)))
    base=Config(database_url=cfg.database_url.rsplit('/',1)[0]+'/'+database,admin_url=cfg.admin_url.rsplit('/',1)[0]+'/'+database)
    migrate(base)
    for tenant in ('northwind','harbor'):
        with session(tenant,base) as conn:
            for row in load_jsonl(f'data/{tenant}/kb.jsonl'):
                conn.execute('INSERT INTO kb VALUES (%s,%s,%s,%s,%s,%s::vector)',(tenant,row['id'],row['title'],row['body'],row['internal'],str([1.0]+[0.0]*767)))
    yield base
    admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(database)))
    admin.close()
