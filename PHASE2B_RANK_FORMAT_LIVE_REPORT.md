# P2B-N — Completed live normalization follow-up

Completed 2026-10-28; frozen report cutoff **2026-10-28T18:55:44Z**. **All four new orders are scored, all 72 comparison rows are complete, and the frozen development rule selects C-N.**

The run made **43 known provider calls**, with **$0.367448 additional accounted cost**, zero failures, retries, pending requests or unresolved liability. The inspected launcher exited successfully. The original strict-C study remains inconclusive; its failures, scores, decision and report are unchanged.

## Result and interpretation

The comparison averages two repeats within each of the 12 development prompts, then gives each prompt equal weight. The independent sample size is 12 prompts. C-N reorders B's existing answers; it creates no new answers.

| Condition | Scored orders | Mean native utility | Mean distinct groups | Attributed generation/planning/ranking cost |
|---|---:|---:|---:|---:|
| A: ordinary independent sampling | 24 | 2.747011 | 2.083333 | $0.635220 |
| B: fixed planner + generation | 24 | 6.658122 | 7.916667 | $1.320486 |
| C-N: original ranking inference + N1 | 24 | **6.797187** | 8.083333 | $1.621512 |

The paired mean **C-N−B difference is +0.139065 utility points**, about 2.09% of B's mean. B−A is +3.911111. C-N improves six prompts, declines on five and ties on one. Its attributed generation/ranking cost is about 22.80% above B; the predeclared selection rule prioritizes utility, then cost only for a tie. No gain threshold or significance requirement was added after observation.

**This is an exploratory, post-hoc benchmark-track starting point.** It does not establish a general reranking advantage. N1 was designed after inspecting the original format failures, and 68 of the 72 assessments are reused historical evidence. The password task contributes about 66.1% of the net C-N−B mean gain and includes the previously documented identical-content grouping discrepancy. Reusing those judgments creates no independent replication.

Fresh judging also shows visible variability. Across the four newly assessed orders, B and C-N retain the same first answer and the same semantic partition, but **12 of 39 shared-head quality scores differ**. The first score changes from 8 to 9 for the people task and from 7 to 8 for gift repeat 2 despite unchanged first-answer text. Order changes, fresh judge scores and earlier grouping variability are therefore mixed into the observed comparison. The fixed rule's selection is valid for this development view; it is not clean evidence that ranking alone caused the gain.

## What was reused and newly measured

All 24 saved rank responses pass the frozen, score-blind `rank-format-N1` policy. Twenty normalized orders exactly match the original valid C orders. Four new derived identities preserve their original B task, response IDs, texts and statuses, and link the saved rank result, parent B, N1 procedure and new study.

The comparison references 48 original A/B assessments and 20 original C assessments on their original portfolio hashes. Only the four new C-N orders received fresh native judgments. No original assessment was retagged or assigned to another portfolio hash.

| Newly assessed order | Repeat | New distinct | Original B utility | New C-N utility |
|---|---:|---:|---:|---:|
| `curated-2`: Easter romcom in rural Kansas | 1 | 9 | 8.729347 | 8.682359 |
| `curated-63`: influential nineteenth-century people | 1 | 10 | 7.907820 | 8.097577 |
| `curated-29`: twenty-fifth-birthday gift | 1 | 10 | 6.808591 | 7.134935 |
| `curated-29`: same gift task | 2 | 10 | 6.653756 | 7.113446 |

All 44 declared slots have a disposition: **43 successful calls and one unnecessary nonhead** (`p2-cce2c41315048eab5ffb1d45.quality.09`). There were no malformed/refused/truncated judgments, unknown outcomes, budget stops, fallback models, replacements or extra answer/plan/rank calls.

## Models, controls and accounting

| New role | Calls | Requested and returned model | Unchanged request controls |
|---|---:|---|---|
| Native grouping | 4 | `gpt-5.6-luna` | Chat Completions and native strict grouping schema; effort, output cap, temperature and seed omitted |
| Native head quality | 39 | `claude-opus-5` | Adaptive thinking, effort `high`, `max_tokens=16000`, native strict score JSON schema; service tier and geography omitted |

All grouping responses ended with `stop`; all quality responses ended with `end_turn`. All returned model IDs match the requests exactly. The saved quality outputs contain scores, not model-internal reasoning. Output usage includes billable thinking; requested effort does not identify an observed thinking budget.

Historical generation/planning/ranking used `claude-sonnet-5-5`, adaptive thinking, effort `low` and the original 4,096-total-token controls, as documented in the [unchanged parent report](PHASE2B_REPORT.md). No new Sonnet calls occurred. Native NoveltyBench v1.1 prompts, schemas, folding and arithmetic remain pinned, with patience 0.8 and delivered ordering (`seed=None`). SDK retries remain zero, HTTP timeouts 90 seconds and calls serialized.

