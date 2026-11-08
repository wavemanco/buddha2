# Phase 3B: completed four-prompt development pilot - reporting revision 2

Reporting revision 2 - 7 November 2026. This is the current readable report. It adds companion-metric reporting and a descriptive loss analysis from the existing sealed records; no new model calls or experiments were made. The [frozen original report](PHASE3B_REMAINING_PAIRS_LIVE_REPORT.md), SHA256 `1981505da5c209681c054a4a825dacb0dbd8826157f53b653551587bbddac313`, remains unchanged. Its [closure receipt](../../../evidence/phase3b-seq2-v1/remaining-pairs-live-outcome-v1.json) and [consolidated review](../../../evidence/phase3b-seq2-v1/remaining-pairs-live/independent-review.json) attest that original revision, not this later reporting update.

The four-prompt comparison is complete. All planned calls, pair reviews, canonical closure and both passive Inspect exports passed. One zero-call saved-report replay reproduced all eight original report files byte for byte without changing the journal. This revision leaves the frozen primary endpoint, partitions, scores, selections, accounting and provenance unchanged.

## What was compared

This completes the [approved continuation definition 1.1](PHASE3B_REMAINING_PAIRS_CONTINUATION.md): preserve the already assessed first pair and run exactly three new pairs. Each task compares actual pinned Google Harness² `seq,k=2` against the fixed planner-and-generation strategy with twelve fresh candidate portfolios and blind whole-portfolio selection.

The adaptive arm generates eight portfolios, uses six model-backed author/composition stages, carries c1 into round two, and selects c1 or c2 without benchmark scores. Each new task starts from the same frozen seed strategy; earlier task scores and strategy changes are not carried forward. Ordered outputs are assessed using the pinned native NoveltyBench protocol after selection. These are four exposed development prompts.

## Results

The frozen primary comparison is selected adaptive utility minus fixed utility, averaged equally over four prompt pairs.

| Pair | Fixed utility | c1 utility | c2 utility | Native choice | Selected minus fixed |
|---|---:|---:|---:|---|---:|
| p3b-01, preserved | 7.753090 | 7.896479 | 7.603189 | c1 | +0.143388 |
| p3b-02, grocery | 7.676650 | 7.308616 | 7.573050 | c2 | -0.103600 |
| p3b-03, password | 1.792464 | 7.497976 | 7.939855 | c1 | +5.705512 |
| p3b-04, birthday gift | 7.229096 | 7.041954 | 6.701155 | c2 | -0.527941 |

Across all four pairs, selected adaptive averages **10 distinct groups and 7.417165 utility**; fixed averages **7.75 groups and 6.112825 utility**. The primary mean paired utility difference is **+1.304340**, with **two wins and two losses**. The median paired difference is **+0.019894**.

The positive mean is driven by p3b-03. Its selected fixed portfolio contains ten distinct strings, which the native grouping judge placed in one semantic group. Only that group's first response contributes, with quality score 8. Its utility is therefore 1.792464. The adaptive portfolios received ten groups each. Textual uniqueness alone does not establish semantic distinctness; the recorded native partition is preserved without rejudging or overriding it. As a labelled post-hoc sensitivity description, the other three pairs average **-0.162717** selected-minus-fixed. This does not replace the frozen primary endpoint.

Mean c2-minus-c1 is **+0.018056**; mean selected-minus-c1 is **-0.019091**. On p3b-03, c1 and c2 use the same strategy, so their score difference reflects fresh sampling. These results do not establish a consistent second-round improvement or a general adaptation benefit.

## Distinctness, novelty and figure populations

Utility was the predeclared primary outcome; distinctness was also measured and belongs beside it in summaries. NoveltyBench distinct@10 counts meaningfully different groups among ten responses. Utility@10 credits the first response in each group using its quality score and weights earlier positions more heavily (patience 0.8). These measure within-portfolio useful variety. External originality, surprise and Bayesian surprise were not evaluated. A score of 10 distinct groups is a count ceiling, not evidence of maximal creativity.

| Pair | Fixed distinct@10 | Selected adaptive distinct@10 |
|---|---:|---:|
| p3b-01, preserved | 10 | 10 |
| p3b-02, grocery | 10 | 10 |
| p3b-03, password | 1 | 10 |
| p3b-04, birthday gift | 10 | 10 |
| **Mean over all four pairs** | **7.75** | **10** |

Both c1 and c2 also have ten groups on every prompt. The measured distinctness improvement therefore occurs on the password prompt; the other pairs tie at the metric's ceiling.

