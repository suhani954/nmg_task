# Runbook

## Ollama unavailable

Start Ollama and check `ollama list`. Verify `OLLAMA_URL`, normally `http://localhost:11434`. Run `python -m relay worker` after restoring service. Transient model failures retry with backoff; exhausted attempts create a case. Inspect `model_calls.error` and `cases` without exposing raw ticket bodies. A dead-letter ticket needs deliberate operator remediation, not repeated inbox ingestion.

## Worker dies

Restart `python -m relay worker`. An outstanding lease expires after LEASE_SECONDS (600 by default); another worker reclaims it. Stale workers cannot commit because their lease token no longer matches. Duplicate model computation can consume tokens, but cannot create a second outbox row. Do not shorten a live lease below the maximum possible ticket processing time.

## Budget exhausted

The decision is held_budget and no approval exists. Review actual usage and retained reservations from failed calls. Increasing environment variables alone does not modify a stored run's limit. An operator must create a new run and explicitly requeue held jobs with an audited database operation; automatic budget resume is not implemented. Never bypass approval to clear a queue.

## Database unavailable

Start Docker Desktop, then `docker compose up -d --wait`. Check `docker compose logs db` and the configured URL. The brief's standalone preflight container is named relay-pg and is reused by the demo if it is already running. Database failure aborts the command: no successful persistence or customer send is claimed. Restore connectivity and run the worker again.

## Draft rejected

Use `python -m relay reject --tenant northwind TICKET --by operator --reason "Explain the policy more clearly"`, then `python -m relay worker`. The first rejection schedules one redraft incorporating the feedback. Another rejection opens a human case. Human reasons are stored as audit data; use operational feedback, never secrets or internal policy text.

## Review and approve

`python -m relay list --tenant northwind` lists pending drafts. `python -m relay show --tenant northwind TICKET` shows one. `python -m relay approve --tenant northwind TICKET --by operator` rechecks the draft and atomically creates the outbox entry. No email or external delivery occurs. Repeat approval is safe and does not add another message.

## Tenant and rejection diagnostics

Unknown tenants and invalid inputs are counted in rejected_inputs with line number and a sanitized reason. The body is not copied into a default tenant. Do not troubleshoot by switching to superuser application credentials: that invalidates isolation.
