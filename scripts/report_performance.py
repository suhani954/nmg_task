"""Preserve raw demo timing and generate a report from an actual clean run."""
import argparse
import json
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from relay.contracts import DecisionRecord
from relay.db import load_jsonl

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('clone',type=Path)
    args=parser.parse_args()
    clone=args.clone.resolve()
    timing_path=clone/'tmp/demo-timing.json'
    timing=json.loads(timing_path.read_text(encoding='utf-8'))
    assert timing['success'] and all(s['success'] for s in timing['stages'])
    assert any(s['name']=='virtual_environment' for s in timing['stages']),'must use a new virtual environment'
    assert timing['total_seconds']<900,'15-minute target not achieved'
    rows=list(load_jsonl(clone/'out/decisions.jsonl'))
    assert len(rows)==24 and len({(r['tenant'],r['ticket_id']) for r in rows})==24
    for row in rows: DecisionRecord.model_validate(row)
    assert not any(r['status'] in ('failed','held_budget') for r in rows)
    assert not list(load_jsonl(clone/'out/outbox.jsonl')),'demo must not approve automatically'
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=clone,text=True).strip()
    Path('benchmarks').mkdir(exist_ok=True)
    shutil.copyfile(timing_path,'benchmarks/clean-clone-timing.json')
    seconds=timing['total_seconds']
    summary={'tested_commit':sha,'total_seconds':seconds,'decisions':len(rows),
             'statuses':dict(Counter(r['status'] for r in rows)),
             'automatic_approvals':0,'within_15_minutes':True,
             'conditions':['new Git clone','new virtual environment','new empty Docker volume',
                           'models and Docker image already downloaded','pip package cache available',
                           'no simultaneous evaluation or other workers']}
    Path('benchmarks/clean-clone-summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    lines=['# Isolated clean clone performance','',
           f'Tested commit: {sha}.',f'Start: {timing["started_at"]}.',f'Finish: {timing["finished_at"]}.','',
           f'Full one-command demo: **{seconds:.2f} seconds ({seconds/60:.2f} minutes)**, below 15 minutes.',
           f'Processed {len(rows)} unique tickets with statuses {summary["statuses"]}; no failed/held tickets and no automatic approvals.','',
           '| Stage | Seconds |','|---|---:|']
    lines.extend(f'| {s["name"]} | {s["seconds"]:.3f} |' for s in timing['stages'])
    lines += ['', '## Conditions','',
              'The clone, Python virtual environment and database volume were new. Model weights and the Docker image had been downloaded during allowed preflight, and pip reused cached packages. The database used a separate loopback port (5433), with matching connection URLs. No other worker or evaluation job ran concurrently. No decision cache, fixture-specific shortcut or fake model was used.',
              '', '## Earlier measurement','',
              'The earlier full run took 1301.34 seconds while evaluation and another inbox worker ran simultaneously on an 8 GB laptop. That historical result remains in VALIDATION.md. The isolated run measures the demo on its own. Startup now prints and records each stage; pip version-update checking is disabled. The agent, approval and safety paths are unchanged.',
              '', '## Reproduce','',
              'Complete the brief preflight, start Docker and Ollama, and run `python scripts/demo.py` from a fresh clone with an empty database. Do not start evaluation until the demo finishes. Read `tmp/demo-timing.json` for the measured stages. Timing depends on hardware and uncached download speeds; this measurement is not a guarantee for every machine.']
    Path('docs/PERFORMANCE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__=='__main__': main()
