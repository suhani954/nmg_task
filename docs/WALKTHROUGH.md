# Walkthrough guide

This guide explains the actual implementation. Read the linked modules and trace a ticket before presenting it. Do not claim you independently wrote code you have not reviewed; AI assistance is declared in AI_USAGE.md.

## Explain the project in thirty seconds

Project Relay is a local multi-tenant support desk. It classifies tickets, retrieves the current company's public policies with vector search, drafts a supported response, checks it with deterministic rules and waits for a human. Approved messages go into a local outbox exactly once. Clinical issues, disputed money, unsupported requests and prompt injection create human cases.

## Why several agents

An agent here is a component with a narrow job and a typed contract, not an autonomous personality. Triage sees only ticket text and returns TriageResult. Retrieval returns Passage objects from a tenant-bound database session. Drafting receives only public retrieved context and returns DraftResult. The lead in engine.py decides the sequence and persists the final DecisionRecord. The checker has no model. The human approver is a CLI operation.

Why not one large prompt? Separate contracts limit context, expose failures and make each boundary independently testable. A model cannot approve its own message or choose a database tenant.

## Trace one ticket in the code

1. __main__.py parses the command. engine.ingest validates each JSONL row with Ticket, then inserts the ticket, job and audit event in one transaction. An existing (tenant,id) is ignored.
2. engine.claim selects one available job with FOR UPDATE SKIP LOCKED, increments attempts and stores a lease token and expiry. It commits before inference, so model calls do not hold row locks.
3. engine.process loads the ticket, calls agents.triage, then retrieval.retrieve and agents.route. Triage never sees KB text. Retrieval embeds the query, searches vector(768) with cosine distance and excludes internal articles.
4. An escalation creates a case. Otherwise agents.draft returns structured text and citation IDs. The checker rejects unsafe text before any approval row exists.
5. Completion locks the job and verifies its lease token. If another worker reclaimed it, the stale result is discarded. Otherwise it stores the decision, approval or case and audit event atomically.
6. approvals.decide locks the ticket and pending draft. Approval rechecks the text and writes the unique outbox row in the same transaction as the approval audit event. Repeating approval returns already approved.
7. engine.export regenerates JSONL snapshots from database rows using a temporary file and atomic replacement.

## Explain retrieval

The embedding model maps text to 768 numbers. Related questions and policies should have similar vectors. pgvector orders the current tenant's public articles by cosine distance, and the drafter sees the top three. Similarity is not proof that a policy supports every claim. The model is instructed to use only the passages; current deterministic checking validates citations and known safety patterns but does not prove semantic entailment.

## Explain tenant isolation

Python validates the tenant allowlist. db.session opens a transaction as relay_app and sets app.tenant_id locally for that transaction. PostgreSQL policies compare every row's tenant against that setting for both reads and writes. Missing context sees zero rows. FORCE RLS and a non-superuser role prevent accidental owner/superuser bypass on the application path. Tests deliberately query Harbor from Northwind and attempt a cross-tenant insert.

Important limitation: the CLI is a trusted operator tool with access to select either tenant. RLS does not replace authentication for a future multi-user web application. Combined submission exports are internal operator artifacts, not tenant client views.

## Explain exactly once

The system does not claim exactly-once model inference: a crash can cause another inference call. It guarantees at most one outbox row per tenant/ticket through a primary key, a unique idempotency key and a transaction that includes approval state and audit. There is no actual email sender. A future external delivery service would need its own idempotency protocol.

## Explain leases and retries

A lease is temporary ownership of work. It expires if a worker dies. SKIP LOCKED lets another worker take different work instead of waiting. A random lease token fences off stale workers. Provider failures retry with exponential delay plus jitter, up to the configured attempts, then become a case. Operator resume is explicit and audited; repeated inbox ingestion alone does not reset failed tickets or budgets.

## Explain budgets and metrics

gateway.py is the only module contacting Ollama. It records actual prompt_eval_count, eval_count, model and elapsed milliseconds. Before inference it atomically reserves a conservative token allowance against the run and ticket. It reconciles successful calls to actual counters; uncertain failed calls keep their reservation. Budget exhaustion holds the ticket and does not produce an approval. Embeddings are also metered. Seed embedding usage is a separate run.

## Explain safety honestly

Prompt injection is assessed semantically by triage and supplemented by deterministic override patterns. The ticket is always untrusted data, never a source of system instructions. Detected attacks escalate. Internal documents are excluded from drafter context. The checker blocks invalid or private citations, canary markers, matching forbidden fragments, other-company names/content, unexpected customer IDs, clinical language and long drafts. These are practical barriers, not a proof against every attack or hallucination.

## Explain evaluation

Only evaluation.py reads golden.jsonl. The decision path never imports golden answers or ticket-specific labels. Evaluation reruns triage, retrieval and routing with real Ollama calls, then compares predictions with labels. It measures action/category accuracy, injection recall and false positives, action stability, tokens, time and per-ticket differences. Draft generation is outside evaluation scope, so show actual inbox output separately when discussing draft safety.

## Decisions to be ready to defend

- Plain Python instead of an agent framework: visible contracts and transactions within the time box.
- A smaller drafting model on an 8 GB laptop: less memory pressure, measured quality trade-off.
- No automatic order changes or patient-record delivery: there are no authoritative operational APIs in the brief.
- One redraft after rejection: bounded review/cost loop, then a human case.
- Clinical escalation with no automatic clinical response: conservative interpretation of the brief's competing instructions.
- Honest failures and incomplete features: status table and limitations matter more than unsupported claims.

## Practice questions

1. What happens if the worker dies after generating a draft but before committing it?
2. What happens if approve is called twice or two operators approve concurrently?
3. Why does a missing tenant setting return no rows?
4. How do you stop an expired worker from overwriting a newer result?
5. Why is a valid citation insufficient to prove the entire reply is true?
6. What does the model see at each stage, and where is human approval enforced?
7. How would you add real external message delivery without duplicate sends?

Answer these by locating the relevant transaction and database constraint in the code, not by memorizing this guide.
