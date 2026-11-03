# Phase 2B — Fixed-strategy pilot report

Closed **2026-10-28**, evidence cutoff **2026-10-28T12:12:19Z**. **The authorized worklist finished with recorded failures. Full benchmark decision: INCONCLUSIVE; no seed selected.**

There were **991 known, accounted provider requests**, **68 of 72 scored orders**, **$5.983504 conservative usage-based public-price accounting**, and **zero pending requests, unknown outcomes or unresolved reservations**. Four reranking responses violated the strict single-JSON-object contract, so their four C portfolios and assessments remain absent. There was no budget stop, retry, fallback, repair or replacement call.

The complete A/B evidence gives a useful development signal: planning increased semantic diversity substantially and produced higher utility on 11 of 12 prompts. That observation does not override the predeclared requirement for complete three-condition coverage before selecting a seed. Recursive adaptation and held-out performance remain untested.

## Scope and authority

This report closes the [P2B-E worklist](PHASE2B_REMAINDER_DEFINITION.md) together with its preserved [P2B-F1 prefix](PHASE2B_F1_REPORT.md). The user's subsequent “proceed” authorized the defined remaining pilot at **$125 cumulative**, including F1; see [authority record](evidence/phase2b-expansion/authorization.json).

The frozen study is `38132ee3a935af4ac975c3fda84154d1a85b1bcb510925f409993a15d3103d8b`, source bundle `5909e90bc49a3251ba431c8ccf677cdc02a2827f36271d9b0abed3a5421ef22c`. It used 12 preselected NoveltyBench curated development prompts, two repeats and three fixed procedures, native v1.1 scoring with patience 0.8, the pinned sources/image/SDKs and one cumulative journal. All methods, prompts, role settings, failure rules and selection criteria remained unchanged after F1.

These public prompts are development material, potentially exposed in legacy work. They are not a fresh holdout. The protected original Buddha2 folder was not accessed, copied, modified or mounted.

## Models, effort and sampling actually used

All requested and returned model IDs matched. Model aliases and saved provenance do not guarantee immutable weights or identical regeneration.

| Role | Actual requests | Requested and returned model | Requested controls |
|---|---:|---|---|
| A/B answers | 480 | `claude-sonnet-5-5` | Adaptive thinking, effort `low`, `max_tokens=4096`, `service_tier=standard_only`, `inference_geo=global` |
| Angle plan | 24 | `claude-sonnet-5-5` | Same Sonnet controls |
| Permutation rank | 24 | `claude-sonnet-5-5` | Same Sonnet controls; instructions requested one JSON object, without provider-enforced output schema |
| Native grouping | 68 | `gpt-5.6-luna` | Chat Completions, frozen strict grouping JSON schema; effort/output cap omitted |
| Native head quality | 395 | `claude-opus-5` | Adaptive thinking, effort `high`, `max_tokens=16000`, frozen strict score JSON schema |

Temperature, top-p, top-k and API seed were omitted. Grouping's effort was not explicitly requested or returned; a documented default is not an observed effort level. Quality service tier/geography were omitted. Anthropic caps include thinking and visible text. The native generation argument of 2,048 expands to the recorded 4,096 total-token request. Exact controls, schemas and omissions are in [settings.json](evidence/phase2b-expansion/report/settings.json), with all request bodies and usage in the canonical journal.

Runtime: pinned Linux/amd64 image, Python 3.12.15, `anthropic==1.4.0`, `openai==1.107.0`, one request in flight and 90-second HTTP timeouts. No tools, web or conversational memory were requested; SDK/stage retries were zero.

| Condition | Sampling and information access | Recorded portfolios |
|---|---|---:|
| A: ordinary sampling | Ten independent fresh-context regenerations per prompt/repeat, with the original task and minimal instruction; no sibling answers | 24/24 |
| B: fixed planner + generation | One ten-angle plan, then ten fresh regenerations, each conditioned only on its assigned angle plus the original task | 24/24 |
| C: isolated reranking | One in-context permutation of the corresponding saved B IDs/texts; no new answers, rewriting or filtering | 20/24 |

