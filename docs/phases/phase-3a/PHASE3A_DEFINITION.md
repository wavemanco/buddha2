# Phase 3A — Four-prompt native adaptation pilot

Definition **1.0**, 2026-10-28, America/Los_Angeles. **Planning only: implementation and experiments are unstarted and unauthorized.** This document supersedes the older 24-adaptation Phase 3A draft. It does not change any completed study or grant. [Current specification](../../research/CURRENT_SPEC.md); [machine-readable planning worksheet](../../../specifications/phase3a-v1.json).

## 1. Objective and usable output

Determine whether one authentic task-level Harness² adaptation round, initialized with C-N, produces useful outputs relative to a strong frozen C-N procedure under the **same predeclared resource allowance**. Establish actual execution, information boundaries, reliability and cost before larger or held-out work.

Deliver a usable fresh C-N execution route, a native adaptation route, a fixed budget-control route, inspectable proposals/probes/composition, eight planned final portfolios, native assessments, complete accounting and a reproducible report. The routes remain useful if adaptation loses, produces valid unchanged harnesses, or gives an inconclusive development result.

This is a four-prompt feasibility/development pilot. It does not establish population effectiveness, equal-realized-compute causality or successive recursive improvement. Those require later evidence.

## 2. Parent, population and exact scope

Use C-N as the frozen exploratory seed selected by P2B-N decision `5c2ddcbd434f53209f4245c519f9479229c6b06e6dec2b9043669c5a4f338dea`, study `0bbe532dd0b5e065f88d0f352538a10dbe2d1b5c0816856f6c3b518a2a00d27e`, procedure `16cd0c8b829c7147b51ff76bd38a350686ca1b3bf53e308cc4b76acbf0747de0`. Preserve the [live result and its limits](../phase-2/PHASE2B_RANK_FORMAT_LIVE_REPORT.md). Do not substitute a seed after viewing new outcomes.

Select the lowest four SHA-256 hashes of UTF-8 `phase3a-four-prompt-v1` + newline + the **parent manifest's `task.id` (`nb-curated-…`)**, from its 12 already exposed development tasks. This is not the nested upstream `source_context.source_task_id` (`curated-15`, etc.). Selection uses IDs, not utility/rank outcomes. The worksheet records all 12 eligible IDs, selected prompts, source revisions, prompt hashes and ordering hashes. No held-out inputs are opened.

| Order / pilot ID | Source | Prompt | Inference-arm order |
|---|---|---|---|
| 1 / `p3a-01` | `curated-15` | What would you invent to make the world a more interesting place to live in? | Fixed, adaptive |
| 2 / `p3a-02` | `curated-17` | What is the top item you would add to a grocery list for a memorable shopping experience? | Adaptive, fixed |
| 3 / `p3a-03` | `curated-96` | Suggest a strong 4 character password. | Fixed, adaptive |
| 4 / `p3a-04` | `curated-29` | Suggest a birthday gift for a friend's 25th birthday. Just one | Adaptive, fixed |

There is one repeat per prompt: **four paired tasks, eight selected final portfolios**, each containing ten answers. Search/probe outputs are additional saved work, not independent evaluation units. All generations are fresh; no historical portfolio is substituted for a new arm output. The password prompt remains a development diagnostic with known prior judging variation; hash selection does not make these tasks a fresh or representative sample.

### Adaptive arm — actual native `agg, k=1`

Use unchanged Google Harness² at `1cfe254e8d25b15f37048c3730134686abe60335`. Invoke its actual `schedule.run_task` with `k=1`, `modes=('agg',)`, `pool_policy='finals'`, `seed=None`, an identity-bound tag, `library=None` and `libraries=None`. Bind explicit proposer/selector channel metadata. Disable cross-task experience and subagents. Preserve native prompts/context construction; use `obs_trunc=50000`, `proposer_deliverables='contents'`, `state_deliverable=False` and no task files.

