# Buddha2 phase definitions

Revision: 0.11 — 2026-10-25, America/Los_Angeles  
Status: Phases 0, 1 and 1A complete; Phase 2A offline preparation complete with a live-admission blocker; Phase 2B unstarted and unauthorized; Route H optional and unstarted; CrPO deferred; later phases provisional and unstarted  
Authority: the user authorized completion of unchanged Phase 2A under frozen revision 0.10. This revision records its offline closeout only; no scientific method, comparison, threshold or spending permission changes. Experiment/API spend and provider/token-count calls are zero. Route H remains optional, CrPO remains deferred, and the original Buddha2 folder remains protected.

The [experiment plan](EXPERIMENT_PLAN.md) gives the research rationale. This document specifies work products and completion gates. [DECISIONS.md](DECISIONS.md) remains Phase 0's historical implementation decision record. Phase 0's exact [specification](specifications/archive/phase-definitions-0.3.md) and [decisions](specifications/archive/phase0-decisions-0.3.md) are preserved byte for byte; their hashes match the retained run manifest. Use the [handoff report](PHASE0_REPORT.md) for evidence and navigation. The archives retain links originally authored relative to the project root.

Refreshing this file changes the effective input identity for a new Phase 0 run. Do not edit old manifests, reports, assessments or the example archive to make them match revision 0.11. Historical completed-run resume belongs to commit `6bafb25` and its frozen inputs; current definitions require a fresh output directory. Revisions 0.4 through 0.10 are preserved in specifications/archive. PHASE1_DECISIONS.md records the approved population change; PHASE1_REPORT.md records execution, the readiness exception and final result. Phase 1's closeout manifest binds documentation at commit `35cc481`, including the exact archived revision 0.6. Phase 1A completed under frozen revision 0.7; its report and closeout manifest bind closure documentation at commit `bed3465`, including exact archived revision 0.8. Route H's definition remains archived in revision 0.9. Current planning changes do not rewrite those reports, evidence or hashes; inspect the corresponding historical commit to verify its bound documentation.

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

All project writes, upstream checkouts, dependencies and run artifacts stay under `C:\Users\arvik\code\research\Buddha2` or its dedicated container image. The protected `C:\Users\arvik\code\buddha2` is never written, used as a working directory, copied or mounted. Validate canonical output/mount paths before execution and retain the actual mount configuration as evidence.

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
- Editing the original Buddha2 folder or either upstream algorithm to make the fixture pass.

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

**Closed:** all P1-1 through P1-8 are complete under [frozen revision 0.5](specifications/archive/phase-definitions-0.5.md), with the explicit [user-approved operator readiness exception](evidence/phase1-live/readiness-exception-approved.json). All 48 presentations finalized for $0.112696 usage-based API cost, with zero retries or unresolved reservations. Held-out both-orders human agreement was 4/12 (floor 9) and order consistency 8/12 (floor 11): **diagnostic-only**, not a screened-valid critic. The [report](PHASE1_REPORT.md) records the single calibration-only JSON-format revision, prediction commit before label access, byte-identical offline replay and credential cleanup. The scope below retains the completed definition; its estimates and pre-launch statements are historical, not authorization for a repeat. The audit is now consumed for a revised critic.

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

The Phase 0 network-disabled, credential-free path stays intact. Phase 1 needs a separately declared network-enabled critic launch with one provider endpoint and only its explicitly supplied credential; no host home/original-folder/credential-directory mounts and no agent tools. Record the actual launch configuration. Do not claim OS-level provider-domain egress enforcement unless implemented and checked. Reuse ordinary artifact/hash helpers and installed dependencies where appropriate; leave the native Harness²/NoveltyBench sources unchanged.

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

**Closed under frozen revision 0.7:** D1A-1 through D1A-6 are satisfied; see [PHASE1A_DATA_READINESS_REPORT.md](PHASE1A_DATA_READINESS_REPORT.md). All 16,948 cached train rows and 48 historical mappings reconcile. The frozen sampler produced eight pairs and a documented four-pair low-stratum shortfall, without new prompt groups. Experiment spend was $0; no model inference, new human ratings or held-out row contents. Development against published labels is ready for that limited use; CrPO reproduction is conditional; human alignment on new outputs is unvalidated. Its report recommended Route H; that optional route is now defined below and remains unstarted. The following scope is retained as executed, not changed after observation.

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

No experiment model/provider inference, including local reward-model or embedding inference; frontier model or reasoning sweeps; model/rubric tuning; weight downloads, training or scorer implementation; dataset repairs/relabeling; new benchmark integration; fresh held-out row/label inspection; paid annotation or recruitment; human validation; new strategy/reranking/adaptation experiments; CrPO replication execution; Bayesian-surprise implementation; or changes to the original Buddha2 folder. Keep these as possible later slices, not hidden prerequisites.

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

