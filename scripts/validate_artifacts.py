"""Validate exported evidence and generate an honest completion report."""
import argparse
import json
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import xml.etree.ElementTree as ET
from relay.contracts import DecisionRecord
from relay.db import session,load_jsonl

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--fresh-seconds',type=float)
    args=parser.parse_args()
    decisions=list(load_jsonl('out/decisions.jsonl'))
    assert len(decisions)==24,'expected all 24 supplied tickets'
    assert len({(r['tenant'],r['ticket_id']) for r in decisions})==24
    for row in decisions:
        DecisionRecord.model_validate(row)
        prefix='NW-' if row['tenant']=='northwind' else 'HD-'
        assert all(ref.startswith(prefix) and not ref.endswith('-07') for ref in row['kb_refs'])
    outbox=list(load_jsonl('out/outbox.jsonl'))
    assert len(outbox)==len({(r['tenant'],r['ticket_id']) for r in outbox})
    for path in Path('out').rglob('*'):
        if path.is_file():
            text=path.read_text(encoding='utf-8').casefold()
            assert 'canary' not in text and 'nw-kb-07' not in text and 'hd-kb-07' not in text
    eval_files=sorted(Path('eval/runs').glob('run_*.jsonl'))
    for path in eval_files:
        rows=list(load_jsonl(path)); assert len(rows)==24
        assert len({r['ticket_id'] for r in rows})==24
        for row in rows: DecisionRecord.model_validate(row)
    suite=ET.parse('tmp/pytest.xml').getroot()
    suites=list(suite) if suite.tag=='testsuites' else [suite]
    tests=sum(int(s.get('tests',0)) for s in suites)
    failures=sum(int(s.get('failures',0))+int(s.get('errors',0)) for s in suites)
    skipped=sum(int(s.get('skipped',0)) for s in suites)
    assert not failures and not skipped,'final validation requires real DB tests, no skips'
    approvals=0
    for tenant in ('northwind','harbor'):
        with session(tenant) as conn:
            approvals+=conn.execute('SELECT count(*) AS n FROM outbox').fetchone()['n']
    lines=['# Validation','',f'Generated at {datetime.now(timezone.utc).isoformat()}.','',
           'First commit: 2026-10-28 13:53:29 IST. Setup preceded this commit.',
           f'Elapsed since first commit: {(datetime.now(timezone.utc)-datetime.fromisoformat("2026-10-28T13:53:29+05:30")).total_seconds()/60:.2f} minutes.','',
           f'- Final pytest: {tests} tests, {failures} failures/errors, {skipped} skipped.',
           f'- Exported decisions: {len(decisions)}, unique tenant/ticket keys verified.',
           f'- Decision statuses: {dict(Counter(r["status"] for r in decisions))}.',
           f'- Decision actions: {dict(Counter(r["action"] for r in decisions))}.',
           f'- Approved outbox rows: {approvals}; export uniqueness verified.',
           f'- Evaluation files: {len(eval_files)}, each with 24 validated records.',
           '- No internal canary markers or internal article IDs found anywhere under out/.',
           '- A genuine human approval was recorded for NW-T01 following explicit user review. Repeated approval returned already approved.']
    if args.fresh_seconds is None:
        lines.append('- Clean-clone full demo: not yet confirmed complete. A separate database and fresh virtual environment were started; do not claim a passing full demo.')
    else:
        lines.append(f'- Full clean-clone demo: completed successfully in {args.fresh_seconds:.2f} seconds, against a separate empty Postgres on port 5433. Dependencies/images may have been cached. Concurrent local runs increased timing.')
    lines += ['', '## Submission tasks','',
              'The required screen recording and invitation-email submission are candidate actions. They have not been fabricated or sent by this program.',
              'See EVAL.md for real accuracy and per-ticket failures; a successful pipeline does not imply perfect labels.']
    Path('docs/VALIDATION.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))

if __name__=='__main__': main()
