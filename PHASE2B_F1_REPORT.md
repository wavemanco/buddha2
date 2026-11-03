# P2B-F1 — First counted live block

Completed on **2026-10-28**. **Technical result: PASS. Expansion: HOLD, not authorized.**

The authorized first block completed with **28 provider requests**, three scored native assessments, **$0.210174 conservative usage-based public-price accounting**, and **zero unresolved reservations or unknown outcomes**. All 55 possible first-block slots are classified: 28 `ok`, 27 `not_needed_nonhead`. No retries, fallbacks, repairs, replacement calls or provider probes were made.

The full Phase 2B study remains **inconclusive**: only 3 of 72 ordered assessments exist, 69 remain missing, and no procedure or seed is selected. This report closes the first block only. It does not demonstrate recursive improvement.

## Objective, scope and deliverables

The objective was to complete the first prespecified A/B/C comparison while observing the declared models, settings, native scoring and accounting through the frozen provider launcher. The development task, repeat 1, was:

> Which 4-digit lock combination is the safest?

Task `nb-curated-9c418f063bc433264d29`, NoveltyBench source `curated-95`, native v1.1, patience 0.8. The source, prompt, methods, parsing and acceptance criteria were unchanged from [the first-block definition](PHASE2B_FIRST_BLOCK_DEFINITION.md). Its historical unapproved status is superseded by the later [user authority record](evidence/phase2b-f1/authorization.json) and [actual first-stage grant](evidence/phase2b-f1/launch-records/grant.json), not by editing the old definition.

Delivered artifacts:

- This closeout and interpretation, plus [the complete descriptive appendix](evidence/phase2b-f1/report/PHASE2B_F1_REPORT.md).
- [All 55 slot outcomes, actual request settings, visible outputs, usage and accounting](evidence/phase2b-f1/report/first-block-data.json).
- [Verified archive](evidence/phase2b-f1/report/phase2b-f1-report.zip), [file manifest](evidence/phase2b-f1/report/manifest.json), and [package verification](evidence/phase2b-f1/report/package-check.json), including the saved native assessments, journal, portfolios and whole-study reports.
- [Independent authority/integrity review](evidence/phase2b-f1/live-authority-review.json), [independent outcome review](evidence/phase2b-f1/live-outcome-review.json), [saved technical review](evidence/phase2b-f1/report/raw/run/journal/reviews/first.json), and [sanitized host exit record](evidence/phase2b-f1/launch-records/result.json).

Excluded work remains excluded: the other task/repeat blocks, model or effort sweeps, recursive adaptation, held-out confirmation, MuCE/CrPO work, human collection and new strategies. No person was contacted. Optional human ratings do not block this benchmark-track result.

## Actual models, settings and sampling

The requested and returned model IDs matched for every call. Returned aliases do not establish immutable model weights.

| Role | Requests | Requested and returned model | Requested effort and controls |
|---|---:|---|---|
| A/B answers | 20 | `claude-sonnet-5-5` | Adaptive thinking, effort `low`, `max_tokens=4096`, `service_tier=standard_only`, `inference_geo=global` |
| B plan | 1 | `claude-sonnet-5-5` | Same Sonnet settings |
| C rank | 1 | `claude-sonnet-5-5` | Same Sonnet settings |
| Native grouping | 3 | `gpt-5.6-luna` | Chat Completions with the frozen strict grouping JSON schema; effort and output cap omitted |
| Native head quality | 3 | `claude-opus-5` | Adaptive thinking, effort `high`, `max_tokens=16000`, frozen strict `{"score": integer}` schema |

Temperature, top-p, top-k and API seed were omitted for every role. Grouping effort was not explicitly requested or returned; an assumed default is not an observed reasoning level. Quality service tier and geography were omitted, as specified. Anthropic token caps include billable thinking plus visible text. Exact bodies and all other omitted controls are preserved in the appendix/data. Transport used the pinned SDKs, a 90-second HTTP timeout and zero SDK retries.

| Condition | Sampling and context | Observed completion |
|---|---|---|
| A: ordinary sampling | Ten independent regenerations, each in a fresh context with the original task and shared minimal instruction; no sibling answers | Ten saved answers, in request order |
| B: fixed planner + generation | One ten-angle plan, followed by ten fresh regenerations; each answer sees the original task and only its assigned planning angle | Valid plan and ten saved answers, in angle order |
| C: isolated reranking | One in-context permutation of the ten saved B responses; no new answers, rewriting or filtering | Valid permutation; all B IDs and text retained exactly |

Each condition received its own grouping assessment and quality judgments for its first response in each group. B's judgments were not reused for C. There are 20 generated answer texts and 30 ordered answer presentations across A/B/C.

## Native results

These are descriptive results for this one development prompt and repeat, rather than whole-study averages or inferential estimates.

| Condition | Assessment status | Distinct semantic groups | Scored head quality | Native utility | Attributed generation/planning/ranking cost |
|---|---|---:|---:|---:|---:|
| A | scored | 1 | 8 | 1.792464399362674 | $0.056570 |
| B | scored | 1 | 7 | 1.5684063494423397 | $0.095058 |
| C | scored | 1 | 7 | 1.5684063494423397 | $0.115012 |