Generation order rotated as frozen: A/B for repeat 1, B/A for repeat 2, then C. Each delivered order received a fresh grouping and its own head-quality calls. B's judgments were not reused for C. All 480 answer outcomes were recorded as `ok`; all 24 plans passed the strict angle contract. These statuses do not establish semantic task compliance. The 20 valid C portfolios preserve their complete B texts/IDs exactly. There are 680 recorded answer presentations and 40 absent C presentations; C presentations are not additional independent generations.

## What failed

| Source/task | Repeat | Failed rank attempt | Visible format violation |
|---|---:|---:|---|
| `curated-2`: five-sentence Easter romcom in rural Kansas | 1 | 78 | Explanatory prose precedes the JSON order |
| `curated-63`: three influential nineteenth-century people | 1 | 432 | JSON, self-correction prose, then a second JSON object |
| `curated-29`: one gift for a friend's twenty-fifth birthday | 1 | 607 | JSON, claimed ID correction, then a second JSON object |
| `curated-29`: same gift task | 2 | 642 | JSON, claimed ID correction, then a second JSON object |

All four calls returned normally with `end_turn`, known usage and the intended model. They were not timeouts, refusals, output-cap truncations or native judge failures. Their combined accounted cost is **$0.051352**, already included in the total.

Read-only structural inspection found **seven embedded JSON order objects, all valid exact permutations of their parent B IDs**. In the three self-correction cases, both lists are identical: the stated correction did not change the order. This diagnosis does not convert the whole response into valid strict JSON. No order was extracted into a replacement C portfolio, no score was invented, and no failed slot was retried or rescored. The full visible responses and diagnostic checks are retained in [the outcome review](evidence/phase2b-expansion/live-outcome-review.json) and raw journal.

The runner correctly preserved each known paid failure, skipped its dependent C grouping/quality slots and continued independent work. All 24 task/repeat blocks reached their defined disposition. The result is a **limited execution closure**, rather than a completed comparable three-condition benchmark.

## Native results and the separate A/B descriptive supplement

The unchanged official [decision](evidence/phase2b-expansion/report/public-report/decision.json) has `native_complete=false`, `status=inconclusive`, `selected_method=null`. Its aggregate utility means and primary contrasts remain `null`, because four required C assessments are missing. The human status is `not-required`; missing human reviews did not cause this result.

**The following A/B utility means are supplementary descriptive arithmetic computed after closure**, using every preselected A/B prompt and both repeats. They do not overwrite those official nulls, select a seed, discard failed C cases or introduce a new eligibility rule. Average the two repeats within each prompt, then weight all 12 prompts equally. The independent task count is 12, not 480 answers or 72 orders.

| Measure | A: ordinary | B: planner | C: reranked |
|---|---:|---:|---|
| Scored orders / planned | 24/24 | 24/24 | 20/24 |
| Supplementary all-12-prompt mean utility | 2.747011 | 6.658122 | Not computed across incomplete coverage |
| Native mean distinct groups | 2.083333 | 7.916667 | Missing under full-coverage rule |
| Native mean first-answer quality | 8.250000 | 8.208333 | Missing under full-coverage rule |
| Native mean of per-prompt head quality | 8.259970 | 7.788442 | Missing under full-coverage rule |

The supplementary mean paired **B−A difference is +3.911111 utility points**, with B ahead on **11 of 12 prompts**. This is a development observation, not a significance claim, held-out estimate, proof of general human preference or isolation of planning from extra inference. B used more than twice A's accounted generation/planning cost. Planning increased useful semantic variety while first-answer quality was similar and average head quality was lower. The four-character-password task is an important counterexample: A outperformed B there.

The following prompt means and differences come from the saved native analysis. A C cell stays missing unless both repeats exist; one available repeat is not substituted for the missing one.