The utility means (7.417165 versus 6.112825), mean paired difference (+1.304340), two wins/two losses and distinctness means above cover **all four pairs**, including the preserved first pair. The **$19.981693 continuation cost and 6.30-times inference-cost ratio cover only the three new pairs**. The complete four-pair comparison cost is $31.221549. The preserved pair is included once in whole-pilot results and is never counted as a new observation or new expense.

## What the two utility losses share

The grocery and birthday comparisons both tie at ten distinct groups for fixed, c1 and c2. Their utility losses therefore concern judged answer quality and its positional weighting, rather than a measured loss of group count.

| Loss case | Fixed mean judged quality | Selected c2 mean judged quality | Mean-quality difference | Positional-residual difference | Utility difference |
|---|---:|---:|---:|---:|---:|
| Grocery | 7.8 | 7.5 | -0.300000 | +0.196400 | -0.103600 |
| Birthday gift | 7.1 | 6.7 | -0.400000 | -0.127941 | -0.527941 |

For this descriptive decomposition, let Q be the unweighted mean of the ten observed quality scores and P = utility - Q. Then the paired difference is exactly delta-Q + delta-P. It is applicable here because all ten responses in both arms have their own group and quality score. P describes the relation between the observed scores and their positions; it is not a causal ordering ablation independent of score distribution. Earlier-position weighting partly offsets grocery's lower mean quality and increases birthday's disadvantage. With duplicate groups or unjudged responses, do not extend this calculation by inventing their quality scores or assigning them zero quality.

Both native selectors chose c2, and **both c1 and c2 scored below fixed in both loss cases**. Grocery's c2 is the better adaptive checkpoint, improving on c1 by 0.264434. Birthday's c2 scores 0.340798 below c1; selecting c1 would reduce that loss but would still leave it 0.187143 below fixed. These are retrospective diagnostics on the saved candidates. The original score-blind selections remain the primary outcomes; no candidate is reselected after judging. Selection alone cannot explain the shared losses.

Both adaptations added answer instructions emphasizing one concretely named recommendation and suppressing alternatives. Grocery also rejected wildcard/rule/ritual answers; birthday added nonoverlapping concrete planning. The ranking instructions stayed unchanged in both. Selected adaptive responses were longer: approximately **339 versus 199 regex-word tokens per answer** for grocery and **187 versus 153** for birthday. These are observed associations with stricter single-pick instructions and longer responses, not proof that either caused a penalty.

Counterexamples prevent a simple content explanation. Grocery's adapted tomato opening scored 8 versus 7 for the fixed wildcard opening: the more specific opening received the higher score in this instance, without isolating specificity's effect. In the birthday case, a fixed cooking-class-for-two answer scored 8, while the selected pottery-workshop-for-two answer scored 6; two experience-gift recommendations received different scores. The adaptive Dutch-oven answer scored 8 but followed a star-map answer scored 7 and the pottery answer scored 6, illustrating the importance of recorded positions.

The saved benchmark judgments contain scalar scores without explanatory rationales. Two cases and one judge pass do not identify a common causal failure mechanism. Over-elaboration, constraint fit, item choice and ranking remain hypotheses rather than established reasons for the losses.

## Actual adaptation

| New pair | Stages changing their input strategy | KEEP decisions | Distinct effective strategy outputs |
|---|---:|---:|---:|
| p3b-02 | 6 | 0 | 4 |
| p3b-03 | 3 | 3 | 3 |
| p3b-04 | 6 | 0 | 4 |

Composition may adopt an existing variant. Distinct-output counts are within each pair, not independent discoveries or a count of globally unique techniques. For p3b-03, the broader seed-relative `effective_changed` field stays true after c1; input/output hashes, `kept_base` and session-level `effective_changed_from_input` establish the three later KEEP decisions. The report uses that distinction rather than presenting retained changes as new edits. No model weights were trained.

## Cost and accounting

| New work | Requests | Recorded API cost |
|---|---:|---:|
| Adaptive inference | 501 | $16.512431 |
| Fixed inference | 435 | $2.622912 |
| Native assessments | 90 | $0.846350 |
| **New continuation total** | **1,026** | **$19.981693** |

All new requests are settled, with zero pending or unknown results and zero new held liability. There were 9 grouping calls and 81 quality judgments, totaling 90 assessment calls; nine potential quality slots were unused. In total, 732 of the 1,758 possible new admissions were unused.

The approved ceiling was $350 total, with $50 per inference cell and $100 for assessments nested inside it. These were caps, not spending targets. Adaptive inference cost about **6.30 times** fixed inference over the three new pairs. Common ceilings do not establish equal realized expenditure or efficiency parity.

