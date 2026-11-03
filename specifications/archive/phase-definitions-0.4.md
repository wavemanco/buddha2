# Buddha2 phase definitions

Revision: 0.4 — 2026-10-24, America/Los_Angeles  
Status: Phase 0 complete under frozen revision 0.3; Phase 1 concretely proposed; later phases provisional and unstarted  
Authority: the current request authorizes planning/document updates only. No Phase 1 implementation, dataset sampling, model calls or later-phase execution is authorized by this document. The original Buddha2 folder remains protected.

The [experiment plan](EXPERIMENT_PLAN.md) gives the research rationale. This document specifies work products and completion gates. [DECISIONS.md](DECISIONS.md) remains Phase 0's historical implementation decision record. Phase 0's exact [specification](specifications/archive/phase-definitions-0.3.md) and [decisions](specifications/archive/phase0-decisions-0.3.md) are preserved byte for byte; their hashes match the retained run manifest. Use the [handoff report](PHASE0_REPORT.md) for evidence and navigation. The archives retain links originally authored relative to the project root.

Refreshing this file changes the effective input identity for a new Phase 0 run. Do not edit old manifests, reports, assessments or the example archive to make them match revision 0.4. Historical completed-run resume belongs to commit `6bafb25` and its frozen inputs; current definitions require a fresh output directory. No historical replay was executed during this planning refresh.

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

### Data selection proposal

