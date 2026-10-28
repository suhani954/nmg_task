# Project Relay

A local support desk for Northwind Cycles and Harbor Dental. Model outputs are proposals; tenant isolation, safety checks and human approval are enforced in code and PostgreSQL.

Build started 2026-10-28 13:53:29 IST. Setup and model downloads preceded the first commit.

## Build plan

1. Database, transaction-bound row-level security, exact seed data and vector retrieval.
2. Typed triage, retrieval and drafting handoffs; deterministic checker and approval CLI.
3. Durable queue, metered gateway, budgets, tests and actual evaluation.
4. Reproduction check, operating documentation and submission artifacts.

## Assumptions

- The supplied llama3.2:3b model substitutes for qwen2.5:3b for drafting; qwen2.5:1.5b handles triage.
- Clinical requests always escalate. No automated clinical draft is produced, including emergency guidance; the human case records the emergency routing requirement.
- A second rejection opens a human case.
- Database approval states are separate from the initial decision snapshot required by Appendix B.
- An ordinary thank-you can receive a short acknowledgment without a KB citation.
- Unknown tenants are recorded in a separate sanitized rejection log, never processed with a default tenant.

Implementation status and measured results will be updated before submission.