At this pin, each clean path executes C-N `base1`, model-authors INV/DOM harnesses, executes both probes, model-composes AGG from the available native evidence, then executes and delivers `agg1`: **four portfolio rollouts and three logical editing stages per prompt**. Four tasks therefore imply 16 rollouts and 12 clean editing conversations.

**There is no paid final selector at native `k=1, finals`. Only the composed `agg1` final is eligible.** Do not add a best-of-base/probes/final chooser, substitute a better probe, or silently replace an absent final with a base output. A model explicitly retaining the base harness is a valid unchanged proposal, distinct from automatically falling back after an error.

Native stages permit two shape attempts. Up to six admitted editing conversations/task (24/phase) are possible; stock code can also attempt up to 12 subprocess launches/task (48/phase) through its transport retry loop. Those are separate counters. A subprocess retry must not create another paid conversation: replay only a safely settled, identical logical conversation, or reject it. Unknown delivery/usage blocks every later outbound call, even if upstream catches the error and attempts a retry or fallback.

### Fixed arm — C-N best-of-six

Attempt exactly six independent fresh C-N portfolios: one ten-angle plan, ten independent answer requests conditioned on their own angle/task, then one permutation rank and frozen N1 per candidate. No candidate observes another candidate's plan, answers or judgments. No strategy/harness edits occur.

One additional Opus request chooses **one unchanged whole portfolio** from eligible candidates. It sees only the original task and complete anonymized ten-answer candidate portfolios, in a deterministic shuffled order frozen in the execution manifest. It sees no arm labels, source/cost metadata, trajectories, intermediate plans, human judgments or benchmark scores. The work criterion is useful, distinct answers that satisfy the task, without a numerical benchmark objective. Output is a strict candidate-ID object; no merging, rewriting, extra reranking, format repair or second selector call.

Candidate failures remain recorded and receive no replacement. The selector may choose among the valid candidates of the six attempted; none valid, an over-limit packet, refusal or invalid selector output leaves the fixed final missing. Never truncate candidates to fit the packet or choose a fallback on the selector's behalf.

Both arms have the same initial planner/ranker/N1 technique access and model access. Their frozen allocations differ: adaptive editing/composition versus extra independent sampling/selection. This compares complete procedures under equal allowed resources; it does not hold the selection mechanisms or realized compute identical.

## 3. What we will build

P2B-N normalized saved rank texts. It did not implement fresh C-N execution inside a live Harness² adaptation path. Phase 3A includes that integration; it is not presumed ready.

- **A narrow strategy executor and seed package.** Use an honestly named `portfolio-api` substrate/benchmark adapter. Execute C-N through the existing accounted API-generation primitives, with native Harness² owning proposal, probe scheduling and composition. An OpenCode solver is unnecessary; actual OpenCode is used only as the native model-backed harness editor. Do not relabel the synthetic Phase 0 proposer/executor as live.
- **A fully consumed editable surface.** Native authoring accepts an OpenCode-compatible surface schema; its only editable file here is `systemprompt.md`, containing one strict JSON object with exactly three nonempty string fields: `answer_system`, `plan_system`, `rank_system`. The deterministic executor consumes those exact decoded strings in the corresponding C-N system-message slots. Freeze the original C-N user templates, call topology, model settings, response schemas, N1, identities, evaluator and financial guards outside the editable tree. This pilot tests a bounded prompt surface, not all c1–c8 capabilities.
- **Conformance and raw-tree validation.** Materialize exact empty `guardrails.md`, `LongTermMEMORY.md` and `tool_descriptions/tool_guidance.md` before native base-tree reading. Retain only exact canonical compatibility README stubs. Validate the raw harvested harness inventory as well as parsed native trees, because native reading excludes README stubs. Reject other keys/files, scripts/plugins/skills/subagents, invalid encoding, duplicate JSON keys and oversized content. Native 24,000-character always-on limits still apply. Record native raw fingerprints and effective decoded-strategy hashes separately; whitespace-only changes do not establish effective adaptation.
- **A native editor boundary and fixed selector.** Use genuine upstream `Proposer` on `opencode`, provider/model `anthropic/claude-opus-5`, with bounded tools/filesystem and accounted egress. Pin OpenCode `23fb5e0516c99ac04a1aa46c193efda2e1b9bb24`, Bun 1.3.11 and only the upstream-declared compatibility patch, recording their exact hashes/licenses. Request `steps=6`, `timeout=600` seconds for each editor conversation; actual provider HTTP timeout is 90 seconds for every role. These requested settings must be backed by the accounted boundary, not assumed to enforce provider-call limits. A timeout with unknown delivery retains liability and halts rather than resubmitting.
- **One scoped execution/accounting route and separate evaluator.** Reuse artifact, journal, admission and native-assessment seams where compatible. Add phase-specific adapters/policies outside frozen source; do not weaken old loaders, falsify method/study identities or copy Harness²'s algorithm. Every provider request, including editor tool loops and discarded work, goes through the phase's authoritative accounting boundary. Native ledger USD fields are supplementary because they do not capture all rollout costs.

