# P2B-F1 — First counted live block

Definition version **1.0**, 2026-10-27, America/Los_Angeles. **Defined; unstarted and unauthorized.** Authority for this document is the user's request to define the block, including objective, scope, deliverables, exclusions, completion criteria, exact settings, costs and next action. It supplies no paid grant, credentials or permission to contact provider endpoints.

This is an operational addendum to specification 0.19 and the completed P2-R kit under frozen 0.18. It introduces no scientific, source, protocol or budget-policy change. The existing release gate binds the earlier planning documents, so those files, the study, source bundle, runbook, manifests and gate remain untouched. This new addendum records the current first-block definition without invalidating that release.

## Objective

Complete the first prespecified A/B/C comparison while observing actual account/model access, acceptance of the declared settings, native scoring and usage/accounting through the already-tested launcher. Preserve this as the first counted portion of Phase 2B, with a usable report and an explicit proceed/hold decision at its end. Its conclusions concern execution validity and descriptive results for one development prompt.

It contributes to the later comparison of base sampling, fixed planning and isolated reranking. A full Phase 2B benchmark decision needs the complete 12-prompt/two-repeat pilot. Recursive adaptation is a later phase.

## Scope and fixed inputs

- Frozen release: `38132ee3a935af4ac975c3fda84154d1a85b1bcb510925f409993a15d3103d8b`, at `runs/phase2-release-r018/release/study.json`; source commit `20da5ee`.
- Exactly **the first selected development task, repeat 1**: `nb-curated-9c418f063bc433264d29`, source `curated-95`, **“Which 4-digit lock combination is the safest?”**
- Source: NoveltyBench curated data at `64a23be6b18ec1dacc298830aab276061b6e143c`, source file SHA-256 `ca9b6f470e5d7f7e34a281e2fdaa6f6e51c38bdae075ea580d184139ec391fa7`.
- Native NoveltyBench **v1.1**, patience **0.8**, frozen prompts, schemas, folding/arithmetic, output IDs and ordering. Development material only; no new confirmation rows.
- Existing inspected Windows/PowerShell/Docker launcher, pinned image and SDKs (`anthropic==1.4.0`, `openai==1.107.0`), canonical live journal and single request in flight.

| Condition | Work |
|---|---|
| A: ordinary sampling | Ten fresh independent answer requests, each receiving the original task and shared minimal answer instruction. Preserve request order. |
| B: fixed planner + generation | One request plans ten ordered angles. Ten fresh answer requests each receive the original task and only their assigned angle. Preserve angle order. |
| C: isolated reranking | One request returns a permutation of B's ten saved response IDs. Preserve every text and ID exactly; no new answer generation. An identity permutation is valid. |

The first block's sequence is **A's ten answers → B plan → B's ten answers → C rank → native assessment of A, B, C**. Each assessment obtains its own grouping result, then quality judgments for the first response in each returned group. B's grouping/quality results are not reused as C's assessment.

## Exact requested models and settings

| Role | Model/API | Effective settings |
|---|---|---|
| A/B answers, B plan, C rank | `claude-sonnet-5-5`, Anthropic Messages | `thinking.type=adaptive`; `output_config.effort=low`; `max_tokens=4096`; `service_tier=standard_only`; `inference_geo=global`. Temperature/top-p, tools and conversational memory omitted. |
| Native grouping | `gpt-5.6-luna`, OpenAI Chat Completions | Frozen strict grouping JSON schema. Reasoning effort, output cap, temperature and API seed are **omitted**, preserving the native request. Documented effort default is currently **medium**. Native `seed=None` means the ordered portfolio is shown without shuffling; it is not a requested provider seed. Reserve up to the documented 128,000 output-token maximum. |
| Native head quality | `claude-opus-5`, Anthropic Messages | Frozen native rubric/strict JSON score schema; adaptive thinking; effort **high**; `max_tokens=16000`. Temperature, service tier and geography omitted; inherited billing behavior must remain within the supported public profile. Each call sees the original task and its one head answer. |