1. Phase 1A is complete. Route H is now concretely defined below as an optional, one-pass check of these diagnostic cases. It is not a dependency for Phase 2, and it does not replace the separate human check of new pilot outputs. No human work has begun.
2. Prioritize the next core slice: refresh Phase 2's actual generator, native evaluation, new-output human-check plan and total budget. Further MuCE/CrPO implementation and **Route F** (frontier evaluator/reasoning comparison) or **Route C** (measurement-only reproduction) are deferred until a concrete pilot measurement need justifies one bounded slice. Model cards inform compatibility, not scientific equivalence. Do not launch all routes together or reproduce the CrPO training study.
3. Freeze that route's development/selection/confirmation separation, applicability, actual role/model revisions, observed reasoning controls where relevant, sample size/decision criteria and total cost before work/calls. Select configurations using development evidence; preserve fresh confirmation for the final frozen choice. The consumed Phase 1 audit cannot validate a revised evaluator.
4. Then refresh Phase 2's measurement contract and budget before comparing fixed strategies. Native benchmark evaluation plus predeclared human checks remains an independently usable option; Phase 1A is not a universal prerequisite for every benchmark. Never silently replace broader creativity claims with native benchmark utility. Phases 3A/3B retain actual upstream Harness² and the core recursive-improvement question.

## Route H — A bounded independent human-reference check (optional)

**Status:** defined, unstarted. The user can nominate two readers. Their identities, eligibility and volunteer availability must be recorded before collection; this definition does not invent or recruit them. It is not a gateway to all subsequent project work.

### Objective and usable output

Determine how two fresh human readers apply our existing overall-creativity rubric to the eight fixed diagnostic pairs, and identify concrete ambiguities or conflicts with the released MuCE score ordering. The question is whether these examples and our displayed criterion make sufficiently clear sense to merit further MuCE-based evaluator work. This is a rubric/context diagnostic, not recovery of the original source raters' judgments, a new gold dataset or validation of any model.

Usable output: a short case-by-case report with two independent response sheets, preserved ties/abstentions and a bounded decision about further MuCE work. The packet, form and reconciliation table can be reused as development evidence even if readers disagree. All eight groups remain consumed development material.

### Scope and who the readers would be

- **Reader R1:** one user-nominated, consenting adult fluent in English and able to explain a metaphor judgment, preferably with writing, editing, literature-teaching or similar experience. Record that experience; specialist recruitment is not required if the nominees lack it.
- **Reader R2:** a second user-nominated, consenting English-fluent adult able to explain a metaphor judgment. A different background is useful; specialist creativity credentials are not required. This is not an expert-versus-novice experiment.
- Neither has seen these pairs, the score key, the report's examples, earlier Sonnet choices/reasons or our qualitative notes, and neither helped construct the examples, rubric or study. Record relevant experience and prior-exposure attestation using R1/R2 identifiers; personal contact details need not enter the research artifacts.
- They work separately, with no discussion, web search, LLM assistance or coaching before submission. Independence here means independent judgments under a shared instruction, not independent data acquisition or a representative sample of humans.
- The user is the coordinator and has seen examples; their observations remain useful as separately labeled informed feedback. Codex, Claude or two subagents cannot serve as the two human readers. Actual reader names are not known to the assistant at definition time.

Use exactly the existing eight pairs in [inspection-packet.json](evidence/phase1a-data-readiness-r07/inspection-packet.json), SHA-256 `88bf5d3e8bfebfecfac77549663638bbc0a8ed89e6dfd05a58136bd8a2ca7f6a`, once per reader: **16 planned pairwise judgments**. No new tasks, pairs or groups; no reopening other row contents. Preserve the released prompt and response spelling exactly. The four-pair sampling shortfall remains; do not fill it for Route H.

### What we will prepare and collect

