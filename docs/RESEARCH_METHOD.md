# Research method and interpretation

This page explains the experiment in ordinary language. Exact active settings and acceptance criteria belong in the [current specification](../CURRENT_SPEC.md) and the applicable frozen study definition.

## The contribution we want to measure

A capable base model, a useful fixed procedure and an adaptation mechanism can each improve output. Combining them and reporting one score would not tell us which contribution mattered. The programme therefore separates ordinary generation, fixed strategies and native Harness² adaptation. It starts with small development studies before broader model comparisons or held-out confirmation.

A fixed strategy remains fixed even if it uses several model calls. Planning different angles, generating one answer per angle, ranking answers and selecting a whole portfolio are designed strategies. They are not evidence of learning by themselves.

In the adaptive condition, actual upstream Harness² asks a model to change the permitted strategy instructions. It executes probes, composes changes and selects an output. We retain the initial instructions, proposals, actual diffs, evidence read, selected instructions and rejected candidates. A normal decision to keep the existing strategy is valid; an experiment must not force an edit to look successful.

The current experiment does not train model weights or share learned experience across prompts. Engineering changes to transport, accounting, launchers and evidence validation happen outside the experimental loop, before the study is frozen.

## What two-round refinement means here

Pinned Harness² `seq,k=2` executes two initial reference portfolios. Round one proposes general and task-specific changes, runs their probes and composes checkpoint c1. Round two begins from c1, retaining both references and the native cumulative strategies, diffs, outputs, trajectories and author notes. It produces checkpoint c2. Native selection chooses between the completed c1/c2 outputs without external scores.

The first checkpoint inside this route is not a reused standalone one-step experiment: it has two references and round-aware instructions. A later checkpoint can improve because of changed instructions, a fresh sample or selection. Its score difference alone does not isolate a causal effect of edits or recursion depth.

The fixed Phase 3B control generates twelve fresh portfolios and selects one unchanged portfolio. Native search has eight solver rollouts plus authoring and selection sessions. This preserves the earlier control's sampling advantage while applying the same per-arm resource ceilings. Actual cost and compute can still differ substantially.

## Assessment stays outside search

NoveltyBench supplies the first native assessment protocol. Its grouping and quality judges assess delivered answers; native benchmark code folds these into distinctness and utility measures. Utility rewards useful answers across an ordered portfolio while accounting for duplication and the protocol's continuation weighting. These are protocol-specific, model-based measurements.

We seal both arms' choices before assessing a prompt. The proposer, composer and selectors do not receive benchmark scores, grouping, judge reasoning or assessment paths. Both c1 and c2 are assessed retrospectively. The selected native output references its checkpoint's existing assessment; it is not judged again or counted as another independent observation.

Phase 3B has four paired prompt units, eight delivered outputs and twelve candidate assessment targets. The primary descriptive comparison is selected-native minus selected-fixed utility. Checkpoint and selection differences are secondary diagnostics. Missing required targets remain missing and prevent full phase completion; we do not manufacture a winner from a convenient subset.

## Development evidence and confirmation

These four prompts have already been exposed during development. Their upstream dataset names do not make them held out for this project. Four chosen prompts do not support population-level, cross-model or human-preference claims.

The completed one-step pilot favoured the fixed control. That result is preserved, including unequal realized spending. It motivates a bounded successive-refinement test, not an automatic claim of improvement or a required positive result.

Confirmation is a later phase. It needs a frozen method and analysis, an adequate sample/precision justification, overlap checks and genuinely unopened experimenter-held-out material. The old large-matrix planning envelope is not an automatic next run.

Human assessments can be attached later as separately versioned evidence. They do not rewrite the benchmark outputs or closed decisions. A method changed using later human feedback needs fresh material for a confirmatory claim.

CrPO/MuCE, Lluminate-style exploration, design-workflow strategies, Bayesian surprise, other benchmarks and broader model coverage remain possible extensions. Each needs its own concrete scope and usable output. The failed small MuCE evaluator screen does not validate that evaluator for new generated portfolios, or by itself establish that its model, rubric or dataset was the sole problem.

## Reliability, cost and reproducibility

The experiment layer records effective requests and model IDs, strategy/input hashes, physical SDK invocations, usage categories, failures and discarded work. Reservations are conservative next-call liabilities, not guaranteed spending. Global, cell, assessment, first-prompt, token, request and deadline limits all apply together. Unknown delivery retains its liability and stops outbound admission without resend.

Mocks test mechanics with fake provider responses in a network-disabled environment. They cannot establish live model adherence, provider availability or scientific effectiveness. Independent acceptance, actual operational rehearsal, complete artifact preservation and saved zero-call replay precede a live launch.

Inspect is a separate passive projection of saved evidence. Canonical native outputs, provider execution and spending stay on the controlled path. Viewer limitations and failed exports remain explicit; a display repair cannot retroactively change a failed timed checkpoint or a scientific result.

See the [Phase 3B definition](../PHASE3B_DEFINITION.md) for exact models, allowances, completion requirements, exclusions and stop rules, and the [attribution inventory](ATTRIBUTIONS.md) for upstream components and related research.