The Sonnet 4,096 and Opus 16,000 limits include billable thinking and text. The generator's native `2048` argument becomes 4,096 total tokens through the pinned helper; it is not a strict 2,048-visible-token promise. Do not substitute current newer models, add a grouping effort/output cap or change a parser to make this run pass. Requested aliases and actual returned model IDs are recorded; aliases do not freeze model weights.

Use the supported direct public PAYG profile from the frozen runbook, without unreviewed billing/endpoint overrides. Transport timeout is 90 seconds, redirects disabled, **zero retries, fallbacks, response repair or paid replacements**. A timeout does not prove that provider execution or charging stopped.

Active AM-1 admission uses the frozen serialized-body caps: **5,952 UTF-8 bytes** for answer/plan/quality and **61,952 bytes** for rank/group, with supported full-context financial reservations. The profiles' retained 8k/64k `input_limit` bookkeeping is not a certified provider-token bound. Do not truncate or edit scientific requests to get past admission.

Official sources refreshed for this definition: [Sonnet 5.5](https://platform.claude.com/docs/en/models/sonnet-5-5/overview), [Opus 5](https://platform.claude.com/docs/en/models/opus-5/overview), [Luna settings/limits/pricing](https://developers.openai.com/api/docs/models/gpt-5.6-luna), [Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing). The exact study chooses the settings; documentation is not evidence of access on the user's accounts. The fixed Opus 5 judge remains deliberate despite newer available models.

## Counted workload and limits

| Role | Maximum requests |
|---|---:|
| A answers | 10 |
| B plan | 1 |
| B answers | 10 |
| C rank | 1 |
| Fresh grouping: A/B/C | 3 |
| Native quality heads | 30 |
| **Total** | **55** |

A successfully completed block uses `25 + hA + hB + hC` requests: **28–55**, because each valid ten-answer partition has 1–10 heads. Nonhead quality slots remain explicitly undispatched. Failed prerequisites or an earlier stop can produce fewer requests. There are **20 generated answers**, two generated portfolios and one permutation, giving three ordered assessment instances and 30 answer presentations across A/B/C.

All of this work counts inside the full pilot's 1,320 slots. There are no additional auth, model-list, token-count, warm-up or replacement probes before or alongside it. The runner stops at this block even if budget remains.

## Expected cost, scenarios and proposed cap

**Measured expected live cost is not yet available.** The mock ledger is fabricated usage and must not be used as a spend forecast. Hidden reasoning, actual response lengths, head counts and returned billing categories remain unknown. The first block supplies the first live evidence for a revised expansion estimate.

Current ordinary public rates are Sonnet **$2 input/$10 output**, Luna **$0.20/$1.20**, and Opus 5 **$5/$25**, per million tokens. Output charges include thinking. Actual accounting also considers cache writes/reads, supported tier and regional premiums. Sources are linked above; caching discounts or standard-tier behavior are not silently assumed by the financial guard.

The following independent arithmetic illustrates sensitivity, **not a prediction, confidence interval or completion guarantee**. Each case assumes all 30 quality heads, respective input tokens per answer/plan/rank/group/quality of **300/500/6,000/6,000/1,000**, no caching, standard grouping tier and a conservative 10% regional uplift for grouping/quality. Extra output can be reasoning rather than longer visible text. These hypothetical token amounts are not certified admission bounds.

| Case | Output tokens per answer / plan / rank / group / quality | Hypothetical full-block cost |
|---|---|---:|
| Concise outputs | 500 / 800 / 300 / 500 / 1,000 | **$1.13194** |
| More billable reasoning | 2,000 / 2,000 / 1,000 / 500 / 8,000 | **$7.22594** |
| Quality output reaches its 16k cap | 2,000 / 2,000 / 1,000 / 500 / 16,000 | **$13.82594**; admission would stop before completion under these exact assumptions |

Formula in USD is `(2*I_s + 10*O_s + 1.1*(0.2*I_g + 1.2*O_g + 5*I_q + 25*O_q)) / 1,000,000`, using summed tokens within each model group. For example, the concise case is $0.136 Sonnet + $0.00594 grouping + $0.99 quality. Fewer heads lower those cases; different usage/cache/tier behavior can raise or lower them. The third row is not the full configured worst case: it holds its input/grouping assumptions fixed.

**Proposed first-stage cap: $20, unapproved.** It covers cumulative settled public-price cost plus outstanding liability and the next request's reservation. This is an admission/stop ceiling, not guaranteed spend, an invoice guarantee or a promise to finish.

| Next-request reservation | USD |
|---|---:|
| Each Sonnet answer/plan/rank | 2.540960 |
| Each grouping request | 1.661880 |
| Each quality request | 11.440000 |

Every new quality request needs **$11.44 available**. With no existing liability, if earlier settled cost exceeds **$8.56**, another quality request cannot start under $20, even when its eventual bill would be small. Understood usage replaces/releases its reservation; reservations are not permanently added after each completed request. Unknown usage retains liability and halts. Under the third row's exact assumptions, the $13.83 hypothetical full-block case would stop before completion under the $20 admission cap; actual usage is still unknown.

The summed first-block liability envelopes are **$404.086760**. That sum is not expected spend or money simultaneously reserved during serial settled execution. The frozen policy permits at most $20 for this stage; a higher first-stage ceiling requires an explicit amendment, not an ad hoc flag or new directory. No increase is proposed or authorized here. Exclude ordinary assistant-session charges and local operator/electricity costs from these API figures; no paid infrastructure/data/human collection is included.

## Deliverables and usable result

1. **First-block output archive:** original A/B answers, B angle plan, C permutation, stable IDs/text/order and every original outcome/status; preserved native exchange and three assessment records when successful.
2. **Provider/protocol evidence:** requested/returned model IDs, exact requests/settings, request IDs, stop reasons, usage/cache/tier categories, latency, strict native folding and C's one-to-one permutation check. No raw keys in files or logs.
3. **Cumulative accounting and coverage:** one canonical live journal at `runs/phase2-release-r018/<study_sha256>/live`, recorded grant/attempts/results, settled/reserved amounts, nonheads, skipped dependents and all failures. Earlier work is never rebilled on resume.
4. **Usable first-block report:** `runs/phase2-release-r018/reports/live-first/PHASE2_REPORT.md` and separate execution/native/analysis/decision JSON; local descriptive A/B/C metrics, actual costs and readiness findings. For a successful first block, only **3/72 orders** are assessed; the other **69 remain missing** and the full-study benchmark decision stays **inconclusive with no selected seed**.
5. **Explicit proceed/hold record:** a written review referencing the exact trace/journal prefix, observed account/settings/billing compatibility and revised full-pilot cost scenarios. Record a hold and the required recovery/amendment if this block is incomplete. First-prompt costs alone are not a representative full-pilot forecast.

If launch is rejected before dispatch, report that rejection rather than inventing results. If interrupted or stopped, retain all available evidence and a partial report where the journal remains replayable; corruption is rejected rather than repaired into a favorable decision.

## Exclusions

No expansion, second repeat or additional prompt; no whole-pilot seed/winner/general-effectiveness or held-out conclusion; no model/reasoning sweep; no recursive adaptation, memory or proposer; no new strategy, rubric, benchmark or leaderboard submission; no CrPO/MuCE work, Route H execution or real human collection. Human availability cannot block this benchmark block. No tuning on first-block results, silent model substitution, parser relaxation, answer rewriting, sample replacement or first-block retry budget. The Phase 1 readiness exception does not carry forward.

## Stop rules and manual review

Automatic source/authority/runtime/request/accounting checks remain the existing frozen behavior. One request is in flight phase-wide.

| Event | Required behavior |
|---|---|
| Unknown delivery/usage, unsupported accounting, insufficient next-request headroom or unexpected contract failure | Halt further dispatch; preserve settled costs, full unresolved liability and evidence. No free retry or automatic top-up. |
| Source, grant, runtime, path or saved-artifact mismatch | Reject execution; do not count a process exit as successful readiness. |
| Answer refusal, empty text or truncation with understood usage | Preserve text/placeholder and status. Other declared work may continue; these are visible method outcomes. |
| Known invalid/refused/truncated B plan | Skip dependent B/C work. Independent A work may finish. First-block review cannot pass. |
| Known invalid rank | Preserve B; skip C assessment. First-block review cannot pass. |
| Settled malformed/refused native judge outcome | Preserve the non-scored native outcome; independent orders may continue. Quality schema validation occurs at that order's finalization after its head requests. First-block review cannot pass. |
| First-block work ends | Stop even if funds remain. Produce the report, then manual review before expansion. |

There is no newly invented immediate-stop-on-any-malformed-text policy and no manual two-call gate hidden inside this block. Known content failures follow the declared dependency rules; financial/authority/contract ambiguity halts. Operator interruption uses the existing bounded owned-container stop/recovery procedure. A forced process kill can bypass cleanup; retain and reconcile the recorded container and durable request intent before any relaunch.

## Completion criteria and exit decision

**Successful completion / eligible for expansion review requires all of the following:**

- Exact first task/repeat, A/B/C procedures, source/runtime/settings and accounted single-attempt request trace; no unauthorized probes, repeats or replacements.
- A/B ten answer slots and C's exact permutation, including preserved answer refusals/empty/truncated statuses where applicable.
- **All three native assessments have status `scored`.** Every first-stage slot is classified as `ok`, a preserved answer refusal/empty/truncation, or known `not_needed_nonhead`; no missing/invalid prerequisite or required assessment.
- Reconciled cumulative accounting, zero unresolved reservation/liability, all requested/returned identities and supported usage categories checked. Recorded cost is identified as a usage-based public-price upper bound, not an independently certified invoice.
- Exact saved-evidence native/coverage/analysis/decision replay; first-block report retains 69 missing orders and no full-study seed. No generation is needed to reproduce it.
- A manual review referencing the immutable first-block evidence/prefix concludes that the declared live path worked. **No positive utility, planning gain, reranking gain or human-reader rating/agreement threshold applies.** A low score or identity permutation is a valid result.

The saved review command independently checks its required evidence; `--approve` cannot bypass it. A zero process exit alone is insufficient. A budget stop, missing/non-scored native assessment or unresolved accounting produces a **usable bounded-stop/partial report, with successful readiness incomplete and expansion forbidden**. Preserve uncertainty; do not relabel it as method ineffectiveness or rerun failed slots until they pass.

## What happens next

1. **Now:** review this definition only. No grant or real credential is created/read and no provider probe/call is made.
2. **If subsequently authorized:** record a first-stage grant for this exact release/profile and the approved amount, at most $20; the grant covers only this first block. Operator confirms supported public accounts/current prices and supplies both keys through the inspected masked-entry launcher. Execute using the existing runbook; no new software prerequisite is planned.
3. **After a successful first block:** stop, review the actual trace and revise the remaining-work cost scenarios. Refresh the concrete expansion specification from these observations. Expansion needs its own applicable **cumulative** grant, currently proposed at **$125 total**, covering the remaining **23 blocks/69 orders/up to 1,265 requests** in the same journal. If $2 was already spent, $125 cumulative leaves $123. Neither this definition nor first-stage approval authorizes expansion.
4. **After an incomplete block:** deliver the partial evidence/hold decision. Resolve the actual defect or financial limit within the existing kit's correction/compatibility process; any effective source/science/budget change is explicit and versioned. Unknown liability is not cleared by a top-up, and consumed failed slots are not silently replaced. This does not introduce another unnamed preparation project.
5. **After complete Phase 2B:** native benchmark evidence can support its development seed decision without readers. Optional later human evidence attaches separately. Actual Harness² one-step and successive recursive refinement each receive their own concrete phase refresh before execution; neither starts automatically.

The [frozen runbook](PHASE2B_RUNBOOK.md) contains commands for preparation/inspection, first launch, review, cumulative expansion, interruption and replay. All monetary amounts here remain proposals or labelled scenarios. Original Buddha2 and every frozen P2-R artifact remain unchanged.
