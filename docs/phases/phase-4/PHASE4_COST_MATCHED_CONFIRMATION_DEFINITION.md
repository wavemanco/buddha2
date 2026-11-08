# Phase 4: cost-matched held-out confirmation

**P4-CM1, definition 1.0 — 7 November 2026. PROPOSED; documentation only.**

This defines one bounded study, including its necessary development qualification, execution and closure. It authorizes no implementation, tests, credentials, prompt inspection or provider calls. The budget below is a fresh proposal, not a continuation of unused Phase 3B funding. The [closed development report](../phase-3b/PHASE3B_REMAINING_PAIRS_LIVE_REPORT_V2.md) remains unchanged.

## 1. Objective and claim

On **24 previously unexposed prompt units**, estimate whether actual native Harness² `seq,k=2` produces better NoveltyBench utility than a fixed strategy given approximately the same **realized inference spending**. Report distinctness alongside utility and test whether the conclusion depends on the grouping judge's partition.

The concrete question is: with the same C-N planning, answering and ranking techniques and role models, does native adaptation beat spending a comparable amount on fresh fixed-strategy candidates and blind selection?

This compares two complete procedures. It does not isolate recursion from every other difference, prove that a second round causes improvement, or establish general creativity. The fixed control's budget is derived from native spending on the same prompt, so native must run first; this ordering and cost dependence are limitations, not randomized causal controls. Dollar matching is not token, latency or FLOP matching.

## 2. Scope: one configuration, two arms

Use the existing unchanged engine and benchmark pins: Harness² `1cfe254e8d25b15f37048c3730134686abe60335`; NoveltyBench v1.1 `64a23be6b18ec1dacc298830aab276061b6e143c`. Start every task independently from frozen C-N procedure `16cd0c8b829c7147b51ff76bd38a350686ca1b3bf53e308cc4b76acbf0747de0`. No learning carries between prompts.

| Component | Frozen proposed setting |
|---|---|
| Adaptive arm | Actual upstream `seq,k=2`, two references, eight solver portfolios, six author/composition stages, c1 carried into round two, native blind selection between c1/c2. Existing 24-request conversation allowance; maximum 408 provider admissions per cell. Normal KEEP is valid. |
| Fixed arm | **Hierarchical fixed search**, specified below: at most eight independent pools of twelve fresh C-N portfolios, each with one blind selector, then at most one blind selector over pool winners. No instruction adaptation, response mixing or rewriting. |
| Planning, answers, ranking | `claude-sonnet-5-5`, adaptive thinking, low effort, max output 4,096; existing global/standard-only controls. |
| Authors, composers, all selectors | `claude-opus-5`, adaptive thinking, high effort, max output 16,000; existing global/standard-only controls. |
| Primary grouping | Upstream `gpt-5.6-luna` Chat/schema request, preserving native omissions of effort, output cap, tier and geography. |
| Primary quality | Upstream `claude-opus-5`, adaptive/high, max output 16,000, native tier/geography omissions; no fallback judge. |
| Delivered portfolio / assessment | Ten answers, original delivered order, native patience 0.8; one generation replicate, no fixed provider sampling seed, no automatic retries. |

Freeze effective model IDs, requests, native prompts, runtime/dependency pins and prices before launch. A model's withdrawal or material protocol change requires review, not silent substitution. This is a benchmark-specific subset study, not a leaderboard submission.

The new fixed arm is **not** the old single best-of-twelve or a single best-of-96 judgment. Increasing its resources is a declared strategy revision, required because the pilot's adaptive inference cost approximately 6.30 times its fixed control. It gives fixed instructions additional search, while adaptation uses that budget for proposals and probes.

## 3. Prospective cost-matching rule

For each confirmation prompt:

