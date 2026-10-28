"""Invalidate pre-renderer drafts without pretending a human rejected them."""
from relay.config import TENANTS
from relay.db import session,audit
import argparse

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--routing-only',action='store_true')
    args=parser.parse_args()
    work=[]
    for tenant in TENANTS:
        with session(tenant) as conn:
            if args.routing_only:
                rows=conn.execute("SELECT t.id,d.record FROM tickets t JOIN decisions d ON t.tenant=d.tenant AND t.id=d.ticket_id WHERE t.status IN ('pending_approval','escalated') FOR UPDATE OF t").fetchall()
                rows=[r for r in rows if r['record']['category'] in ('other','clinical') or r['record']['injection_detected']]
            else:
                rows=conn.execute("SELECT id FROM tickets WHERE status='pending_approval' FOR UPDATE").fetchall()
            for row in rows:
                identity=row['id']
                conn.execute("UPDATE approvals SET state='superseded' WHERE tenant=%s AND ticket_id=%s AND state='pending'",(tenant,identity))
                conn.execute("UPDATE tickets SET status='failed',revision=revision+1 WHERE tenant=%s AND id=%s",(tenant,identity))
                reason='routing policy revalidation' if args.routing_only else 'grounded renderer replaces unsupported model prose'
                event='routing_revalidation' if args.routing_only else 'draft_superseded'
                audit(conn,tenant,identity,event,reason,'automated-quality-review')
                work.append((tenant,identity))
    print('Marked',len(work),'tickets for revalidation. Run scripts.resume_unfinished next. Previous history retained.')

if __name__=='__main__': main()
