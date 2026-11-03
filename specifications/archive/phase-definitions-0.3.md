# Buddha2 phase definitions

Revision: 0.3 — 2026-10-24, America/Los_Angeles  
Status: Phase 0 execution specification; current progress/completion is recorded in README.md and the completion report; later phases unstarted  
Authority: the user requested Complete Phase 0, then asked to refresh the spec and keep the original folder untouched. Only Phase 0's offline implementation is authorized; no model/provider calls or later phases are authorized.

The [experiment plan](EXPERIMENT_PLAN.md) gives the research rationale. This document specifies the work products and completion gates. The refreshed [implementation decisions](DECISIONS.md) resolve Phase 0's source pins, Linux environment, folder protection, minimal implementation shape and fixture boundaries. Phases 1–4 are provisional definitions to refine using earlier evidence.

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

## Phase 1 — A usable, audited creativity evaluator

**Objective:** determine whether one declared critic is reliable enough for its proposed supplementary creativity assessment, with a bounded human-label calibration exercise.

**Usable output:** a callable versioned evaluator package/rubric and an audit report stating where it may be used. If it fails, retain a diagnostic-only package and a documented fallback to native assessment plus blinded human review. Neither outcome is a universal creativity meter.

**Build/do:** select 24 distinct eligible MuCE prompts, grouped by normalized prompt and compatible rating definition. Allocate 12 calibration and 12 locked audit prompts; use one declared-margin human preference pair per prompt, each shown in both orders: 48 planned presentations. Permit at most one rubric revision using calibration observations; freeze before opening audit labels. Count any added calls/retries explicitly rather than silently exceeding the envelope.

**Stays out:** optimizing generators/harnesses using this critic; validating all CrPO metrics or Bayesian surprise; model training; additional critics; generating new benchmark portfolios; broad task-generalization claims.

**Done:** every planned presentation has an explicit status; preserve prompt separation, rubric versions, audit access timing and cost. Report prompt-weighted human agreement, order consistency, refusals, length/family diagnostics and uncertainty. Apply the frozen acceptance decision. The existing 75% agreement and 90% consistency floors are provisional operational targets, not scientific standards; finalize their exact denominators/failure treatment before calls. A failed audit closes this phase with a diagnostic limitation, not a validated evaluator claim.

Acceptance uses only the 12 locked audit prompts under the final frozen critic, never pooled calibration data or rubric versions. A revision based on the first 24 calibration presentations followed by 24 audit presentations fits the 48-presentation envelope. Repeating calibration requires additional explicitly budgeted calls.

**Refresh before start:** exact MuCE revision/IDs and pair margins, critic/provider, rubric, applicability, acceptance calculations, maximum attempts, dollar cap and human-review availability.

## Phase 2 — A usable fixed-strategy baseline tool

**Objective:** isolate the contribution of the original planner and of answer ordering with one generator, before testing harness adaptation.

**Usable output:** working ordinary-sampling and planner strategy packages, an isolated reranking transformation, immutable generated portfolios, and a paired report. A researcher can rerun a declared condition or apply compatible assessments to saved outputs. The report identifies the fixed procedure chosen for the next comparison or recommends stopping.

**Build/do:** 12 development prompts, two independent repeats, two generating conditions: 48 generated portfolios of ten responses. Rerank the 24 planner portfolios, creating 24 recorded permutations without replacing response texts. Use pinned native NoveltyBench evaluation on each new order; fixed-partition estimates are labeled diagnostics. Record every planning/ranking/assessment call and failure. Add only supplementary scorers explicitly activated in the phase definition; retain the other CrPO dimensions in the measurement backlog.

**Stays out:** Harness² efficacy claims, a second generator, a strategy tournament, a full Lenny/Lluminate library, cross-task memory, confirmation material, or a new benchmark. Do not automatically search more strategies when results disappoint.

**Done:** all planned portfolios/permutations have statuses and traceable identities; the generator/protocol is held constant; assessments and costs are complete or transparently missing. The report separates planner effects from reranking effects and declares the selected fixed procedure without asserting that it is globally best. Negative results are valid. An invalid scoring/accounting path requires correction before claiming a valid comparison.

**Refresh before start:** development prompt IDs/families, generator and ranking roles, exact planner/reranker prompts, native scoring profile, human-check sample, supplementary scorer coverage, attempt/spending caps and reporting rules. If an extra strategy family is warranted, define it as a separate bounded development slice.

## Phase 3A — A usable native one-step adaptation tool

**Objective:** establish authentic task-level Harness² adaptation from the selected fixed procedure, and measure its observed quality/cost before deciding on confirmation.

**Usable output:** a working native adaptation route, inspectable starting/proposed/composed/selected harnesses and traces, and a comparison against the frozen fixed procedure. The fixed and adaptive routes remain usable even if adaptation loses.

**Build/do:** one generator and declared technique set, the 12 development prompts with two repeats: 24 native parallel `k=1` task adaptations. Use an actual model-backed proposer in the upstream scheduler; disable shared cross-task experience. Preserve all probes, selections, rejected candidates, accounting and failures. A proposer choosing to keep the initial harness is a valid recorded outcome; changing a file is not a success criterion.

**Stays out:** deeper recursion, mode comparisons, online libraries, preference-supervised search, extra strategy families, a second generator or claims that an unmatched comparison isolates adaptation from additional compute.

**Done:** every task adaptation has a classified outcome, trace and accounted costs; evidence establishes actual native/model-backed execution and the declared information boundary. Compare native utility, quality, coverage and cost with the selected fixed baseline. Document the proposed fixed-control budget policy for confirmation. Negative or inconclusive outcomes are legitimate; infrastructure failure remains a distinct limitation. This phase supports one-step claims only.