1. Before collection, freeze the packet hash, instructions, blank response fields, reader IDs/eligibility, display mapping, outcome rules and collection deadline in `runs/route-h-r09`; retain non-private evidence in `evidence/route-h-r09`. Ordinary Markdown/CSV/JSON files suffice. No application, new package or reusable annotation platform is needed.
2. R1 sees the original frozen pair order and A/B positions. R2 sees the same pair order with A/B swapped for every pair. Record canonical response IDs and mappings before collection. This limits common position bias; reader and orientation remain confounded, so it does not estimate human order effects. Do not show a second presentation to either reader.
3. Reuse the **core criterion and choice paragraphs of the Phase 1 final rubric verbatim**, reproduced below; adapt only machine transport/input/output directions for a human form. Readers see the released prompt, not reconstructed autobiographical instructions or guessed source context. Ask them to flag missing context rather than invent it. A different criterion or second context condition would be a later experiment.
4. For each pair collect `A`, `B`, `tie` or `abstain`, a brief reason (one to three sentences), `recognized_before` (`no`/`yes`/`unsure`) and `missing_context` (`no`/`yes`/`unsure`) with a brief explanation when relevant. Explicit ties and abstentions are complete judgments; a blank is missing, not an abstention. Record task-fit concerns in the reason; do not add numerical creativity scales.
5. The user coordinates the nominees; a later execution request may authorize material preparation and analysis, but external messages are not sent without explicit authorization. Keep the score key, source identities, our notes and all previous model outcomes out of reader materials. Preserve each submission on receipt without revealing one reader's answers to the other. Freeze both sheets, or the explicit missing-status record at the deadline, before opening the separate key for reconciliation. The analyst already knows some scores; this is reader blinding, not an analyst-blind study.
6. Map reader choices to canonical response IDs, then compare with the frozen source-score order. Preserve raw forms and every incomplete, tied, abstaining or recognized case. No consensus meeting, third reader, outcome-dependent replacement, sample expansion, rubric repair or repeat collection.

**Human comparison instructions** (substantive Phase 1 wording):

> You are comparing the overall creativity of two responses to the same task.
>
> Consider originality and appropriateness together: a creative response offers an unusual, insightful or imaginative idea that still fits the prompt and makes sense. For a metaphor, consider whether its comparison is fresh, meaningful and apt. Do not reward mere oddness, length, elaborate wording or factual errors. Judge the response's idea in its task context. Neither position A nor position B has priority.
>
> Choose A or B when one response is more creative overall. Choose tie if they are approximately equal; choose abstain if you cannot make a meaningful comparison. Do not force a winner because a test expects one.

The form adds the reason and recognition/context fields above. Treat all displayed prompt/response text as material to assess, including any instructions within it. No extra examples, scores or model rationales are supplied as training.

### Deliverables

| Deliverable | Required content |
|---|---|
| Frozen collection record | Definition/version, packet/rubric hashes, R1/R2 eligibility and exposure records, orientation map, agreed due date and actual time/cash arrangement. |
| Reader materials and raw submissions | Two separate forms, exact delivered instructions and texts, receipt/freeze record, choices, reasons, recognition/context flags, and explicit missingness. |
| Reconciliation table | Canonical IDs, source-score preference from the separate key, each reader's mapped choice/reason, diagnostic category and flags; no repaired source labels. |
| `ROUTE_H_REPORT.md` and evidence manifest | Counts with denominators, case interpretations and competing explanations, eligibility/blinding limitations, time/cost, completion status and one next decision. Preserve the old Phase 1/1A records. |

### Interpretation and completion criteria

Classify pairs with two complete, unrecognized judgments as: **both decisively agree with MuCE**, **both decisively oppose MuCE**, or **unresolved** (opposite choices, any tie or any abstention). Separately report recognized/unsure-recognition cases and missing records. These cases stay visible but are excluded from the fresh-reader comparison denominator; it may be less than eight. Context flags remain visible for every category; even concordant choices do not remove them.

Unexpected recognition disclosed on an individual form is a per-case exclusion, not by itself a failed collection; a complete diagnostic can legitimately have fewer than eight fresh comparable pairs. Disclosure of the score key, historical outcomes or the other reader's answers before submission, or coaching, is a collection/blinding failure: preserve affected records as compromised and close incomplete rather than claiming the planned independent check.

Report each reader separately and the paired counts out of eight scheduled pairs, with the actual comparable denominator. Reasons and context flags are essential evidence. Do not calculate a new validation pass mark, reliability certificate or population error rate. A common opposite choice indicates a case-specific conflict under **our displayed rubric**, not a proven error by the original raters. Even eight unanimous matches would support only compatibility on these cases. Do not compare new human choices with old Sonnet choices by prompt alone: the inspection can select a different pair within an old group. A direct comparison requires identical canonical response IDs and declared rubric/context; it is not a planned Route H statistic.

| Criterion | Evidence required |
|---|---|
| H-1: Frozen material and eligible readers | Exactly eight pinned pairs; two actual human readers; eligibility, instructions and counterbalanced identity mapping recorded before responses. |
| H-2: Independent collection | Sixteen preserved status records with raw choices/reasons and flags, no cross-reader coaching or score disclosure, submissions frozen before reconciliation. |
| H-3: Correct comparison | Mapping and source-key hashes reconcile; all eight pairs have categories and explicit exclusions/missingness; counts can be checked from the preserved sheets. |
| H-4: Bounded decision | Report explains what these cases show and cannot establish; no retrospective MuCE pass, model verdict, general validity claim or automatic next experiment. |
| H-5: Cost and preservation | Actual reader/analyst time and any agreed cost recorded; no model calls, new dataset rows/corpora, package code or upstream edits; old evidence unchanged. New human judgments are the intended output. |

