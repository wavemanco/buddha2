# Phase 3A — RP2 live development pilot

November 2, 2026, America/Los_Angeles. **Phase3A is complete under approved RP2/AM1:** execution, saved-data replay, independent outcome review and actual closure-archive acceptance passed. This final readout and its receipts form the committed delivery. The protected original Buddha2 folder remains outside all reads, writes and mounts.

## Result

Fixed C-N best-of-six outscored native one-step adaptation on all four exposed development prompts. Mean native utility was **6.325890 fixed versus 5.794553 adaptive**, an unweighted paired difference of **−0.531336** (adaptive minus fixed). The frozen descriptive selection is **fixed**. This is a completed development comparison, not population, held-out or human-preference confirmation.

| Prompt | Fixed utility | Adaptive utility | Adaptive − fixed | Distinct fixed / adaptive |
|---|---:|---:|---:|---:|
| p3a-01: inventions, curated-15 | 7.967044 | 7.819012 | −0.148032 | 10 / 10 |
| p3a-02: grocery item, curated-17 | 7.969927 | 7.620121 | −0.349806 | 10 / 10 |
| p3a-03: four-character password, curated-96 | 3.005851 | 2.033045 | −0.972806 | 4 / 2 |
| p3a-04: one birthday gift, curated-29 | 6.360736 | 5.706036 | −0.654701 | 10 / 10 |
| Mean | **6.325890** | **5.794553** | **−0.531336** | **8.5 / 8.0** |

First-answer quality tied at 8 on the first three prompts; on the gift prompt it was 7 fixed and 6 adaptive. The duplicate assessment of the first fixed portfolio exactly matched its partition, all ten shared head scores and utility. One matching diagnostic does not establish general judge reliability or a variance estimate.

The four prompts, order and single repeat were frozen before this attempt. They are development material already exposed during earlier work. No incomplete historical attempt was pooled into these eight primaries, and no held-out material was opened.

## What ran

The approved [RP2 definition](PHASE3A_RP2_RECOVERY_DEFINITION.md), [delivery clarification](PHASE3A_RP2_DELIVERY_CLARIFICATION.md) and [AM1 amendment](PHASE3A_RP2_AM1_DEFINITION.md) govern this one fresh attempt. Their original proposal-only openings are historical; the append-only authorization records preserve the user's subsequent approvals. The accepted [offline kit](P3A_RP2_OFFLINE_REPORT.md) is committed in `67ede23`; implementation is `9ef1d3c`, with source549 unchanged throughout live execution.

Actual pinned Harness² `1cfe254e8d25b15f37048c3730134686abe60335` ran native `agg,k=1`, final-only selection and no experience library. Each adaptive path performed three native proposal/composition stages and four executor rollouts (`base1`, `inv1`, `dom1`, `agg1`). The fixed arm generated six fresh C-N portfolios and used its declared blind whole-portfolio selector. Both arms had the same initial strategy access and resource allowances. No required edit, favourable score or human reply controlled continuation.

Generation/planning/ranking used `claude-sonnet-5-5`, adaptive thinking, low effort and 4,096 output tokens. Native authoring and the fixed selector used `claude-opus-5`, adaptive thinking, high effort and 16,000 output tokens. Native NoveltyBench v1.1 code at `64a23be6b18ec1dacc298830aab276061b6e143c` used `gpt-5.6-luna` grouping and Opus5 high-effort quality assessment. Published request omissions were retained. The model/role profiles and exact request bodies are preserved in the canonical protocol and physical audits.

All eight primaries and the duplicate are scored. There were **681 admitted requests and 681 validated physical SDK invocations**, all known, with zero retries, missing audits, pending intents, new unknown results or new held liability. The 967 potential slots were inventory; the admitted-attempt ceiling was 775. Native quality scoring covered group heads only: 9 grouping requests and 76 quality requests were required, not 90 mandatory quality calls.

## Actual adaptation

All four native paths are authentic and normally completed. All twelve editor sessions were accepted; none used fallback, cap-limited unchanged status or a terminal note. Eight stage attempts changed consumed strategy fields; four deliberately kept their input.

Selected-final attribution was checked against actual seed and selected `agg1` file bytes, rather than inferred from stage labels:

| Prompt | Selected final versus initial seed |
|---|---|
| p3a-01 | Unchanged; all three stages chose KEEP_BASE. |
| p3a-02 | Changed `answer_system` and `rank_system`; AGG selected the DOM strategy. |
| p3a-03 | Unchanged; AGG kept the seed despite changed INV and DOM probes. |
| p3a-04 | Changed `answer_system` and `plan_system`. |

The grocery changes emphasized a single concrete named choice and ranking consistent with the task's singular request. The gift changes addressed “just one,” recipient-specific planning and generic answer padding. These are model-authored instruction changes inside the experimental loop. The earlier C1, H1, RC1 and AM1 engineering remains external infrastructure and is not credited as learned adaptation.

This comparison does not isolate the causal effect of edits: two selected finals retained the seed, the procedures allocate their search differently, and the fixed arm selects among six fresh portfolios. The observed result supports retaining fixed C-N as the exploratory development seed for now. It does not prove that every adaptation method or successive recursive refinement fails.

## Cost, tokens and time

| Scope | Requests | Recorded USD |
|---|---:|---:|
| Fixed inference | 292 | 2.572995 |
| Adaptive inference | 304 | 12.650235 |
| Native assessment, including duplicate | 85 | 0.946974 |
| Total | **681** | **16.170204** |

Adaptive inference cost approximately 4.92 times fixed inference. The matched $20-per-prompt/arm allowances were ceilings, not equal realized spending or compute. No unused allowance was transferred or consumed to equalize costs.

