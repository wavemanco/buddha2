# Phase 3A-R2 — Pilot outcome

2026-10-29, America/Los_Angeles. **The authorized four-prompt R2 run finished with all eight primary portfolios scored, all 665 requests accounted for, and $7.792588 recorded R2 cost. The scientific completion criterion was not met: none of the four native paths qualified as authentic adaptation. Phase 3A remains incomplete.**

All twelve editor sessions reached their eight-turn limit without changing the consumed strategy fields. The frozen report therefore retains `status=incomplete`, `primary_scored=8`, `complete_primary=false`, zero authentic paths and a null pooled mean/method selection. Here `complete_primary` includes the authenticity requirement; it does not indicate missing benchmark scores. This outcome does not answer whether genuine recursive adaptation improves beyond the fixed strategy.

## Authorized method and observed execution

The accepted [recovery definition](PHASE3A_RECOVERY_DEFINITION.md), [authority](evidence/phase3a-r2-v1/authorization.json) and [runbook](PHASE3A_R2_RUNBOOK.md) cover one fresh four-prompt paired pilot, first-pair review, remaining pairs and closure. The [first-pair report](PHASE3A_R2_FIRST_PAIR_REPORT.md) and snapshot were committed in `8af57be` before continuation. No score, parser, model, effort, threshold, timeout or resource ceiling changed during execution; no old outcome became a new primary.

The study remains `17f35cf72cad95351e726cd9f02824be78db35a0a16c3f83db9e7bae9d762032`, with the same 157-file source `a3b9403d6bc0a144d0bb74e74a330ccf057850da0d23dcb2d9059d94a20883e3` from `e8b1f8d`. The pinned image is `sha256:8792a096b4881d47ab19cc7cbf6a74a232f9ff7cedc978fe93f902a71522d4f2`. The [protocol record](runs/phase3a-r2-v1/reports/live-final-v1/protocol.json) retains all upstream pins, exact requests/settings, task order and identities.

The fixed arm generated six fresh C-N portfolios per prompt and used one blind whole-portfolio selector. Actual pinned Harness² executed native `agg,k=1` in the adaptive arm: base, INV probe, DOM probe and AGG final rollouts, with three model-backed editor stages per prompt. Both arms used the same frozen seed strategy and declared allowance vector; neither saw native judge scores during search. Both final portfolios for every prompt were sealed before judging. Every adaptive final used native trivial single-final `agg1` selection.

| Role | Frozen model/settings | Actual requests |
|---|---|---:|
| Plan, ten-answer generation, N1 ranking | `claude-sonnet-5-5`; adaptive/low; 4,096 output; standard_only/global | 480 |
| Native editing and fixed selection | `claude-opus-5`; adaptive/high; 16,000 output; standard_only/global | 100 |
| Duplicate grouping | `gpt-5.6-luna`; unchanged native Chat Completions/schema; effort/cap/temperature/seed omitted | 9 |
| Head-quality scoring | `claude-opus-5`; unchanged native adaptive/high/16,000; tier/geography omitted | 76 |

There were 40 fresh C-N rollouts: 24 fixed candidates and 16 native executions. These account for 40 planning, 400 answer and 40 ranking requests. Four fixed selector requests and 96 editor requests bring inference/editing/selection to 580; nine grouping and 76 quality calls bring the total to 665. The 775-slot worklist has 110 unused slots: 96 unused second-shape editor slots and 14 native nonhead quality positions. These are classified noncalls, not replacement or missing primary outcomes.

## Native authenticity and mechanism evidence

All four native wrappers returned a complete final portfolio. Every INV/DOM/AGG stage has `kept_base=true`, `fell_back=false`; all twelve have the exact terminal note and unchanged consumed fields, hence `cap_limited_unchanged=true` and `authentic_eligible=false`. The seed's consumed strategy identity stayed `de42f86a2517f53ee14fd5ce87002e9dd1018c7508597a2663437cdff80f8ee6`. Cap-forced unchanged outcomes are distinct from a normally completed, eligible `KEEP_BASE` decision.