1. Run and seal native adaptation. Let **T** be its settled API inference bill, including both references, all probes, authors/composers, ranking, selection and discarded work. No benchmark assessment contributes to T. An incomplete/uncertain native cell cannot supply a matching target.
2. Start fresh fixed pools in a prespecified ordinal order. Each pool generates twelve complete portfolios and selects one unchanged whole portfolio using the existing C-N/selection procedure. Every completed candidate participates; no candidate is dropped after looking at a score.
3. After each complete pool, compare its cumulative settled generation-plus-pool-selection bill **S** with **0.90 × T**. Stop adding pools at the first boundary with S at or above that threshold, or after eight pools, whichever comes first. The 90% threshold leaves room for final selection and pool granularity; it is not a prediction of the next bill. No partial ninth pool, padding, dummy request or cost-based post-hoc rerun is allowed.
4. With two or more pools, make exactly one blind selection over all pool winners, retaining a winner unchanged. With one pool, retain its winner without another call. Add final selection to the fixed inference bill **F**. All completed and failed paid work counts, including any overshoot.

If any required fixed candidate, pool selector or final selector fails, classify that fixed cell incomplete. Preserve its completed candidates and spending; do not select from eleven candidates, silently retain an earlier pool winner, add a replacement pool or restart the cell. Continue other independent safe prompts within their limits. An incomplete native cell similarly has no eligible final result or cost-matching target; do not invent a partner budget. Report completion/refusal/failure rates for both procedures alongside scores.

The budget coordinator receives only settled accounting, task/slot identities and completion status. It does not pass native answers, learned instructions, scores or partitions to the fixed arm. Both arms receive the same original task and fixed starting toolkit. Seal both choices before any external grading; complete generation for all 24 prompts before releasing benchmark results for analysis.

**Matching qualification, not a runtime gate:** call the complete study approximately cost-matched only if aggregate F / aggregate T is within **[0.90, 1.10]**, and at least **20 of 24** individual F/T ratios are within **[0.80, 1.20]**. Report all 24 ratios beside their utility/distinctness differences, the eight-pool ceiling hits and both arm totals. Never select a matching subset or remove expensive/loss cases. Explicitly qualify a positive mean concentrated in mismatched cases; these thresholds do not make every pair cost-matched. A miss completes a resource-comparison study but cannot support the equal-cost benefit claim; it does not trigger a paid repeat. Matching uses usage-accounted price estimates, not a claim of provider-invoice equality.

Pool boundaries can overshoot. The rule cannot guarantee either exact parity or completion within a financial cap. The actual ratio, not shared ceilings, determines whether matching was achieved.

Retain the existing declared cache policy and fresh task/pool sessions; no synthetic warming, deliberate delay to expire caches, or reuse of another arm's generated answers. Record input, cache-write/read, output, rate/tier and model categories. Native-first execution can affect cache reuse. Report a **cache-neutral diagnostic** repricing all input categories at the same frozen ordinary uncached input rate, plus output at its ordinary rate; do not use it to change T, F or the primary matching decision. Report tokens and wall time separately. Engineering, local compute and subscription costs are outside API inference matching and must be labelled as unmeasured or separately accounted.

## 4. Held-out population and selection

**Target frame:** the pinned NoveltyBench WildChat-1k source, after a project-wide exposure/overlap audit. Eligibility is not established today. All 100 curated prompts have already been inspected as development material; none qualifies as fresh confirmation. See the recorded [Phase 2 eligibility audit](../../../src/buddha2/phase2.py) and [upstream locks](../../../upstreams.lock.json).

Before sampling, inventory all available prior task IDs, prompt hashes, inspected sources and study manifests, including documented exposure outside the four-prompt pilot. Do not treat the Phase 1 ledger alone as complete. Exclude known exposed rows, all normalized prompt matches to development inputs/curated prompts, and duplicate prompt units. Normalize for matching with Unicode NFKC, case folding and whitespace collapse while preserving original task bytes for execution. Collapse exact normalized duplicates within the frame to one unit, represented by the lexically smallest source ID. Record that this does not prove semantic non-overlap or absence from model pretraining. Unresolved known exposure or gaps in prior-exposure records prevent certifying affected units/the frame; merely exhausting the available records cannot silently establish project-wide freshness. Resolve the gap or report inability to certify.

Machine-only integrity/overlap processing is permitted during future intake, with content hidden from method development. Do not analyst-browse the remaining corpus to choose interesting tasks. Use the pinned text-task population without new language, topic, difficulty, expected-quality or safety-success filters. Provider refusals and difficult tasks are outcomes, not eligibility failures.

