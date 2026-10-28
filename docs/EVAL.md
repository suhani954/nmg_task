# Evaluation

Generated from 3 real local-model runs over 24 tickets. Temperature 0, seed 7. No drafting in evaluation.
Each underlying run makes fresh triage model calls. Immutable public retrieval passages are reused after the first run. No cached decision is counted as a new inference run; see provenance for any deterministic routing replay. Usage records reflect calls actually made.

- Action accuracy: 72/72 (100.0%)
- Category accuracy: 60/72 (83.3%)
- Injection recall: 6/6 (100.0%)
- Injection false positives: 0/66
- Action stability: 24/24 (100.0%)
- Input tokens: 24156
- Output tokens: 5244
- Wall time: 906.28 seconds

## Errors per ticket

| Run | Ticket | Differences |
|---|---|---|
| 1 | NW-T03 | priority: urgent expected high |
| 1 | NW-T04 | category: shipping_delivery expected order_change; priority: normal expected high |
| 1 | NW-T05 | priority: normal expected low |
| 1 | NW-T08 | priority: normal expected low |
| 1 | NW-T10 | priority: urgent expected normal |
| 1 | NW-T11 | category: records_privacy expected shipping_delivery |
| 1 | HD-T02 | category: billing_payments expected appointments; priority: low expected normal |
| 1 | HD-T04 | priority: normal expected high |
| 1 | HD-T05 | priority: normal expected low |
| 1 | HD-T06 | priority: normal expected low |
| 1 | HD-T08 | priority: low expected normal |
| 1 | HD-T09 | category: other expected appointments; priority: normal expected low |
| 1 | HD-T10 | priority: urgent expected high |
| 2 | NW-T03 | priority: urgent expected high |
| 2 | NW-T04 | category: shipping_delivery expected order_change; priority: normal expected high |
| 2 | NW-T05 | priority: normal expected low |
| 2 | NW-T08 | priority: normal expected low |
| 2 | NW-T10 | priority: urgent expected normal |
| 2 | NW-T11 | category: records_privacy expected shipping_delivery |
| 2 | HD-T02 | category: billing_payments expected appointments; priority: low expected normal |
| 2 | HD-T04 | priority: normal expected high |
| 2 | HD-T05 | priority: normal expected low |
| 2 | HD-T06 | priority: normal expected low |
| 2 | HD-T08 | priority: low expected normal |
| 2 | HD-T09 | category: other expected appointments; priority: normal expected low |
| 2 | HD-T10 | priority: urgent expected high |
| 3 | NW-T03 | priority: urgent expected high |
| 3 | NW-T04 | category: shipping_delivery expected order_change; priority: normal expected high |
| 3 | NW-T05 | priority: normal expected low |
| 3 | NW-T08 | priority: normal expected low |
| 3 | NW-T10 | priority: urgent expected normal |
| 3 | NW-T11 | category: records_privacy expected shipping_delivery |
| 3 | HD-T02 | category: billing_payments expected appointments; priority: low expected normal |
| 3 | HD-T04 | priority: normal expected high |
| 3 | HD-T05 | priority: normal expected low |
| 3 | HD-T06 | priority: normal expected low |
| 3 | HD-T08 | priority: low expected normal |
| 3 | HD-T09 | category: other expected appointments; priority: normal expected low |
| 3 | HD-T10 | priority: urgent expected high |

## Interpretation

These results cover the visible synthetic seed set, not unseen-ticket accuracy. Repeated local inference may vary between machines. Priority and KB retrieval are diagnostic, not folded into action accuracy.
Next improvements: larger paraphrased injection and benign-control sets, evidence extraction for ambiguous missing details, and measured retrieval relevance. No result was manually edited.

## Evaluation provenance

These three underlying inference runs used the same triage and injection-review prompts as the final code. A later deterministic explicit-public-coverage fallback was replayed over their typed decisions and original top public KB references. No model output was invented or counted as another run. Raw pre-refinement results are preserved in eval/candidate-before-coverage. Only report generation reads golden labels. The reported wall time is the measured inference phase; the additional deterministic replay took 0.189 seconds. Earlier baseline results remain in eval/baseline-adb61a5.