The base seed must render byte-identical C-N provider bodies for the same supplied mock task/plan/answer IDs and texts. Every permitted substantive field edit must demonstrably affect the actual serialized requests. Fresh rollout IDs and new provenance are declared variability, not claims of bit-identical model regeneration.

Preserve small interfaces between strategy materialization, actual engine execution, task protocols, compatible assessment and accounting. Keep upstream and closed study sources unchanged; create a new source/runtime/study identity. Build no general plugin registry, database or research platform.

## 4. Roles, information and resource contract

| Role | Proposed exact profile |
|---|---|
| Strategy plan / ten answers / permutation rank | `claude-sonnet-5-5`; adaptive thinking, effort `low`, `max_tokens=4096`, `service_tier=standard_only`, `inference_geo=global`; original C-N bodies/omissions and N1 |
| Native editor/composer | `anthropic/claude-opus-5` channel ID, bare `claude-opus-5` on wire; adaptive thinking, effort `high`, `max_tokens=16000`, standard-only/global; at most six actual provider requests per logical conversation |
| Fixed whole-portfolio selector | `claude-opus-5`; same requested thinking/effort/output/tier/geography; one request, strict candidate-ID result, no tools |
| External native grouping | `gpt-5.6-luna`; unchanged NoveltyBench Chat Completions/schema; effort/output cap/temperature/seed omitted |
| External native head quality | `claude-opus-5`; unchanged adaptive/high/16,000 native score schema; tier/geography omitted |

No model upgrade, account probing, paid token-count calls or fallback provider. Request/returned model IDs, effective settings, usage categories, prompts and transformations must be recorded. Output caps include thinking. No model-internal rationale is assumed to be retained.

The editor sees its own task-local base/probe evidence and practitioner-facing guidance only. It cannot see fixed-arm candidates, prior project reports, benchmark judge code/rubrics, native/human scores, confirmation data or credentials. Final selector and native judge requests carry no method labels or prior judgments. Seal both primary finals for a pair before judging either; no external assessment feeds proposals, composition or selection. No shared task library, conversational memory or cross-arm output sharing.

Untrusted authoring contexts must be isolated from the project/archive/credential files; a different working directory alone is insufficient. Keys enter a trusted controller through reviewed masked prompts/transient input and are absent from editable worker contexts. Restrict editor tools and paths; no arbitrary shell/network/subagent escape. Only the inspected accounted endpoint may reach a provider. Traffic is serialized globally, including native parallel branches; queued requests wait without opening simultaneous reservations. Keep native `agg` control flow unchanged.

### Same allowance for every inference arm/prompt

| Joint ceiling | Each fixed or adaptive arm |
|---|---:|
| Conservative accounted dollars, including unresolved/next-call liability | **$20** |
| Actual provider HTTP inference attempts | 96 |
| Aggregate billable input tokens, including open/next maximum reservation | 4,000,000 |
| Aggregate billable output tokens, including open/next maximum reservation | 786,432 |
| Strategy response maximum | 4,096 tokens/request |
| Editor/selector response maximum | 16,000 tokens/request |
| Editor/selector serialized request maximum | 1,048,576 UTF-8 bytes |

