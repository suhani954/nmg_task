"""Apply a pure evidence-coverage rule to preserved real inference records.

This is explicitly a deterministic policy replay, not additional model runs.
It never reads golden labels; report generation alone compares predictions.
"""
import json
import re
import shutil
import time
from pathlib import Path
from relay.agents import refine_explicit_coverage
from relay.contracts import DecisionRecord,Ticket
from relay.db import load_jsonl,session
from relay.evaluation import write_report

def main():
    started=time.perf_counter()
    source=Path('tmp/routing-eval-v2')
    report=Path('tmp/ROUTING_EVAL_V2.md')
    inference_seconds=float(re.search(r'- Wall time: ([0-9.]+) seconds',report.read_text()).group(1))
    tickets={(r['tenant'],r['id']):Ticket.model_validate(r) for tenant in ('northwind','harbor') for r in load_jsonl(f'data/{tenant}/tickets.jsonl')}
    articles={}
    for tenant in ('northwind','harbor'):
        with session(tenant) as conn:
            articles[tenant]={r['id']:r['title']+': '+r['body'] for r in conn.execute('SELECT id,title,body FROM kb WHERE NOT internal')}
    raw=Path('eval/candidate-before-coverage'); raw.mkdir(parents=True,exist_ok=True)
    Path('eval/runs').mkdir(parents=True,exist_ok=True)
    all_runs=[]; changes=[]
    for number in range(1,4):
        path=source/f'run_{number}.jsonl'
        shutil.copyfile(path,raw/path.name)
        rows=list(load_jsonl(path)); assert len(rows)==24
        final=[]
        for row in rows:
            before=DecisionRecord.model_validate(row)
            texts=[articles[before.tenant][ref] for ref in before.kb_refs[:1]]
            after=refine_explicit_coverage(tickets[(before.tenant,before.ticket_id)],before,texts)
            if after.action!=before.action:
                assert before.status not in ('failed','held_budget')
                changes.append({'run':number,'ticket':before.ticket_id,'from':before.action,'to':after.action})
                after.status='pending_approval'
            final.append(after.model_dump())
        all_runs.append(final)
        (Path('eval/runs')/path.name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in final),encoding='utf-8')
    shutil.copyfile(report,raw/'EVAL.md')
    replay_seconds=time.perf_counter()-started
    note=('These three underlying inference runs used the same triage and injection-review prompts as the final code. '
          'A later deterministic explicit-public-coverage fallback was replayed over their typed decisions and original top public KB references. '
          'No model output was invented or counted as another run. Raw pre-refinement results are preserved in eval/candidate-before-coverage. '
          'Only report generation reads golden labels. The reported wall time is the measured inference phase; '
          f'the additional deterministic replay took {replay_seconds:.3f} seconds. '
          'Earlier baseline results remain in eval/baseline-adb61a5.')
    write_report(all_runs,inference_seconds,'docs/EVAL.md',note)
    Path('eval/routing-replay.json').write_text(json.dumps({'inference_runs':3,'additional_model_runs':0,'replay_seconds':replay_seconds,'changes':changes},indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'refined_decisions':changes,'replay_seconds':replay_seconds},indent=2))

if __name__=='__main__': main()