**Completed diagnostic:** both eligible readers submit all eight choices, including legitimate ties/abstentions, and H-1 through H-5 hold. Disagreement or ambiguity is a valid completed result. If a reader is unavailable, collection/blinding fails, or forms remain missing, deliver the usable materials and a **deferred or closed-incomplete collection** report. Do not describe that as a completed two-reader check or silently replace an exposed reader.

**Exit rule:** if any case has a common opposite preference, unresolved judgment or context concern, keep it explicitly unresolved for MuCE-based evaluator selection; no automatic frontier sweep or rubric rewrite follows. If no such obstacle appears, report only that none was observed on these eight, retaining Phase 1A's transfer/training-overlap limits. In either event, pause further CrPO implementation and refresh the core Phase 2 slice. A later decision to investigate one particular ambiguity needs its own bounded definition.

### Exclusions, cost and stopping rule

Out: new model calls or evaluator selection; new datasets/weights; original-source reconstruction; new prompt groups; model training; new metric or Bayesian-surprise implementation; a third reader; adjudication/re-rating; numerical creativity scores; a human study of new generated outputs; global MuCE reliability or CrPO reward-model validity claims. Route H does not replace Phase 2's separately declared check of fresh outputs.

**Planned direct cost: $0**, assuming the two nominees voluntarily participate without payment. Confirm that arrangement before collection. API/compute/rented-service cost is $0. Plan **30–45 minutes per reader, capped at 45 minutes each**, plus **60–90 minutes of preparation/reconciliation, capped at 90 minutes**: at most **three person-hours**, not zero human effort. These are workload allowances, not measured completion times or market rates. If compensation is wanted, define the actual honorarium/total ceiling before any paid arrangement; none is authorized or hidden in this $0 estimate.

One nomination/availability round; no platform procurement or extended recruitment. Agree a single due date no later than seven calendar days after dispatch. At that deadline preserve received forms and missingness and close with the appropriate status, rather than waiting indefinitely or expanding the study. This waiting period never blocks Phase 2 planning. No reminders or other messages are sent automatically.

## Phase 2 — A usable fixed-strategy baseline tool

**Status:** **2A offline preparation complete under frozen revision 0.10, with live execution blocked**; **2B unstarted and unauthorized**. The [preparation report](PHASE2_PREPARATION_REPORT.md), [frozen study](runs/phase2-r010/frozen-study/study.json) and [closeout](evidence/phase2-r010/closeout.json) record 175 passing project tests, five upstream checks, 72 synthetic assessments with exact replay, zero new resume dispatches and $0 experiment/API spend. The verified offline provider-token bound was not established, an explicitly allowed reported blocker in the definition below. Real dispatch stays disabled; this is not full pilot completion or live readiness. Before 2B, resolve admission and billing assumptions, bind access/readers and obtain applicable spending authorization, then stop for review after its first counted check. The closed Phase 1 grant does not carry forward. Methods and criteria below remain the unchanged execution definition.

### Objective and usable output

Measure whether one fixed planner-and-generation procedure improves native NoveltyBench utility over ordinary sampling, and whether reranking that planner's unchanged answers improves it further. Produce a usable baseline tool and a bounded development decision before actual Harness² adaptation.

The comparison concerns these complete procedures, including their additional inference and conditioning. It does not isolate an abstract planning ability from extra compute. There is one generator, 12 independent development prompts and two fresh repeats. Base-model breadth, native one-step adaptation and successive refinement remain later phases. Route H is optional; no MuCE/CrPO evaluator is activated in Phase 2.

**2A output:** an offline-tested live-output/export/assessment kit, frozen study/worklist, exact prompts/profiles, cost/accounting review and synthetic walkthrough, ready for a bounded live check. **2B output:** immutable real outputs, native assessments and accounting, a small independent human diagnostic, paired report and selected fixed procedure or an explicit inconclusive/stop decision. Saved outputs remain assessable later without generation when another criterion has compatible evidence requirements.

### Scope: tasks and three fixed conditions

Use the independently obtained, cached public `data/curated.jsonl` at NoveltyBench commit `64a23be6b18ec1dacc298830aab276061b6e143c`. It is development material, potentially previously examined in legacy work, not fresh confirmation. Do not access the original Buddha2 folder to reconstruct its results. Do not open WildChat or future confirmation rows for this phase.

In 2A, hash the source file, inventory eligible nonempty English text-only task records, normalize prompt aliases with the existing project rule, exclude Phase 0 synthetic and Phase 1/MuCE exposed aliases and record all exclusions. Use ascending SHA-256 over the canonical tuple `(namespace="phase2-development-v1", seed=20261025, source_task_id, normalized_prompt)`, accepting one record per normalized prompt until 12. No family quota, semantic cherry-picking or replacement after results. Freeze IDs, exact prompts, source/context hashes and order before calls. If fewer than 12 are eligible, report a preparation shortfall rather than switch source/construct silently. Task IDs are deliberately not selected during this definition update.