Freeze method/analysis/source/pricing and the eligibility manifest before selecting/opening task contents. Rank eligible source IDs by SHA-256 of UTF-8 `P4-CM1-v1|` followed by the exact source ID, with lexical ID tie-break; take the first 24. Treat the hash order as deterministic pseudorandom sampling without replacement. This fixed seed cannot be searched for favorable examples. Eligibility must not depend on model outcomes. Publish counts, exclusions, source hashes and the selected manifest; no selected prompt has yet been inspected for this definition.

At least 24 certifiably eligible units are required. No sampled task is replaced after it is opened, fails, refuses or receives a score. A later discovered exposure invalidates that unit's held-out status and is disclosed without substituting another task. If freshness cannot be established, stop before confirmation and deliver the eligibility/no-go report; a new source requires a revised definition rather than an invented holdout claim.

## 5. One contained preparation and qualification path

Future whole-block approval would cover these steps together; they are not separate infrastructure projects:

1. **Offline implementation/acceptance.** Extend the existing fixed-control/worklist and reporting paths only for bounded pools, cost-only stopping, this sample manifest and the supplemental assessments. Reuse native Harness², controlled provider/accounting, saved-assessment reuse and passive Inspect. In this profile, replace the old first-prompt-assessment progression gate with score-blind generation/provenance review so later generation can precede grading. Use bounded per-prompt journals and existing aggregation: only one child journal admits calls at a time; its grant is bounded by the remaining shared allocation, and its settled spend/holds reconcile before the next opens. No child receives an independent copy of the full study allowance. Do not put approximately 40,000 requests through one repeatedly replayed journal.

   Test the changed path with provider dispatch blocked: legal producer maxima reach consumers; genuine corruption/leakage is rejected; 1/8-pool boundaries, threshold equality/overshoot, per-prompt/global accounting and changed-limit contracts work; settled replay creates zero calls; actual pre-credential Windows launch and coordinated timing pause/Continue work. Cover the declared full task/response envelope, native history, twelve-candidate pool selectors and final winner selectors. The current 5,952-byte plan/answer and 61,952-byte rank guards must not be assumed suitable for WildChat; derive compatible bounds from producer/provider contracts on synthetic/development maxima before freeze. Never truncate or filter selected tasks to hide an integration defect. One mocked native/fixed/assessment/export journey, focused boundary cases and a bounded offline journal-scale check suffice; do not recreate a platform or repeat unrelated historical matrices. Independent review precedes keys.
2. **Exactly two exposed, fixed-only cost qualifications.** Use existing p3b-02 and p3b-04 task bytes and recorded native inference targets **$6.016759** and **$5.402521**. Run the frozen hierarchy rule once for each, with no new native generation, grouping, quality calls or historical artifact changes. They bracket the recorded fixed-pool costs; their benchmark outcomes do not select or tune the rule. Both individual F/T ratios must lie in [0.80, 1.20], and their aggregate ratio in [0.90, 1.10], with complete, reconciled control outputs. This is a small operational feasibility gate, not statistical validation that costs on the new population will match. Their results are development evidence only, never two additional confirmation prompts. A qualification miss closes this proposal as change-required before holdout opening; no automatic calibration repeat or silent method revision.
3. **Freeze and execute once.** If qualification and eligibility pass, bind the exact accepted source, matching procedure, finite worklist, sample/analysis and current prices. Request fresh credentials only after offline acceptance; one entry may cover qualification, the frozen confirmation and review pauses within the approved ceilings. Before the first held-out dispatch, independently verify that qualification did not change method or limits. Run 24 pairs in manifest order, native first within every pair. After pair one, review only execution/provenance/accounting and resource behavior, with no benchmark feedback; valid execution permits the other 23 without another approval or canary. Once every generation cell has a sealed result or terminal failure classification, assess all available valid targets under the primary and supplemental plan, report and close. A missing cell must not globally erase valid unrelated results.

Usable intermediate outputs are an eligibility decision and accepted bounded runner, then a cost-qualification dossier, then sealed portfolios with native results and passive Inspect records. Failure at an earlier gate preserves those outputs and does not spawn another automatic block. No holdout is opened to debug the new control.

## 6. Primary analysis, precision and interpretation

The independent unit is **one prompt**, not an answer, candidate, checkpoint or judge repeat. Equal prompt weights; n = 24; no effect-driven expansion or optional stopping. The primary paired contrast is selected-native minus selected-fixed **utility@10**, computed by pinned upstream code on the official original-order grouping and native head-only quality judgments.