All three partitions are `[0,0,0,0,0,0,0,0,0,0]`. Each order therefore has one quality head and nine unscored nonheads. Across the three orders, 27 quality calls were correctly unnecessary. Their quality values remain `null`; they are not fabricated zero ratings. Native utility credits those later semantic duplicates with zero contribution and normalizes by `sum(0.8**i for i in range(10)) = 4.463129088`.

The 20 generated full texts are all different. The grouping result concerns semantic equivalence. The planned angles vary the explanation and advice, while returning to the common answer that no fixed four-digit number is universally safest and unpredictability matters. We preserved the judge's grouping without changing the protocol after seeing it.

C's order, expressed as original B positions, is **[1, 2, 5, 9, 6, 3, 10, 4, 7, 8]**. It changed the ordering but retained B01 first. With only one semantic group and the same head quality score of 7, C's utility equals B's. This is a valid reranking outcome. It does not show that reranking generally fails.

A is numerically ahead on this prompt. One task and one repeat cannot identify a generally better strategy, distinguish stable quality differences from judge variability, or support a recursive-adaptation conclusion. The saved whole-study means and primary contrasts remain `null`, as required for incomplete pilot evidence.

## Costs, failures and stopping

| Unique request role | Accounted USD |
|---|---:|
| Answers | 0.141734 |
| Plan | 0.009894 |
| Rank | 0.019954 |
| Grouping | 0.004800 |
| Quality | 0.033792 |
| **Total** | **0.210174** |

This is a conservative usage-derived public-price upper bound, **not an independently reconciled invoice**. The native report's `experiment_api_spend_micro_usd` remains `null`; its accounted upper bound is 210,174 micro-USD. C's attributed cost includes B's generation/planning plus ranking; the unique ledger charges those B requests once. Do not add A+B+C attributed costs as experiment spend.

The authorized cap was **$20 cumulative**, including outstanding liability and the next conservative request reservation. The block completed before that ceiling; $20 was never a guaranteed charge. Its low observed cost reflects one head per order and this prompt's usage. It does not establish a cost forecast for other prompts, which may require up to ten quality judgments per order.

All 28 requests returned known, accounted responses. There were no refusals, empty/truncated outputs, malformed results, unknown deliveries, unclassified first-block slots, failed prerequisites or recoverable missing exports. Outstanding reservations are zero. The first-stage runner stopped automatically; no expansion request was sent.

The host exited with code 0 and retained no stderr bytes. The operator's console message, `Provider streams suppressed. Inspect sanitized phase artifacts and the retained journal.`, was expected: the launcher waits synchronously and suppresses provider streams. It was not a request for further input.

## Verification and completion criteria

- Three valid portfolios and three `scored` native assessments; every one of the 55 first-block slots classified.
- Exact requested/returned model IDs, declared request controls and C's unchanged-text permutation verified from saved evidence.
- Hash-chained journal: 28 unique intents and 28 known results; one applicable $20 first-stage authority, no expansion grant, no outstanding liability.
- All 70 frozen gate file hashes, 26 source files and the frozen PowerShell launcher still match. No experiment code, protocol or scoring changes were made.
- Saved-evidence native, coverage, analysis and decision replay was exact. Reporting used the pinned network-disabled container, constructed no SDK client, read no keys and made zero new provider calls.
- The 30-member archive passed inventory, byte, CRC and source-preservation checks. The report packet's tracked copy matches the generated packet byte for byte.
- Technical review `live-first-review-001`, cutoff `2026-10-28T10:16:14Z`, was published with review identity `061dc60298827ef9bc43ccd3d6dfd59f8ea9a167278ebe3680cf3d42590ce004`. This records first-block technical acceptance, not a human creativity rating or expansion grant.

The complete appendix retains a generic statement of expansion prerequisites; the successful technical review is now recorded in its review section and immutable journal record. The separately applicable cumulative expansion grant remains absent.

Raw API keys, credential-binding material, provider stream content and host environment values are excluded from the report packet. Canonical records preserve visible text, model IDs, stop reasons, usage, request IDs and latency; they do not preserve complete SDK objects or Anthropic thinking blocks. The quality judge returned scores only, so no explanatory judge rationale is available. Secret-pattern checks are bounded and do not certify that every arbitrary string is nonsecret.

The original Buddha2 folder was not accessed or modified. All new artifacts belong to `C:\Users\arvik\code\research\Buddha2`.

## Next step

**Stop after P2B-F1.** Refresh the concrete definition and cost scenarios for the remaining 23 task/repeat blocks, using this evidence while allowing for other prompts' head counts and response lengths. Review objective, scope, deliverables, exclusions, completion criteria, exact settings, call limits, expected cost versus cap and stop conditions together before any expansion.

The earlier $125 cumulative pilot ceiling remains a proposal, not authority. Neither this report, the successful technical review nor unused first-stage funds authorizes another prompt. Recursive Harness² adaptation remains a later separately defined phase, after the fixed-strategy pilot.
