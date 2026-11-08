# P4-CM1 eligibility — frame certified

8 November 2026. **Controlled, network-disabled intake passed after offline kit acceptance.** The pinned WildChat source contains 1,000 rows and 1,000 unique prompt units. Recorded exposures exclude 263 units, leaving **737 eligible units**; **24 units are fixed** by the prespecified hash ranking. Task text was not printed, and no model calls or real credentials were used. This is data readiness, not a scientific result.

The [controlled-intake receipt](../../../evidence/phase4-cm1-v1/controlled-intake-v1.json) and [frozen selection manifest](../../../evidence/phase4-cm1-v1/eligibility-manifest-v1.json) bind the result to the accepted method, source file and exposure inventory. See the [kit report](PHASE4_CM1_KIT_REPORT.md) and [acceptance summary](../../../evidence/phase4-cm1-v1/offline-acceptance-v1.json).

## Recorded exposure coverage

The [hash-bound audit](../../../evidence/phase4-cm1-v1/exposure-audit-v1.json) retains 263 known WildChat IDs/input hashes, all 100 exposed curated prompts and 50 earlier normalized exclusion aliases. The [independent coverage review](../../../evidence/phase4-cm1-v1/exposure-coverage-review-v1.json) approved that recorded exclusion inventory before frame intake; it did not itself certify an eligible count.

Historical metadata covers 263 actual input-bearing attempts: 259 cases with summary/grade-file presence and four additional cases without those summaries. All 263 are excluded. File presence supports exposure coverage, not scientific success or a failure-cause claim. The earlier source revision is unknown, so both IDs and normalized input aliases were checked conservatively against the current pinned frame.

The bounded project metadata audit parsed 116 descriptors: 99 contain task lists and 17 do not. They are parsed descriptors, not 99 independently validated studies. The audit retains source-provenance filenames and hashes for the curated and earlier alias inventories; no task or answer text is embedded in this coverage record.

## Controlled intake result

| Quantity | Verified count |
|---|---:|
| Pinned source rows | 1,000 |
| Unique normalized prompt units | 1,000 |
| Duplicate rows collapsed | 0 |
| Excluded known-exposed units | 263 |
| Eligible units | 737 |
| Frozen selected units | 24 |

The source is NoveltyBench commit `64a23be6b18ec1dacc298830aab276061b6e143c`; the WildChat file SHA-256 is `8534288089508df3f413c1151a58d5fa5bda9d8f8385ae2815384d4e310a54ca`, verified during controlled intake. Normalization uses Unicode NFKC, case folding and collapsed whitespace with the existing canonical-JSON SHA-256 convention. Selection ranks `SHA256(UTF8("P4-CM1-v1|" + exact source ID))`, with lexical-ID tie-breaking, and takes the first 24 eligible units. No favorable-case substitution is allowed.

The manifest seal is `944e429e9bed89bce08cf542d3ad7d0578deba22cd9c4b41f714a553b2c792da`; its file SHA-256 is `95cafe840aa3261d24862d5c76f39b559cbf8b5eac89676f49755707a32adbfc`. It binds the frozen method and exposure inventory without opening tasks to analyst-led selection.

## Limits and next step

Eligibility is relative to recorded project exposures and exact normalized matching. It does not prove semantic independence, universal absence of unrecorded access or model-pretraining freshness. Offline independent review preceded this later controlled intake; its original no-intake-at-review statement remains historical and was not rewritten.

This current report supersedes the audit-time text whose SHA-256 was `1525c877fe57a68c6532d3ec19fa1d23a3379ed16691c2e6ba13c16321370899`. The earlier coverage review retains that original report hash and scope; current frame certification comes from the separate intake receipt and manifest above.

Next is fresh masked key entry and the authorized two exposed fixed-only cost qualifications, followed by the frozen comparison only if qualification passes. No live calls, cost-qualification result or confirmation outcome is established here. The [definition](PHASE4_COST_MATCHED_CONFIRMATION_DEFINITION.md) and existing $1,200 limits remain unchanged.