Report the paired mean and a prespecified **two-sided 95% paired-t confidence interval** (23 degrees of freedom), median, wins/losses/ties, range and all task results. This is an approximate prompt-sampling interval, potentially fragile under skew at n=24, conditional on one stochastic execution per task and these judges; it does not separately measure within-prompt run variability. There is no randomized arm assignment to justify a paired-label randomization claim. Report the paired distinct@10 contrast and its corresponding interval as a companion outcome. It cannot be omitted because utility is primary, and it does not establish external originality or surprise.

**Why 24:** this is a deliberately limited first held-out estimate, not a powered cross-model study. The utility interval half-width is approximately **0.422 × the observed paired standard deviation**: SD 1, 2 or 3 would imply about ±0.42, ±0.84 or ±1.27. These are precision scenarios, not variance or power inferred from the four exposed pilot cases. No minimum detectable effect is promised. Report each leave-one-prompt-out mean to show influence without deleting any prompt; do not select whichever analysis is favorable.

Predeclare these result labels:

| Evidence | Conclusion allowed |
|---|---|
| All required valid data; utility interval lower bound above zero; matching qualification passes | Evidence of positive average utility benefit for these procedures on the eligible task frame, at approximately matched API spending. Report distinctness and its uncertainty alongside it. |
| Same, and both supplemental grouping passes retain strictly positive paired means | The observed positive direction is robust to the **two specified** grouping/order perturbations; not proof of judge correctness. A zero supplemental mean is attenuated/non-positive, not robust-positive. |
| Utility interval includes zero, is below zero, matching fails, or grouping changes direction | State the applicable inconclusive, negative, unmatched or partition-sensitive outcome. Do not claim broad adaptation benefit, equivalence, or a successful matched confirmation. |
| Required cells/assessments are unavailable or invalid | Partial study, with all units accounted for. Available-case summaries are explicitly descriptive; no planned full-study positive claim. |

There is no additional practical-significance cutoff disguised as a stopping rule. Report the interval and absolute magnitude for the next scale-up decision; a statistically positive but tiny effect does not by itself justify deployment. Distinctness, checkpoint diagnostics and sensitivity contrasts are secondary, without separate confirmatory hypothesis claims. No choice of method or threshold may be revised using these outcomes.

## 7. Grouping sensitivity and quality coverage

For each prompt, the three assessment targets are fixed, c1 and c2. Selected-native aliases the chosen checkpoint's existing assessment. Neither primary selection nor delivered order changes after grading.

- **Official primary:** one native original-order partition per target; native quality judging of its group heads and unmodified upstream metric folding. Retain this result even when unfavorable.
- **Two supplemental grouping calls per target:** present response indices in (a) reverse order `9,8,7,6,5,4,3,2,1,0` and (b) rotated order `5,6,7,8,9,0,1,2,3,4`, using the same native grouping model/settings. Map membership back to original indices and order groups/heads by their earliest original index. This probes grouping instability under order perturbation, not arbitrary replacement judges or an independent replication of generation.
- **Complete quality once per response:** reuse each official scored-head judgment unchanged. For non-head answers only, request the same native quality judgment separately, giving every target ten observed quality scores. These supplemental scores never replace the official scores or make duplicates count in the official fold. They allow exact alternative-partition folds on the original output order without inventing zero quality for previously unjudged answers. The extra calls are explicitly inside this proposal's assessment scope, not automatic report-filling work.
- **Report separately:** official and both alternative group counts, response-pair same/different membership disagreements, head changes, distinctness and utility; all three selected-native-minus-fixed mean contrasts and their per-prompt changes. Reuse the same complete quality vector across sensitivity folds, retaining judge-score noise as a limitation. Do not vote, average or choose partitions to replace the official primary result. A direction reversal in either supplemental mean earns the partition-sensitive label.

Maximum assessment work is **9 grouping + 30 quality = 39 requests per prompt**, including primary and supplements: **936 requests for 24 prompts**, with no retries. This is not 39 independent observations. All official targets are required for full primary coverage; unavailable supplemental judgments make grouping sensitivity incomplete rather than invalidating otherwise valid official results.