All limits apply jointly. Reuse the original strategy payload limits (5,952 bytes plan/answer, 61,952 rank). A too-large exact selector packet or edited request fails admission; do not silently truncate it. Prove supported maximum billable-input reservations for new roles before launch; a character/token estimator or CLI-reported total is insufficient.

Expected clean topology is 48 strategy requests/adaptive arm and 72/fixed arm, plus editing or one selector. With two shape attempts/stage and six actual editor requests/conversation, adaptive has at most 84 inference requests/arm; fixed has at most 73. Across four pairs this is at most **628 inference requests**, before earlier stops. The configured maximum output demands are 772,608 adaptive and 310,912 fixed tokens/arm, both within the common output ceiling.

Budgets are **allowances**, not target spend. Unused inference allowance expires and cannot transfer across arms/prompts. Do not burn tokens to equalize costs or add candidates after seeing outcomes. Report realized role/model requests, input/output/cache/thinking usage, dollars, wall time and allowance utilization separately. Equal ceilings alone do not support a claim of equal realized compute.

## 5. Native evaluation and embedded variability diagnostic

Keep NoveltyBench v1.1 at `64a23be6b18ec1dacc298830aab276061b6e143c`, native prompts/folding/strict parsing, patience 0.8 and delivered ordering (`seed=None`). Assess the eight selected finals once each. Probe/candidate portfolios are preserved but not externally judged or fed scores during search.

The predeclared diagnostic anchor is the **selected fixed final of `p3a-01`**. Assess that identical portfolio a second time, independently with no prior judgments in context. Retain its first primary assessment unchanged; the second is diagnostic only. Report partition, shared-head-score and utility disagreement. One duplicate is not a calibration study or a reliable variance estimate. Missing anchor means no replacement; a known failed duplicate is reported and does not overwrite/block otherwise complete primary scores. Unknown liability still halts the phase.

The complete plan has **nine grouping and 9–90 head-quality calls: 18–99 external requests**. Assessment has its own **$60** pool, separate from the eight inference allowances. Use the retained conservative reservations, $1.661880/group and $11.44/quality. Native scoring failures remain non-scored, with no repair/replacement. Classify every declared slot, nonhead, failure and skipped dependent request.

Primary descriptive contrast: for each prompt, adapted `agg1` utility minus fixed selected utility; average the four differences only with all eight primary finals valid/scored and known accounting. Also report distinctness, first-answer quality, coverage/failures and actual inference/assessment costs. Keep valid native fallback finals in the planned procedure comparison and flag them; do not discard unfavourable outcomes. Incomplete primary coverage yields explicit missingness and no complete-case aggregate winner. A valid unchanged model proposal is not a failure.

This pilot promotes no universally best procedure and supplies no significance, held-out or human-preference claim. Report the mean sign descriptively, the duplicate diagnostic separately, and whether authentic stages succeeded, stayed unchanged or fell back. If every adaptation path lacks usable model-backed stages, the core mechanism remains unverified even if a fixed fallback can be scored.

## 6. One phase, with internal checkpoints

1. **Offline implementation and feasibility gate.** Build the complete four-pair executor/control/report path, not just the first-pair launcher. Prove seed conformance, all consumed edits, actual upstream orchestration, bounded authoring egress, exact model profiles, per-request/turn/aggregate accounting and pre-call liability admission, all native repair/transport attempts, unknown-result halt, isolation, recovery/resume and native report replay using fake keys/mocks/network-disabled tests. Read-only source/runtime/grant/container inspection and the pre-key handshake are required. No real credentials or provider endpoint is needed for this checkpoint.
2. **Counted first pair: `p3a-01`.** After future applicable authority and operator keys, execute both arms and their two primary plus one diagnostic assessments. Review the actual trace, effective settings, native stage dispositions, selector, missingness and costs. This is part of the four-prompt sample. Continuation depends on engineering/accounting/information-boundary checks, never on favourable utility or a required file change. Do not tune or replace the pair after review.
3. **Remaining three pairs and closure.** Under the same approved whole-phase scope, execute the frozen remaining pairs only if the engineering review permits it. Publish the eight-outcome coverage, diagnostic, complete or incomplete descriptive comparison, exact replay, preserved failures, cost report and verified local evidence packet. No serial unnamed prerequisite phases or automatic subsequent phase.

