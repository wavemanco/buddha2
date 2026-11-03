# P2B-E — Remaining fixed-strategy pilot and benchmark decision

Definition **1.0**, 2026-10-28, America/Los_Angeles. **Defined; expansion is unstarted and not authorized.** The current request completes the next planning step after P2B-F1. It supplies no expansion grant, credential access or paid-call authority.

This is one bounded execution-and-reporting block within Phase 2B. It uses the completed kit; there is no planned new engineering prerequisite or sequence of per-task approvals. The 23 task/repeat units below are its internal worklist. All models, methods, tasks, scoring, failure rules and selection policies remain frozen.

This addendum supplies the current continuation definition without editing the 70 gate-bound historical files. [P2B-F1](PHASE2B_F1_REPORT.md), its `eb0a3b3` closeout and all earlier specifications remain unchanged. The old main documents' historical “unstarted” statements do not undo F1's observed completion.

## Objective

Finish the prespecified development comparison: **does fixed planning improve native NoveltyBench utility over ordinary sampling, and does reranking the planner's unchanged answers improve it further?** Produce a benchmark-specific fixed procedure to carry into the later authentic Harness² adaptation comparison, or an explicit incomplete/inconclusive decision.

This compares complete procedures, including their different inference costs. It does not establish compute-controlled attribution to planning, human preference, held-out performance or recursive improvement. Ordinary sampling can legitimately be selected.

## Scope and immutable starting point

- Release/study: `38132ee3a935af4ac975c3fda84154d1a85b1bcb510925f409993a15d3103d8b`, `runs/phase2-release-r018/release/study.json`.
- Source bundle: `5909e90bc49a3251ba431c8ccf677cdc02a2827f36271d9b0abed3a5421ef22c`; frozen image `sha256:585a5539c6091592258ec19d0bf8e216b189405f95766b167df0d2e88e251366`; unchanged source, launcher, locks and upstream pins.
- Preserve the single canonical live journal and its **28 completed attempts/27 permanently unnecessary first-block nonheads**, $0.210174 accounted upper bound and zero liability.
- Preserve approved first review `live-first-review-001`, identity `061dc60298827ef9bc43ccd3d6dfd59f8ea9a167278ebe3680cf3d42590ce004`, and first authority `abf45dbabb5f9689fe8d2aa81273be654f5a87220317f804f337e2789ec81e39`.
- Execute only the **23 existing `checkpoint=expansion` blocks**, in their frozen order. These finish the same **12 development prompts × two repeats**, with the first repeat of the first prompt already completed. No task selection is reopened.

| Frozen source, abbreviated label | Remaining repeats, in order |
|---|---|
| `curated-95`: safest four-digit lock combination | 2 |
| `curated-2`: Easter romcom in rural Kansas | 1, 2 |
| `curated-80`: well-received book | 1, 2 |
| `curated-21`: loyal dog's name | 1, 2 |
| `curated-62`: reputed science publication | 1, 2 |
| `curated-63`: influential nineteenth-century people | 1, 2 |
| `curated-17`: memorable grocery-list item | 1, 2 |
| `curated-29`: twenty-fifth-birthday gift | 1, 2 |
| `curated-36`: best thing about vacation | 1, 2 |
| `curated-15`: invention making life interesting | 1, 2 |
| `curated-96`: strong four-character password | 1, 2 |
| `curated-41`: US city with poor quality of life | 1, 2 |

These are labels, not edited prompts. Exact task IDs, prompt hashes and all 23 blocks are bound in [the worksheet](../../../evidence/phase2b-expansion-definition-v1/worksheet.json) and frozen study. This cached public curated material is development data, potentially exposed in legacy work. No WildChat, new confirmation rows or held-out labels are opened.

## Procedures and exact settings

| Condition | Work per task/repeat |
|---|---|
| A: ordinary sampling | Ten fresh independent regenerations with the original prompt and shared minimal instruction. No angles, sibling answers or score feedback. Preserve request order. |
| B: fixed planner + generation | One ten-angle plan, then ten fresh regenerations, each conditioned on the original prompt and its assigned angle only. Preserve angle order. |
| C: isolated reranking | One in-context permutation of that B portfolio's saved IDs/texts. No new answers, rewriting, filtering or deduplication; identity permutations are valid. |