| Prompt | INV reads | DOM reads | AGG reads | Write/edit actions | Eligible native path |
|---|---:|---:|---:|---:|---|
| Invention | 18 | 18 | 18 | 0 | No |
| Grocery item | 19 | 19 | 20 | 0 | No |
| Four-character password | 18 | 17 | 22 | 0 | No |
| Birthday gift | 18 | 16 | 19 | 0 | No |

These 222 read actions occurred within 96 paid editor HTTP requests; they are not 222 additional provider calls. No tool result flagged an error. All 684 published native/editor artifact hashes, twelve immutable session-input/settled proofs and 96 raw/effective request bindings match. All twelve terminal translations retained the exact 765-byte note, cache metadata, earlier thinking/history and direct-caller metadata. There is no observed failed write attempt or model substitution explaining the unchanged trees.

A bounded primary-source review found two concrete design frictions:

- The saved missions restrict editing to three JSON strings, then retain upstream instructions preferring skills, scripts, subagents and plugins that this pilot cannot execute. Legal text edits and `KEEP_BASE` remain available; the mismatch does not prove adaptation was impossible. The writable surface is enforced in [editor.py](runs/phase3a-r2-v1/release-v1/source/followups/phase3a_v1/editor.py).
- Representative first-prompt INV/DOM contexts each contain 12 files/57,384 bytes; AGG contains 36 files/198,657 bytes before its mission. The missions require inventorying and inspecting evidence before deciding. Upstream `k=1` wording also treats a defect in one base observation as noise while rendering an example with two failures out of one. These establish workload and wording concerns, not context-window exhaustion or proof that eight turns could never suffice.

Some generated notes incorrectly describe unfinished editor work as non-delivering solver rollouts. The actual solver records contain ten responses and are complete. Model explanations are self-reports, not established environment failures or causal diagnoses. The [independent audit](evidence/phase3a-r2-v1/live-outcome-v1/independent-audit.json) binds the representative mission/source hashes and separates observed facts from these inferences.

## Benchmark observations

The [rows](runs/phase3a-r2-v1/reports/live-final-v1/rows.json) and [analysis](runs/phase3a-r2-v1/reports/live-final-v1/analysis.json) preserve unrounded native values. Rounded primary observations are:

| Development prompt | Fixed utility | Adaptive procedure utility | Distinct: fixed / adaptive |
|---|---:|---:|---:|
| Invention to make the world more interesting | 7.92835 | 7.87783 | 10 / 10 |
| Memorable grocery-list item | 7.38635 | 7.91259 | 9 / 10 |
| Strong four-character password | 2.61476 | 2.43151 | 4 / 3 |
| One gift for a friend's 25th birthday | 7.31061 | 7.03915 | 10 / 10 |

These are outputs from the two declared procedures. In the adaptive procedure, all generated portfolios used the unchanged harness. The observed gaps cannot establish a benefit or cost of genuine recursive adaptation. The accepted gate keeps the pooled mean and method selection null; no aggregate winner is inferred from the scored subset or from all eight scores alone. Four exposed development prompts supply no population, held-out or human-preference conclusion.

The fixed first-prompt duplicate remains diagnostic: utility 7.59503 versus its original 7.92835; identical grouping, four of ten shared head ratings different, utility difference -0.3333267. It never replaces the primary score. This one repeat illustrates judge variation, not a general reliability estimate or permission to tune/rejudge.

## Accounting, budgets and preservation

Every request has one known result, a unique dispatch/provider request/message identity and settled usage. Independent Decimal recomputation matches all 665 recorded charges and every admission respects its overlapping dollar/HTTP/token limits. The final journal has 1,331 valid chained events, including the unchanged first-pair engineering review; there are no new unknowns, pending requests, retries or reserved liabilities.

| Component | Requests | Input tokens | Output tokens | Accounted USD |
|---|---:|---:|---:|---:|
| Fixed inference/selection | 292 | 310,407 | 148,389 | 2.592951 |
| Adaptive inference/editing/probes | 288 | 1,275,079 | 134,774 | 4.349478 |
| Primary and duplicate judging | 85 | 112,170 | 16,451 | 0.850159 |
| **R2 total** | **665** | **1,697,656** | **299,614** | **7.792588** |

