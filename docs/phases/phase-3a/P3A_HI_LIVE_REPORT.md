# P3A-HI live attempt — closed, scientific comparison incomplete

The accepted P3A-HI kit ran one fresh provider-backed attempt. The first paired comparison completed, including its counted readiness and duplicate assessment. The second adaptive primary failed its final ranking contract. The controller stopped further paid admissions as specified. **Phase 3A's scientific milestone remains incomplete: two of eight primary portfolios were scored, no four-prompt mean or method selection is available, and no paid repetition was started.**

This report closes the attempt under [definition 1.0](PHASE3A_H1_INTEGRATED_PILOT_DEFINITION.md), sections 6–9. It preserves the original outcomes and distinguishes offline kit acceptance, scientific completion and visibility. All work used the project root.

## Execution and result

The accepted kit is commit `094b64c`, with source identity `2440535e5274c106a44efb28cf9533308b7dbea8fd8768649a089145cbc150a3` and study identity `a233fbc5ed3fedaa21e6b364ecfbfdd15496e25c005897067eb2cc7aed90d28a`. Actual pinned Harness² and NoveltyBench remained unchanged. Native adaptation used `agg,k=1`; fixed sampling used six independent C-N candidates and one blind whole-portfolio selector. Both retained the same declared technique access and inference ceilings, rather than equal realized spending.

| Pilot | Adaptive | Fixed | Paired interpretation |
|---|---|---|---|
| p3a-01 | Scored; utility 7.6759632761, distinctness 10, first-answer quality 8 | Scored; utility 8.0, distinctness 10, first-answer quality 8 | Adaptive-minus-fixed utility −0.3240367239; one descriptive development result |
| p3a-02 | Final ranking rejected; no eligible composed final | Unattempted after primary stop | No paired quality comparison |
| p3a-03 | Unattempted | Unattempted | No comparison |
| p3a-04 | Unattempted | Unattempted | No comparison |

For p3a-01, all three normal editor stages made grounded KEEP_BASE decisions. Four solver rollouts were fresh despite the unchanged strategy. The independent counted-readiness review passed. For p3a-02, INV and AGG changed the consumed `answer_system`; DOM kept the base. All six editor conversations across these two prompts were classified authentic and normally completed, using 54 editor requests, without terminal rescue or fallback. These observations establish working ordinary native editing/history paths, not an improvement in benchmark quality.

The predeclared identical p3a-01 fixed duplicate was scored once. Its grouping, all ten shared-head scores and utility matched its original assessment. This single diagnostic does not calibrate general judge reliability. No scores, direction or Inspect output were used to decide continuation.

## Why the second primary failed

The composed rollout delivered a plan and ten answers. Sonnet's ranking reply then contained two JSON orders: the first mistyped one response ID; a prose correction introduced a second, valid permutation. The frozen N1 rule rejects the whole reply if any candidate order is invalid and expressly disallows selecting a claimed correction. It therefore recorded `invalid_rank:invalid_ids`.

That left no completed `agg1` portfolio. Actual Harness² finals-only selection correctly supplied no base/probe fallback, so the branch had no primary final and triggered the prospective `missing_primary_final` stop. All twelve calls for that final rollout had settled responses; this was not an API exception or billing uncertainty.

The actual consumed `rank_system` was unchanged from the seed and explicitly requested one JSON object with every response ID exactly once. The editors had changed only `answer_system`. Both adaptive rollouts and fixed candidates use the same C-N execution and N1 parser, although their final-selection topology differs. The evidence establishes the contract violation and rejection chain, not why the ID was mistyped or whether the answer edit contributed. No second-object selection, output repair, replacement final or paid repeat occurred.

The source-bound [diagnostic note](../../../runs/phase3a-h1-integrated-v1/verification-v4/reviewer/live-primary-failure-v1/NOTE.md) and [diagnostic record](../../../runs/phase3a-h1-integrated-v1/verification-v4/reviewer/live-primary-failure-v1/diagnostic.json) retain the exact reply, ID derivations, request/result hashes and unchanged ranking instruction. This failure is an end-to-end reliability outcome; it is not a complete negative quality result for recursive adaptation.

## Accounting and shutdown

| Work | Settled requests | Usage-based cost |
|---|---:|---:|
| p3a-01 adaptive | 76 | $3.707716 |
| p3a-01 fixed | 73 | $1.069455 |
| p3a-02 adaptive | 74 | $2.701682 |
| Two primary assessments plus the diagnostic | 33 | $0.404118 |
| **This attempt** | **256** | **$7.882971** |

