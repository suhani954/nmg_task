# Isolated clean clone performance

Tested commit: 4d05d27211f95daf1c5a0058a6ff71b08e6b2a24.
Start: 2026-10-28T09:44:29.788143+00:00.
Finish: 2026-10-28T09:56:02.703020+00:00.

Full one-command demo: **692.91 seconds (11.55 minutes)**, below 15 minutes.
Processed 24 unique tickets with statuses {'pending_approval': 17, 'escalated': 7}; no failed/held tickets and no automatic approvals.

| Stage | Seconds |
|---|---:|
| database | 6.770 |
| virtual_environment | 13.572 |
| dependencies | 31.388 |
| migrations | 2.591 |
| embeddings | 46.045 |
| inboxes | 588.906 |
| approval_queue_northwind | 2.228 |
| approval_queue_harbor | 1.173 |

## Conditions

The clone, Python virtual environment and database volume were new. Model weights and the Docker image had been downloaded during allowed preflight, and pip reused cached packages. The database used a separate loopback port (5433), with matching connection URLs. No other worker or evaluation job ran concurrently. No decision cache, fixture-specific shortcut or fake model was used.

## Earlier measurement

The earlier full run took 1301.34 seconds while evaluation and another inbox worker ran simultaneously on an 8 GB laptop. That historical result remains in VALIDATION.md. The isolated run measures the demo on its own. Startup now prints and records each stage; pip version-update checking is disabled. The agent, approval and safety paths are unchanged.

## Reproduce

Complete the brief preflight, start Docker and Ollama, and run `python scripts/demo.py` from a fresh clone with an empty database. Do not start evaluation until the demo finishes. Read `tmp/demo-timing.json` for the measured stages. Timing depends on hardware and uncached download speeds; this measurement is not a guarantee for every machine.
