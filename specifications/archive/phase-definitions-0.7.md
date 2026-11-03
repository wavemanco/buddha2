# Buddha2 phase definitions

Revision: 0.7 — 2026-10-25, America/Los_Angeles  
Status: Phases 0 and 1 complete under their frozen definitions; Phase 1A data-readiness checkpoint defined and unstarted; subsequent work provisional and unstarted  
Authority: the user requested a concrete data-readiness definition and specification update after examining Phase 1 disagreements. This revision authorizes that planning work only. It does not start Phase 1A, authorize new model calls, or extend the closed Phase 1 $5 grant. 

The [experiment plan](../../docs/research/EXPERIMENT_PLAN.md) gives the research rationale. This document specifies work products and completion gates. [DECISIONS.md](../../docs/phases/phase-0/DECISIONS.md) remains Phase 0's historical implementation decision record. Phase 0's exact [specification](phase-definitions-0.3.md) and [decisions](phase0-decisions-0.3.md) are preserved byte for byte; their hashes match the retained run manifest. Use the [handoff report](../../docs/phases/phase-0/PHASE0_REPORT.md) for evidence and navigation. The archives retain links originally authored relative to the project root.

Refreshing this file changes the effective input identity for a new Phase 0 run. Do not edit old manifests, reports, assessments or the example archive to make them match revision 0.7. Historical completed-run resume belongs to commit `6bafb25` and its frozen inputs; current definitions require a fresh output directory. Revisions 0.4, 0.5 and 0.6 are preserved in specifications/archive. PHASE1_DECISIONS.md records the approved population change; PHASE1_REPORT.md records execution, the readiness exception and final result. Phase 1's closeout manifest binds documentation at commit `35cc481`, including the exact archived revision 0.6; subsequent documentation edits do not invalidate that historical acceptance or rebind its manifest. This revision adds a new checkpoint without rewriting the completed experiment.

## Working rule for every phase

Before starting each phase, repeat this definition exercise and present its current specification: objective, usable output, inputs, work, exclusions, acceptance checks, budget, limitations, and the decision at its end. A request to begin a reviewed, unchanged phase can authorize its defined implementation scope; it does not supply an unspecified paid-call budget.

Use this short cycle:

1. **Define:** revise the phase using available evidence. Identify the exact models, revisions, data, checks, caps and unresolved choices relevant to that phase. Later phases may retain explicit decision points; an active phase may not leave its execution-critical choices implicit.
2. **Review:** present the bounded specification and changes before starting. Resolve missing choices or authorization. A definition is a proposal until the user authorizes the work.
3. **Build and verify:** complete a small usable slice. Stop and report before chaining into the next slice. New features enter the backlog unless needed to meet the current acceptance criteria.
4. **Close:** deliver the usable artifact, evidence, limitations and next decision. Never advance automatically to the next phase.

Before observation, snapshot the applicable specification revision with the run definition. Record material changes, their evidence and consequences. Preserve earlier results under their original definitions; do not rewrite thresholds after seeing outcomes. A changed intervention or opened holdout may require a new run or fresh confirmation material.

Every closure distinguishes **usable completion**, **closed with a diagnostic limitation**, and **incomplete because of an integration or accounting defect**. A preferred method need not win. A broken execution path is not evidence that the method is ineffective.

## Phase 0 — Usable offline integration kit

**Closed:** all P0-1 through P0-8 passed under revision 0.3: 43 project tests, five upstream tests and documented workflows. The following scope is retained for reference; the archived revision and original evidence govern that completed work. It established offline execution/artifact behavior, not live judge validity, transport or spending enforcement.

### Objective

Prove that a small external integration can invoke actual, unchanged upstream Harness², materialize one strategy, preserve the selected response portfolio, and evaluate that artifact through separate assessment routes. Establish these boundaries without contacting any model provider.

### Usable output

A researcher can follow documented commands in one supported environment to run a deterministic example, inspect its effective harness and trace, export the selected portfolio, validate an imported compatible portfolio, and rerun offline assessments without generation. The result is a command-line research tool with an inspectable example, not just interface diagrams.

All example responses, proposal decisions and judge inputs are visibly marked as fixtures. The tool is useful for integration work and artifact inspection; it does not yet generate new real-model answers or establish live readiness.

### Inputs and decisions to settle before implementation

- Source pins resolved: Harness² `1cfe254e8d25b15f37048c3730134686abe60335` (Apache-2.0), NoveltyBench `64a23be6b18ec1dacc298830aab276061b6e143c` (MIT). See DECISIONS.md for the CPU dependency subset, license notes and exact synthetic protocol. Lock the transitive dependency closure before installation.
- Environment resolved: available Docker Desktop Linux engine, Linux/amd64, pinned Python 3.12.15 slim-bookworm image. Runtime execution is network-disabled and credential-free. Do not build another platform path.
- Native seam resolved: upstream `OpencodeSubstrate` materialization in workspace-config mode with a deterministic local fixture launcher. Actual OpenCode/provider execution remains unverified in this phase.
- Freeze one synthetic prompt, one ten-response portfolio, one deterministic proposal sequence using a single native parallel `k=1` path, and small malformed/incompatible fixtures. These are development assets, not benchmark evidence or held-out inputs.
- Agree the minimal adapter/runner/artifact shape and offline checks before implementation. Reuse upstream facilities and ordinary files wherever they suffice.

All project writes, upstream checkouts, dependencies and run artifacts stay under the project root or its dedicated container image. Validate canonical output/mount paths before execution and retain the actual mount configuration as evidence.

### What we will build

| Piece | Minimum behavior |
|---|---|
| Reproducible setup | One documented setup with pinned dependencies, license notes, and the exact upstream source revision/path. Keep upstream checkouts unchanged. |
| Thin external runner and task adapter | Invoke the real Harness² scheduler through its existing contracts. Supply a representative NoveltyBench-shaped task through a deterministic local fixture. Do not recreate proposal/probe/compose/selection. |
| One strategy package | Materialize the intended planner-and-generation workflow as inspectable native harness files. Preserve its prompt/file identities. Model-generated planning is replaced only in the explicitly labeled fixture route. |
| Artifact boundary | Save task ID, status, ten stable response IDs/texts/order, effective harness/trace references, and provenance. Export the native NoveltyBench generation format and validate compatible imports. Keep response IDs in a small companion mapping keyed by output hash/index when the native format carries only ordered strings. |
| Independent assessments | Read saved output through native NoveltyBench loading/scoring arithmetic with frozen synthetic partitions/head scores, plus a mechanical portfolio/schema check. Store separately identified assessments without editing the output. No live judge. |
| Minimal identity and recovery | Bind run identity to task/configuration and all effective files. Use ordinary immutable files and explicit statuses; refuse incompatible reuse and avoid duplicate completion records on resume. No database or queue. |
| Offline report and checks | Produce a readable example report, zero-provider-call evidence, and runnable regression checks for the boundaries below. Fixture usage/accounting records must be distinguishable from real usage. |