| Accounted component | Amount |
|---|---:|
| Four new grouping calls | $0.003516 |
| 39 new quality calls | $0.363932 |
| **New marginal total** | **$0.367448** |
| Shared original study, counted once | $5.983504 |
| **Combined Phase 2 evidence total** | **$6.350952** |
| Approved additional ceiling | $30.000000 |
| Unresolved reservation | $0.000000 |

Amounts are conservative usage-based public-price accounting, not verified account invoices. Independent integer-ceiling recomputation matches every new request's recorded cost. The unchanged admission reservations were $1.661880 per grouping and $11.44 per quality request; those reservations were released on known settlement. The unused cap does not authorize another block.

C-N's attributed $1.621512 includes B's original planning/generation plus **all 24 original rank calls**, including the four strict failures. Historical costs and reused judgments are not charged twice. Synthetic mock accounting is excluded from every real spending total above.

## Identity, preservation and verification

The [definition](PHASE2B_RANK_FORMAT_DEFINITION.md), [whole-block approval](evidence/phase2b-rank-format-v1/authorization.json) and [frozen offline checkpoint](PHASE2B_RANK_FORMAT_REPORT.md) govern this follow-up. Implementation is unchanged from commit `8b76fd2`; no runtime source, model profile, parser, threshold or budget changed during or after the live run.

| Record | SHA-256 |
|---|---|
| New study | `0bbe532dd0b5e065f88d0f352538a10dbe2d1b5c0816856f6c3b518a2a00d27e` |
| Effective source | `c60b28e81e905fd6ac0a5bae3cc1b95d65e197482710927dd7135f79ed145b03` |
| Approved live grant | `1ec88376aaee918e3783a57883d9c20cfdbd1105d0ca82283c4181f45ef9ddbb` |
| New decision | `5c2ddcbd434f53209f4245c519f9479229c6b06e6dec2b9043669c5a4f338dea` |
| Selected C-N procedure | `16cd0c8b829c7147b51ff76bd38a350686ca1b3bf53e308cc4b76acbf0747de0` |
| Unchanged original inconclusive decision | `6cc0d324f9be864a9747140c4d6bd41a42606f31e38ee772e5c35aac62e381fc` |

Launcher `398ee1e4becf4ca58d5214a4bc9cba4e` records exit code 0 and zero stderr bytes. Its actual image, mounts, source/grant bindings and pre-key handshake match the reviewed release. Provider stream content was not retained; raw keys were not written. The canonical new journal is under `runs/phase2-am1/<new-study-sha>/first-block/journal`.

The frozen reporter replayed all reused and new native evidence twice in the pinned, network-disabled runtime. The two seven-file reports are byte-identical, no provider transport was constructed, and all 108 canonical live-run files remain byte-identical after replay. The live entry point was not restarted. Independent standard-library arithmetic reproduces the means, decision, role counts and per-request costs. The 28-test offline gate remains recorded; no runtime code change required repeating it.

All 962 previously tracked files, including the original strict report and offline checkpoint/packet, remain unchanged. The protected original `C:\Users\arvik\code\buddha2` was not accessed or modified. The [live closeout](evidence/phase2b-rank-format-v1/live-v1/closeout.json), [independent arithmetic](evidence/phase2b-rank-format-v1/live-v1/independent-arithmetic.json), [native report](evidence/phase2b-rank-format-v1/live-v1/report/PHASE2B_RANK_FORMAT_REPORT.md), [request/settings index](evidence/phase2b-rank-format-v1/live-v1/report/protocol.json) and [verified live evidence archive](evidence/phase2b-rank-format-v1/live-v1/evidence.zip) retain the complete result. The original strict C remains 20/24, inconclusive and without a seed; this separate C-N decision does not rewrite it.

## Exit and reuse

P2B-N is complete. Stop at this report: no additional paid calls, strategy/model sweep, human collection, CrPO/MuCE work, held-out confirmation or recursive adaptation follows automatically. Human review remains optional and did not block this benchmark-track decision. Actual Harness² recursive improvement is still untested.

The next separately defined step can review C-N as the exploratory seed for Phase 3A, with an authentic Harness² adaptation step and a budget-comparable fixed control using the same declared techniques. Refresh that phase's concrete objective, scope, deliverables, exclusions, completion criteria and budget before starting it.

Saved-evidence replay requires no credentials or providers. In the pinned offline runtime, use a fresh output destination:

```text
python -B -m followups.rank_format_v1.cli report --study /results/phase2b-rank-format-v1/release-r2/study.json --grant /results/phase2b-rank-format-v1/release-r2/grant-live.json --output /results/phase2b-rank-format-v1/live-replay-next
```