| Role | Requests | Recorded USD |
|---|---:|---:|
| Plan | 40 | 0.342292 |
| Answer | 400 | 2.260854 |
| Rank | 40 | 0.481852 |
| Native editor/composer | 112 | 11.352193 |
| Fixed selector | 4 | 0.786039 |
| Group | 9 | 0.011659 |
| Quality | 76 | 0.935315 |

The ledger records 5,567,521 input tokens: 533,125 uncached, 885,459 cache-creation and 4,148,937 cache-read tokens; output totals 383,110. Reported reasoning totals 52,280 tokens and is a subset of output, not an extra charge. Unreported thinking is not inferred as zero. Exact role/model/cache/thinking breakdowns and per-cell allowance utilization are retained in `accounting.json`.

The actual controller-container lifetime was 8,279.1339105 seconds (about 138 minutes), from 11:40:25 to 13:58:25 PST on November 2. This includes credential entry and review pauses. The journal does not measure wall time; its wall-time field remains null, and the actual sanitized host/runtime records are retained separately. No per-role provider-server latency or timing parity is claimed.

The fresh joint cap was $190, including reservations, with the overlapping $50.86 checkpoint, eight $20 inference cells and $45.86 assessment pool. Accounting is a usage-based public-price upper bound, not an invoice. Assistant sessions, engineering effort and local compute are separate. Prior known Phase 3A cost remains $29.874161 and two old unresolved liabilities remain fully held at $22.88. Cumulative known cost is **$46.044365**, with **$68.924365 maximum current exposure** including those old holds. Historical accounting is not fully settled; no old liability was released. This attempt supplies no paid repeat or transfer of its unused cap.

## Execution, replay and delivery evidence

Fresh masked keys followed full independent kit acceptance. A real dedicated keyless supervisor was dispatched before the console opened; a new actual running-agent observation was taken after the startup request. Its bound ACK was consumed before any paid intent. The controller then completed counted readiness, the supported first-pair engineering review and the remaining work without another key entry. Reviews used evidence and accounting, not favourable scores. All source/model/prompt/criterion settings remained frozen.

Both actual separate SDK-free I1 exports passed within their original 600-second windows. First-pair checkpoint elapsed time was 90.178874 seconds and closure was 222.951309 seconds. Exact exporter IDs and the paid controller were independently confirmed removed; the actual host core process terminated and the sanitized launcher exited 0. Raw credentials and real/unknown provider streams were not inspected.

The independent saved-live replay took 274.646 seconds. All eight canonical files were directly byte-identical; all549 source files and main retained copies, 1,198 bounded public native input files, the raw journal and all681 physical transport audits were unchanged. Actual SDK, socket and process-attempt arrays were empty. Its exact contained owner was removed and absence proved. The [replay review](runs/phase3a-readiness-recovery-v1/verification-v3/reviewer/live-closeout-v1/replay-review-v1.json) and included raw result bind these checks to this study.

The versioned [outcome](evidence/phase3a-readiness-recovery-v1/live-outcome-v1.json) binds exactly the eight canonical reports and embeds 17 selected public operator records losslessly with original paths, byte lengths, raw SHA256 and base64 bytes. Superseded attachment/service records and the honest UI-check limitation remain preserved. The frozen packager already includes this outcome; no runtime or packaging-code change was made after observation.

Inspect remains a passive record/viewer layer. Actual native audit dates and model-role configurations are imported; Inspect made no provider calls. Activity's model-call chart is unavailable for imported InfoEvents; use the dated event timeline and native-audit CSV. The static [first-pair viewer](http://127.0.0.1:8774/#/tasks/first-pair.eval/samples) and [closure viewer](http://127.0.0.1:8775/#/tasks/closure.eval/info) are served on loopback with credential-free environments. App opening was queued; the specific first-pair IAB lookup found no tab, so rendered UI verification is not claimed.

The [independent outcome review](evidence/phase3a-readiness-recovery-v1/live-independent-review-v1.json), SHA256 `98dd1b1b2a53c4a45411468fee8e8fb4a7d78d76efc8a869b80485ebe32e0ee8`, and [physical archive acceptance](evidence/phase3a-readiness-recovery-v1/live-packet-acceptance-v1.json), SHA256 `1e897fc321aecaa868003edc4a2b643ba37f00d59268c67bdf429de1662c39ed`, pass. Every one of the 9,761 actual ZIP members passed raw-hash/CRC/inventory/privacy checks, including all681 physical audits and current data. The [closure manifest](evidence/phase3a-readiness-recovery-v1/live-outcome-v1.manifest.json) binds archive SHA256 `e463acf545cacd94221a74e44ae41edb3964f978af07c2f572c175930942fcba` (584,542,601 bytes); manifest SHA256 is `a8a7357be32ee5f9ffdd5c787bc294c23a4886f860510da37cd858dc562a2b25`. No second replay or additional provider call was performed. The exact prearchive readout reviewed by the independent reviewer is retained inside the ZIP at `runs/phase3a-readiness-recovery-v1/verification-v3/reviewer/live-closeout-v1/readout-prearchive-v1.md`, raw SHA256 `c87d6a794c657b430286054cbac3a5df5f30515308678bfa422871f9bff4b926`; this final revision changes delivery-status/link wording, preserving its results and limitations.

## Next decision

Retain fixed C-N as the descriptive development seed. Refresh Phase 3B's concrete definition for actual successive native `seq,k=2`, using this pilot's measured costs, selected strategy changes and search/selection differences to define its matched control and stopping rules. A standalone k=1 run is not substituted for the first round of k=2. No Phase 3B implementation or paid experiment starts automatically. Fresh held-out confirmation remains a later separately frozen phase. Human evidence, CrPO/MuCE, Bayesian surprise, additional strategies/models and benchmark updates remain separately scoped.