| Condition | Fixed procedure | Planned count |
|---|---|---:|
| A: ordinary sampling | Ten independent fresh requests receive the original task only, with a shared minimal answer instruction. No prior answers, angles or sibling context. Preserve request-index order. | 24 portfolios, 240 answer requests |
| B: planner + generation | One request produces ten ordered, distinct task-appropriate angle records. Each of ten fresh answer requests receives the original task and only its assigned angle, with the same base answer instruction. No sibling answers, score feedback or revision. Preserve angle order. | 24 portfolios, 24 plan + 240 answer requests |
| C: reranked planner | One request receives B's prompt and ten saved responses with stable IDs and returns a permutation only, prioritizing task fitness/usefulness, then useful variety among early responses. Use the same Sonnet profile; no native/MuCE scores. No rewriting, filtering, deduplication or replacement; an identity permutation is valid. | 24 reordered versions, 24 rank requests |

Total: **48 generated portfolios / 480 answer slots**, plus **24 permutations**, yielding **72 ordered assessment instances**. C is paired with its exact B responses; it is not another independently generated sample. Two repeats are separate requests, not a promise of statistical independence from the provider or seed-controlled reproduction. Rotate A/B generation scheduling deterministically across prompt/repeat blocks; C follows its own completed B. Score each order only after its generation/ranking decision has been frozen. No tuning between the live check and the remaining work.

### Exact role and protocol choices

| Role | Requested model/profile | Bounds and source |
|---|---|---|
| Generator, angle planner, reranker | `claude-sonnet-5-5`, adaptive thinking, effort `low`, global standard service; no temperature/top-p override, tools, web or conversational memory | Answer profile follows the pinned NB documented `max_tokens=2048` argument: the native helper sends **4096 total thinking-plus-text tokens**. Use the same 4096 API cap for plan/rank. It is not a strict 2048 visible-token guarantee. |
| Native grouping | `gpt-5.6-luna`, unchanged native structured prompt/schema, seed `None` so each assessed order is shown as delivered | Bind explicitly: the CLI's shared default is a different judge. Pinned OpenAI request supplies no effort/output cap; preserve that omission, record provider defaults (currently medium) and reserve up to its documented **128,000 output tokens**. No claim that grouping explicitly requested low/high effort. |
| Native quality | `claude-opus-5`, unchanged native prompt/schema, adaptive thinking, effort `high`, API `max_tokens=16000` | Scores the first response of each native group, on the original task without plan/sibling answers. No fallback judge. |

Use native version **1.1**, patience **0.8**, and unchanged native call construction, strict folding and utility/summary arithmetic at the pinned source. These settings are a declared native-metric study with controlled execution; it is not a leaderboard submission or reproduction of every native CLI recovery policy. The plain condition is the reference generation procedure; B/C are explicitly declared interventions.