Repeat 1 generates A then B; repeat 2 generates B then A. C follows both generated portfolios. Native assessment follows in A/B/C order: a fresh grouping for each order, then quality calls for that order's first answer in each returned group. Do not reuse B's assessment for C. Earlier outputs, scores or this first-block diagnosis do not guide later generation. No tuning between blocks.

| Role | Unchanged requested model and API | Controls |
|---|---|---|
| Answers, plan, rank | `claude-sonnet-5-5`, Anthropic Messages | Adaptive thinking, effort `low`, `max_tokens=4096`, `service_tier=standard_only`, `inference_geo=global` |
| Native grouping | `gpt-5.6-luna`, Chat Completions | Frozen strict grouping JSON schema; effort, output cap, temperature and API seed omitted |
| Native head quality | `claude-opus-5`, Anthropic Messages | Adaptive thinking, effort `high`, `max_tokens=16000`, frozen strict score schema; service tier/geography omitted |

No temperature/top-p/top-k override, tools, web or conversation memory. Grouping's documented default effort is medium, but an omitted parameter is not an explicitly requested or observed effort. Anthropic caps include thinking plus visible text. Keep the exact native NoveltyBench v1.1 prompts, strict folding and arithmetic, patience 0.8, and `seed=None` ordering. This is a native-metric study, not a leaderboard submission. No newer-model substitution or SDK/upstream upgrade.

The same direct public PAYG profile and AM-1 controls apply: 5,952-byte serialized-body caps for answer/plan/quality, 61,952 for rank/group; no truncation to force admission. These are payload safeguards, not certified provider-token counts. The old 8k/64k bookkeeping fields are not token guarantees. One request in flight, 90-second transport timeout, **zero retries, repairs, fallbacks or replacements**. A timeout does not establish provider termination or free billing.

## Work and call limits

| Remaining work | Count |
|---|---:|
| Task/repeat blocks | 23 |
| Generated A/B portfolios; derived C permutations | 46; 23 |
| Answer / plan / rank requests | 460 / 23 / 23 |
| Fresh native grouping requests | 69 |
| Native quality requests, if all orders succeed | 69–690 |
| **New provider requests for successful remaining execution** | **644–1,265** |

Each successful block uses `25 + hA + hB + hC` calls, with 1–10 heads per order. Failures or a financial stop can produce fewer. The full coverage denominator remains **1,320 logical slots**; the 27 earlier nonhead slots cannot become fresh calls. Including F1, a successful full pilot would therefore use **672–1,293 actual calls**, not 1,320 or `1,320 − 28` new calls.

## Cost: measured basis, sensitivity and proposed ceiling

**Definition work: $0 API spend. No model calls are part of this planning step.** No new installation, rented compute, paid dataset or annotator is needed. Ordinary assistant-session fees, electricity and voluntary human time are outside the API worksheet.

F1 measured a $0.176382 nonquality cost per block and $0.011264 mean cost per quality head, under conservative public-price accounting. The three quality calls used 977/931/931 input tokens, 155/227/279 total output tokens and no cache tokens. One prompt and three judgments do **not** establish a representative expected cost. The following are conditional scenarios, not a forecast, confidence interval or upper bound.

They repeat F1's generation/grouping costs and quality input/cache mix across the remaining blocks, varying only head counts and quality output. Output includes thinking. All figures below are **additional cost**, rounded to cents; add **$0.210174** for cumulative pilot cost.

| Billable quality output per head | 1 head/order | 5 heads/order | 10 heads/order |
|---|---:|---:|---:|
| Observed pattern, mean 220⅓ tokens | $4.83 | $7.94 | $11.83 |
| 1,000 tokens | $6.31 | $15.34 | $26.62 |
| 4,000 tokens | $12.01 | $43.80 | $83.55 |
| 6,000 tokens | $15.80 | $62.78 | $121.50 |
| 8,000 tokens | $19.60 | $81.75 | $159.45 |
| 16,000-token cap stress | $34.78 | $157.65 | $311.25 |

