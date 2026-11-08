# Research method and interpretation

This page explains the experiment in ordinary language. Exact active settings and acceptance criteria belong in the [current specification](research/CURRENT_SPEC.md) and the applicable frozen study definition.

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

## Required contents of every future report

This is the project reporting contract for future study reports, partial-result reports and result summaries. Primary status does not justify omitting measured companion outcomes. Executive summaries must show the primary and companion metric headlines with their populations; detailed diagnostics may be linked to the full report.

1. **Metrics together.** For NoveltyBench, report distinctness and utility side by side, per paired task and in aggregate, with the declared k, patience, native judge/protocol versions and primary versus companion/diagnostic status. State the novelty reference population: within-portfolio distinctness does not establish external originality, surprise or Bayesian surprise. Other benchmarks use their applicable native metrics and analogous dimensions; mark a dimension not applicable or not measured, with a reason, rather than inventing a score.
2. **Scope beside each figure.** Name the model/settings, task/sample unit, number of paired prompts and targets, development or held-out status, and whether a figure covers all prompts, only new work or a subset. Identify reused/imported observations once. Costs must name their population and distinguish inference, assessment, actual spending, caps and unresolved liability.
3. **Per-case and aggregate results.** Include both metrics for every case, wins/losses/ties, central summaries and the prespecified uncertainty analysis when applicable. Show negative cases, missingness, grouping-driven outliers and any labelled post-hoc sensitivity. Preserve the frozen primary endpoint and candidate choices.
4. **Quality separately.** Report observed response-quality or scored-head distributions and their counts where available. Identify unjudged/non-head responses and missing scores. The native utility rule may assign a duplicate zero credit; this is not a measured zero quality score. Do not claim a full-portfolio quality average when only group heads were judged.
5. **Order separately.** State the weighting and original order. Where every response has a quality score and all groups are distinct, an unweighted quality mean and utility-minus-mean residual can describe placement. Label this as descriptive, dependent on the observed score distribution, not an isolated causal ordering effect. With grouping or incomplete quality data, report the limitation or a valid prespecified analysis; do not fabricate a decomposition or replace official ordered outputs.
6. **Selection, edits and sampling separately.** Record the actual score-blind choice, available candidates/checkpoints, their retrospective outcomes, and actual strategy input/output hashes, KEEP decisions and fresh rollouts. Candidate-score comparisons are diagnostics, not a causal selector ablation; selection differences overlap changes in portfolio quality/order. Do not reselect after judging or present fresh sampling/composition reuse as a new learned edit.
7. **Loss analysis and limits.** Describe shared observations in negative cases, relevant counterexamples and whether judges supplied explanatory rationales. Separate those observations from hypotheses about verbosity, constraint fit, quality, ranking or model behavior. Small exposed panels and single judge passes do not establish causal mechanisms or population benefit.
8. **Grouping sensitivity and cost fairness.** Report semantic group counts and their contribution to utility. Predeclare any confirmatory sensitivity analysis; retain the official primary partition/result. Distinguish common allowances from matched realized computation, and report all generation/editor/selector costs. Supplemental judgments require separate scope and authorization rather than automatic spending to fill a report.
9. **Provenance and closure.** Link the frozen study, assessments, accounting and preserved report revisions; name unavailable evidence and incomplete diagnostics. Summarize what was done, what remains unmeasured and the next decision without rewriting closed outcomes.

The author checks this list before publishing a report, and the reviewer checks the same fields. Applicable quality, order and selection panels must be present; a reasoned not-applicable/not-measured panel is valid when the data or benchmark cannot support that analysis. Required native assessment targets still follow the frozen study's completion rules. Supplemental reporting gaps must not become new runtime stops or automatic extra model calls.

This is an authoring/publication requirement, not a claim that the closed Phase 3B formatter has gained a new coded validator. Every future phase definition must carry these requirements into its reporting deliverables and acceptance checks before implementation. Frozen reports remain unchanged; later analysis uses a clearly identified reporting revision.

## Development evidence and confirmation

These four prompts have already been exposed during development. Their upstream dataset names do not make them held out for this project. Four chosen prompts do not support population-level, cross-model or human-preference claims.

The completed one-step pilot favoured the fixed control. The subsequent two-round pilot is also complete: its positive mean is driven by one grouping-sensitive prompt, with two wins/two losses and unequal realized inference costs. The [current two-round report](phases/phase-3b/PHASE3B_REMAINING_PAIRS_LIVE_REPORT_V2.md) records distinctness, utility, loss cases and their limits. Neither result establishes a general adaptation or cost-efficiency benefit.

The [P4-CM1 confirmation definition](phases/phase-4/PHASE4_COST_MATCHED_CONFIRMATION_DEFINITION.md) now proposes 24 eligible, previously unexposed WildChat prompts and one model configuration. All curated prompts are already development-exposed; the new frame still needs certification. Native seq,k=2 runs first, and its settled inference bill sets a cost-only target for up to eight fixed best-of-twelve pools and a blind selection among their winners. This is a declared hierarchical fixed strategy, not an unchanged single best-of-twelve control. Its complete resource-matching rule, tolerance, cache accounting, two exposed development qualifications, sample/precision limits, proposed budget and stop rules are defined before implementation. Native-first cost yoking compares complete procedures; it does not isolate a causal recursion effect.

Utility remains primary, with distinctness reported alongside it and quality/order/selection/edits and loss diagnostics kept separate. Official native partitions remain the primary result. Two frozen grouping-order perturbations per target and separately scoped non-head quality judgments support sensitivity folds without inventing quality or choosing favorable partitions. The proposal keeps every sampled case: cost mismatches, negative scores and grouping disagreement affect interpretation rather than triggering paid restarts. This is documentation only, not an accepted execution kit, budget grant or instruction to open the holdout. Changed methods after opening need fresh confirmation material. The old large-matrix envelope is not an automatic next run.

Human assessments can be attached later as separately versioned evidence. They do not rewrite the benchmark outputs or closed decisions. A method changed using later human feedback needs fresh material for a confirmatory claim.

CrPO/MuCE, Lluminate-style exploration, design-workflow strategies, Bayesian surprise, other benchmarks and broader model coverage remain possible extensions. Each needs its own concrete scope and usable output. The failed small MuCE evaluator screen does not validate that evaluator for new generated portfolios, or by itself establish that its model, rubric or dataset was the sole problem.

## Reliability, cost and reproducibility

The experiment layer records effective requests and model IDs, strategy/input hashes, physical SDK invocations, usage categories, failures and discarded work. Reservations are conservative next-call liabilities, not guaranteed spending. Global, cell, assessment, first-prompt, token, request and deadline limits all apply together. Unknown delivery retains its liability and stops outbound admission without resend.

Mocks test mechanics with fake provider responses in a network-disabled environment. They cannot establish live model adherence, provider availability or scientific effectiveness. Independent acceptance, actual operational rehearsal, complete artifact preservation and saved zero-call replay precede a live launch.

Inspect is a separate passive projection of saved evidence. Canonical native outputs, provider execution and spending stay on the controlled path. Viewer limitations and failed exports remain explicit; a display repair cannot retroactively change a failed timed checkpoint or a scientific result.

See the [Phase 3B definition](phases/phase-3b/PHASE3B_DEFINITION.md) for the closed pilot's settings, the [Phase 4 proposal](phases/phase-4/PHASE4_COST_MATCHED_CONFIRMATION_DEFINITION.md) for the next study's scope, allowances and completion/stop rules, and the [attribution inventory](ATTRIBUTIONS.md) for upstream components and related research.
