# Phase 3B: first live attempt stopped during round two

4 November 2026, America/Los_Angeles. Scientific status: **incomplete**. Execution and financial closure: **complete**. This is a stopped attempt, not a completed four-prompt comparison or a negative benchmark result.

## Planned comparison and actual coverage

The approved comparison was actual native Harness² `seq,k=2` against fixed best-of-twelve on four already-exposed development prompts. It retained the original $180 fresh-exposure ceiling, $55 included first-prompt checkpoint, $35 inference-cell ceilings, $70 assessment pool and at most 2,344 new admitted requests. These overlapping limits were unchanged.

The first prompt reached its composed first-round checkpoint, c1, and generated that checkpoint's portfolio. The second-round domain editor then reached its fifteenth model response before an editor-side boundary check halted the run. Native checkpoint selection, the fixed arm, external assessment and the other three prompts were not executed. No readiness or first-pair PASS was issued. There are **zero benchmark-scored primary outputs and zero of twelve scored assessment targets**.

The first admission followed the consumed supervisor attachment at 09:50:53 Pacific. The controller finished at 10:30:09 Pacific. The model calls were part of the actual adaptation attempt, not synthetic or mock traffic. Harness², NoveltyBench, the study's models/settings and the effective source were unchanged during execution.

## What failed, and what remains uncertain

The financial journal's exact halt category is `editor_boundary_violation`; its state is `halted-integrity`. The last admitted and settled request is `p3b-01.adaptive.editor.dom2.a1.t15`. That response has `stop_reason=tool_use` and a `write` tool call.

A bounded, offline recheck of that retained request using the existing information-before-decision verifier reproduced **`malformed numbered read content`**. This is a rejection in our evidence-reading check. It points to a concrete compatibility question about the read format consumed by that check; it does not establish an unsafe file operation, a history mutation, a model refusal, a timeout, or a spending-limit failure.

The live relay uses a broad error category covering several predicates and does not retain the specific exception message. Its error path can raise before saving a settled editor-session record. The recheck therefore retains `original_failing_predicate=unknown`: reproducing a checker rejection is not proof that the live relay invoked that exact predicate on that turn. No temporary-workspace-dependent normal-session or tool replay was attempted after cleanup. No source repair, fresh model call, fallback substitution or replacement pilot followed.

## Accounting

| Item | Observed result |
| --- | ---: |
| New admitted requests and actual SDK invocations | 122 |
| New usage-based settled cost | **$12.528747** |
| New reserved or unresolved liability | **$0** |
| Active unsettled intents | 0 |
| Validated transport audits | 122 |
| Late-known responses or SDK-invocation unknowns | 0 |
| Earlier known Phase 3A cost, preserved | $46.044365 |
| Earlier held liability, preserved and unreleased | $22.88 |
| Cumulative known cost plus retained liability | **$81.453112** |

Unused allowance does not authorize another repetition. No old liability was released, and the accounting is usage-based exposure rather than an invoice.

## Closure and verification

- The controller stopped further admissions and completed its existing closure route. Its exit code 0 describes closure execution, not scientific success.
- Canonical reports and the passive Inspect closure export completed within the original 600-second window, in 49.36 seconds. The export preserved source attachment bytes, round-tripped successfully and made zero provider calls. No first-pair export was reached.
- The exact controller and Inspect exporter containers were removed; their absence was checked without a global container inventory.
- One existing saved-report replay ran in the pinned H1 image with networking disabled and no keys. All eight public reports were byte-identical to canonical closure: rows, coverage, analysis, summary, accounting, protocol, readiness and the Markdown report. A bounded metadata-only postmortem used the same offline job. The job exited 0 and its exact container was removed.
- Experiment implementation, upstream source, starting prompts, model settings and allowances remained frozen. Native-produced strategy edits are experimental outputs. No new test campaign, dependency, framework, packaging system or paid repeat was introduced.

See the [independent stopped-outcome review](../../reviews/phase3b-live-stop-review-2026-11-04.json) for verification scope and evidence hashes. Private credential bindings, locks, raw streams, provider payloads and captured source bundles are not published.

## Provenance

| Identity | Value |
| --- | --- |
| Study | `ed17a788fdd61b203cf7d5c856b635430e824ea254e31cdf215eea76f7d12b5c` |
| Effective canonical source | `c6eb4157c15ff859e70a0411b9b92f227ccfdf94dd1da94f38d1cdac21ef08c1` |
| Corresponding reviewed public source | `97f16655087287dd32a1f491d17219e83adc9284c49570b46f32b7ca413e1ca8` |
| Live grant | `de89bfbf62d68272af3101c3bfbf364548024bf4d55a98f85fe9a590a0b99921` |
| Launcher nonce | `5b3674c51a5f484aa508ffd53b01ed84` |
| Canonical summary file SHA-256 | `6b302d23860fc2e77bf42921116f25612f3ae5ae94600ed93a4d8d178ca749a2` |
| Postmortem record seal | `30f12e0cbaf03edf4836e5f7018de4b7ba0d11f8d3a2172cbcdd7a47d9a02118` |

The exact current local run is `runs/phase3b-seq2-v1/native/<study>/live`; its journal is separately under `runs/phase3b-seq2-v1/<study>/live/journal`. Canonical reports are in `reports/final`, saved reports in `reports/saved-replay-v1`, and closure status in `visibility/closure/status.json` beneath that live run. These are local provenance references, not public download links.

## Implication and next decision

This attempt establishes neither a utility gain nor a utility loss from two-round adaptation. It exercised the native loop through c1 and into round two, but did not deliver the planned comparison. The Phase 3A result remains the completed benchmark evidence; Phase 3B remains incomplete.

The next decision concerns the single reproduced read-format rejection: determine whether this check is rejecting valid editor output before proposing any paid repetition. No broader reliability project, new phase block or implementation is authorized by this report. Further execution would require a deliberate decision consistent with the one-fresh-pilot stop rule; the unused cap is not automatic permission to repeat.