**Refresh before start:** frozen seed strategy/source access, all model roles, exact native mode/budgets, per-task and phase ceilings, maximum attempts, failure criteria, human-check plan and the rule for proceeding or stopping. If making budget-controlled attribution in this phase, explicitly define and fund that fixed control first; it is not silently added to the 24 adaptations.

## Phase 3B — A usable successive-refinement tool

**Objective:** test Harness²'s repeated improvement mechanism explicitly: can a later native round refine an earlier composed harness into a more useful procedure under a comparable total inference budget?

**Usable output:** a native two-round sequential route, inspectable per-round harnesses/trajectories and final selection, plus a bounded comparison against a frozen budget-comparable procedure. It remains a reusable tool even if the extra round does not help.

**Build/do:** provisional envelope of four development prompts, one repeat: four native sequential `k=2` adaptations and four comparable-budget fixed-control outputs. Start from the same declared strategy and technique access. Record the second round's use of the earlier harness/evidence, all base executions/probes/editor/composer/selector calls, discarded results and costs. Preserve native choice among round outputs; do not require adoption of the latest candidate. Score only after decisions, with no shared cross-task library. A first round inside `k=2` is not a reusable standalone `k=1` result.

**Stays out:** a broad depth sweep, more generators, changing the external objective, model training, online memory, or a claim that sequential depth beats equally budgeted parallel adaptation. This small pilot cannot establish a population-level improvement claim.

**Done:** actual successive native execution is evidenced, all planned outcomes/costs are classified, and the fixed comparison respects technique access and the frozen budget policy. Report whether observed later refinement helps, hurts, is retained/rejected, or is inconclusive. Recommend a method/depth and precision requirements for confirmation. Unchanged proposals and rejection of the later candidate remain valid outcomes. Failure to complete execution leaves the recursive-improvement question unanswered.

**Refresh before start:** review 3A's integration and actual call costs; freeze the four eligible prompts, role models, starting procedure, native sequential settings, fixed-control budget policy, assessment coverage and attempt/spending ceilings. This is an explicit planned milestone, not automatic authorization. A negative one-step result does not by itself rule out repeated refinement. If the project stops before this phase, record successive improvement as untested.

## Phase 4 — A usable held-out comparison and decision

**Objective:** estimate the incremental benefit of the selected adaptation method under comparable inference budgets, and assess whether it is worth using for the declared models/population.

**Usable output:** a reproducible held-out report, frozen method packages, versioned outputs/assessments and an explicit recommendation to use adaptation, retain the fixed procedure, narrow the claim or gather more evidence. An inconclusive answer is a usable decision artifact, not a win.

**Build/do:** provisionally two generators and three methods: ordinary sampling, a frozen fixed procedure allowed extra generation/blind selection under a comparable budget policy, and native adaptation from the same procedure with the same declared techniques. The planning envelope is 40 fresh prompts and two repeats: 480 delivered portfolios/4,800 answers before probes, discarded candidates and assessment. Determine actual size from pilot variability, worthwhile-effect thresholds and the ceiling before opening holdout inputs. Freeze trained libraries if any; no cross-held-out-task learning.

**Stays out:** adjusting methods/evaluators after observing confirmation results; forcing this sample size without a precision/budget justification; new operators/models/benchmarks; claims about populations, recursion depths or efficiency outside the frozen design. Do not add a fourth main arm merely to handle compute matching.

**Done:** verify development/legacy overlap exclusions; account for all planned independent prompts, repeated portfolios, failures and liabilities. Report paired prompt-level effects/uncertainty, native utility, quality/validity, coverage, actual total inference costs and separate assessment costs. Report model/family results with appropriately limited claims, plus activated secondary measurements and blinded human review. Apply the predeclared decision rule, including meaningful gain, acceptable quality loss and cost. Preserve the held-out analysis and limitations regardless of outcome.

**Refresh before start:** exact held-out population/IDs, both generators and all other roles, fixed/adaptive definitions and budget policy, precision calculation, primary contrast, thresholds, multiplicity/secondary-outcome treatment, human sample, missingness policy and total cap. If precision cannot be achieved within the ceiling, revise scope before launch or do not launch; do not relabel an underpowered run as confirmatory.

## Later phases

NoveltyBench is only the first task protocol. Other benchmarks can supply tasks and native assessments through separate adapters; compatible criteria can assess saved artifacts. A new task protocol may require new generations, not just rescoring old text.

No omnibus extension phase is authorized or specified. A second benchmark, new strategy family, CrPO scorer activation, Bayesian-surprise operationalization, depth beyond Phase 3B or online memory each needs its own definition using this same structure. State the one question and usable output first, then bound the work. Earlier artifacts remain usable independently of whether that extension proceeds.

## Revision record

- **0.1:** initial phased proposal; no implementation or scientific observations.
- **0.2:** user authorized Phase 0 and requested a refresh. Verified Docker availability and canonical folder separation; fixed upstream/image references and the offline implementation shape in DECISIONS.md. Original scope and P0-1 through P0-8 remain intact. No acceptance threshold was changed to accommodate execution results; implementation and acceptance execution have not yet occurred.
- **0.3:** offline implementation began. Dependency auditing identified vulnerable initial Transformers/Torch versions; update the runtime pins and require fresh native regression/audit evidence. Preserve the initial findings. Source commits, fixture protocol, scientific scope and all acceptance checks remain unchanged.
