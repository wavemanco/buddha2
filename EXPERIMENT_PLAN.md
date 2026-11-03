# Buddha2 experiment plan

Date: 2026-10-27, America/Los_Angeles  
Status: Phase 2A preserved; benchmark-only and optional human-augmented research tracks defined; offline policy update complete; offline live-readiness checkpoint complete/change-required; AM-1 offline candidate complete; P2-R complete under frozen 0.18 (closure 0.19); Phase 2B unstarted/unauthorized; Route H optional/unstarted; CrPO deferred; current specification revision 0.19  
Project: `C:\Users\arvik\code\research\Buddha2`

## 1. Decision and scope

Use a phase-wise approach. The first milestone is one trustworthy small comparison, not a general research platform or a full model-by-strategy-by-benchmark matrix.

Proposed governing question:

> For a given base model and task family, when and by how much does genuine Harness² adaptation improve useful output beyond a frozen strategy procedure, given the same declared techniques and a comparable total inference budget?

Three supporting comparisons keep the objective interpretable:

| Contribution | Comparison | What it establishes |
|---|---|---|
| Base model | Ordinary sampling from each selected generator under a declared protocol | Starting performance and cost before adding strategies |
| Fixed strategy | Ordinary sampling versus an exact, frozen strategy procedure with the generator held constant | Whether that procedure helps, and its cost; optional operators require separate comparisons |
| Harness adaptation | A frozen procedure versus native Harness² initialized with that procedure, with the same technique access and comparable inference-budget envelopes | Incremental value of changing the procedure beyond additional sampling and selection |

The first bounded adaptation question concerns the existing planner-and-generation procedure and one authentic Harness² Propose-Probe-Compose step (Phase 3A). Testing successive native refinement is an explicit research milestone (Phase 3B), not merely an unspecified extension. A one-step result does not answer that repeated-improvement question. Broader model, strategy and task-family coverage is a research direction, not a requirement to complete a full matrix before obtaining an answer. Report model/family estimates descriptively unless enough independent prompts support comparative or interaction claims.

Begin with one generator, one native executor, one benchmark protocol and one fixed planning strategy. Phase 1 screened one creativity evaluator; it missed both held-out floors and remains diagnostic-only. That result does not isolate the model, rubric or reference-data validity. Phase 1A completed the bounded data-readiness decision: published-label development is supported, CrPO reproduction is conditional, and independent human alignment remains unvalidated. Optional Route H now defines one small human diagnostic; it is not a Phase 2 gate. Prioritize native benchmark evaluation and predeclared blinded review of new outputs. Defer further CrPO implementation and frontier evaluator selection until a concrete pilot measurement need justifies them. Introduce the second generator only for confirmation. Additional strategies and benchmarks must fit the interfaces, but need not be implemented in advance.

Human review is an optional additional assessment, not a prerequisite for answering which procedure performs better under a declared benchmark protocol. The `benchmark` track can conclude and select its next seed from complete native evidence/accounting; later `human-augmented` decisions use separately attached human evidence. These support different claims, and the small human sample does not establish general judge validity. Both tracks retain the same base-model/fixed-strategy/recursive-adaptation question.

This new project does not inherit the earlier Buddha² implementation or its effectiveness claims. Previously examined results are development context. In particular, the legacy 100 curated prompts and completed 259 WildChat prompts cannot become clean confirmation evidence merely because this project has a new folder.

## 2. Use Harness² itself

The dependency is the actual upstream Google Harness² at a pinned commit. Its code owns recursive proposal, probe execution, composition, selection, and, when enabled, cross-task experience. Our integrations provide the benchmark inputs and native execution/scoring boundaries. Do not copy those algorithms into a new core or substitute a deterministic editor in an efficacy experiment.