The observed-pattern range is a useful low-usage planning case; heavier reasoning can dominate it. Longer generated answers can also change generation, ranking and grouping costs, which this table holds fixed. Reaching an output cap may cause truncation/non-scored evidence. Expensive rows would stop before their hypothetical completion under the proposed ceiling. Do not count mock usage as a price forecast.

Arithmetic, including per-request rounding, is in the worksheet. For output `O`, its micro-USD formula is `23 × [176382 + h × (ceil((977×5500 + O×27500)/1000) + 2×ceil((931×5500 + O×27500)/1000))]`. The observed row instead uses the actual three quality costs summing to 33,792 micro-USD per block.

**Proposed expansion ceiling: retain $125 cumulative, including F1. It remains unapproved.** After F1, this would leave **$124.789826** of accounting headroom. It is not $125 additional, $125 plus the earlier $20, or guaranteed spend. A smaller explicitly approved expansion ceiling may be used within the frozen $20–$125 cumulative policy, with its greater risk of early stopping disclosed.

The unchanged admission reservations are **$2.540960 per Sonnet request, $1.661880 per grouping request, and $11.44 per quality request**. Before dispatch, settled cost + unresolved liability + the next reservation must fit the active cap. With a $125 ceiling and no liability, another quality request cannot start after settled spending exceeds **$113.56**. A hypothetical final cost fitting below $125 does not guarantee completion: the 10-head/6k-output case totals about $121.71 cumulative, but its late quality calls cannot all satisfy that reservation rule. Known usage releases/replaces reservations; unknown usage retains liability and halts. No automatic top-up or reserve reduction is included.

