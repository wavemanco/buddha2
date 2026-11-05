# Phase 3B continuation live attempt - closed incomplete

Date: 5 November 2026, America/Los_Angeles.

The approved fresh four-prompt comparison closed incomplete after **161 provider calls/$5.877824**, with 161 valid physical call audits and zero pending requests, unknown results or new held liability. It reached the first prompt's native selector, turn 10. The fixed arm and external judges had not started. Final reports contain **zero of eight primary scores, zero of twelve assessment scores, zero normal native selectors and zero completed fixed pools**. There is no benchmark result, completed four-prompt comparison or adaptation-gain claim. The [machine-readable outcome](../../../evidence/phase3b-seq2-v1/continuation-live-outcome-v1.json) records the closure evidence and its limits.

## Observed stop

The journal contains 323 records: 161 intents, 161 known responses and one halt record. Its reason is `known_deadline_stop:pre_intent_deadline`. Independent inspection identifies a **600-second, nonrenewable native-selector window**. The tenth response finished about 543.052 seconds into that window, leaving 56.948 seconds. Another request required 60 seconds: a 30-second admission margin plus a 30-second minimum request allowance. The next request, turn 11, was therefore rejected before admission. This was not an unknown or timed-out provider response, and it did not require the full 600 seconds to elapse.

| Timing evidence | Value |
|---|---|
| Monotonic clock start / deadline | `527154.04467838` / `527754.04467838` |
| Approximate UTC start / deadline | 18:09:44.117475 / 18:19:44.117475, 5 November 2026 |
| First provider admission after clock start | 177.522 seconds |
| Tenth response completed | Approximately 18:18:47.114367 UTC |
| Exact rejected-turn-11 check time | Not recorded |

The UTC window is inferred from the first budget record's UTC/monotonic anchor. The 177.522 seconds before the first admission combine local boundary work, relay/Bun startup and admission overhead; their individual shares are not established. Native context copying is excluded from that interval. It would be unsupported to attribute the entire delay to Bun.

All ten selector responses were valid known responses ending in `tool_use`. They requested two reads each: **20 reads, zero writes or edits, and no `end_turn` or settled normal-completion proof**. The saved `selection.json` records `ok=false`, `fallback=true`, candidate A/c1. That fallback is not a valid normal selector completion and is not used to rescue the comparison.

All admitted calls belong to `p3b-01:adaptive`:

| Role | Known responses |
|---|---:|
| Planning | 8 |
| Answer generation | 80 |
| Ranking | 8 |
| Editor | 55 |
| Native selector | 10 |
| **Total** | **161** |

These counts describe work performed. They do not establish that recursive adaptation improved the strategy or its outputs. No fixed-arm or judge call is included in the observed ledger.

## Approved method and accounting

The [approved continuation](PHASE3B_CONTINUATION.md) retained the same four exposed development prompts, models, generation settings and benchmark protocol. It prescribed comparing actual Harness2 `seq,k=2` adaptation with a fixed best-of-twelve control under declared resource allowances. The corrected native-output proof remained in force; exhaustive read coverage and final-chat prose differences remained diagnostic. No source, upstream algorithm, scoring protocol or model substitution was authorized during execution.

The ceilings were **$152.313066 aggregate, $31.971901 for the included first-prompt checkpoint and 1,674 new requests**, within the unchanged cumulative envelope of $248.924365/4,341 attempts. Observed spend was $5.877824; this is usage-based public-price accounting, not provider invoice verification.

Cumulative lineage is **2,828 calls/$79.609123 known spend**, plus the unchanged **$22.88 historical held liability**, for **$102.489123 maximum current exposure**. All earlier stopped attempts, reports, grants and first-pair snapshots remain unchanged. No historical result is imported or requalified. Unused budget supplies no automatic retry or further paid repetition.

## Closure, visibility and verification

Canonical closure reports were produced and validated; their scientific summary remains incomplete. All 161 SDK invocations have valid physical audits, with no missing audit. Final reports contain zero read audits. The separate saved-read-log diagnostic below does not alter those reports or qualify an unfinished result.

The passive Inspect **closure-only** export completed at 18:34:39.044039 UTC, inside its original 18:32:40.450161-18:42:40.450161 UTC window. Snapshot identity is `fb39b3c6ea265164e8d04a14573b1d95a065a00cf0053e069d55805fcb1bb1e3`. Attachment preservation and semantic roundtrip passed, with zero provider calls, external sockets or model constructors. No first-pair export or completed first pair is claimed.

One keyless, network-disabled saved-report replay ran from 18:40:08.818161367 to 18:41:42.472159932 UTC and exited successfully. All eight reports matched byte for byte; the journal remained unchanged and API calls added were zero. Its raw receipt hash is `7c716a6b5e0c5f3a88948c521c578324a141409c38497956ddda81e75353f76f`.

The exact live, preflight, Inspect exporter and replay owners were removed and independently confirmed absent. The replay cleanup observation has raw hash `7879a0a063800afdd19fe21890327f50245c8f6e90d6cba2446e25625470b945` and sealed identity `69af5ce6c52e00183213eafbca733601f5ec9ea96646ffe034d8d21538c51981`. No keys or raw provider content are published.

The launcher lifetime was 20,681.6582979 seconds, from 12:50:05.221617381 to 18:34:46.87991527 UTC. This includes waiting for masked key entry; its acknowledgment was accepted at 17:12:59.460933 UTC. Launcher lifetime is not model inference time. The selector timing above is a separately observed, bounded interval.

## Separate saved-read diagnostic

The existing auditor ran once against saved evidence, with zero provider calls and unchanged source. It observed **seven of the 28 planned sessions**: six validated, settled author sessions and one partial selector session. The other 21 sessions were unattempted.

Across the six author sessions, the before-decision audit counted **96 complete target occurrences out of 692**, with 596 incomplete occurrences, zero read errors and zero parse errors. All six saved notes-reread audits were incomplete. For the partial selector at its last admitted request, turn 10, the audit counted **13 of 18 targets complete**, five incomplete, zero read errors and two parse errors.

The final turn's two tool-read results never entered a later admitted provider request; their consumption is not inferred. These are diagnostics of the saved read evidence, not model comprehension scores, a reason for the halt, or qualification of a completed selection. The diagnostic's raw receipt hash is `e53d154c50c036b4ef10e6ada364d96664d5601cc2c5d937e52dae73fa1f64d9`, with sealed identity `91fb2f04434d10f2974f73a0466562ab7d0fdd39ce2ff558526fcf65768150b2`. Its owner was removed and independently confirmed absent at 18:48:26.918334 UTC. Both saved-only observers, report replay and read auditor, therefore have independent absence confirmation.

## Provenance and next step

The accepted kit was published in [commit 8902002](https://github.com/wavemanco/buddha2/tree/8902002). Its [offline acceptance receipt](../../../evidence/phase3b-seq2-v1/continuation-offline-acceptance-v1.json) records 133 distinct checks and independent readiness review. Offline acceptance establishes the tested engineering coverage; this live attempt did not complete the scientific comparison.

The unchanged canonical source is `19e03f2dfc8623e571574decde2859a73074e5b9a0c94626dab775525664dff1` / 163 inputs. Its public projection is `1d6e31c846593997e2a333c1d8450fcfbd481504a44b8769fd1d99ecfb4c2326`. The study is `90e0562959a2ba5a03411a45aa86be5ed77b6f9115fe0791ee5811f91e94a838`.

Next is to review the existing selector time allowance, including its startup time. That decision precedes any changed configuration or new paid repetition. No new block, code change or further paid attempt has started or is authorized by this outcome.
