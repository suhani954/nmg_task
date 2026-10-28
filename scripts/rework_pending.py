"""Invalidate pre-renderer drafts without pretending a human rejected them."""
from relay.config import TENANTS
from relay.db import session,audit
from relay.engine import resume

def main():
    work=[]
    for tenant in TENANTS:
        with session(tenant) as conn:
            rows=conn.execute("SELECT id FROM tickets WHERE status='pending_approval' FOR UPDATE").fetchall()
            for row in rows:
                identity=row['id']
                conn.execute("UPDATE approvals SET state='superseded' WHERE tenant=%s AND ticket_id=%s AND state='pending'",(tenant,identity))
                conn.execute("UPDATE tickets SET status='failed',revision=revision+1 WHERE tenant=%s AND id=%s",(tenant,identity))
                audit(conn,tenant,identity,'draft_superseded','grounded renderer replaces unsupported model prose','automated-quality-review')
                work.append((tenant,identity))
    print('Superseded',len(work),'drafts. Run scripts.resume_unfinished next. Previous history retained.')

if __name__=='__main__': main()
