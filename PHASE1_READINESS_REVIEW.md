# Phase 1 first-two readiness review

2026-10-25, America/Los_Angeles. **Historical first-two stop and proposal, followed by an explicitly approved exception.** The user subsequently replied “Approve documented readiness exception (Recommended)”; the [approved record](evidence/phase1-live/readiness-exception-approved.json) and [operator review](evidence/phase1-live/readiness-review.json) permitted the remaining 46 scheduled presentations. Phase 1 is now complete with a diagnostic-only outcome; see [PHASE1_REPORT.md](PHASE1_REPORT.md). The original automatic gate did not pass. The account below preserves the observations and proposal as they stood at the initial stop; its no-approval/no-control statements describe that earlier checkpoint.

The PowerShell credential worked. Both requests returned exact `claude-sonnet-5-5`, the requested global/standard tariff and complete usage. Actual containment matches the approved launcher. One output was valid JSON; the second added prose before its JSON object and the strict parser correctly saved it as `malformed`. No extraction, repair or retry was performed. Human labels have not been opened.

| Presentation | Input tokens | Output tokens | Status | Cost, USD |
|---|---:|---:|---|---:|
| First order | 431 | 111 | ok | 0.001972 |
| Reverse order | 431 | 192 | malformed | 0.002782 |
| Total | 862 | 303 | 2 finalized outcomes | **0.004754** |

There are zero unresolved reservations and zero retries. The two count results match actual input usage. Both message/request IDs are retained; zero cache/tool/premium activity is reported. The runtime uses the pinned image, read-only `src`, one writable staged run, explicit key-name forwarding, bridge networking and suppressed raw logs. Neither source ratings nor audit labels were mounted. See [summary](evidence/phase1-live/first-two-summary.json), [live runtime](evidence/phase1-live/first-two-runtime.json) and [offline replay runtime](evidence/phase1-live/first-two-replay-runtime.json). An independent agent verified metadata/accounting without response texts or human labels.

## Why execution stopped

The original automatic readiness writer at `src/buddha2/phase1.py:258` requires both saved statuses to be `ok`; otherwise it raises **“readiness requires two valid calibration responses and complete accounting.”** This condition was not met. `replay_run.status=ready` means accounting is ready; it does not mean this separate readiness gate passed. No active `controls/readiness.json` exists.

The written outcome policy records malformed responses as terminal failures, while this implementation's initial gate additionally insists on two format-valid results. We will not silently relax that gate, repair the result or make replacement calls to obtain two successes.

## Bounded proposal for explicit review

Approve a **documented operator readiness exception**, based only on these calibration observations and complete route/accounting evidence: accept one valid parsed comparison plus one correctly classified malformed response as sufficient to proceed with the technical route check. This is a prospective change to the initial execution gate, not a claim that the original automatic gate passed.

If approved:

- Preserve both calls byte for byte. The malformed result stays malformed and earns zero under the existing calculation; do not extract its embedded preference.
- Keep the strict parser, current model/settings, selected data, original calibration rubric and audit floors unchanged. Retain the existing permission for at most one rubric wording revision only after the full calibration.
- Continue the remaining **46 scheduled presentations** (22 calibration, 24 audit) in the same shared journal and $5 authorization. The original two count toward 48; no added canary, retry or replacement is introduced.
- Record the user-approved exception and observed limitations in the operator review, evidence and final report. Preserve the original automatic writer and its tests. An operator-reviewed record may allow the existing dispatcher to proceed; do not label it an automatic readiness pass.
- Keep audit labels sealed until all final audit predictions are committed. Apply the same fixed 12-prompt denominators, >=9 human agreement and >=11 order consistency floors.

The concrete [proposed exception](evidence/phase1-live/readiness-exception-proposed.json) binds the exact run, bundle and two judgment hashes. It is inactive. No new paid calls will occur until this exception is explicitly approved or another bounded correction is reviewed. Alternatively, retain the current stop and review a different correction. The scientific evaluator audit remains uncompleted.