The first pair cost $2.963757; the remaining stage added $4.828831. Equal ceilings were allowances, not equal realized compute/spending. All eight cells retain their $20/96-HTTP/4-million-input/786,432-output ceilings; no capacity was transferred or spent to equalize.

Historical known accounting remains $2.695297, with the full **$11.44 unresolved reservation** held. Adding R2 once gives **$10.487885 cumulative known accounting and $21.927885 maximum current exposure**. There were 842 cumulative attempts including the historical 177, inside the approved 952. The R2 $205.86/$50.86 and original $220/$65 overlapping ceilings remain unchanged. These public-price-envelope amounts are not provider invoices, and unspent allowance grants no automatic new repetition.

Both provider launchers exited zero and their owned containers were removed. Their lifetimes include long masked-key waits and validation/execution; they do not measure inference-only latency. Provider streams were suppressed and not retained. Credentials were not included in the evidence. The original folder was neither accessed nor mounted.

Current and retained 157-file source, prior 142/149-file source bundles, 1,126 earlier public baseline files, 17 prior reports, offline/first-pair packets and both stopped-episode archives remain unchanged. Four historical private identities were checked through Git metadata only; their contents were not read. All earlier report/archive commits remain preserved.

## Reproducibility, closure and next decision

The final frozen cutoff is `2026-10-29T14:59:58Z`, evidence identity `dd7c20daef1eb64ff0fcac2353f1453c33608485e4e41859a12b18b9dd20499b`. The [final report](runs/phase3a-r2-v1/reports/live-final-v1/PHASE3A_REPORT.md), [exact replay](runs/phase3a-r2-v1/reports/live-final-replay-v1/PHASE3A_REPORT.md) and [report proof](runs/phase3a-r2-v1/final-replay-v2/report-proof.json) use 880 exact hash-verified copied inputs at identical canonical result paths, bounded memory, a network-disabled pinned image and blocked SDK/socket entry points. The copy includes 713 public run files and all 684 bound native/editor artifacts. Seven report files match byte-for-byte, with zero new provider requests or SDK constructions; no execution resume was performed. The proof records input/output hashes and preservation checks. This verifies reporting from saved evidence, not new model effectiveness.

The first offline replay attempt was rejected by strict native-artifact validation: a blanket lock-file exclusion omitted four authenticated empty `summary.lock` artifacts. Upstream `schedule.py` creates these empty public synchronization files; their empty-byte hashes were already bound in the saved native records. The corrected evidence copy includes only those exact authenticated public metadata paths while continuing to exclude private credential bindings and writer locks before inspection. Twelve fixture-only negative/positive guard cases passed, including rejecting a nonempty marker before opening it and rejecting private/unlisted paths. The failed copy manifest/log/helper bytes are retained as diagnostics. No study source, original artifact, score, old first-pair packet or paid request was changed.

The final [archive](evidence/phase3a-r2-v1/live-outcome-v1/archive.zip), [manifest](evidence/phase3a-r2-v1/live-outcome-v1/manifest.json) and [closeout](evidence/phase3a-r2-v1/live-outcome-v1/closeout.json) preserve the public full-run outcome, both launch records, reports/replay/proof and audits. Private bindings, fingerprints, key files and writer locks are excluded before reading/copying. The four authenticated empty native summary locks are public artifact metadata. CRC, every archive member hash and original public input preservation are verified. The exact 157-file source is referenced through the retained verified offline kit.

The authorized R2 execution attempt is closed with its authenticity criterion unmet. The original goal of a completed Phase 3A scientific comparison remains unresolved. The next decision should be a bounded offline instruction/surface compatibility definition, addressing the demonstrated mission mismatch and context workload before proposing another paid readiness check. More dollars alone do not change the frozen turn cap. The behavioral cause and effective remedy remain unestablished. No R3, Phase 3B, new strategy/model/benchmark, held-out access, CrPO/MuCE or human collection starts from this report.
