# Phase 3A C1 completion R1 — live early-stop report

2026-10-29, America/Los_Angeles. **Closed on an unresolved provider-call timeout. Scientific Phase 3A is incomplete.** The source remains the accepted 221-file R1 source `33cc36cb56fa75b6b427add09934a943515dd40e57cccfb4d4cfcb92a8b4bc1c`; study `28519e20cf71fbf599f6f21a5c2c3b275fbc9c24ffedf4df2041d49816e8eb62`. The accepted offline kit is committed in `c7165af`.

## Observed outcome

The controller made **24 requests: 23 known responses and one durable unknown result**, then exited normally on the accounting hold. Process exit zero records controlled shutdown; it is not scientific success. No active intent remains, and no request was resent.

- The base C-N portfolio completed in 12 calls: planning, ten answers and ranking.
- DOM completed normally in seven calls, with a strict final response matching its saved single notes block. It kept all three consumed strategy strings unchanged. Independent review found its KEEP_BASE explanation consistent with the fresh baseline ideas and plan/rank evidence, including its stated inability to verify rank quality from ID-less extracted answers. This is observed compliance in one completed session, not a measured adaptation benefit or proof of a robust format fix.
- INV completed four read-only tool turns. Its fifth request, `p3a-01.adaptive.editor.inv1.a1.t05`, received a durable `unknown` result with sanitized failure category `timeout`, stage `provider_call`, and no HTTP status, provider request ID, response or usage. No INV edit, harvested strategy or final decision is available.
- No DOM/INV/AGG probe, AGG editor, fixed-control or judge call occurred. There is no completed adaptive branch, readiness barrier/review, pair seal or scored primary. All eight primary scores and the duplicate diagnostic remain missing; the paired mean and method selection remain null.

The failed request used `claude-opus-5`, adaptive/high, 16,000 maximum output tokens and standard-only/global routing. Its canonical admission body was 111,758 UTF-8 bytes, below the 1 MiB ceiling. Bytes do not establish billable tokens. The partial INV metadata reports about 133.3 seconds for the entire session, including local retry bookkeeping; it does not measure the failed call's duration. The native second local invocation was rejected by the started-session guard without another provider request.

## Accounting and preservation

| Item | Usage-based known cost | Unresolved reservation |
|---|---:|---:|
| This R1 study | **$0.951801** | **$11.44** |
| Earlier Phase 3A history | $11.279643 | $11.44 |
| Cumulative | **$12.231444** | **$22.88** |

Current cumulative maximum exposure is **$35.111444**, across 885 attempts: 883 known and two historical/current unknowns. The new $11.44 is a conservative retained liability, not a known charge. Neither unknown is inferred to cost zero or released. The stopped R1 grant supplies no further admissions. The remaining 751 worklist slots were not attempted.

Independent [accounting review](evidence/phase3a-c1-completion-v2/live-accounting-review.json) verifies the 48-event chain, matched unique intents/results, known per-request arithmetic, exact source and accepted packet preservation. The [partial authoring review](evidence/phase3a-c1-completion-v2/partial-authoring-review.json) distinguishes DOM's normal grounded KEEP_BASE from the missing full readiness path. No affirmative inspection was created.

The saved report and a second replay were built in the pinned image with networking disabled, source read-only and SDK constructors/sockets blocked. Eight report files reproduce byte-identically, all 427 protected inputs remain unchanged, and no provider call, resume, journal append or liability release occurred. Proof and replay are under `runs/phase3a-c1-completion-v2/live-closeout-v1/`. The public final archive and external manifest must include that subtree and every artifact bound by `live-outcome.json`; independent packet acceptance is a separate packaging result.

The actual host result is `runs/phase3a-c1-completion-v2/launcher/316b713dda7447658d3325e4948ad347.result.json`. Its container lifetime includes approximately three hours awaiting operator key entry, so it is not model execution latency. The keys were discarded at shutdown. The original Buddha2 folder and all prior sources, failures, archives and liabilities remain untouched.

## Interpretation and next boundary

The evidence establishes an inner provider-call timeout. The pinned SDK uses a **90-second per-I/O timeout**, not a 90-second total-call clock, with zero retries. It collapses connect/read/write/pool timeout subtypes into its timeout exception, and the retained sanitized failure does not identify which subtype occurred. Provider load, prolonged generation and a network stall remain possible explanations; none is established.

The relay currently waits for a complete non-streaming provider response before producing local SSE. OpenCode has a 590-second local fetch abort and native Harness² a 600-second whole-conversation deadline; relay teardown waits for admitted handlers to settle. A larger inner timeout by itself is therefore insufficient. A prospective correction needs a total provider-call deadline coordinated with remaining conversation time, explicit cancellation/settlement tests and safe timeout diagnostics. Anthropic also documents streaming as an option for long requests; it would require separately declared assembly/failure-boundary work. [Official error/long-request guidance](https://platform.claude.com/docs/en/api/errors).

This saved study cannot complete: its durable unknown/global hold and started-session guard remain enforced. No review, new claim or missing usage estimate unlocks it. Any fresh recovery must have a separately defined source/worklist/grant, retain both liabilities and all failed observations, pass its entire offline gate and require a new operator invocation. No automatic repeat, held-out evaluation, Phase 3B, new strategy/model or human/CrPO work follows from this report.
