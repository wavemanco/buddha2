# Phase 3B: completed four-prompt development pilot

7 November 2026. The four-prompt comparison is complete. All planned calls, pair reviews, canonical closure and both passive Inspect exports passed. One zero-call saved-report replay reproduced all eight report files byte for byte without changing the journal. The [closure receipt](../../../evidence/phase3b-seq2-v1/remaining-pairs-live-outcome-v1.json) and [consolidated independent review](../../../evidence/phase3b-seq2-v1/remaining-pairs-live/independent-review.json) record the final evidence.

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

Selected adaptive mean utility is **7.417165**, versus **6.112825** for fixed: a **+1.304340** mean paired difference, with **two wins and two losses**. The median paired difference is **+0.019894**.

The positive mean is driven by p3b-03. Its selected fixed portfolio contains ten distinct strings, which the native grouping judge placed in one semantic group. Only that group's first response contributes, with quality score 8. Its utility is therefore 1.792464. The adaptive portfolios received ten groups each. Textual uniqueness alone does not establish semantic distinctness; the recorded native partition is preserved without rejudging or overriding it. As a labelled post-hoc sensitivity description, the other three pairs average **-0.162717** selected-minus-fixed. This does not replace the frozen primary endpoint.

Mean c2-minus-c1 is **+0.018056**; mean selected-minus-c1 is **-0.019091**. On p3b-03, c1 and c2 use the same strategy, so their score difference reflects fresh sampling. These results do not establish a consistent second-round improvement or a general adaptation benefit.

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

Next is a concrete definition for a held-out confirmation that addresses cost matching and grouping sensitivity before any new execution. Preserve this pilot and its frozen primary result; do not retroactively reselect candidates, rejudge an unfavorable partition or treat unused budget as permission for another experiment.