Verified extension points exist in upstream `BenchmarkAdapter`, `BenchSpec`, and the executor substrates. The current CLI factory has a fixed benchmark list, so the initial entry point should be a thin external runner calling upstream APIs. A supported upstream registration hook could replace that runner later. This is an integration seam, not a promise of a stable public API. [Harness² adapter contract](https://github.com/google-research/harness2/blob/main/harness2/core/spec.py), [CLI factory](https://github.com/google-research/harness2/blob/main/harness2/cli/_common.py).

Use the pinned Linux/amd64 Docker environment resolved in DECISIONS.md. A Windows port and additional executors are outside the first slice. [Upstream installation](https://github.com/google-research/harness2#install).

The primary adaptation arm remains score-blind: the proposer and selector receive permitted task inputs, trajectories, and internal critique, without external benchmark judgments or held-out human labels. Preference-supervised harness search is a separate later method, not a silent modification of this arm. [Native method](https://github.com/google-research/harness2#readme).

## 3. Modular boundaries

Borrow DeepSeek's replaceable interfaces and configuration-based composition. Initially use ordinary modules with explicit registration, not a new runtime framework. DeepSeek Harness itself is not an additional execution dependency. [DeepSeek architecture](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/architecture.md).

| Component | Owns | Initial implementation |
|---|---|---|
| Task-suite adapter | Versioned task IDs, splits, inputs, task families, required output types and execution capabilities | NoveltyBench task source; MuCE labeled-response source for calibration |
| Execution integration | Calls upstream Harness², or invokes a declared plain/fixed condition; captures native outputs and traces | One Harness² revision and one native executor |
| Strategy package | Native harness files, prompts, workflow operators, or explicit output transformations; parameters and requirements | Plan-then-generate; reranking as a separately measured transformation |
| Model configuration | Generator, proposer, selector, reflector, and evaluator identities; provider capabilities and generation controls | Existing upstream/provider facilities where sufficient; explicit role bindings |
| Evaluator adapter | Required task/output evidence, native scoring invocation, criterion identity, metric values, units, direction, applicability and failures | Native NoveltyBench; one MuCE creativity critic; simple mechanical format checks |

Each extension declares an ID, version/source revision, configuration digest, contract version, and required/provided capabilities. A strategy must expose its effective prompts and files; the word "plugin" must not hide an unrecorded intervention.

The study runner retains the invariants: split access, frozen arm definitions, spending limits, immutable results, complete accounting, and denominator/failure policy. Strategies and adaptive agents cannot edit those rules during a run. DeepSeek's distinction between cooperative extension hooks and final invariant guards is useful here. [Extension patterns](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/cookbook/extension-cookbook.md).

### Tasks and evaluation are separate

A new benchmark can register its task source, any execution requirements, and its evaluator. A new criterion can register only an evaluator. Several evaluators can read the same saved artifacts without regenerating them when the required evidence is present.

NoveltyBench is the first integration and testbed, not the scope of the research engine. Another benchmark receives its own pinned adapter and concrete phase definition. Cross-benchmark effectiveness claims require actually evaluating on those benchmarks; adapter compatibility alone does not establish generality.

Compatibility includes task meaning and protocol, not only file format. A text judge can assess a saved story; a software benchmark may need runnable code, tests, and its environment. A math benchmark normally requires answers to its own questions. Missing prerequisites produce `not applicable` or an explicit incompatibility, not a fabricated score. Evaluation itself may incur model cost.

NoveltyBench runs in its own pinned environment. Export/import documented artifacts and call its native evaluation stages; do not transplant its judge implementation into our engine or present a heuristic substitute as official scoring. Preserve raw native results and metric names. Upstream Harness²'s passed/total reporting does not make continuous utility a pass fraction. [NoveltyBench workflow](https://github.com/novelty-bench/novelty-bench#basic-workflow), [Harness² scoring representation](https://github.com/google-research/harness2/blob/main/harness2/core/judge.py).

## 4. Phases and gates

All counts below are proposed planning envelopes. Exact eligible IDs, model IDs, phase ceilings, and stopping rules must be frozen before the relevant calls. No phase advances automatically.

The concrete scope, usable outputs and acceptance criteria are specified in [PHASE_DEFINITIONS.md](PHASE_DEFINITIONS.md), revision 0.19. Phase 0's completed work is governed by its [frozen revision 0.3](specifications/archive/phase-definitions-0.3.md) and [decision record](DECISIONS.md). Phase 1 completed under [frozen revision 0.5](specifications/archive/phase-definitions-0.5.md), the user's $5 authorization and explicit readiness exception. Its [report](PHASE1_REPORT.md) records the diagnostic-only outcome, 48 judgments, $0.112696 usage-based cost and offline replay. The [previous closeout specification](specifications/archive/phase-definitions-0.6.md) and commit `35cc481` preserve its historical documentation identities. Phase 1A completed under [frozen revision 0.7](specifications/archive/phase-definitions-0.7.md); its [report](PHASE1A_DATA_READINESS_REPORT.md), [closure revision 0.8](specifications/archive/phase-definitions-0.8.md) and commit `bed3465` preserve that checkpoint. Route H's [definition revision 0.9](specifications/archive/phase-definitions-0.9.md) remains preserved and optional. Do not rewrite historical records or hashes. Phase 2A completed under frozen revision 0.10 and closed at revision 0.11/commit 9ef4024. Revision 0.12 defines benchmark-only continuation and optional later human augmentation before live observation. Phase 2B remains unstarted and unauthorized. Refresh and present every phase before starting it.

| Phase | Bounded work | Deliverable and decision |
|---|---|---|
| **0: Establish the integration** | Actual upstream Harness², one executor, NoveltyBench adapter, one strategy package, artifact export, minimal study manifest. Offline fixtures only. | Prove the seams work without changing either upstream. Review this slice before live work. |
| **1: Check one creativity evaluator — complete** | One critic; 24 approved MuCE Metaphors creativity groups, 12 calibration/12 audit; one pair in both orders. One JSON-format wording revision, no calibration rerun. | Usable pair-evaluation kit and diagnostic-only report: both-orders human agreement 4/12 and consistency 8/12 missed the frozen floors. 48 calls, $0.112696 usage-based cost, zero retries/liabilities under the authorized $5 ceiling. |
| **1A: Establish reference-data readiness — complete** | All 16,948 cached rows and 48 historical mappings reconcile; eight fixed inspection pairs, with the four-pair shortfall preserved; metadata-only release/asset review. No experiment inference. | Usable report, packet and exposure/candidate inventory. Published-label development ready; CrPO reproduction conditional; independent human alignment unvalidated. $0 experiment spend. Its report recommended Route H, now separately defined; no next experiment started. |
| **H: Optional rubric/context diagnostic — defined, unstarted** | Two eligible user-nominated humans; same eight fixed pairs, once each; same substantive rubric and separate blinded responses. No model calls. | Sixteen planned judgments, case report and explicit ambiguity. $0 cash assuming volunteers; at most three person-hours. Does not gate Phase 2 or validate a general evaluator. |
| **Live readiness: 0.14 checkpoint — complete, change required** | Gate 1 failed to establish input/billing controls; no Gate 2 runner/preflight/mock trace built. Original code/study preserved; no endpoints or credentials. | $0 API spend; five-role dossier, conditional recost/review and AM-1 proposal. No launch-ready packet; Phase 2B remains blocked. |
| **AM-1: offline follow-up — complete** | Supported public-PAYG full-context financial envelope; same payload acceptance/scientific requests; versioned controls and actual pinned-SDK first-block mocks. | Frozen candidate, 55/40-request traces, zero-call resume, 230 project tests/five upstream checks and offline handoff. $0 API spend. Provider-enabled host launch remains unbuilt; no paid grant. |
| **P2-R: Complete Phase 2B Execution Kit — complete under 0.18** | One block for every remaining software prerequisite: complete 24-block runner, cumulative staged journal, guarded host launch, new-release reports/replay/human compatibility and full offline rehearsal. | One frozen kit/acceptance gate; $0 API budget. No further planned engineering after the counted check; operator inputs/grants and real first-block observations remain. |
| **2: Establish fixed baselines — 2A preserved; 2B blocked/unstarted** | After P2-R passes, run the counted first block, review and explicitly authorize cumulative expansion using the already-built kit. Same generator, 12 frozen development prompts/two repeats and A/B/C methods. | Benchmark paired report/seed or inconclusive decision without readers; optional later human supplement. Future $20 first/$125 cumulative proposals are not grants or guaranteed spend. |
| **3A: Test one authentic adaptation step** | Same generator/development population. Actual upstream parallel Harness² at `k=1`, initialized with the selected fixed strategy; two repeats. | 24 task adaptations, with all probes charged. Establish feasibility and observed quality/cost; an unmatched pilot cannot attribute gains specifically to adaptation. |
| **3B: Test successive recursive refinement** | Native sequential `k=2`, starting from the same fixed procedure and technique set. Provisional initial envelope: four development prompts, one repeat, with a comparable-budget frozen control for each. | An inspectable two-round tool and bounded policy comparison. Evaluate whether later refinement is useful; four prompts are feasibility evidence, not confirmation. Review real costs from 3A before starting. |
| **4: Confirm on held-out material** | Two frozen generators; ordinary sampling, the selected fixed procedure with a frozen policy for spending a comparable inference budget, and selected adaptation; initially 40 new prompts and two repeats, subject to a predeclared precision/budget calculation. | A paired held-out report by model. The budget-comparable fixed control is required for the central adaptation claim. |
| **Later: Answer one new question** | A matched breadth-versus-depth comparison, depth beyond two rounds, another operator, another benchmark, online memory, or supervised harness search. | One extension and one named comparison per slice. |

The [0.14 checkpoint](PHASE_DEFINITIONS.md#live-readiness-checkpoint) remains historical no-go; the separate [AM-1 follow-up](PHASE2_AM1_REPORT.md) completed its offline scope. All known remaining software is now consolidated in [P2-R — Complete Phase 2B Execution Kit](PRE_PHASE2B_BLOCK.md): full pilot/expansion, staged cumulative accounting, host launcher and current-release reports/human compatibility. Actual account/model/settings/usage verification belongs to Phase 2B's counted first block, following P2-R completion and applicable operator inputs/grant; it is not another preparation experiment.

### Two research tracks, one implementation

Approach (a) means two scientific lineages sharing Phase 2A, saved Phase 2B outputs and native assessments. It does not require two Git forks, two providers or duplicate generation. The benchmark track advances independently of reader availability; the optional human-augmented track starts its decision when usable submissions arrive. Both freeze policy/sample before outputs and name their parent decision, assessment set, evidence cutoff and policy identity. See [track rules](PHASE_DEFINITIONS.md#research-tracks-and-later-human-input).

Late human review adds assessment and decision records without altering native scores or the earlier benchmark decision. If it selects the same seed, compatible downstream evidence can be referenced by both tracks with no double-counting. If it selects a different seed/procedure, scope future execution from the last compatible parent; do not automatically rerun completed phases or fund a second full matrix. Human review of an earlier seed does not imply review of later outputs, and feeding critiques into adaptation defines a separate human-guided intervention.

After a track opens confirmation, changed methods need fresh unopened material for a new confirmatory claim; old-set reanalysis is retrospective. Shared scoring/data/accounting defects require correction in every affected track. Human absence/concerns affect only the human decision, except where they reveal a shared validity defect.

The historical 0.10 kit retains its old human gate. The authorized $0-API offline policy update is now complete under frozen revision 0.12, closed in 0.13; see PHASE2_POLICY_UPDATE_REPORT.md. The `phase2-policy` command separates benchmark and human decisions, imports late supplements, checks declared continuation compatibility and binds a refreshed source/study identity. All 203 project tests pass and the saved-output public demonstration preserves original execution/native evidence. This does not authorize live work. Preserve both kits and the 9ef4024 closure.

### Phase 0: authorized offline implementation slice

The usable deliverable is an offline command-line integration kit. Minimum proof: native Harness²'s deterministic fixture works; an external benchmark adapter passes a representative task/output fixture through the actual native scheduler; strategy materialization is inspectable; stored artifacts can receive two compatible offline assessments without generation; malformed/incompatible inputs and missing evidence are explicit. Verify native utility arithmetic with frozen partitions/scores. P0-1 through P0-8 in the phase definition specify the required evidence.

Record the exact source file/revision of executed Harness² code. Check identities, resume behavior, leakage boundaries, native evaluation import/export, and failures. Phase 0 proves offline orchestration/artifact boundaries, not real agent/provider behavior, live judge validity or billing enforcement. Before paid expansion, validate the actual paths under a separately authorized small readiness check. Paid-generation control must cover calls initiated by native executors and strategy helpers; a surrounding CLI limit alone is insufficient.

If the integration requires rewriting upstream recursion, stop and propose a bounded upstream extension. Do not quietly turn this into another inspired implementation.

### Phases 1 and 1A: establish what the measurements support

Phase 1 is closed under its frozen definition. Its custom Sonnet/rubric screen produced a failed reference-agreement result, not a diagnosis of model ability or dataset-wide label quality. Keep its exact outcomes, settings, thresholds and cost unchanged. New observations about low-quality pairs, score interpretation or reasoning usage belong in the new data-readiness report rather than a rewritten old experiment. The old audit is development material for any revised evaluator, not fresh confirmation.

[Phase 1A](PHASE1A_DATA_READINESS_REPORT.md) completed source semantics, integrity and policy reconciliation, fixed inspection without selecting on Sonnet agreement, and exposure/candidate records. The result supports limited published-label development, conditionally supports CrPO measurement reproduction, and does not independently validate human alignment. Some released instructions are generated transformations and exact reward-model training membership is unknown. Optional [Route H](PHASE_DEFINITIONS.md#route-h--a-bounded-independent-human-reference-check-optional) defines one bounded diagnostic with the user's two nominees; a review packet alone adds no human validation.

The Phase 1A session is closed. Do not reopen provenance research indefinitely. Route H is a single eight-pair pass, not a repair loop: no outcome-based resampling, third reader or new rubric round. If readers are unavailable or context remains unresolved, preserve the limitation and proceed to defining the native-scored core comparison. Frontier evaluator/reasoning selection and measurement-only CrPO reproduction remain deferred. Exact source assets are preferred if later activated; model-card similarity does not establish equivalent measurements. No route automatically starts.

### Priority decision after Phase 1A: cap the CrPO detour

**Recommendation:** retain CrPO's measurement ideas, but pause further implementation and evaluator tournaments now. Its broader dimensions remain relevant to the research question; resolving an entire supplementary measurement stack is not required before observing a base-model/fixed-strategy comparison. The [paper](https://arxiv.org/html/2505.14442v2) motivates several creativity dimensions, but does not establish that our proposed harness comparison depends on reproducing its training setup. This sequencing choice is a project judgment, not a result claimed by the paper.

The current [asset and source review](PHASE1A_DATA_READINESS_REPORT.md#crpo-measurements-identified-not-executed) identifies genuine extra work: gated model bases, unknown reward-training membership, code-versus-formula fidelity choices, and unproved transfer from these Metaphors judgments to future generated portfolios. More work on those questions would not by itself verify the project's live generator, native benchmark judges or actual Harness² adaptation. Route H is worth one small pass because the user can provide readers, but it cannot settle those other questions and must not become a critical-path prerequisite.

**Now:** [P2-R is complete](PHASE2B_EXECUTION_KIT_REPORT.md) under frozen 0.18, closed in 0.19. After applicable operator inputs and a first-stage grant, execute/review the counted Phase 2B block, then explicitly authorize cumulative expansion using the already-built software. No additional planned engineering checkpoint sits between those steps. Keep human input optional, CrPO deferred and all historical evidence immutable.

**Reopen one CrPO-related slice only after** a usable native-scored core pilot identifies a decision-relevant gap, for example whether a native-utility gain corresponds to useful variety or merely stranger answers. Name the decision, choose one criterion, establish its applicability/reference and minimum independent check, and freeze its inputs, expected information and effort/dollar cap. A clearly defined earlier blocker may justify a separate proposed slice, but cannot silently expand current scope. No full CrPO reproduction, reward-model deployment, frontier tournament, model training or Bayesian-surprise implementation follows merely from Route H agreement or disagreement.

### Phases 2 and 3: isolate the useful comparison

Phase 2's [concrete definition](PHASE_DEFINITIONS.md#phase-2--a-usable-fixed-strategy-baseline-tool) preserves the 12 selected curated development prompts, Sonnet 5.5 generation profile, ordinary/planner/permutation arms, native v1.1 roles and first-two-prompt optional human sample. Revision 0.12 changes prospective completion/selection: complete native evidence can select a benchmark seed without readers; a separate later human-augmented decision may retain or change it. The offline update and refreshed r012 identity are complete; resolve the remaining live prerequisites before any calls. Curated material remains development-only, CrPO is not activated and Route H need not run.

The nominal workload is 528 Sonnet requests, 72 Luna grouping requests and 72–720 Opus quality-head requests: **672–1,320 model calls**, not 72 judge calls. Explicitly request the README's grouping model rather than the CLI's different default. Native Opus quality uses high adaptive effort and 16k output tokens. Control every dispatch through the accounted boundary; no hidden SDK retries, fallback judge, lenient repair or cross-order score-cache optimization. Keep native prompts/call construction/strict folding/arithmetic unchanged and record the declared operational profile.

The retained historical cost sheet in the definition gives scenarios of about **$21.68–$106.36** and a proposed **$125 API stop limit**, with an included **$5 first-check sublimit**. All admitted maxima could total about $364.33; the first check's maximum is about $15.18. These figures require live-readiness recosting, including grouping writes; they are not current certified reservations. Either cap may stop its slice incomplete, so neither is a completion guarantee. The first preselected prompt/repeat supplies a counted composed live check before expansion; no favorable quality outcome is required. If spending, access, coverage or accounting prevents completion, preserve the usable kit and an explicit limited report rather than silently changing the metric or expanding the budget.

Raw sampling means ten independent responses under the pinned generation protocol. Fixed procedures declare every extra call, including planning and ranking. Keep the generator unchanged within a comparison. Reranking reuses the same texts but receives native evaluation in the new order; fixed-partition estimates are diagnostics only.

"Fixed" means the procedure is frozen: it may still plan, critique, revise, rank, or evolve outputs. Harness adaptation changes the effective procedure itself. Start adaptation from the same fixed strategy it is being compared against, and give both access to the same declared techniques and source material. A real proposer must inspect execution evidence and be able to keep, edit, combine, or reject available techniques. A changed file alone is not proof of improvement; preserve effective harnesses, trajectories, outputs, and failures.

The original planner is a named strategy candidate, not an effectiveness assumption. Port its intended behavior without importing the old scheduler, scoring or cache. Claude's reranking is a separate strategy transformation; cache/scoring corrections are correctness requirements, not experimental strategy arms. Human steering is a separate condition with its effort and information access recorded. MuCE calibration assesses an evaluator; using that evaluator to guide strategy search defines a separate supervised method.

`k=1` is one authentic upstream Propose-Probe-Compose step, chosen to limit scope. Phase 3B uses native sequential `k=2` to test a second round that starts from the earlier composed harness and accumulated evidence. Parallel `k=2` explores breadth and does not substitute for successive rounds. Preserve both rounds and native final selection; do not force the last candidate to win. An internal first round from `k=2` is not interchangeable with a cached standalone `k=1` run. [Native recursion modes](https://github.com/google-research/harness2/blob/main/harness2/core/recursion.py).

The matched fixed control estimates the value of the complete sequential adaptation policy; isolating depth from equally broad adaptive search requires a separate comparison. Improvement is the hypothesis, not a guaranteed outcome. If cost or integration limits stop the project before 3B, report repeated recursive improvement as untested. A negative one-step pilot alone does not establish that successive refinement cannot help.

Initially disable cross-task experience: use upstream's per-task execution without a mutable shared library. This isolates task-level adaptation and avoids an accidental order-dependent study. Development-trained libraries may be evaluated later as frozen starting artifacts. [Upstream task driver](https://github.com/google-research/harness2/blob/main/harness2/core/schedule.py).

A pilot succeeds by producing a valid comparison, even if the fixed strategy wins. Infrastructure failure, inferior quality, excessive cost, and inconclusive evidence are reportable outcomes. Do not automatically add operators or increase depth until something wins.

### Phase 4: honest confirmation

Use fresh eligible prompts after checking overlap with development and known legacy runs. Public availability means experimenter-held-out, not guaranteed absence from model pretraining. A new task source can supplement unused NoveltyBench material; report sources separately instead of pooling incompatible metrics.

Freeze the two generators and all other model roles. Holding proposer/selector/critic roles constant across generators measures generator-by-method effects; changing them creates a different complete-system comparison. Freeze strategies, adapter/evaluator revisions, permitted within-task adaptation, and libraries before opening confirmation inputs. External scores never enter the score-blind arm.

Primary contrast: adaptation versus the selected fixed procedure under comparable inference-budget envelopes and the same declared technique access. Freeze a policy allowing the fixed procedure extra candidate generation and blind selection; include selection cost, and keep final external judgments unavailable to both methods. This retains three main arms rather than adding a fourth. Ordinary sampling establishes the base-model contribution. Primary native outcome: utility, with distinctness, quality/validity, cost, latency and coverage reported separately. Any separately activated MuCE-style creativity measurements are supplementary and diagnostic unless their applicability/validation is established. They are not required for the native comparison, do not replace native NoveltyBench criteria and do not supply ground-truth labels for new outputs.

Before confirmation, set a minimum worthwhile gain, maximum acceptable quality loss, and cost ceiling using development evidence and intended use. Use pilot variability to decide whether the proposed 40 prompts can resolve that gain. If the required size exceeds the ceiling, narrow the claim or stop; do not launch an underpowered study labelled confirmatory.

The proposed confirmation matrix alone is 480 delivered portfolios, or 4,800 responses, before adaptation probes, discarded fixed-control candidates, judges or human review. It is a later planning envelope, not the next work commitment. Revisit its size after the small pilots; do not implement the entire matrix in advance.

Use paired prompt-level effects and uncertainty; repeated answers and seeds do not create independent tasks. Include failures and assessment coverage with explicit denominators. If activating human review, blind a fixed sample of new outputs without choosing only the highest-scoring cases; its absence never blocks benchmark-specific completion. Name the track/parent and report each model/task family before any pooled summary. An interval that permits both meaningful gain and harm is inconclusive. A revised method after holdout exposure needs fresh confirmation; retrospective rescoring is labelled accordingly.

## 5. Cost and measurement discipline

Maintain separate totals for development, generation/deployment, adaptation/search, and external assessment. Count probes, discarded portfolios, retries, repairs, ranking, selection, and any library-building cost.

Show two views: usefulness at each method's declared budget, and usefulness versus actual total cost. More compute can explain a gain. The central attribution requires a fixed procedure given a comparable total inference budget for extra candidates and blind selection, with its selection cost included. Count all output-producing/search calls, including proposer, probes, composition, selection, repairs and failed calls. Report final external assessment separately and in the total study cost. Match declared resource envelopes and report actual usage/frontiers; do not pad calls to force exact equality or equate call counts with compute. Select the fixed procedure only from the bounded development candidates actually tested, not an imagined globally best strategy.

Before paid work, bind the phase ceiling and conservative call reservations to all executing providers. Bound retries; retain ambiguous/lost-response liabilities until resolved. Stop on unknown accounting or unsupported generation controls. Do not advertise a hard dollar guarantee that provider behavior or timeout ambiguity cannot support. The planning document is not spending authorization.

Retain CrPO-inspired diversity, novelty, surprise and quality as standing secondary measurement dimensions across compatible benchmarks, independently of NoveltyBench's native protocol. Their initial status is diagnostic until the relevant measures are validated; this does not make them disposable benchmark-specific checks. Freeze scorer models, reference populations and normalization. Their proxies need validation; the current implementation's novelty is word-dispersion deviation and its perplexity includes the formatted conversation. Avoid silently porting a formula or treating one composite as universal creativity. Activation of additional scorers needs a separately bounded measurement slice; no new calls are added to the initial phases. [CrPO metrics](https://github.com/mismayil/creative-preference-optimization/blob/main/src/crpo/metrics.py).

### Deferred measurement candidate: Bayesian surprise

Predictive surprisal/perplexity and Bayesian surprise are different constructs. Bayesian surprise measures posterior-to-prior belief change, conventionally `KL(p(theta | x) || p(theta))`, relative to a specified observer and hypothesis space. It is not obtained simply by renaming token surprisal, embedding distance or a critic's numerical rating. [Itti and Baldi, Bayesian Surprise Attracts Human Attention](https://papers.neurips.cc/paper/2822-bayesian-surprise-attracts-human-attention.pdf).

Before adopting it, define the observer, hypotheses, prior, observation, likelihood/update rule and order/reset policy. Distinguish an output revising an observer's beliefs from an experiment revising our beliefs about a strategy's effectiveness. Neither belief change nor predictive improbability alone establishes useful creativity. Validate the chosen operationalization separately; MuCE calibration of a creativity critic does not validate it automatically. Measurement and using surprise to direct search remain separate experiments.

This is a recorded research candidate, not a Phase 0 requirement, new study arm or added experiment. Native benchmark outcomes and CrPO-derived measurements remain separate; no new composite creativity score is specified.

Background: [user-supplied surprise conversation](references/surprise-conversation.md), preserved verbatim from `C:\Users\arvik\Downloads\Use only credible @Academic _ Scientific _ Enginee.md` on 2026-10-24. SHA-256: `CA59390105B0A42913A0DE950C8926D4BD63EA794A7654BC5D8F357ACEB07FD5`. The attachment is a conversation and source lead, not an instruction to implement its proposed architecture or a validated literature review. Only its relevant surprise/LLM-measurement sections were reviewed here; its broader claims and bibliography remain unverified.

## 6. Versioning and upgrades

Each run binds engine/executor/adapter/strategy revisions; task and split content hashes; every effective harness file and prompt; all model roles and requested/returned IDs/settings; evaluator protocol and reference assets; order, seeds where supported, transformations, budgets, and environment identity. Keys and secrets are excluded. Stochastic/provider behavior means exact provenance does not guarantee bit-identical regeneration.

Use immutable run and assessment records. Reranking retains original response identities plus its permutation. Score sets reference output hashes and their own evaluator revision. A new criterion adds assessment records, not edits to the original generation. Explicit registrations and JSON/JSONL files are sufficient initially.

Decision identities additionally bind research track, parent decision, policy revision/hash, input assessment sets and evidence cutoff. A later human assessment is an optional compatible extension, not an edit to the execution manifest or benchmark metrics. Reports distinguish shared prior cost/evidence from new marginal work, and shared outputs are never counted as independent replication.

Upgrade procedure:

1. Stage the candidate upstream revision in a separate environment; retain the previous pin.
2. Run relevant upstream checks and adapter conformance fixtures. Confirm task semantics, strategy materialization, native execution, information isolation, artifact schemas, missingness and identities.
3. Inspect changed defaults/prompts/model controls. Pass explicit protocol parameters; do not equate an upstream CLI default with a published benchmark profile.
4. Run a small budgeted compatibility canary only when separately authorized.
5. Adopt the version in a new study manifest and namespace. Never silently upgrade an interrupted run or pool changed measurements.

"Plug and play" means bounded adapters, declared compatibility and checks. Arbitrary future breaking APIs may require adapter work. New benchmark generation rules can require new generations: rescoring old text does not make it compliant with a protocol under which it was never generated.

## 7. Strategy families and deferred research

The original planner and isolated reranking enter Phase 2. Proposed Lenny-derived procedures and Lluminate operators are additional strategy packages: each can be tested as a frozen procedure and, later, made available as a starting harness or technique for adaptation. Their source does not make their generalization to these tasks an established result. They are optional development slices, not prerequisites for Phase 3.

Keep these as named candidates, not implementation commitments: wider short-intent search and brief refinement; bounded fresh-context critique/revision; subtractive editing; internal SSoT versus external seeds as distinct interventions; Lluminate creativity operators; population summaries; mutation/crossover with quality gates; task-dependent routing from a frozen strategy library.

Add at most one operator family in a development cycle, then isolate its contribution. Full Lluminate-style evolution, multiple simultaneous critics, model retraining, and preference-supervised harness optimization are separate later experiments. [Lluminate operators](https://github.com/joel-simon/lluminate/blob/main/src/creativity_strategies.json), [SSoT study](https://arxiv.org/html/2510.21150v3), [CrPO study](https://arxiv.org/html/2505.14442v2).

Defer a plugin marketplace, hot reload, automatic dependency discovery, a universal benchmark language, dashboards, a custom model gateway, and large benchmark sweeps. A second concrete use case should justify a new abstraction.

## 8. Next checkpoint

Phase 0 is complete under [frozen specification 0.3](specifications/archive/phase-definitions-0.3.md). The [handoff report](PHASE0_REPORT.md) records its offline execution, independent assessments, provenance/failure checks and live limitations. Its saved artifacts remain bound to those original inputs; the planning refresh does not rebind or replay them.

Phases 1 and 1A are complete. Optional Route H is now [defined](PHASE_DEFINITIONS.md#route-h--a-bounded-independent-human-reference-check-optional): two user-nominated eligible humans, eight pairs/16 one-pass judgments, fixed substantive rubric, reader blinding and a descriptive case report. Names/eligibility and volunteer arrangements are bound before collection; no recruitment, human ratings or model calls have begun. Do not tune the consumed audit or start a frontier tournament or CrPO reproduction.

**Phase 2A and the later policy/AM-1 slices remain complete under their frozen definitions.** The full remaining execution work is now [P2-R](PRE_PHASE2B_BLOCK.md), implemented under frozen revision 0.18 and closed in 0.19: provider launcher, whole-pilot controller/one cumulative staged journal, new-release report/replay/optional-human routes and complete offline verification. Its completed offline gate leaves only operator inputs/grants and the counted live first-block/review gates. No paid work is authorized; readers stay optional and CrPO deferred. Later Harness² adaptation still receives its own phase definition and authority.

**AM-1 offline follow-up complete (closure 0.17):** the evidence check passed in 358 seconds and the versioned correction/narrow first-block candidate passed all offline checks. See [report](PHASE2_AM1_REPORT.md). No provider calls, real credentials, Phase 2B experiment or spend occurred. The parent no-go and historical evidence remain preserved.

**P2-R closure 0.19:** complete full-worklist/staged-authority execution kit; 271 project tests and five upstream checks pass; all 1,320 mock requests/72 native assessments replay exactly, with optional late synthetic human supplementation. API spend, provider requests, real credentials and human collection were zero. See [report](PHASE2B_EXECUTION_KIT_REPORT.md) and [operator runbook](PHASE2B_RUNBOOK.md). No later phase is started.