- **Pin:** `CNCL-Penn-State/MuCE`, revision `a02181e394c41602a95d0678b0ce9d880e994289`, configuration `full_agreement`, `train` only. Repository metadata declares MIT; retain attribution/notices and record any applicable source-dataset restrictions during preparation. No paid data subscription is expected. The public `val`, `test`, `heldout_item` and `heldout_task` splits remain unopened in this phase. [Pinned metadata](https://huggingface.co/api/datasets/CNCL-Penn-State/MuCE/revision/a02181e394c41602a95d0678b0ce9d880e994289).
- **Size:** 24 unique eligible prompt groups; 12 calibration and 12 audit. Target Alternative Uses, Design Solutions, Real-Life Creative Problem Solving and Metaphors: six groups per family, split three/three. These quotas are a proposal, not a verified claim about available rows. Three audit prompts per family cannot validate a family-specific evaluator.
- **One construct:** overall creativity, using a documented compatible `RatingLabel` value. Verify actual field semantics before selection; do not infer label meaning from its name or silently combine originality with overall creativity. If the selected population cannot support the construct/quotas, produce the eligibility shortfall report and stop before calls. Propose a smaller population explicitly instead of silently substituting families or relaxing filters.
- **Pair eligibility:** English, identical effective task/prompt and compatible `Dataset`, `Set`, `DatasetsSplit`, task/language and rating context; two different nonempty responses; finite, documented scaled human scores with gap **at least 5 points**. The paper reports a 10–50 rescaling and uses a five-point preference margin; verify that interpretation for the pinned public fields rather than re-rescaling or treating cross-source scores as interchangeable. Ambiguous scales/context are excluded pending resolution. [MuCE preference construction](https://arxiv.org/html/2505.14442v2#S4).
- **Selection:** freeze normalization (Unicode NFKC, case-folding and collapsed whitespace for grouping only), prompt/context alias rules and seed `20261024` before inspecting evaluator outcomes. Retain original text. Cluster duplicate prompt identities across sources before allocation. Choose groups, split assignment and one eligible pair by stable seeded hash order; do not choose the easiest pair, largest rating gap or best observed evaluator result. No mid-run replacements.
- **Identity:** preserve dataset revision/configuration/split, original source IDs, field values, prompt/response hashes and selection revision. Conflicting duplicate composite IDs fail explicitly. Resolve missing IDs and cross-source aliases before freezing; never merge distinct responses merely because their text matches.
- **Exclusions:** reserve every selected calibration/audit group from future method confirmation. Documentation review exposed published example response/label material; exclude prompt groups illustrated in the paper's example-response tables (10–14) and its Sentence Completion example. Record that exposure instead of claiming the public examples were unseen.
- **Separation:** the preparation process may read ratings to construct pairs; it emits audit inputs separately from audit labels. The critic receives no ratings, source prestige, preferred-response position or other judgments. Calibration tuning sees calibration outcomes only. Freeze the complete final rubric/model/settings before audit inference; commit all audit predictions before unsealing audit labels. Record label access. This is experimenter-held-out evaluation with procedural separation, not evidence against model-pretraining contamination.

Exact row IDs and source-field values will be selected and frozen at the first implementation checkpoint, using these rules. No rows or audit labels have been selected for this specification refresh. The eligibility manifest, not this proposed quota, is the pre-call execution lock.

### Evaluator and execution proposal

Recommend the first-party Anthropic Messages API with **`claude-sonnet-5-5`**, one versioned creativity-comparison rubric, `output_config.effort=medium`, adaptive thinking, `max_tokens=2048`, no tools, no conversation history, no caching/batch assumptions and global standard pricing. Do not send unsupported sampling parameters. Record requested/returned model IDs, actual effective controls, SDK/image/source revisions and usage. These settings are a proposed profile, not a tested route or a claim that Sonnet is the best critic. A model/control change requires a pre-audit definition change; after audit observation it consumes that audit. [Model and controls](https://platform.claude.com/docs/en/models/sonnet-5-5/overview), [effort/output budget](https://platform.claude.com/docs/en/build-with-claude/effort), [model-version guarantees and limits](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions).

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

No automatic calibration rerun, second critic, model-based format repair, outcome-driven retry or post-audit rubric revision. Ordinary tie, refusal, truncation or valid-but-wrong judgments are recorded outcomes. Retry only a declared transient transport/service failure; disable hidden SDK retries. Persist intent before dispatch and preserve each attempt. Unknown delivery/charge consumes its conservative reservation and stops expansion until resolved; do not blindly repeat it. Resume must not duplicate an already finalized request. No distributed or arbitrary-crash exactly-once guarantee is promised.

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

Ties, abstentions, refusals, malformed/missing or exhausted-attempt results earn zero for these fixed-denominator gates; two abstentions do not count as consistency. Report per-presentation agreement and decisive coverage separately. Report 95% prompt-level Wilson intervals for the two proportions, first-position preference and error patterns by answer length and family. These diagnostics add no model calls, cannot reliably estimate family effects with three audit prompts each, and are not additional post-hoc acceptance gates. The thresholds are a proposed operational screen, not a scientific standard or high-confidence validation claim.

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

Before implementation, review this specification and its offline shape. Before paid launch, deliver the actual eligible pair/split manifest, exact rubric/profile/request schema, tested offline controls, permitted endpoint/credential handling, observed readiness policy and an explicitly authorized ceiling. Do not ask for a budget merely to finish this planning document. No rows, requests or phase execution have been started here.

## Phase 2 — A usable fixed-strategy baseline tool

**Objective:** isolate the contribution of the original planner and of answer ordering with one generator, before testing harness adaptation.

**Usable output:** working ordinary-sampling and planner strategy packages, an isolated reranking transformation, immutable generated portfolios, and a paired report. A researcher can rerun a declared condition or apply compatible assessments to saved outputs. The report identifies the fixed procedure chosen for the next comparison or recommends stopping.

**Build/do:** 12 development prompts, two independent repeats, two generating conditions: 48 generated portfolios of ten responses. Rerank the 24 planner portfolios, creating 24 recorded permutations without replacing response texts. Use pinned native NoveltyBench evaluation on each new order; fixed-partition estimates are labeled diagnostics. Record every planning/ranking/assessment call and failure. Add only supplementary scorers explicitly activated in the phase definition; retain the other CrPO dimensions in the measurement backlog.

This yields **72 portfolio/order assessment instances**, not 72 necessarily billable judge calls, and only **12 independent prompts**. The generator and official grouping/quality-judge routes need their own readiness evidence. Define a versioned live-output contract instead of relaxing Phase 0's fixture-only grading guard or reusing its invented labels. Phase 1's evaluator may remain diagnostic or unused; native assessment and a frozen blinded human sample remain the fallback. Do not silently turn its pair preference into a scalar portfolio score.

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