The saved transport audits record 256 SDK invocations. There were zero retries, new durable unknowns, active unsettled intents or unresolved reservations at closure. The 967-slot inventory classifies 208 known responses, 48 known tool responses, 700 slots unattempted under primary fail-fast and 11 skipped for the missing final. Inventory slots are not additional paid attempts.

The $205.86 ceiling was a maximum exposure allowance, not guaranteed spending. Historical Phase 3A known cost remains $16.580264 and the two old unknown holds remain **$22.88**, unreleased. Cumulative Phase 3A known cost is **$24.463235**; known plus historical held exposure is **$47.343235**. The cumulative admitted-attempt count is 1,233: 977 historical plus 256 new, including the two historical unknown results. These are recorded usage-based figures, not independently verified invoices or all-project lifetime spending.

The exact provider container was removed; both PowerShell owners and both exporter hosts exited. The sanitized launcher result records exit 0 and no retained provider streams. Exit 0 means the controller closed the attempt successfully, not that the scientific comparison passed. Process-held credentials ended with their owners. Only credential-free loopback static viewers remain for display.

## Inspect and the missed first handoff

The tables, navigation and sample drill-down interface are **Inspect AI's stock saved-log viewer**. Codex supplies the surrounding browser pane. Our isolated adapter imports public native records; Inspect performs no model calls, scoring, admission, spending control or native execution. No exported material feeds back into adaptation.

The first-pair canonical snapshot and reports completed successfully. The operator missed the bounded export handoff while investigating the wait, so its original visibility status remains `timeout`. This was a monitoring error, not a canonical-validation startup stall. It did not alter results or stop the remaining experiment. The incident and exact original status/request hashes are preserved. After every keyed owner stopped, the same frozen snapshot was exported offline into a fresh namespace without a late ACK or changed canonical status.

The closure export completed within its live window. Both exports preserve snapshot bytes and imported native values, pass saved-reader round trips and confirm cleanup with zero model-constructor or external-socket attempts. Inspect remains a checkpoint viewer, not a continuously updating live monitor.

- [Actual closed-run viewer](http://127.0.0.1:8770/#/tasks/closure.eval/samples): task failed, with the second adaptive sample's native `missing_final` disposition.
- [Actual first-pair snapshot](http://127.0.0.1:8769/#/tasks/first-pair.eval/samples): its historical partial `RUNNING` label describes that frozen checkpoint, not current provider activity.

The older ports 8767/8768 retain mock rehearsal views. Generic sample-row `ok` labels describe imported records, not successful native primaries; native metadata and attachments remain authoritative. Blank answer/token columns and absent reconstructed conversations are retained rather than filled with invented data.

## Verification, deliverables and exit

The [offline acceptance report](P3A_HI_OFFLINE_REPORT.md) and immutable two-part accepted kit remain unchanged. No production code, prompt, model, parser, threshold, step allowance, price policy or deadline changed after live observations began.

Saved zero-call replay passed in 228.45 seconds: all eight regenerated canonical report files were byte-identical, with input hashes preserved and owned cleanup completed. The [independent closure review](../../../evidence/phase3a-h1-integrated-v1/live-independent-review.json) passed accounting, ownership, both visibility exports, the deterministic ranking rejection and unchanged source/history checks. The immutable [outcome](../../../evidence/phase3a-h1-integrated-v1/live-outcome.json) binds all eight canonical report files, the source/study/runtime/policy/launcher identities and exact sanitized launcher records.

The [live packet manifest](../../../evidence/phase3a-h1-integrated-v1/live-outcome-v1.manifest.json) indexes 8,059 members in the local archive, including the 256 explicitly authenticated transport-audit copies needed for cold replay. The external [packet acceptance](../../../evidence/phase3a-h1-integrated-v1/live-packet-acceptance.json) passed every member's privacy classification, CRC, SHA256 and current-byte comparison, source/dependency completeness and both actual views. This accepts a faithful incomplete-attempt record; it does not certify scientific success. The final narrative is committed beside the archive rather than retrospectively inserted into it. Original offline archives and all packed inputs remain unchanged.

HI-1 through HI-3 retain their accepted offline status. HI-4 is unmet. HI-5 is the faithful failed-attempt closure, rather than full scientific completion. HI-6's reached checkpoints are viewable after the disclosed first-pair offline repair. The full block is not described as a completed Phase 3A scientific comparison.

The next decision is whether to define a bounded offline ranking-contract checkpoint: reproduce this saved rejection, decide a prospective shared contract for both arms, and freeze/test it before any fresh pilot. Do not repair this historical result or run again using the unused ceiling. Successive refinement, held-out evaluation, new strategies/models, CrPO and human collection remain outside this closure.
