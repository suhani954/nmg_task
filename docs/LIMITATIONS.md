# Limitations

This is a local assessment prototype, not a production support service. Read EVAL.md for actual measured errors and VALIDATION.md for what was run successfully.

- Small-model triage can misclassify categories and priorities. Unsupported `other` requests now escalate, except narrowly recognized acknowledgments or questions with direct coverage in the top public passage. Incorrect classification into a supported category can still bypass that fallback; lexical coverage is not a general semantic proof.
- Latest measured errors and provenance are in EVAL.md. The original baseline, including its false positives and two database connection failures, remains unchanged in eval/baseline-adb61a5. A subsequent deterministic routing fallback may be replayed over real inference artifacts; that is disclosed and never counted as additional fresh model runs.
- Factual replies are extractive. The drafter proposes text and evidence IDs, but a deterministic renderer composes the final facts from retrieved public policy. This avoids the invented requirements observed in an initial real draft, at the cost of sometimes including irrelevant policy sentences. Rejection feedback may not change wording much.
- The deterministic checker catches known language, IDs and copied fragments. It is not a general semantic proof of grounding, clinical safety or absence of every possible private identifier. Canary detection handles the literal marker, not every encoded leak.
- Clinical tickets create cases; no automatic clinical or emergency reply is produced. A human must contact the patient. This is a conservative but incomplete interpretation of the severe-symptom requirement.
- The operator CLI has no authentication layer. A future tenant portal must derive tenant identity from trusted credentials, not a caller-selected command argument.
- The trusted checker reads forbidden seeded policy fingerprints for leak detection. Tenant retrieval and all model drafting contexts remain isolated. Replace this local seed-file mechanism with a dedicated security service before expanding access.
- Retries can duplicate model computation and token consumption. Outbox uniqueness is a database guarantee; actual external email delivery is not implemented.
- Export replaces files atomically but assumes one operator exporter at a time. Do not concurrently run multiple export commands into the same directory.
- Reserved usage on uncertain provider failures is retained. Operator resume preserves cumulative ticket consumption and needs sufficient budget; it does not silently erase usage.
- Stale cases from superseded failed attempts remain as historical records. There is no case-closing workflow or human-authored response UI.
- Tests use fake models and a separate temporary real Postgres database. They need Postgres, but never Ollama. Database-unavailable integration tests skip; the CI service supplies it.
- Fresh-clone dependencies and images require internet on first setup. Ticket processing itself uses local Ollama and Postgres only.
- No circuit breaker, chaos mode, secondary provider, reports, production authentication or cloud deployment is included.

With one more day: add data-driven coverage verification, extractive sentence selection, a broader adversarial/benign injection set, stronger clinical/identifier checks, transactional tenant-scoped export jobs, audited case resolution, a real worker-kill integration test and a more polished review interface. Benchmark model choices against the hardware before making quality or latency claims.