Upstream already provides a deterministic proposer pattern that calls the real scheduler and executes local Python. It demonstrates orchestration without exercising the real OpenCode CLI. The external adapter fixture must also traverse the upstream path; merely running the bundled demo is insufficient. [Native demo entry point](https://github.com/google-research/harness2/blob/main/harness2/cli/demo.py), [fixture implementation](https://github.com/google-research/harness2/blob/main/harness2/demo.py).

### What stays out

- Live model generation, real proposer/selector reasoning, paid judges, model downloads, MuCE calibration, or comparative experiments.
- Claims about quality, self-improvement, deeper recursion, or `agg` versus `seq`.
- Implementing reranking or a Lenny/Lluminate strategy library. The artifact format must preserve response order/identity; the reranker itself belongs in Phase 2.
- Live provider transport, real agent tool/plugin behavior, or production billing enforcement. Record these as unverified, not implicitly solved by fixture tests.
- A plugin marketplace, dynamic discovery, universal benchmark language, dashboard, custom model gateway, distributed execution, or a second benchmark implementation.
- Editing either upstream algorithm to make the fixture pass.

### How we know it is done

| Check | Required evidence |
|---|---|
| P0-1: Real upstream control flow | A trace identifies the pinned scheduler, deterministic proposer fixture, probes, composition and selection. The external adapter participates, and a controlled fixture difference proves that the effective materialized harness affects probe execution. Record native trivial selection at `k=1` explicitly; no model-backed proposer or selection has been verified. |
| P0-2: Inspectable strategy | The materialized files and their hashes match the declared package and upstream tree requirements. A Markdown/prompt change changes identity, just as a code change does. |
| P0-3: Native artifact exchange | The selected ten-response portfolio exports successfully and is read by the pinned native NoveltyBench loader. Task ID, texts and order survive the round trip; the companion mapping restores/verifies response identities without requiring custom fields in the native loader. Duplicate texts are permitted; duplicate external IDs are not. |
| P0-4: Separate assessment | Native arithmetic on declared synthetic partitions/head scores matches frozen expected utility/distinctness/summary values. A second mechanical assessment references the same output hash. No response regeneration or mutation occurs. |
| P0-5: Failure boundaries | Malformed records, missing evidence, duplicate IDs, incompatible capabilities and mismatched manifest/artifact identities produce explicit failures. No silent fallback or fabricated successful score. |
| P0-6: Recovery | At one declared interruption checkpoint between output and assessment finalization, resume produces the expected artifacts without duplicate finalized outputs/assessments. Replaying local deterministic work is acceptable; arbitrary-crash exactly-once guarantees are out of scope. Changed effective inputs require a new identity or an explicit refusal, never silent stale reuse. |
| P0-7: Zero external calls | The fixture checks pass without credentials and with outbound networking denied during execution. All generation/judge/proposer behavior is local and marked synthetic. A non-fixture invocation refuses before dispatch. This proves offline containment, not live cost enforcement. |
| P0-8: Usability and handoff | Documented setup/example/import/assessment commands are exercised; relevant upstream fixture and project boundary checks pass. Deliver the sample artifacts, test evidence, source-integrity evidence and an explicit list of live behaviors still unverified. |

The native NoveltyBench arithmetic/loading seams are source-backed integration targets, not a reimplementation specification: [score](https://github.com/novelty-bench/novelty-bench/blob/main/src/score.py), [summary](https://github.com/novelty-bench/novelty-bench/blob/main/src/summarize.py), [generation loading](https://github.com/novelty-bench/novelty-bench/blob/main/src/partition.py). Frozen inputs do not validate a live grouping or quality judge.

**Budget:** zero model/provider calls. The user has authorized Phase 0's offline implementation and verification; ordinary dependency setup and advisory checks may access public source/package registries, while fixture execution itself remains offline.

**Exit decision:** accept the offline kit, request a bounded correction, or report a specific upstream incompatibility. If passing requires replacing upstream recursion or adding another platform, stop and review that change. Phase 1 remains unstarted until its definition is refreshed and its work authorized.

## Shared entry conditions for paid phases

At the relevant phase review, name eligible task IDs/splits, effective prompts/strategy files, all model roles/settings, native protocol/evaluators, independent unit, planned counts, quality/failure rules, and the spending/attempt ceiling. Freeze these before the corresponding observations. Never expose final judgments to the score-blind arm.

Before a new live path expands, perform a separately budgeted tiny readiness check on development material. Verify the actual executor/provider route, supported controls, reservation/accounting, timeouts and bounded retry behavior; offline tests do not establish these. Where possible, use the first predeclared development item as that check and count it in the phase, rather than adding an unrecorded experiment. Stop and review it before bulk execution. Unknown billing liabilities remain recorded and reserved; unsupported controls or incomplete accounting stop expansion.

The Phase 1 critic path, Phase 2 generation/judging paths and Phase 3 proposer/selection paths each need relevant live evidence. Reuse valid readiness evidence where the effective path is unchanged. Use development-only material for any confirmation preflight; do not tune on held-out results.

A Phase 1 MuCE pass is limited to its pairwise comparison contract/population. New model outputs, absolute ratings, whole portfolios and new task families require their own applicability decision; by default such use remains diagnostic. A failed MuCE audit does not prevent later native benchmark evaluation plus predeclared blinded human review. Do not add an unbudgeted transfer study as an implicit requirement to start the next phase.

## Phase 1 — A usable, audited creativity evaluator

**Closed:** all P1-1 through P1-8 are complete under [frozen revision 0.5](phase-definitions-0.5.md), with the explicit [user-approved operator readiness exception](../../evidence/phase1-live/readiness-exception-approved.json). All 48 presentations finalized for $0.112696 usage-based API cost, with zero retries or unresolved reservations. Held-out both-orders human agreement was 4/12 (floor 9) and order consistency 8/12 (floor 11): **diagnostic-only**, not a screened-valid critic. The [report](../../docs/phases/phase-1/PHASE1_REPORT.md) records the single calibration-only JSON-format revision, prediction commit before label access, byte-identical offline replay and credential cleanup. The scope below retains the completed definition; its estimates and pre-launch statements are historical, not authorization for a repeat. The audit is now consumed for a revised critic.

### Objective and claim

Determine whether **one frozen LLM evaluator can choose the human-higher-rated creative response to the same prompt, consistently across response order**, on a small declared MuCE population. Deliver a usable comparison tool and a clear pass, diagnostic-only, or inconclusive decision. This phase evaluates an evaluator; it does not test strategy quality or recursive improvement.

The public MuCE configuration provides a response and one aggregate rating with source/task metadata. It does not supply separate human truth labels for every CrPO measurement dimension. Its public ordinary splits do not establish prompt separation, and model-pretraining exclusion cannot be established here. [Pinned dataset card](https://huggingface.co/datasets/CNCL-Penn-State/MuCE/blob/a02181e394c41602a95d0678b0ce9d880e994289/README.md), [paper, data construction and evaluation](https://arxiv.org/html/2505.14442v2).

### What we will build

| Piece | Bounded deliverable |
|---|---|
| MuCE preparation route | Read the pinned development split, validate source/rating semantics, create one eligible pair per normalized prompt group, and save deterministic calibration/audit manifests with separate label records. No training pipeline. |
| One evaluator package | Versioned rubric and one provider/model profile. Input: prompt plus two saved responses. Output: `A`, `B`, `tie` or `abstain`, a short reason, explicit execution status and provenance. A result references stable response IDs and input hashes. It is a pair record, not a fabricated ten-response portfolio or a synthetic Native NoveltyBench score. |
| One bounded live route | Direct use of the installed provider SDK where sufficient, one process and sequential requests; refuse concurrent writers for a run. Explicit token/attempt limits, recorded intent/results/usage and conservative handling of unknown billing. No custom gateway or general accounting platform. |
| Replayable analysis | Read saved judgments and, only at the declared audit point, labels. Recompute agreement, consistency, coverage, uncertainty and cost without model calls. |
| Handoff | A working documented comparison command, immutable sample judgments, frozen rubric/profile, eligibility and exclusion counts, an applicability report and the next decision. |

Two delivery checkpoints keep the phase useful and bounded. **First:** the zero-model-cost preparation, pair contract, rubric/profile, replay report and offline failure checks work; review before any paid launch. **Second:** the bounded live calibration/audit delivers the evaluator decision. These checkpoints do not authorize one another automatically.

### Approved data selection

- **Pin:** `CNCL-Penn-State/MuCE`, revision `a02181e394c41602a95d0678b0ce9d880e994289`, configuration `full_agreement`, `train` only. Repository metadata declares MIT; retain attribution/notices and record any applicable source-dataset restrictions during preparation. No paid data subscription is expected. The public `val`, `test`, `heldout_item` and `heldout_task` splits remain unopened in this phase. [Pinned metadata](https://huggingface.co/api/datasets/CNCL-Penn-State/MuCE/revision/a02181e394c41602a95d0678b0ce9d880e994289).
- **Size:** 24 unique eligible **Metaphors** prompt groups, 12 calibration and 12 audit. The source inspection disproved the original four-family creativity quota: zero eligible Alternative Uses/Design groups, one Real-Life Problem Solving group and 46 Metaphors groups after exposed-example exclusion. Before selection, the user explicitly chose Metaphors only to preserve overall creativity. This narrows applicability rather than changing the construct or acceptance floors.
- **One construct:** overall creativity, literal `RatingLabel="creativity"`. Originality remains excluded. The source provides 978 creativity-labeled Metaphors rows and 46 eligible prompt groups under the frozen policy. Public metadata/paper semantics were checked before allocation. An insufficient population must still produce a shortfall manifest before any pair allocation or calls.
- **Pair eligibility:** English, identical effective task/prompt and compatible `Dataset`, `Set`, `DatasetsSplit`, task/language and rating context; two different nonempty responses; finite, documented scaled human scores with gap **at least 5 points**. The paper reports a 10–50 rescaling and uses a five-point preference margin; verify that interpretation for the pinned public fields rather than re-rescaling or treating cross-source scores as interchangeable. Ambiguous scales/context are excluded pending resolution. [MuCE preference construction](https://arxiv.org/html/2505.14442v2#S4).
- **Selection:** freeze normalization (Unicode NFKC, case-folding and collapsed whitespace for grouping only), prompt/context alias rules and seed `20261024` before inspecting evaluator outcomes. Retain original text. Cluster duplicate prompt identities across sources before allocation. Choose groups, split assignment and one eligible pair by stable seeded hash order; do not choose the easiest pair, largest rating gap or best observed evaluator result. No mid-run replacements.
- **Identity:** preserve dataset revision/configuration/split, original source IDs, all field values, prompt/response hashes and selection revision. Source `ID` is reused even within a prompt; it is not a unique response key. Use complete source/context/prompt/response content identity, excluding score, and retain source ordinals privately. True conflicting full-content identity/ratings fail. Cluster normalized source and effective-prompt aliases before allocation; never merge distinct response records merely because their texts match.
- **Exclusions:** reserve every selected calibration/audit group from future method confirmation. Documentation review exposed published example response/label material; exclude prompt groups illustrated in the paper's example-response tables (10–14) and its Sentence Completion example. Record that exposure instead of claiming the public examples were unseen.
- **Separation:** the preparation process may read ratings to construct pairs; it emits audit inputs separately from audit labels. The critic receives no ratings, source prestige, preferred-response position or other judgments. Calibration tuning sees calibration outcomes only. Freeze the complete final rubric/model/settings before audit inference; commit all audit predictions before unsealing audit labels. Record label access. This is experimenter-held-out evaluation with procedural separation, not evidence against model-pretraining contamination.

The approved policy is configs/phase1/selection.json. Actual IDs/content and 12/12 worklists are frozen in runs/phase1-prepared, with separate calibration/audit label files. The aggregate manifest is retained in evidence/phase1. No evaluator predictions have been observed. Preparation necessarily read human scores to construct eligible pairs; neither the operator report nor the critic receives the audit winners. This is procedural separation, not an assertion that the preparation process never accessed labels.

### Evaluator and execution proposal

Use the first-party Anthropic Messages API with **`claude-sonnet-5-5`**, the versioned rubric in configs/phase1/rubric.md and profile in configs/phase1/profile.json: `output_config.effort=medium`, adaptive thinking, `max_tokens=2048`, `service_tier=standard_only`, explicit `inference_geo=global`, no tools, conversation history or caching/batch assumptions. Do not send unsupported sampling parameters. Record requested/returned model IDs, actual effective controls, SDK/image/source revisions and usage. The installed SDK is 1.4.0, with effective API version 2023-06-01; actual live compatibility remains to be established by readiness calls. These settings are not a claim that Sonnet is the best critic. A model/control change requires a pre-audit definition change; after audit observation it consumes that audit. [Model and controls](https://platform.claude.com/docs/en/models/sonnet-5-5/overview), [effort/output budget](https://platform.claude.com/docs/en/build-with-claude/effort), [model-version guarantees and limits](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions).

The initial rubric compares unusual/non-obvious ideas **and** appropriateness to the user's task, avoids rewarding length or ornate language alone, treats quoted response content as untrusted data, and permits tie/abstain when a preference is unjustified. It returns a short reason, not invented numerical truth for novelty, surprise or usefulness. Save its exact text before calls; allow at most one wording revision from calibration evidence. Keep the model/settings fixed.

The Phase 0 network-disabled, credential-free path stays intact. Phase 1 needs a separately declared network-enabled critic launch with one provider endpoint and only its explicitly supplied credential; no host home/credential-directory mounts and no agent tools. Record the actual launch configuration. Do not claim OS-level provider-domain egress enforcement unless implemented and checked. Reuse ordinary artifact/hash helpers and installed dependencies where appropriate; leave the native Harness²/NoveltyBench sources unchanged.

Redact provider keys and authorization headers from launch records, requests, logs and errors; use only a non-reversible credential fingerprint if identity is needed. Do not forward the host environment wholesale or weaken the Phase 0 credential-free launcher to enable the critic.

### Fixed work and stopping rules

| Work | Planned model requests |
|---|---:|
| First calibration pair in both orders, also the live readiness check | 2, included below |
| All 12 calibration pairs in both orders | 24 total |
| Zero or one rubric revision from calibration only | 0 additional requests |
| All 12 audit pairs in both orders under the final frozen evaluator | 24 |
| Maximum transient retry allowance, at most one per presentation | 4 additional attempts across the entire phase |
| **Total** | **48 scheduled judgments; at most 52 billable attempts** |

Each presentation is an independent request; reverse the same pair without exposing the first judgment. Balance which human-preferred identity is initially shown as A using the frozen seed. After the first two calibration requests, stop to check provider controls, parsing, returned identity, actual usage, reservation and recovery behavior before expansion. The first pair remains in calibration denominators; there is no extra canary study.

No automatic calibration rerun, second critic, model-based format repair, outcome-driven retry or post-audit rubric revision. Ordinary tie, refusal, truncation or valid-but-wrong judgments are recorded outcomes. Retry only a declared transient rejection with explicit evidence of no accepted generation/charge; disable hidden SDK retries. Official documentation does not guarantee that a 429/529 implies zero charge, so the initial live transport conservatively stops and reserves on every HTTP error instead of automatically retrying. The four-retry allowance is an upper bound, not an obligation to retry. Persist intent before dispatch and preserve each attempt. Unknown delivery/charge consumes its conservative reservation and stops expansion until resolved; do not blindly repeat it. Resume must not duplicate an already finalized request. No distributed or arbitrary-crash exactly-once guarantee is promised.

Limit the complete counted request to **8,000 input tokens**, including rubric and formatting, and reserve **2,048 output tokens**, including any reasoning. Use the provider's token-count endpoint on exact requests, separately log those non-generation requests, and stop on unsupported controls or unexpected usage. Never truncate an audit response or replace an over-limit pair after seeing outcomes. Freeze input eligibility/token handling at preparation; a final rubric that makes the locked audit requests incompatible stops the run for review. [Token counting and its free pricing](https://platform.claude.com/docs/en/build-with-claude/token-counting).

### How we know it is done

| Check | Required evidence |
|---|---|
| P1-1: Frozen population | Eligible IDs/content/source/rating context, deterministic selection, exclusions, 12/12 separation and audit access records. Insufficient data is reported before paid launch. |
| P1-2: Usable evaluator | Pair input/output contract, one callable versioned rubric/profile, preserved response identities, explicit applicability and saved example. No dependence on ten-response fixture labels. |
| P1-3: Real critic route | First two calibration calls verify the actual provider path, supported controls, output parsing, usage and bounded launch before expansion. Phase 0 is not this evidence. |
| P1-4: Complete accounting | All 48 scheduled presentations have a status, with no outcome-based replacement; at most four permitted retries, all reservations/charges classified, no silent fallback. Unresolved accounting prevents a clean completion claim. |
| P1-5: Fixed audit calculation | Apply the prompt-level rules below to all 12 audit prompts, using only the frozen final evaluator. Do not pool calibration, rubric versions or retries as extra independent samples. |
| P1-6: Replay and boundaries | Offline checks cover malformed/duplicate/missing pair inputs, incompatible evidence, swapped response order/IDs, stale identities, label/secret exclusion, token/attempt reservations, duplicate/concurrent launch refusal, retry/ambiguous-charge handling and interrupted resume. Saved analysis recomputes without requests. |
| P1-7: Decision report | Counts, refusals/ties/failures, actual costs, prompt-level uncertainty and no-call length/order/family diagnostics; explicit applicability, pass/failure/inconclusive decision and fallback. |
| P1-8: Preserved scope | Original project, completed Phase 0 evidence and upstream sources remain unchanged. Only this evaluator was assessed; no new strategies or improvement claims. |

**Operational audit floors:**

1. **Human agreement:** a prompt succeeds only if **both** valid decisive orders choose the human-higher response. Require **at least 9 of 12 prompts** (75%).
2. **Order consistency:** both valid decisive orders choose the same underlying response identity, whether right or wrong. Require **at least 11 of 12 prompts** (91.7%, the integer realization of a 90% floor).

Ties, abstentions, refusals, malformed/missing or exhausted-attempt results earn zero for these fixed-denominator gates; two abstentions do not count as consistency. Report per-presentation agreement and decisive coverage separately. Report 95% prompt-level Wilson intervals for the two proportions, plus descriptive first-position preference and error patterns by answer length and family. These diagnostics add no model calls. This population contains only Metaphors and supports no cross-family comparison. They are not additional post-hoc acceptance gates. The thresholds are an operational screen, not a scientific standard or high-confidence validation claim.

**Completion and outcome are separate.** A functioning, fully accounted run that misses a floor closes with a usable **diagnostic-only evaluator** and report. Passing permits only limited supplementary pairwise use on the declared MuCE-like population. Broken transport/accounting, label leakage or an unassemblable population is **incomplete/inconclusive**, not evidence that the evaluator is bad; deliver the working offline checkpoint and limitation report, then review a bounded correction. Never enlarge the sample or keep tuning until it passes.

### What stays out

Generator/base-model comparisons; planning/reranking experiments; native live Harness²/OpenCode; recursive improvement; model training; a second critic or effort sweep; new benchmarks; full CrPO scorer implementation; Bayesian surprise; human steering; dashboards/marketplaces; and a universal provider or billing framework. No new paid human annotation study is required: MuCE supplies the human reference. Operator review is still needed, and its time is not included in API pricing.

Pairwise MuCE agreement does **not** calibrate absolute scores, portfolio diversity, factual correctness, official Native NoveltyBench judges or preferences over new LLM answers. Applying the evaluator outside its screened population remains diagnostic unless a separate bounded transfer check is specified. Do not automatically add that transfer study to Phase 1.

### Estimated cost and launch decisions

Planning estimate checked **2026-10-24, America/Los_Angeles**: standard Sonnet 5.5 pricing is **$2 per million input tokens and $10 per million output tokens**. Use first-party/global pricing with no tool fees, premium mode, cache writes or batch-discount assumptions. [Official pricing](https://platform.claude.com/docs/en/about-claude/pricing).

| Budget item | Estimate/ceiling, USD |
|---|---:|
| This specification refresh and the future offline preparation/checkpoint | $0 model/API generation spend |
| 48 judgments, illustrative 2,000–4,000 input and 512–2,048 output tokens each | Approximately **$0.45–$1.37** |
| All 52 attempts at 8,000 input + 2,048 output tokens each | **$1.89696**, conditional token-price bound |
| Recommended future authorization ceiling, including unresolved reservations | **$5**, not a spending target or present authorization |

Formula: `cost = (input_tokens * 2 + output_tokens * 10) / 1,000,000`. Offline analysis/downloads require local resources but no model requests. Taxes, provider account funding minima, implementation/operator time and any separately commissioned human work are excluded. Reconfirm prices, account availability and token accounting before launch. The bound depends on enforced controls and correct provider billing; unknown liabilities remain reserved and stop expansion rather than being written off.

The original preparation checkpoint is documented in PHASE1_PREPARATION_REPORT.md: actual eligible pair/split manifest, exact rubric/profile/request schema, tested offline controls, permitted endpoint/credential handling and readiness policy. The user subsequently authorized the $5 ceiling and readiness exception; the completed live study and requirement-by-requirement closure are in PHASE1_REPORT.md. Synthetic checks alone did not satisfy P1-3 through P1-5; actual live evidence and the held-out report now do. No repeat run or additional spending is authorized.

## Phase 1A — Data readiness for a specified evaluation use

**Status:** defined, unstarted. Before starting, present this definition and confirm it still fits the evidence. A request to execute this unchanged checkpoint authorizes its zero-experiment-spend scope; it does not authorize the next experiment.

### Objective

Determine which uses the pinned MuCE release can defensibly support, what fresh reference material remains available, and which unresolved questions matter before either selecting a frontier-model judge or reproducing CrPO's measurement setup. The output is a bounded decision about a named population, criterion and use, not a universal certificate that MuCE is correct.

Phase 1 remains a completed failed agreement screen. Its custom pairs, rubric and reasoning configuration did not isolate model ability, reference validity or rubric alignment. Neither counterintuitive examples nor this inspection establish a dataset-wide error rate. Do not drop inconvenient Phase 1 pairs, change its floors or declare a retrospective pass.

### Scope and inputs

- Use the existing cached original `CNCL-Penn-State/MuCE`, revision `a02181e394c41602a95d0678b0ce9d880e994289`, `full_agreement/train`, its conversion/preparation records, and the completed Phase 1 artifacts. Reconcile all 16,948 cached training rows and the 48 selected response-to-score mappings. The original and newer similarly named releases remain distinct.
- Review the published paper, original dataset card, public CrPO source/configuration and model-card/training metadata. Record exact revisions, URLs, dates and accessible evidence at execution. Public documentation and small metadata requests are permitted; fetching new row corpora, opening published held-out answer/label content, or downloading weights is outside this checkpoint.
- Establish rating construct, original study/task instructions where available, source grouping, score direction/transformation, identity/alias rules, missingness and available rater evidence. Keep overall creativity and originality separate. Scores are source-scoped derived estimates, not raw means or a common creativity scale. Published human agreement does not demonstrate direct unanimous preference over our constructed pairs. [Score construction](https://arxiv.org/html/2505.14442v2#A1).
- Compare our frozen inclusion/pairing rules with the authors' actual preference construction, including the full-agreement subset, minimum score 20 for both members, margin 5, pairing limits and split rules. Distinguish training-data curation from an evaluator-validation protocol. Produce counts under each policy; do not retroactively rescore Phase 1 after filtering. [Paper](https://arxiv.org/html/2505.14442v2#A2), [implementation](https://github.com/mismayil/creative-preference-optimization/blob/main/src/crpo/data.py).
- Map public asset/training metadata for the released CrPO measurement components only: quality reward adapter/base, embedding reference and surprise reference. For the frontier route, record required identity/reasoning/usage controls without creating a model catalogue or selecting a shortlist. The released [CrPO reward adapter](https://huggingface.co/CNCL-Penn-State/CrPO-RM-gemma-2-9b-it) is a distinct trained evaluator, not interchangeable with its base model or an instruction-prompted frontier model. Classify membership overlap as proven present, proven absent within the available records, or unknown. Do not assume MuCE training pairs are held out from a MuCE-trained evaluator. Metadata availability does not prove weight access, local feasibility or scientific equivalence of substitutes.

Use the existing supported environment and helpers. Keep upstream checkouts, frozen package/rubrics/profiles, historical source caches and all completed run evidence unchanged. Write new checkpoint outputs only beneath the new project, using `runs/phase1a-data-readiness-r07` and `evidence/phase1a-data-readiness-r07`. No new provider, dependency installation, image or framework is needed. If a small reproduction script is necessary, retain it with the checkpoint evidence without changing the frozen evaluator package.

### Fixed inspection and exposure boundary

Prepare an inspection sample of **at most 12 pairs**, one per distinct prompt group, from the **24 already exposed Phase 1 groups only**. Candidates use the same source/task/language/rating context, overall creativity and a score gap of at least 5. Inspecting additional responses within those groups creates no new confirmation group. Existing train ratings were already machine-read for preparation; do not call remaining groups wholly unopened data.

Target four pairs per stratum: both scores below 20; one below 20 and one at least 20; both at least 20. These are inspection strata addressing the filter difference, not comparable psychological quality intervals. Enumerate compatible candidates, derive their existing canonical content identities, and rank by canonical SHA-256 of `{namespace: "phase1a-inspection-v1", seed: 20261025, sorted_response_ids: [...]}`. Iterate that order, accepting a pair only if its prompt group is unused and its stratum has fewer than four pairs. Stop when all quotas fill or candidates are exhausted. Record algorithm/seed before displaying the selected texts. Selection must not use Sonnet choices, correctness, reasons or an analyst's preference.

Sparse strata produce an explicit shortfall; do not redistribute quotas, change the seed, consume unused groups or enlarge the sample to obtain appealing examples. Exhaustion with documented counts is a legitimate completed inspection with limited coverage. Keep the previously examined disagreements as a separately labelled case appendix; they do not replace random selections or contribute an error-rate estimate.

Produce a packet with task instructions, two unchanged responses and space for observations, excluding scores, source prestige and Sonnet judgments. In accepted-pair hash order, put the lexically smaller canonical response ID at A on even zero-based indices and at B on odd indices. This balances canonical orientation, not the human-higher position; it never uses Sonnet outcomes. Freeze that ordering rule in the sampling record before showing texts. Retain a separate identity/source/score key. Record analyst observations as qualitative hypotheses before consulting the key where feasible; do not claim the analyst is blind to earlier examples. **A blinded packet is not a completed independent human study.** No human recruitment, new ratings or human-reliability claim is included.

Preserve an exposure ledger and an ID/hash-only candidate inventory of remaining cached train groups by family, construct and source context. Mark whether content was manually exposed, machine-read only, previously model-evaluated, or subject to unknown evaluator-training overlap. Record candidate counts under both inclusion policies. Published held-out splits receive metadata pointers only: their answer/label contents and row inventories remain unopened. The inventory may support development and a later experimenter-held-out design, but does not establish independent validation material for the MuCE-trained reward model without proven training-membership separation. It is a feasibility artifact, not a frozen confirmatory sample or a guarantee of model-pretraining exclusion.

### Deliverables and usable output

| Deliverable | Minimum contents |
|---|---|
| `PHASE1A_DATA_READINESS_REPORT.md` | Source/score interpretation, reconciled integrity findings, policy comparison, illustrative anomalies with competing explanations, limitations and an explicit permitted-use decision. |
| Evidence manifest and policy/count records | Source/code/model-card identities; exact commands or reproduction script; counts/exclusions; snapshot of the sampling rules; evidence references or explicit unknowns for every material claim. |
| Inspection packet and separate key | Up to 12 reproducibly selected pairs, recorded shortfalls, source-text preservation and qualitative notes; useful for a later separately specified human review. |
| Exposure and candidate inventory | IDs/hashes/context/construct, exclusions, overlap classification and candidate counts; no unused answer texts or score key exposed in the report. |
| One next-step recommendation | Choose one proposed route, name its unresolved prerequisites, describe the smallest usable next experiment and identify the definition/budget still needed. No automatic launch. |

The report must distinguish three uses: (1) development-only agreement with published MuCE labels; (2) a CrPO measurement reproduction; (3) claims that a judge agrees with humans on new outputs. Readiness for one does not imply readiness for the others. Missing original rater records remain a limitation; reconstructing unavailable records or obtaining an author reply is not a completion requirement. No author messages are sent in this checkpoint.

### Exclusions

No experiment model/provider inference, including local reward-model or embedding inference; frontier model or reasoning sweeps; model/rubric tuning; weight downloads, training or scorer implementation; dataset repairs/relabeling; new benchmark integration; fresh held-out row/label inspection; paid annotation or recruitment; human validation; new strategy/reranking/adaptation experiments; CrPO replication execution; or Bayesian-surprise implementation. Keep these as possible later slices, not hidden prerequisites.

### Completion criteria

| Check | Required evidence |
|---|---|
| D1A-1: Traceable references | Exact release/revision/field semantics and policy comparison are documented; every material claim has a source or an explicit unknown. No silent substitution of datasets or models. |
| D1A-2: Integrity and counts | Cached counts, original texts/scores, source contexts, identities/aliases and all Phase 1 mappings reconcile, or discrepancies are itemized and affected uses rejected. No source repair. |
| D1A-3: Reproducible inspection | Frozen rules reproduce packet IDs/hashes/order without model calls; strata/unique-group counts and shortfalls are correct. Separate disagreement appendix and separate score key are retained. |
| D1A-4: Exposure and overlap | All inspected groups remain development-only; candidate inventory and overlap states are explicit; protected held-out row contents stay unopened. Unknown membership never becomes an unsupported no-overlap claim. |
| D1A-5: Bounded decision | Each of the three uses is classified ready for a specified limited use, conditional on a named later check, or not currently suitable, with evidence and prohibited claims. No universal validity or dataset-error-rate claim. |
| D1A-6: Handoff and preservation | Usable report/packet/inventory plus one next-step proposal; evidence identity/links checked; no experiment calls/spend; protected source/upstream/history unchanged. |

**Completion is not a positive validity verdict.** An evidence-backed conditional or not-suitable decision completes the checkpoint. A tool/integrity failure that prevents producing the promised records is reported as an execution limitation. A technical-data check can support bounded development or replication; it cannot, without independent evidence, certify agreement with humans on new outputs. If unresolved reference validity is material to judge selection, the next proposal must include a bounded independent human check before any confirmatory claim.

### Cost, time and stopping rule

**Experiment spending ceiling: $0.** No generation/token-count provider requests, local model inference, rented compute, paid data or paid annotators. Use cached data, existing local compute and public documents/metadata. Normal assistant-session usage, local electricity and analyst time are not priced as experiment API spend.

Estimated active analysis/preparation time: **2–3 hours**, capped at **one three-hour working session** when execution is requested. Stop investigation by two hours forty minutes and reserve the final twenty minutes for the handoff, with remaining questions explicitly conditional/unknown. Do not extend research, fetch another corpus, recruit reviewers or await an upstream reply indefinitely. This is not a promise to resolve unavailable provenance. Paid human review or model work needs its own later cost estimate and authorization.

### What happens next

1. Execute Phase 1A only when requested; return its usable report and use-specific decisions before another slice.
2. Refresh one next definition around its findings: **Route F**, a small comparison starting with frontier models and supported reasoning configurations; **Route C**, a measurement-only CrPO reproduction using exact assets where feasible; or **Route H**, a small independent human-reference check if label validity is unresolved. Model cards inform compatibility but do not establish equivalent scientific measurements; substitutions are separately identified departures. Do not launch all routes together or reproduce all CrPO training/generation experiments.
3. Freeze that route's development/selection/confirmation separation, applicability, actual role/model revisions, observed reasoning controls where relevant, sample size/decision criteria and total cost before work/calls. Select configurations using development evidence; preserve fresh confirmation for the final frozen choice. The consumed Phase 1 audit cannot validate a revised evaluator.
4. Then refresh Phase 2's measurement contract and budget before comparing fixed strategies. Native benchmark evaluation plus predeclared human checks remains an independently usable option; Phase 1A is not a universal prerequisite for every benchmark. Never silently replace broader creativity claims with native benchmark utility. Phases 3A/3B retain actual upstream Harness² and the core recursive-improvement question.

## Phase 2 — A usable fixed-strategy baseline tool

**Objective:** isolate the contribution of the original planner and of answer ordering with one generator, before testing harness adaptation.

**Usable output:** working ordinary-sampling and planner strategy packages, an isolated reranking transformation, immutable generated portfolios, and a paired report. A researcher can rerun a declared condition or apply compatible assessments to saved outputs. The report identifies the fixed procedure chosen for the next comparison or recommends stopping.

**Build/do:** 12 development prompts, two independent repeats, two generating conditions: 48 generated portfolios of ten responses. Rerank the 24 planner portfolios, creating 24 recorded permutations without replacing response texts. Use pinned native NoveltyBench evaluation on each new order; fixed-partition estimates are labeled diagnostics. Record every planning/ranking/assessment call and failure. Add only supplementary scorers explicitly activated in the phase definition; retain the other CrPO dimensions in the measurement backlog.

This yields **72 portfolio/order assessment instances**, not 72 necessarily billable judge calls, and only **12 independent prompts**. The generator and official grouping/quality-judge routes need their own readiness evidence. Define a versioned live-output contract instead of relaxing Phase 0's fixture-only grading guard or reusing its invented labels. Phase 1's evaluator may remain diagnostic or unused; native assessment and a frozen blinded human sample remain the fallback. Do not silently turn its pair preference into a scalar portfolio score.

**Entry update after Phase 1:** the actual critic missed both audit floors, which establishes failed reference agreement without isolating model, rubric or data validity. Phase 1A now defines the proposed reference-data decision before choosing further MuCE/CrPO work. At the Phase 2 refresh, use that decision to name the actual measurement route; native benchmark evaluation plus a predeclared blinded human sample remains available independently. Select the human-review sample/criteria, generator/native-judge profiles, exact task IDs, ranking procedure and total ceiling before implementation/calls. Treat any retained Phase 1 critic output as diagnostic; using it within reranking is a declared strategy intervention requiring independent evaluation. Do not add a model tournament, CrPO reproduction, critic repair or larger strategy search implicitly. This update does not begin Phase 2; its concrete review and spending decision are still pending.

**Stays out:** Harness² efficacy claims, a second generator, a strategy tournament, a full Lenny/Lluminate library, cross-task memory, confirmation material, or a new benchmark. Do not automatically search more strategies when results disappoint.

**Done:** all planned portfolios/permutations have statuses and traceable identities; the generator/protocol is held constant; assessments and costs are complete or transparently missing. The report separates planner effects from reranking effects and declares the selected fixed procedure without asserting that it is globally best. Negative results are valid. An invalid scoring/accounting path requires correction before claiming a valid comparison.

**Refresh before start:** development prompt IDs/families and exclusion list (including Phase 1 material), generator/ranking/native-judge roles, exact planner/reranker prompts, live artifact schema, native scoring profile, human-check sample/availability, supplementary scorer applicability/coverage, all-call and dollar ceilings, retries/liabilities and reporting rules. Price the 48 generated portfolios, 24 reorderings and 72 native assessment instances using actual route costs before launch; no dollar estimate or spend is authorized here. If an extra strategy family is warranted, define it as a separate bounded development slice.

## Phase 3A — A usable native one-step adaptation tool

**Objective:** establish authentic task-level Harness² adaptation from the selected fixed procedure, and measure its observed quality/cost before deciding on confirmation.

**Usable output:** a working native adaptation route, inspectable starting/proposed/composed/selected harnesses and traces, and a comparison against the frozen fixed procedure. The fixed and adaptive routes remain usable even if adaptation loses.

**Build/do:** one generator and declared technique set, the 12 development prompts with two repeats: 24 native parallel `k=1` task adaptations. Use an actual model-backed proposer in the upstream scheduler; disable shared cross-task experience. Preserve all probes, selections, rejected candidates, accounting and failures. A proposer choosing to keep the initial harness is a valid recorded outcome; changing a file is not a success criterion.

Deliver and review the first actual live adaptation trace with reconciled costs before expansion, using a predeclared development item counted within the envelope. At the current source pin, 24 successful native `agg`, `k=1` paths imply **96 executor rollouts and 72 editor/composer sessions**, before repairs or other configured activity. Sessions can contain multiple model calls, and rollouts can invoke strategy helpers; neither number is a billing cap. Phase 1 critic transport does not verify this live executor/proposer route. MuCE screening does not remove the need for native scoring or blinded human checks of new outputs.

**Stays out:** deeper recursion, mode comparisons, online libraries, preference-supervised search, extra strategy families, a second generator or claims that an unmatched comparison isolates adaptation from additional compute.

**Done:** every task adaptation has a classified outcome, trace and accounted costs; evidence establishes actual native/model-backed execution and the declared information boundary. Compare native utility, quality, coverage and cost with the selected fixed baseline. Document the proposed fixed-control budget policy for confirmation. Negative or inconclusive outcomes are legitimate; infrastructure failure remains a distinct limitation. This phase supports one-step claims only.

**Refresh before start:** frozen seed strategy/source access, all model roles, exact native mode/budgets, role-specific readiness, per-task and phase token/call/dollar ceilings, assessment coverage, maximum attempts/reserved liabilities, failure criteria, human-check plan and the rule for proceeding or stopping. Include all native/helper calls and external assessment in the cost sheet. If making budget-controlled attribution in this phase, explicitly define and fund that fixed control first; it is not silently added to the 24 adaptations.

## Phase 3B — A usable successive-refinement tool

**Objective:** test Harness²'s repeated improvement mechanism explicitly: can a later native round refine an earlier composed harness into a more useful procedure under a comparable total inference budget?

**Usable output:** a native two-round sequential route, inspectable per-round harnesses/trajectories and final selection, plus a bounded comparison against a frozen budget-comparable procedure. It remains a reusable tool even if the extra round does not help.

**Build/do:** provisional envelope of four development prompts, one repeat: four native sequential `k=2` adaptations and four comparable-budget fixed-control outputs. Start from the same declared strategy and technique access. Record the second round's use of the earlier harness/evidence, all base executions/probes/editor/composer/selector calls, discarded results and costs. Preserve native choice among round outputs; do not require adoption of the latest candidate. Score only after decisions, with no shared cross-task library. A first round inside `k=2` is not a reusable standalone `k=1` result.

The usable product must expose that earlier-to-later evidence flow, including a later candidate that is unchanged or rejected. Budget all native executions, proposer/composer/selector sessions and tool/provider turns, plus the fixed control's extra candidates/blind selection and external assessments. Reuse evaluator/readiness evidence only within its demonstrated applicability; additional depth and selector behavior need this route's checks. The budget-comparable control is mandatory in this slice, but does not isolate depth from adaptive breadth.

**Stays out:** a broad depth sweep, more generators, changing the external objective, model training, online memory, or a claim that sequential depth beats equally budgeted parallel adaptation. This small pilot cannot establish a population-level improvement claim.

**Done:** actual successive native execution is evidenced, all planned outcomes/costs are classified, and the fixed comparison respects technique access and the frozen budget policy. Report whether observed later refinement helps, hurts, is retained/rejected, or is inconclusive. Recommend a method/depth and precision requirements for confirmation. Unchanged proposals and rejection of the later candidate remain valid outcomes. Failure to complete execution leaves the recursive-improvement question unanswered.

**Refresh before start:** review 3A's integration and actual call costs; freeze the four eligible prompts, role models, starting procedure, native sequential settings, fixed-control budget policy, assessment coverage and attempt/spending ceilings. This is an explicit planned milestone, not automatic authorization. A negative one-step result does not by itself rule out repeated refinement. If the project stops before this phase, record successive improvement as untested.

## Phase 4 — A usable held-out comparison and decision

**Objective:** estimate the incremental benefit of the selected adaptation method under comparable inference budgets, and assess whether it is worth using for the declared models/population.

**Usable output:** a reproducible held-out report, frozen method packages, versioned outputs/assessments and an explicit recommendation to use adaptation, retain the fixed procedure, narrow the claim or gather more evidence. An inconclusive answer is a usable decision artifact, not a win.

**Build/do:** provisionally two generators and three methods: ordinary sampling, a frozen fixed procedure allowed extra generation/blind selection under a comparable budget policy, and native adaptation from the same procedure with the same declared techniques. The planning envelope is 40 fresh prompts and two repeats: 480 delivered portfolios/4,800 answers before probes, discarded candidates and assessment. Determine actual size from pilot variability, worthwhile-effect thresholds and the ceiling before opening holdout inputs. Freeze trained libraries if any; no cross-held-out-task learning.

Exclude development/legacy material, every MuCE calibration/audit prompt group and known related source/alias overlap. Use public material as experimenter-held-out only. Validate the second generator and any changed evaluator/provider controls on development material before opening confirmation. A MuCE pass alone does not establish transfer to these generators' answers; unvalidated supplementary criteria remain diagnostic. If a transfer or human-review requirement cannot be met within the frozen budget, narrow the declared claim before launch rather than implying validation.

**Stays out:** adjusting methods/evaluators after observing confirmation results; forcing this sample size without a precision/budget justification; new operators/models/benchmarks; claims about populations, recursion depths or efficiency outside the frozen design. Do not add a fourth main arm merely to handle compute matching.

**Done:** verify development/legacy overlap exclusions; account for all planned independent prompts, repeated portfolios, failures and liabilities. Report paired prompt-level effects/uncertainty, native utility, quality/validity, coverage, actual total inference costs and separate assessment costs. Report model/family results with appropriately limited claims, plus activated secondary measurements and blinded human review. Apply the predeclared decision rule, including meaningful gain, acceptable quality loss and cost. Preserve the held-out analysis and limitations regardless of outcome.

**Refresh before start:** exact held-out population/IDs, both generators and all other roles, fixed/adaptive definitions and budget policy, precision calculation, primary contrast, thresholds, multiplicity/secondary-outcome treatment, human sample, missingness policy and total cap. If precision cannot be achieved within the ceiling, revise scope before launch or do not launch; do not relabel an underpowered run as confirmatory.

### Cost worksheet required for Phases 2–4

Every refresh must give the model/pricing date, delivered outputs, total generation/search/helper requests and token reservations, external assessment instances and their actual requests, retries/unknown liabilities, human-review provision and a dollar ceiling. Report deployment/search/assessment totals separately and together. Use preceding readiness costs to estimate the next phase; do not extrapolate the Phase 1 pair-comparison price to a portfolio, a native adaptation or an official judge pipeline. Counts above remain provisional; unresolved cost estimates are not zero-cost assumptions or permission to launch.

## Later phases

NoveltyBench is only the first task protocol. Other benchmarks can supply tasks and native assessments through separate adapters; compatible criteria can assess saved artifacts. A new task protocol may require new generations, not just rescoring old text.

No omnibus extension phase is authorized or specified. A second benchmark, new strategy family, CrPO scorer activation, Bayesian-surprise operationalization, depth beyond Phase 3B or online memory each needs its own definition using this same structure. State the one question and usable output first, then bound the work. Earlier artifacts remain usable independently of whether that extension proceeds.

## Revision record

- **0.1:** initial phased proposal; no implementation or scientific observations.
- **0.2:** user authorized Phase 0 and requested a refresh. Verified Docker availability and canonical folder separation; fixed upstream/image references and the offline implementation shape in DECISIONS.md. Original scope and P0-1 through P0-8 remain intact. No acceptance threshold was changed to accommodate execution results; implementation and acceptance execution have not yet occurred.
- **0.3:** offline implementation began. Dependency auditing identified vulnerable initial Transformers/Torch versions; update the runtime pins and require fresh native regression/audit evidence. Preserve the initial findings. Source commits, fixture protocol, scientific scope and all acceptance checks remain unchanged.
- **0.4:** after Phase 0 completion, preserve its exact specification/decisions and evidence; define the proposed Phase 1 pairwise evaluator, data eligibility, 48 judgments/52-attempt maximum, integer audit floors and dated cost estimate. Clarify later-phase live readiness, limited evaluator transfer, assessment/count units, cost worksheets and held-out exclusions. No code, dataset sampling or experiment was performed for this refresh; no earlier scientific threshold was changed after observation.
- **0.5:** before evaluator observation, the user selected Metaphors-only overall creativity after the four-family quota proved infeasible. Preserve revision 0.4 and the completed Phase 0 records.
- **0.6:** close Phase 1 with a diagnostic-only evaluator under its approved readiness exception; record live accounting, frozen predictions and offline replay. Preserve revision 0.5 and the actual failed floors.
- **0.7:** define unstarted Phase 1A, a zero-experiment-spend data-readiness checkpoint with bounded inspection of already exposed groups, use-specific outcomes and one next-route decision. Preserve revision 0.6 and commit `35cc481`'s closeout evidence. No checkpoint execution, new sampling, model calls or implementation accompanies this specification update.
