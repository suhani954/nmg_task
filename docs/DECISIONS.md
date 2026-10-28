# Decisions

1. **Explicit Python orchestration over an agent framework.** The alternative was LangGraph or CrewAI. Explicit contracts and transactions make leases, retries and human resume easier to inspect within four hours.
2. **Postgres is the source of truth.** The alternative was writing JSONL as tickets complete. Unique database keys and atomic exports avoid duplicate decisions and outbox rows after restart.
3. **RLS plus an application tenant allowlist.** The alternative was application WHERE filters alone. RLS fails closed even when a developer forgets a filter. The administrator connection is reserved for migrations; application operations use a restricted role.
4. **No internal article in drafting context.** The alternative was retrieving all articles and relying on prompt instructions. Exclusion removes an avoidable leak path; checker rules add another barrier.
5. **Small triage model and existing llama3.2:3b drafter.** The alternative was downloading qwen2.5:3b. The brief permits open-weight substitutes; reusing the installed drafting model reduces setup bandwidth. A larger model could improve semantic accuracy but consumes more memory.
6. **Conservative token reservations before inference.** The alternative was counting only after calls. Reservation may hold a ticket whose actual usage would fit, but avoids knowingly launching an unbounded call. Usage counters remain the provider's real counts.
7. **Clinical escalation without an automatic clinical response.** The brief says clinical tickets escalate and also says severe symptoms should receive emergency guidance. We prioritize escalation, put clinical routing into the human case, and require a human to provide any emergency guidance. The current automated outbox does not cover that special human-authored response.
8. **One redraft after rejection.** The alternative was unlimited model revision. One retry keeps the cost and review loop bounded; a second rejection creates a human case.
9. **Policy explanation, not transaction execution.** The seed data has no order system, insurer list or appointment availability API. Replies must not claim a pincode changed, refund was issued, insurer is accepted, or appointment was moved. A general explanation may still match a golden draft label while exposing these limits.
10. **Decision snapshots and separate approval states.** Appendix B permits only pending_approval, escalated, held_budget and failed. The richer approval lifecycle is stored in database state and audit records instead of adding unsupported output statuses.
11. **Unknown tenant rejection outside decisions.** Its invalid tenant cannot satisfy the ticket schema and there is no rejected status in Appendix B. We store a sanitized rejection record, not a fabricated decision under a known tenant.
12. **Trusted checker can compare forbidden seed fingerprints.** The alternative was checking only other-tenant prefixes. Fingerprints catch a class of uncited copied policy leaks. They are trusted security configuration, never retrieval results or model context; this distinction is a limitation to revisit for a larger tenant fleet.

## Scaling to 50 tenants

Use a managed PostgreSQL service with pgvector, connection pooling and least-privilege migration credentials. Run stateless workers separately from a private inference server, centralize budgets and lease monitoring, and add tenant-authenticated APIs with per-tenant export destinations. Larger tenants may need dedicated databases and model queues. Keep a paid hosted model outside the graded route.

Hosting choice and cost would depend on concurrency, ticket volume, retention and latency requirements. No current cloud quote was obtained during this assessment; a dollar estimate without those assumptions would be misleading. Obtain quotes after measuring CPU/GPU throughput and database size. S4's rough priced hosting estimate is therefore partial.