The preserved first pair contributes its original 361 requests/$11.239856 exactly once. The complete four-prompt comparison therefore accounts for **1,387 requests/$31.221549**. Tracked earlier-attempt lineage plus this continuation is **$110.830672 known**, with the separate historical **$22.88 unresolved hold unchanged**. This is the tracked execution lineage, not an invoice reconciliation or a total of every project/subscription cost.

## Verification and artifacts

Independent saved-outcome checks validate all request/result links, event chains, usage-price arithmetic, native head-only scoring and utility folds, original candidate-order permutations, score-blind selections and pair seals. The completed first pair retains its generation/assessment identities and cost. Pair reviews depend on execution validity, not favorable scores.

Exhaustive read-consumption auditing remains diagnostic. All 28 recorded sessions across four pairs have incomplete coverage. Selector parse errors in the three new pairs are retained (3, 1 and 2 respectively), with no read, mismatched-range or conflicting-range errors in those reviews. Normal-path proof and benchmark assessment remain separate requirements. Full audit details remain in the canonical analysis artifacts.

The [offline kit report](PHASE3B_REMAINING_PAIRS_KIT_REPORT.md) and [offline acceptance](../../../evidence/phase3b-seq2-v1/remaining-pairs-offline-acceptance-v1.json) bind the accepted 177-input source, runtime, policy, launcher and grant. Canonical execution source is `029657ee94a17d06235c6ec6524995bb8894ade3ca628c551d14e6e97048c2ff`; the new study is `1846b3656b125866f02b88cc1cd6a2a9e9624d5c7189512c3f37abfec2f09ebe`. The public projection's two documentation-path differences are recorded separately; it is not silently substituted for executed source.

The final canonical report has 8/8 primary aliases and 12/12 assessment targets scored, with `scientific_complete=true`. All 177 effective source inputs and 376 preserved-first-pair inputs remain unchanged. The paid controller finished with exit code 0 and was independently confirmed absent. Both Inspect exports passed strict round trips with zero model/socket attempts; the closure contains 1,387 actual native API intervals dated 2026. The one replay used the pinned H1 image with network disabled, read-only code and no supplied credentials; all eight files and both journal hashes matched, and its worker was removed.

Inspect remains a passive saved-log export. Automatic approval review rejected launching the local static viewer server with only “blocked by policy”; both saved exports passed and were consumed, and the canonical report was queued for the Codex file panel. No alternative server or permission bypass was attempted. Raw logs and provenance packets remain local under the [public-source boundary](../../PUBLICATION.md); the closure receipt publishes reviewed metrics, costs, identities and artifact hashes.

## What this supports, and what follows

The pilot exercises genuine native recursive adaptation and produces benchmark-scored, inspectable outputs. It provides a descriptive development result. Four exposed prompts, one grouping-driven outlier, fresh-rollout variability and unequal realized costs limit the scientific claim. It establishes no held-out, population, human-preference or cost-efficiency benefit.

The immediate next step is **the concrete definition and design review of confirmation**, not starting a held-out run. It must settle the following before any implementation, holdout opening or paid work:

- Freeze the compared models, strategy/toolkit access, adaptation depth, selection procedure and primary/companion metrics.
- Define a prospective resource-matching rule that accounts for generation, editing and selection, caching and any allowed overshoot/tolerance. Keep external assessment cost separate. Equal ceilings alone are insufficient; do not pad spending or match costs after seeing results.
- Establish held-out eligibility through exposure/overlap checks and define the sampling unit, sample-size/precision rationale and uncertainty analysis. Freshness is not established by the upstream dataset label.
- Predeclare grouping-sensitivity analysis while retaining the official native partition and score as the primary benchmark result. Saved exposed cases can inform the design. The password fixed portfolio has nine unjudged non-head answers, so its exact alternative-partition utility cannot be recovered from saved data without assumptions or separately authorized judgments.
- Require both native distinctness and utility, with quality, positional weighting, selection, actual strategy changes/KEEP and cost reported separately under the [reporting requirements](../../RESEARCH_METHOD.md#required-contents-of-every-future-report).
- Define objective, scope, usable deliverables, exclusions, completion criteria, cost and stop rules. Resolve development choices before opening genuinely held-out material; changed methods use development evidence and require fresh confirmation material.

This is a planning handoff, not a new study definition, budget grant or instruction to build a reporting framework. Preserve this pilot and its frozen primary result; do not retroactively reselect candidates, rejudge an unfavorable partition or treat unused budget as permission for another experiment.