Official rates were searched and opened again on 2026-10-28: Sonnet $2/$10, Luna $0.20/$1.20 and Opus $5/$25 per million ordinary input/output tokens. Cache and inherited geographic categories remain part of the frozen conservative envelope. See [Sonnet specifications](https://platform.claude.com/docs/en/models/sonnet-5-5/overview), [Luna pricing/limits](https://developers.openai.com/api/docs/models/gpt-5.6-luna), [Opus specifications](https://platform.claude.com/docs/en/models/opus-5/overview), [Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing) and [OpenAI pricing](https://developers.openai.com/api/docs/pricing). Public documentation and F1's accepted requests are not a continuing account/invoice guarantee. Recheck changed profile/prices before dispatch; no paid probe is authorized.

## Deliverables and usable output

1. **Completed or bounded-stop canonical evidence:** all 48 generated-portfolio, 24 permutation and 72 ordered-assessment statuses across the full pilot; preserved F1 prefix; visible plans/answers/rankings, stable IDs, exact settings/requested-returned models, usage, stop reasons, latency, failures and liabilities. Missing scores remain missing.
2. **`PHASE2B_REPORT.md`:** whole-pilot per-prompt paired results, coverage, role settings/sampling, costs, failures, limitations and the benchmark decision. Every outcome remains inspectable through the tracked raw evidence; no hidden-thinking or judge-rationale claim. Separate historical shared F1 cost from marginal expansion and total cost.
3. **Tracked `evidence/phase2b-expansion/report/` packet:** native public report/replay, whitelisted canonical journal/outputs/assessments, exact artifact manifest, verified archive, technical closeout and reproduction instructions. Exclude API keys, credential-binding material, host environment values and provider streams. Preserve the earlier F1 report/packet.
4. **Usable fixed procedure and next-phase handoff:** reference the selected unchanged procedure hash, or explain why none is eligible. Record optional human evidence as absent/not-required. Recommend a concrete Phase 3A definition or defect-resolution decision without starting it.

Use the existing `phase2-release report` / `replay` routes, with new output paths such as `reports/live-full` and `reports/live-full-replay`; package their saved evidence without generation. The F1-only `build_report.py` intentionally rejects expanded journals and is not the full-pilot reporting route. Final report/packet commits belong in this repository; no external publishing or push is included.

## Analysis and completion criteria

Primary contrasts remain **B−A** and **C−B**. Average the two repeats within each prompt, then average the 12 prompt means equally. Report per-prompt effects and descriptive means/ranges, native utility/distinctness, head/first-answer quality with scored coverage, generation/assessment costs, latency and failures. The independent task count is 12, not 480 answers or 72 orders.

For a **complete benchmark decision**, require all 72 comparable scored native orders, all expected portfolios/permutations and traceable slots, valid provenance/native arithmetic, exact saved-evidence replay and reconciled accounting with zero unresolved liability. Preserve refused/empty/truncated answer outcomes according to the frozen contract; no favorable-score threshold applies. Select highest **exact** mean native utility; exact ties use lower attributed generation/planning/ranking cost, then A/B/C simplicity order. C includes B's generation plus ranking; the unique ledger charges B once. Assessment cost is reported but excluded from that tie-break. No new gain floor, significance test or practical margin is introduced after F1.

Completion evidence must establish:

- All 24 blocks/72 orders accounted for, all C text/ID permutations valid, no undeclared calls or replacements, and the F1 prefix unchanged.
- Required native coverage and the saved decision's `native_complete=true`, `status=complete-development`, exact selection rule and procedure identity. Human status is `not-required` for this track.
- Source/gate/launcher identity preserved; model/settings/usage/accounting checked; no unresolved reservations.
- Exact native/coverage/analysis/decision replay without SDK construction, key access or new provider calls; archive inventory/hash/CRC verification and a committed usable report.

**Limited execution closure** is also a usable report: every attempted/unattempted/dependent slot classified, bounded-stop/failure reason preserved, decision inconclusive and no seed when required native evidence is missing/non-scored or liability unresolved. That does not establish full pilot completion. A complete valid comparison finding no planning/reranking benefit is instead a legitimate negative development result.

Do not infer success from process exit 0 or the summary string `first-block-complete`: an incomplete expansion may retain that label because F1 remains valid. Check final coverage, native completeness, decision and accounting directly. No complete-case selection, sample replacement, score repair or alteration of F1 follows from an unfavorable result.

## Exclusions and stop/review criteria

Out: recursive adaptation or experience accumulation, second generator/model-effort sweep, Lenny/Lluminate/new strategy families, MuCE/CrPO/frontier evaluator work, Route H/human collection, new benchmark/upstream versions, held-out confirmation, leaderboard submission, UI/platform work and generic infrastructure. Later human inputs may attach as a separately versioned assessment/decision without rewriting this benchmark root; they never block it or automatically duplicate the matrix.

Stop globally on unknown delivery/usage, financial admission failure, changed/unsupported authority/profile/source/runtime, input/artifact/request-contract failure or unexpected integration error. Retain unknown liability; restarting, changing directories/keys or granting more money does not settle it. An observation timeout alone is not terminal: inspect the same owned process/container before any resume, and never run two launchers.

Known settled content failures follow the existing policy: preserve answer refusal/empty/truncation; an invalid B plan skips dependent B/C work; invalid rank skips C; malformed/refused/non-scored native results remain visible while independent work may continue. Do not invent a new “stop on every malformed response” rule. These outcomes can make the final benchmark decision inconclusive. No per-block favorable-result gate or interim method change is added.

Stop at the end of this worklist regardless of remaining funds. A partial run receives a report; corrections, comparability changes or extra spending require an explicit decision. Any effective source/science change gets a new identity and compatibility assessment; never rewrite the frozen kit or consumed outcomes to pass.

## Entry and what happens next

After this definition is reviewed, **explicit expansion authority and its cumulative ceiling** are still needed. Then use the already implemented grant-template/inspected launcher: new expansion grant ID, same study/journal, current predecessor authority and approved first-review hashes. The first-stage grant cannot dispatch expansion. Reconfirm the supported profile/current prices and re-enter the **same credential pair** through masked prompts; do not reuse the one-time F1 entry script, read ambient keys or rewrite credential fingerprints. No auth/model-list/token-count/warm-up calls are added.

Execute the unchanged remaining worklist once, report/replay/package/commit, and stop. After a complete benchmark decision, refresh **Phase 3A's** objective, scope, deliverables, exclusions, completion criteria, exact native Harness² one-step setup and budget-comparable fixed control before starting it. Actual successive recursive refinement remains Phase 3B, followed by separately scoped held-out confirmation. None starts automatically.