The report must also follow the [project reporting contract](../../RESEARCH_METHOD.md#required-contents-of-every-future-report): full quality distributions/counts, original order and weighting, both checkpoint outcomes, native choices, actual edits/KEEP, sampling, loss cases and separately scoped costs. With all qualities available, report unweighted quality means; use utility-minus-mean only as a descriptive quality/placement residual when all ten groups are distinct. Otherwise report grouping/head effects and do not call that residual a pure order effect. Score judges supply scalar judgments; do not fabricate rationales. Oracle alternative checkpoint scores are diagnostics, not a reselected result or a causal selector test.

## 8. Deliverables and completion criteria

| Deliverable | Completion requirement |
|---|---|
| Frozen study and eligibility dossier | Auditable exposure/exclusion counts, 24-unit manifest, procedure/prompt/model/runtime/price identities, finite slots, predetermined analyses and no unresolved known holdout contamination. |
| Accepted implementation and qualification dossier | Focused offline evidence and independent review; both authorized development controls complete and pass the cost-only qualification before holdout opening. This is future work, not a claim of current readiness. |
| Native study outputs | 24 fixed portfolios, 24 c1 and 24 c2 portfolios, 48 primary aliases; authentic native execution/selection, immutable task/strategy/choice seals, all failures and discarded work accounted. A KEEP does not fail completion. |
| Primary and sensitivity results | All 72 official target assessments, **144 supplemental grouping calls**, giving 216 grouping calls in total; all 720 response-quality scores covered by reused heads plus new non-head judgments. Selected aliases are not rejudged. |
| Scientific report and decision | Both metrics, prespecified intervals, all costs/ratios, influence and grouping panels, quality/order/selection/edits/loss analysis, matched-status decision and limitations; a valid negative/inconclusive result completes the study. |
| Inspect and reproducible closure | Passive saved exports with real timestamps/model/call activity where present; zero-provider-call saved-result replay; independent outcome/accounting review and exact-owner cleanup. Display/replay failures affect delivery status, not preserved scientific scores or permission to regenerate. |

Full scientific completion requires all planned primary and supplemental data, honest classifications and reconciled new spending with no unresolved new delivery liability. If the supplemental portion is incomplete, label **primary comparison complete / grouping sensitivity incomplete** when that is supported; do not overclaim full confirmation or discard the primary comparison. Delivery and claim status are separate from scientific coverage. Closed development reports/journals, earlier assessed pairs and historical holds stay unchanged and are never included as held-out observations.

## 9. Proposed budget, counts and practical time

**Fresh proposed API ceiling: $1,200**, not guaranteed spend or current authorization. Nested allocations are **$100 development qualification**, **$850 confirmation inference**, and **$250 assessment**; at most **$75 per inference cell**, inside its applicable allocation. Allocations cannot be silently borrowed or supplemented with old unused funding. Conservative next-request reservations and settled spend plus unresolved liability must fit both the applicable nested limit and total. No automatic retry budget exists.

Planning from the three new pilot prompts gives approximately **$5.50 native inference per prompt**; a matching fixed arm implies roughly **$264 for 24 paired inference units before pool overshoot**. Allow roughly **$300–$600 total** for two development controls, matching granularity, primary/supplemental assessment and changed prompt lengths/cache behavior. This is an illustrative usage scenario, not a statistical forecast or a completion guarantee: WildChat has not been inspected for this estimate. Existing observed assessment costs are small, but no old price-per-pair is asserted for the new population. Refresh official public prices and reservations at acceptance; changed terms require a revised worksheet before keys.

The retained maximum next-request reservations are currently $11.44 for Opus, $2.540960 for Sonnet and $1.661880 for grouping, under the [7 November billing record](../../../evidence/phase3b-seq2-v1/remaining-pairs-public-billing-v1.json). They are liabilities, not expected request charges. A target near $6 therefore must not become a $6 hard cell cap. A complete twelve-call Sonnet candidate has a $30.491520 worst-case request envelope, before selection; observed cheap calls cannot promise a tiny overshoot. The $75 financial ceiling supplies room to admit requests but does not force spending or guarantee cell completion.

| Finite maximum | Admissions |
|---|---:|
| One fixed cell: eight pools × (144 generation + 1 selection), plus final selection | 1,161 |
| Two development fixed cells, no external judges | 2,322 |
| One confirmation prompt: native 408 + fixed 1,161 + assessment 39 | 1,608 |
| All 24 confirmation prompts | 38,592 |
| **Whole proposed block, no retries/replacements** | **40,914** |

These are absolute slot maxima, not forecasts or a goal; financial ceilings usually bind first. Reused results are counted once. Verify the actual descriptor/worklist/token and request-size compatibility before freeze rather than transplanting historical task-count limits. Earlier liability is not hidden in this budget; the existing $22.88 hold remains separately disclosed.

Planning allowance: **one focused working day for the small existing-path extension/review**, then **roughly 3–6 elapsed days for serial qualification, generation, assessment and closure**. The old twelve-candidate fixed cell could take about 15 minutes; six to eight pools substantially increase latency despite inexpensive calls. These are scheduling estimates, not measured performance on the new population. At the end of the engineering day, show the usable output, remaining gap and revised estimate instead of starting another framework or silently extending scope. Qualification supplies a measured runtime update before confirmation; prolonged runtime can be reviewed without replacing completed work.

## 10. Exclusions

No base-model/model-reasoning tournament, extra strategy family, more recursion depths, parallel/adaptive mode sweep, cross-prompt memory, training, MuCE/CrPO, Bayesian surprise, required human readers, new benchmark or leaderboard submission. Human evidence can later attach as a versioned supplement without blocking this benchmark decision; method changes informed by it need fresh confirmation material.

No upstream source changes, dependency upgrade, Inspect provider bridge, new dashboard, generic plugin/reliability framework, historical regeneration/regrading, extra canary or automatic fresh repetition. No scoring feedback to search, benchmark-specific tuning on selected prompts, post-judge ranking/length adjustment or cherry-picked partitions. Broader base/fixed/adaptive comparisons remain a later roadmap question; this block answers only the incremental native-versus-funded-fixed question in one configuration. It replaces the older broad Phase 4 matrix as the immediate proposal, not as authority to start another matrix.

## 11. Stop, pause and continuation rules

| Situation | Required behavior |
|---|---|
| Before holdout: known exposure unresolved, fewer than 24 eligible units, failed offline acceptance, qualification miss or unavailable frozen model | Do not open confirmation prompts or start its calls. Deliver the concrete no-go/change-required evidence; no automatic qualification repeat. |
| Funding/reservation unavailable, ambiguous provider delivery, unauthorized slot/model/source, genuine artifact corruption, grader leakage or containment failure | Stop new outbound admissions, preserve settled work and unresolved liability, identify the affected predicate/slot. No resend, closed-journal reopening or automatic whole-pair restart. |
| Clock approaching the existing soft allowance | Use the accepted warning at 480 seconds, soft allowance 600 plus 300 seconds grace and actual Continue/Stop decision, with coordinated outer clocks. Waiting is excluded as already defined. Money and dispatch/cleanup safety bounds remain hard; timing does not create extra calls or funding. |
| Low/negative scores, KEEP, eight-pool limit, cost-band miss, grouping disagreement, normal refusal or a required target failing | Record the scientific/missing outcome and continue independent safe work under the unchanged definition and remaining caps. Do not hide, replace or repeat the case to obtain favorable completion. Required missing data limits the eventual claim. |
| Read-consumption gaps, supported formatting/cache annotation differences, final-chat paraphrase or passive Inspect failure | Diagnostic or delivery issue under the existing semantic/artifact contracts; do not invalidate an authoritative valid output or regenerate it. |
| Unexplained checker exception or new unsupported response | Pause new spending for focused diagnosis; it does not establish tampering. Reuse settled compatible outputs/assessments where identities permit, through separate append-only evidence. No unreviewed source patch or silent changed procedure on opened holdout data. |
| All planned work finished, or the user pauses/stops | Seal the state, reconcile costs/holds, report available primary/sensitivity coverage and next decision. Unused funds and a favorable result do not authorize expansion. |

After closure, the next decision is whether the measured effect, distinctness, uncertainty, grouping stability and cost justify a separately scoped replication or practical integration. A weak or negative result can justify retaining fixed search. Do not automatically tune against this consumed sample, add human work or launch a larger study.