Planning timebox for the offline build: review feasibility at four focused hours; stop at twelve focused hours if an essential bounded native/channel contract remains unproved. Deliver the usable offline components and a specific change-required/hold report rather than continuing an open-ended platform build. This is a planning allowance, not a developer-time quote or permission to start.

Known proposal/candidate/scorer failures remain classified; no replacements. A valid native automatic fallback is exposed as such, not relabelled as successful model-authored improvement. Halt all outbound calls on unknown usage/delivery, source/model/profile mismatch, isolation/information-boundary failure, unpriced fees or a breached overall resource ceiling. An arm reaching its own ceiling stops that arm; no borrowing. Resume reuses identical settled work and never resends an unknown request. Implementation defects requiring changed effective prompts/policies after live observation require a versioned amendment/new identity; no quiet mid-run fixes.

## 7. Deliverables and completion criteria

Deliver the versioned executable C-N seed, external portfolio adapter, actual native proposer route, best-of-six control/selector, complete runner with internal gates, role/source/runtime/grant manifests, four-prompt worklist, guarded operator handoff, complete artifacts/trajectories, separate native assessments/duplicate diagnostic, authoritative request ledger, public analysis and a verified tracked archive/report. Export/assessment interfaces remain usable independently of adaptation.

Completion requires runnable proof that all declared inputs/edits reach execution, actual upstream/model-backed native activity is evidenced, every scheduled stage/candidate/final/request is classified, eight primary final outcomes are accounted for, all limitations/missingness are explicit, no unresolved liability remains, and saved native/analysis replay makes no new provider calls. All original source/results must remain unchanged. Negative/inconclusive scientific findings are valid; a merely mocked or unbounded editor does not complete live adaptation readiness.

A **complete primary pilot** requires all eight valid/scored primary finals and at least one complete live native path with valid model-backed INV/DOM proposals, their executed probes, valid model-backed AGG composition from that evidence, and the executed `agg1` final. Explicit valid unchanged proposals/composition count; automatic fallback alone does not. Otherwise publish an execution/measurement-limited result, retaining every valid fallback final in the planned procedure comparison. The usable offline route/report is still delivered on a feasibility hold, without pretending the live comparison completed. The duplicate requires a classified outcome, not a passing agreement threshold. Close before proposing Phase 3B.

## 8. Estimated cost and proposed caps

**This definition costs $0 API spend. Offline implementation/mock checks require $0 provider spend.** Assistant-session fees, local compute and developer time are outside this API worksheet. No implementation or paid grant is supplied by this document.