The [pinned README](https://github.com/novelty-bench/novelty-bench/blob/64a23be6b18ec1dacc298830aab276061b6e143c/README.md) differs from some CLI defaults: bind generation length/effort and grouping model rather than inheriting them. Native source also has hidden SDK retries, grouping retries/lenient repair, and a quality fallback. The external assessment boundary must disable hidden retries/fallbacks and use strict native validation with explicit statuses, without editing upstream prompts or algorithms. One provider generation attempt per planned request; do not retry refusals, malformed content, timeouts or ambiguous deliveries automatically. Preserve invalid results and stop on unresolved accounting. Native metric compatibility does not establish judge validity.

2A must retain exact system/user templates, angle schema and permutation schema; record requested and returned model IDs, full effective files/settings, request/response IDs, original and rendered prompts, texts/order/IDs, stop reasons, failures, usage including thinking/cache categories, and generation versus assessment costs. Runtime snapshots bind actual native call paths and package/image identity. A requested model alias does not guarantee immutable weights; no silent model substitution if access/settings fail.

### 2A: prepare a usable offline kit, then review

- Define a versioned **live-v2** artifact/export/assessment route. Existing Phase 0 contracts intentionally accept synthetic fixtures only; retain those guards and old behavior. Test refusal of synthetic grading on real outputs. Use thin explicit strategy/evaluator adapters and existing artifact/accounting helpers where compatible, not a new engine, plugin framework or provider gateway. Preserve actual upstream Harness² for later recursion; this phase does not copy its algorithm or introduce a fake adaptive loop.
- Freeze the selected 12 tasks, all three templates, 24 prompt/repeat blocks, all expected artifacts/request slots, two human-check prompts, role profiles, hashes, caps, failure policy and selection rule in a new `runs/phase2-r010` namespace, with evidence in `evidence/phase2-r010`. Produce a synthetic offline example/export/analysis walkthrough; synthetic scores stay visibly separate from live scores.
- Reuse the supported pinned environment. No weights, new model-serving stack or benchmark fork. Any essential dependency/setup amendment is pinned, license-reviewed and separately recorded before use; do not broadly upgrade the environment. Exercise tests, lint/type/security checks appropriate to the implementation.
- Verify every provider dispatch passes one accounting boundary, including native structured parsing and hidden retry paths. Prove input admission, output reservations, atomic intent/result reconciliation, resume without rebilling, permutation integrity, per-order native assessment, credential separation and failure denominators with offline checks. Bound input tokens at **8,000** per answer/plan/quality request and **64,000** per rank/group request, including templates/schema overhead, using a verified conservative offline bound. Reject over-limit inputs without truncation; a failed admission is visible and cannot cause sample replacement. No provider/token-count calls occur in 2A. If the offline bound cannot be established, report that blocker before 2B.
- Bind source pins, exact prices/caps and expected workload; verify declared credential availability without printing keys. Account access and actual model behavior remain unverified until 2B. Return `PHASE2_PREPARATION_REPORT.md`, the usable offline kit and unresolved prerequisites. Stop for review before paid work; do not infer a spending grant from the planning estimate below.

### 2B: one counted live check, then bounded expansion

Subject to later authorization, use the first selected task/repeat-1 block for the initial composed live check: **21 answer/planning requests + one rank request + three grouping requests + up to 30 quality requests = at most 55 model requests**. These count inside the full worklist, not as extra training or replacements. Stop and report the actual transport, native metric path, prompt/model identities, accounting, malformed/refusal statuses and revised full-run projection before expansion. Readiness requires correct request/artifact/scoring/accounting behavior, not a favorable score or changed answer order. If a material correction changes a profile/template/metric, preserve the attempted work and refresh its identity and comparability before further calls.

One request in flight phase-wide. Before each dispatch, require `settled cost + unresolved reservations + this request's conservative reservation <= applicable cap`. Reserve all billable thinking/output and worst-case admitted input, including cache writes. Set transport/SDK retries to zero; no implicit fallbacks, lenient partition repair, batch discount or paid replacement calls. Stop on unknown delivery/usage, unsupported controls, invalid identity or budget exhaustion; retain the liability until resolved. A finite request timeout does not prove the provider stopped charging. No automatic increase in budget or attempts.

On a successful reviewed live check, finish the unchanged worklist within the approved ceiling. The maximum is **528 Sonnet requests + 72 grouping requests + 720 quality requests = 1,320 model requests**, with no retry allowance. Quality counts depend on the observed partition heads; minimum is 72 when all orders succeed, maximum 720. Both A/B must have ten answer slots; planning failure marks dependent slots skipped rather than inventing outputs. Retain provider refusals/empty outputs with native-compatible visible placeholders and separate statuses; these are method outcomes. A malformed plan/permutation, missing judge or over-limit request is not silently replaced or converted to a favorable score.

Obtain a fresh grouping assessment for every assessed order, including reranked C. Do not reuse B's partition as C's native result. To keep the slice small, **no new response-level score memoization optimization** is included: budget each ordered instance's native head requests independently. Native caching may avoid exact replay of the same assessment identity; changed order/settings use a different identity. Unscored/invalid cases remain in coverage and failure totals even where a native summary omits them.

### Independent human check of new outputs

Before calls, freeze the first two selected development prompts and repeat 1 as the check sample, irrespective of scores. Two user-nominated English-fluent readers independently review all three anonymized ordered portfolios for each: **six portfolios / 60 answer presentations per reader**. They must be fresh to these pilot outputs, work separately without scores, method/angle labels, discussion or LLM help, and submit brief task-fitness/constraint, meaningful-variety and duplication notes plus `acceptable` / `substantive concern` / `cannot judge` per portfolio. No scalar creativity score, MuCE rubric or forced preference. Capture prior recognition and missing context. Since B/C share texts, perfect method blinding cannot be guaranteed; counterbalance the six presentation units deterministically between readers and record any inferred identities.

Freeze both submissions before comparing them with native results; preserve raw notes, all concerns and disagreements without a third reader or adjudication loop. The same nominees as optional Route H may participate if eligible and willing; Route H completion/exposure does not determine freshness to these new outputs. This small task-specific diagnostic does not validate the native judges or all 12 prompts. Plan at most **60 minutes per reader plus 90 minutes administration**, or **3.5 person-hours**, with $0 cash only if volunteers. Bind availability before 2B; if unavailable, stop at the usable 2A kit or explicitly close a limited native-only run without claiming the full human check was completed. No messages/recruitment are authorized by this definition request.

### Analysis and exit decision

Primary contrasts: native utility **B minus A**, and **C minus its identical B texts in their original order**. Average the two repeats within each prompt, then weight the 12 prompts equally. Report per-prompt contrasts, overall descriptive means/ranges, distinctness, native head-quality/first-answer information with scored coverage, refusals/empty/missing outcomes, latency, and actual generation/planning/ranking versus assessment cost. Do not treat 480 answers, 72 orders or repeated calls as 72 independent tasks. Do not claim a population-wide winner, significance or creativity improvement from this pilot.

Eligible seed candidates require complete comparable native coverage and completed independent human checks without an unresolved substantive concern about that candidate. Select highest mean native utility; exact ties use lower actual answer/planning/ranking cost, then simpler procedure in order A, B, C. A plain procedure is a legitimate selected seed. Human concerns are reported rather than voted away; `cannot judge`, compromised review or differential missingness makes seed selection inconclusive. If no candidate is eligible, return a stop/inconclusive decision instead of choosing favorable complete cases. This is a development selection, not held-out confirmation, compute-controlled attribution or evidence that reranking fixes the scoring model.

### Deliverables, exclusions and completion criteria

| Deliverable | Required usable content |
|---|---|
| 2A preparation kit/report | Frozen tasks/templates/profiles/worklist, separate live contract, native export/import/assessment path, synthetic walkthrough, verified accounting/containment and dated cost sheet. |
| Fixed procedure packages | Inspectable ordinary/planner templates and permutation-only transformation with identities and commands to execute a declared condition later. |
| 2B output/evidence archive | 48 portfolio statuses, 24 permutation statuses, 72 assessment statuses; original plans/responses/IDs/order, native results/traces, all requests/failures/costs and readable human forms. |
| `PHASE2_REPORT.md` | Paired analysis, coverage, human notes, actual cost, limitations and selected seed or explicit inconclusive/stop decision; artifact manifest and replay instructions without generation. |

Out: actual recursive adaptation, second generator, model/reasoning tournament, CrPO/MuCE calibration or weights, Route H execution requirement, additional strategy families, supervised search, online memory, new benchmark, new confirmation material, leaderboard submission, UI/platform work or generic cache/provider infrastructure. The native v1.1 quality judge needs API access, not a local reward model.

| Criterion | Completion evidence |
|---|---|
| P2-1: Usable preparation | 2A kit and walkthrough work; exact worklist/profiles and budget are frozen before live observation; previous fixture safeguards/tests remain intact. |
| P2-2: Real-path readiness | First counted composed trace establishes declared live generation/ranking and actual native scoring through accounted dispatch, with a review before expansion. |
| P2-3: Output and permutation integrity | Every planned slot/status is traceable; C is a validated one-to-one permutation of its B texts/IDs; no replacement/resampling or unreported generation. |
| P2-4: Assessment and accounting | Fresh per-order grouping, correct native heads/arithmetic, model/settings provenance, visible missingness and reconciled settled/reserved cost; no unsupported hard-cap claim. |
| P2-5: Independent human diagnostic | Prespecified new-output sample, two eligible readers, preserved notes/statuses and explicit blinding/coverage limits; no substitution by an LLM or by Route H results. |
| P2-6: Bounded decision and handoff | Reproducible paired report, usable procedures/artifacts, explicit seed or inconclusive decision, exclusions/preservation checks and next-phase refresh recommendation. |

**Full completion:** P2-1 through P2-6 with all 48 portfolios/24 permutations/72 orders accounted for, comparable native coverage and human records. A losing strategy, refusal or a human concern can be a valid scientific outcome; a positive seed recommendation is not required. **Limited closure:** budget stop, missing assessment/reviewer or execution/accounting defect yields a usable kit and limitation report, explicitly short of a completed comparable pilot. Never claim full scientific completion from 2A tests alone. Do not extend work until something wins; Phase 3A begins only after a separate concrete refresh and authorization, and later native proposer/selector execution remains unverified by this phase.

### Cost, time and spending boundary

**2A:** $0 experiment/API spend; no inference or provider token counting. Planning allowance **1–2 focused implementation days**, with a usable preparation handoff at the end of the slice; if a required boundary cannot be implemented within that envelope, report the blocker instead of adding infrastructure. This is an estimate, not work already performed.

**2B proposal, not authorization:** **$125 total API stop limit**, including unresolved liabilities; the first counted live check has a **$5 sublimit included in that $125**. Actual pre-launch prices/request reservations and the user's applicable ceiling must be bound in 2A. Stop and report after that check before expanding, with no automatic budget top-up. Either stop limit can halt its slice before completion: the 55-request first check's full configured maximum is about **$15.18**, so $5 does not guarantee a finished readiness trace. A partial check cannot establish readiness or trigger expansion. Dollar amounts exclude ordinary assistant-session fees, local electricity and volunteer time; no rented compute, paid data or paid annotators is included.

Rates checked **2026-10-25, America/Los_Angeles**, standard global text requests, USD per million billable tokens:

| Role | Input | Output, including thinking | Budget treatment |
|---|---:|---:|---|
| Sonnet 5.5: A/B/planning/ranking | $2 base; $2.50 five-minute cache write | $10 | Budget all input at $2.50; do not assume cache hits or batch savings. |
| GPT-5.6 Luna: grouping | $0.20 | $1.20 | No premium tier or long-context surcharge assumed; admitted input stays below 64k. |
| Opus 5: native quality | $5 | $25 | No cache write enabled; reserve native 16k total output ceiling. |

Sources: [official Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing), [Sonnet 5.5 identity](https://platform.claude.com/docs/en/models/sonnet-5-5/overview), [official OpenAI Luna pricing/limits](https://developers.openai.com/api/docs/models/gpt-5.6-luna), and pinned NB `src/inference.py`, `src/judge.py`, `src/partition.py`, `src/score.py`. Documentation availability is not account access. Recheck before paid dispatch; changed rates/settings require rebinding the cost sheet, not silently reusing it.

With totals in tokens, conservative working formula is `(2.5*I_s + 10*O_s + 0.2*I_l + 1.2*O_l + 5*I_o + 25*O_o) / 1,000,000`; settle using actual billed categories. The following are **scenarios, not measured predictions**:

| Scenario | Mean input/output across 528 Sonnet requests | Group input/output per order | Quality heads and input/output per head | API estimate |
|---|---|---|---|---:|
| Working allowance | 2,000 / 1,000 | 12,000 / 1,000 | 360 heads, 2,500 / 1,000 | **$21.68** |
| Higher reasoning/coverage | 4,000 / 2,000 | 24,000 / 2,000 | 720 heads, 5,000 / 4,000 | **$106.36** |

At every admitted input/output ceiling and 720 heads, the no-retry full envelope is about **$364.33**: $35.55 Sonnet, $11.98 grouping and $316.80 quality. In particular, quality output alone could be $288. This is why $125 is a stop-loss proposal rather than a completion guarantee, and why the first accounted trace must inform expansion. If the observed projection exceeds the ceiling, deliver a limited report and propose a new bounded definition rather than secretly reducing native quality effort/caps. No paid human arrangement is authorized; if volunteers are unavailable, price a separate arrangement before proceeding.

Allow one live-check/review slice, then one frozen expansion/report slice, subject to provider availability and the API cap; no performance-driven extension. Human-check collection has one agreed due date within seven calendar days of delivery. Preserve a usable artifact at each stop. CrPO stays deferred and Route H stays optional whatever the result.

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
- **0.8:** close Phase 1A under unchanged frozen revision 0.7: source reconciliation, eight-pair packet with explicit shortfall, exposure/candidate inventory and use-specific decisions. Archive exact revision 0.7; record $0 experiment spend and Route H as an unstarted next proposal. No scientific method, threshold, prior result or protected source was changed.
- **0.9:** define optional Route H: two user-nominated humans, eight fixed pairs/16 one-pass judgments, unchanged substantive rubric, independent collection, explicit ambiguity/missingness, a descriptive report and volunteer-cost/time caps. Archive exact revision 0.8 and preserve commit `bed3465`'s evidence. Reassess priority: defer further CrPO implementation and frontier evaluator selection until a core pilot presents a specific measurement need; Route H is not required to enter Phase 2. This update performs no collection, experiment or code change.
- **0.10:** concretely define Phase 2 with offline 2A and reviewed live 2B checkpoints, 12 development tasks/two repeats, exact ordinary/planner/permutation conditions, declared native metric roles, new-output human checks, failure/selection rules and dated scenario costs. Propose a $125 API stop limit with an included $5 first-check sublimit, without authorizing spend or promising completion under that cap. Archive revision 0.9; preserve all completed evidence. CrPO remains deferred and Route H optional. No task selection, code implementation or experiment accompanies this update.
- **0.11:** close the authorized offline Phase 2A slice under unchanged revision 0.10. Preserve its exact specification, frozen development study, separate live/fixture contracts, native exchange/assessment path, accounted synthetic walkthrough, tested failure controls and $0-spend evidence. Record the unestablished offline input-token bound and unconfirmed grouping billing assumption before any live work; real dispatch stays disabled. Archive exact revision 0.10. Phase 2B, Route H and later phases remain unstarted, with CrPO deferred; no criteria or scientific outcomes were changed to accommodate results.