| Source, abbreviated prompt | A utility | B utility | C utility | B−A | C−B |
|---|---:|---:|---:|---:|---:|
| `curated-95`: safest lock combination | 1.680435 | 1.792464 | 1.792464 | 0.112029 | 0.000000 |
| `curated-2`: Easter romcom | 2.475393 | 8.826143 | — | 6.350750 | — |
| `curated-80`: well-received book | 2.016522 | 8.043276 | 8.389313 | 6.026754 | 0.346037 |
| `curated-21`: loyal dog's name | 4.775459 | 6.420610 | 6.843615 | 1.645151 | 0.423005 |
| `curated-62`: science publication | 2.016522 | 8.445801 | 8.260349 | 6.429278 | -0.185451 |
| `curated-63`: influential nineteenth-century people | 2.016522 | 7.902223 | — | 5.885700 | — |
| `curated-17`: grocery-list item | 2.691099 | 7.981003 | 7.926516 | 5.289904 | -0.054487 |
| `curated-29`: birthday gift | 1.792464 | 6.731174 | — | 4.938709 | — |
| `curated-36`: vacation | 1.792464 | 7.056351 | 7.011536 | 5.263886 | -0.044814 |
| `curated-15`: invention | 3.203263 | 7.700677 | 7.810083 | 4.497414 | 0.109406 |
| `curated-96`: strong four-character password | 6.711526 | 3.210945 | 4.313538 | -3.500581 | 1.102593 |
| `curated-41`: US city/quality of life | 1.792464 | 5.786798 | 5.478528 | 3.994333 | -0.308269 |

No pooled C effect or complete-case winner is reported. Among valid B/C pairs, the measured difference includes fresh-judge variation as well as ordering: one pair's grouping changed on unchanged texts (password repeat 2, B four groups versus C eight), and **38 of 151 shared head answers** received different scores when judged afresh. Neither grouping is established as ground truth by this study. Preserve the native measurements and qualify attribution; this is not permission to pick favorable judgments, reuse B scores retrospectively or activate a new calibration project.

## Counts, costs and liabilities

| Logical slot status | Count |
|---|---:|
| `ok` | 987 |
| `invalid_rank` | 4 |
| `not_needed_nonhead` | 285 |
| `skipped_invalid_rank` | 44 |
| **Full planned denominator** | **1,320** |

The 991 attempted slots each have exactly one intent and one known result. The 329 undispatched slots are fully explained by nonheads or failed-rank dependencies. There are no unclassified slots, unknown deliveries or pending requests. Native assessment status is scored for every one of the 68 delivered portfolios; the four missing C orders are explicitly `invalid_rank` in coverage.

| Unique request role | Calls | Accounted USD |
|---|---:|---:|
| Answers | 480 | 1.755108 |
| Plans | 24 | 0.200598 |
| Rankings, including four invalid outputs | 24 | 0.301026 |
| Native grouping | 68 | 0.066448 |
| Native head quality | 395 | 3.660324 |
| **Total** | **991** | **5.983504** |

F1 contributed **28 calls / $0.210174**; expansion added **963 calls / $5.773330**. All numbers are usage-derived conservative public-price accounting, including the frozen inherited-premium treatment and per-request rounding. They are **not independently reconciled invoices**; `experiment_api_spend_micro_usd` remains `null` in the native summary. Outstanding reservations are **$0**. No budget stop occurred under the authorized $125 cumulative ceiling. Unused headroom is not authority for new work after this closed worklist.

For candidate comparison, A's complete generation cost is **$0.635220**, B's generation/planning cost **$1.320486**. C's full candidate cost remains missing because its required outputs are incomplete; all actual rank spending is nevertheless counted above. C's attributed cost includes its B parent, while the unique ledger charges each B request once. Assessment spending is separate from the generation-cost tie-break.

Per-request token categories, reasoning/thinking counts where returned, stop reasons, request/message IDs and latency are retained in the index/raw journal. Native latency totals and ranges are in analysis.json; they are cumulative request measurements, not a guaranteed end-to-end runtime. Thinking/output are billable even though thinking-block text is not retained.

## Evidence, replay and acceptance

The [full evidence packet](evidence/phase2b-expansion/report/README.md) contains:

- [All 1,320 slot outcomes](evidence/phase2b-expansion/report/slot-outcomes.json), linked to canonical journal event indices/hashes and saved visible responses.
- [All 72 order outcomes](evidence/phase2b-expansion/report/orders.json), native metrics/head scores/missingness and valid C/B permutation mappings.
- [Five exact role profiles](evidence/phase2b-expansion/report/settings.json), frozen study, plans/answers/rank outputs in the journal, all 68 portfolios/assessments/native exports, four failure records, both grants, first review and final snapshot.
- Seven unchanged native public reports, sanitized actual launch/runtime records, an offline packaging recipe and [the verified archive](evidence/phase2b-expansion/report/phase2b-report.zip).

[Package verification](evidence/phase2b-expansion/report/package-check.json) passed **314 ZIP members**, byte inventory, CRC and SHA-256 checks. The tracked 316-file packet matches the generated packet byte for byte. Archive SHA-256 is `8364bc3a0c4d8f98aa1d60890c92c37b6135bcf47c63ba454623a99441201d2e`.

The existing native report and a separate replay reproduced all seven public files exactly, including decision identity `6cc0d324f9be864a9747140c4d6bd41a42606f31e38ee772e5c35aac62e381fc`. Reporting/packaging used network-disabled pinned containers, no new provider calls, no SDK clients and no credential lookup. The immutable first 28-event-pair prefix, first review, 70 gate-bound files, 26 source files and launcher remain intact; staged authority and usage arithmetic reconcile. See [independent authority review](evidence/phase2b-expansion/live-authority-review.json) and [independent outcome review](evidence/phase2b-expansion/live-outcome-review.json).

The host exited normally with zero stderr bytes, and its owned provider container is no longer running. The frozen summary still labels the run `first-block-complete` because that earlier block remains valid. This historical label and exit code do not establish full benchmark completion; final coverage and `native_complete=false` govern this closeout.

Canonical evidence excludes raw keys, credential-binding/fingerprint material, host environment values, provider streams and complete SDK objects. It retains visible text and declared metadata; Anthropic thinking blocks and explanatory quality-judge rationales were not saved. Credential scanning is bounded to structured fields and recognizable token patterns, not a universal nonsecret guarantee. The archive is a continuation packet for the retained workspace/pinned environment, not a standalone installer.

To reproduce the closed native report without generation or keys, use the unchanged kit from this project, choosing a new output directory:

```powershell
.\phase0.ps1 run phase2-release replay --study /results/phase2-release-r018/release/study.json --run /results/phase2-release-r018/38132ee3a935af4ac975c3fda84154d1a85b1bcb510925f409993a15d3103d8b/live --cutoff 2026-10-28T12:12:19Z --output /results/phase2-release-r018/reports/live-full-replay-next
```

One offline packaging attempt rejected its own recipe's private-key-marker scanner literal before creating the output packet. Its recipe/runtime evidence remains under `runs/phase2b-expansion-closeout`; the corrected packaging-only recipe passed. This caused no model calls, scientific change or evidence mutation.

## Decision and next step

**Accept the limited execution closeout; retain the original benchmark decision as inconclusive and select no seed.** The report is usable even though the full three-condition completion criterion was not met. The complete A/B evidence supports planning as a promising development procedure, with a clear password counterexample and extra inference cost. It is not a formal promotion to the next phase under the old seed rule.

The next bounded specification should address the **reranking output contract**, using the saved evidence: all four failed outputs already contain valid permutations, so diagnosing this defect requires no new answer generation. Decide prospectively whether to use a versioned deterministic format policy or stricter provider output constraints, how compatible saved evidence may be reused, and what fresh validation or native judgments are required. Preserve this strict C condition's failures; do not silently extract orders, replace four calls or loosen selection until something wins. The observed judge variability also limits any later claim about reranking's incremental value.

No corrective experiment, additional spending, human collection, MuCE/CrPO work, new model/strategy or Phase 3A adaptation starts from this report. After the fixed-procedure decision is resolved, refresh Phase 3A concretely before its genuine native Harness² one-step comparison; successive recursion and held-out confirmation remain later phases. Original Buddha2 and every frozen parent artifact remain untouched.