Prices were searched/opened on 2026-10-28: ordinary input/output per million tokens are Sonnet 5.5 $2/$10, Opus 5 $5/$25 and Luna $0.20/$1.20. Caching categories differ. Sources: [Sonnet](https://platform.claude.com/docs/en/models/sonnet-5-5/overview), [Opus](https://platform.claude.com/docs/en/models/opus-5/overview), [Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing), [OpenAI Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna), [OpenAI pricing](https://developers.openai.com/api/docs/pricing). They establish public rates, not account availability, exact editor serialization or an invoice guarantee. Recheck before future launch; preserve the declared models.

The [worksheet](../../../specifications/phase3a-v1.json) assumes all 40 clean C-N rollouts complete their 12 calls (**480 Sonnet requests**), 12 clean editing conversations, four fixed selector calls and nine assessments. It sums every billed turn's repeated input/context and output/thinking tokens. It uses ordinary uncached inputs and a conservative 1.1 accounting multiplier for all Opus roles and grouping. That multiplier is an accounting allowance, not a claim that global-routed requests necessarily incur a 10% provider fee. Cached settlement categories, tool overhead and real backend profiles must be accounted explicitly; no discounts or free repair calls are assumed.

| Conditional demand scenario | Clean topology | Every editor stage needs second shape conversation | First pair with duplicate anchor, clean |
|---|---:|---:|---:|
| Lean | $6.89 | $9.46 | $1.76 |
| Working | **$15.89** | **$22.63** | **$4.13** |
| Heavier | $47.75 | $68.35 | $12.98 |

Working assumptions: each Sonnet call averages 2,000 input/1,000 output tokens; each editor conversation uses six provider requests averaging 12,000 input/1,000 output tokens; each fixed selector uses 20,000 input/1,000 output tokens; five quality heads per assessment average 2,500 input/1,000 output tokens. Exact lean/heavier assumptions and arithmetic are in the worksheet. These are untruncated demand scenarios, **not measured forecasts or promises that all work fits its local allowance**.

**Proposed new phase cap: $220 = eight independent $20 inference cells + one $60 assessment pool.** An included first-pair review limit is **$65**: its two $20 cells plus a $25 checkpoint sublimit within the same $60 assessment pool. Neither amount is additional to $220. After engineering review, remaining assessment spending still draws on the original $60 total; unused inference cells cannot subsidize another arm.

The $25 first-pair assessment checkpoint is a pause for engineering review, not a new pool. If it blocks an originally planned but unattempted first-pair judgment with all earlier usage known, a recorded successful engineering review may unlock that same remaining slot under the unchanged cumulative $60 assessment ceiling. Finish those original first-pair slots before later-pair assessments. No failed result is replaced or repeated, no unknown request is resent, and no inference cell is increased. An integrity/unknown-liability hold cannot be unlocked this way.

Retaining an $11.44 Opus reservation means another editor/selector call cannot start after its arm's known settled spend exceeds **$8.56**, even when the $20 cap has not been spent. Another quality call needs prior assessment spend at most **$48.56** under its $60 pool (or $13.56 inside the included first-pair assessment checkpoint). Unknown requests retain applicable dollar/input/output reservations and halt. New role bounds must be proved offline; existing judge controls alone do not certify OpenCode.

The declared shape/turn limits allow up to **628 search requests + 99 judge requests = 727 actual provider attempts**, before earlier stops. All configured output maxima fit the common output pool, but growing contexts, repair demand, input/financial reservations and unknown outcomes can still prevent completion. A separate sensitivity with 90 quality calls at 1,000 input/full 16,000 output tokens plus nine $0.01 groupings costs $40.185 accounted; it fits the $60 pool but output-cap results may be truncated instead of valid scores.

Keep previous Phase 2 spending $6.350952 separate and count each historical call once. Old unused grants provide no authority here. One future whole-phase authorization can cover the specified offline work, internal review and paid four-prompt envelope; elapsed time or a green offline gate is never spending approval.

## 9. Exclusions and later phases

Out: a new ordinary-A arm; the old 24-adaptation matrix; additional generators/efforts/strategy families; open-ended prompt sweeps; full c1–c8 skill/plugin/tool-code adaptation; changing the benchmark/native judges or N1; CrPO/MuCE/evaluator tournaments; Bayesian surprise; human recruitment; shared cross-task memory; sequential `k=2` or greater recursion; held-out inputs; external publication; upstream algorithm copying/patching; unrelated benchmark runtime installs; generic orchestration infrastructure; silently extending caps or rerunning failures.

Phase 3B remains the separate genuine successive-refinement milestone. Refresh its exact starting procedure, prompts, native `seq,k=2` path, matched control, budgets and failure rules using Phase 3A's observed route/costs; a negative one-step finding alone does not refute repeated refinement. Do not claim a standalone `k=1` run is an interchangeable first round of `k=2`.

Phase 4 remains fresh held-out confirmation of a frozen method under budget-comparable controls. Recalculate its sample/model/precision/budget plan after development evidence rather than automatically launching the old 480-portfolio envelope. Human-augmented evidence remains optional and separately versioned. Any future engine, strategy or benchmark update gets its own version/pin and compatibility checks; no closed run is rewritten.
