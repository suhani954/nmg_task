"""Explicit batch recovery after an operator stops all active workers."""
from relay.config import TENANTS
from relay.db import session
from relay.engine import resume

def main():
    pending=[]
    for tenant in TENANTS:
        with session(tenant) as conn:
            pending.extend((tenant,row['id']) for row in conn.execute("SELECT id FROM tickets WHERE status IN ('queued','failed','held_budget') AND id NOT LIKE 'eval:%'"))
    for tenant,identity in pending:
        resume(tenant,identity,'operator-batch-recovery')
    print('Resumed',len(pending),'unfinished tickets; usage counters preserved.')

if __name__=='__main__': main()
