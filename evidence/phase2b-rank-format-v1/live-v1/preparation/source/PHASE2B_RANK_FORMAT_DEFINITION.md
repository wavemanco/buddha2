# P2B-N — Saved-rank normalization and development comparison

Definition **1.0**, 2026-10-28, America/Los_Angeles. **Defined only; implementation, normalized output publication and further paid judging are unstarted and unauthorized.** The user's “proceed” follows the proposed next step of defining this follow-up. It does not amend the completed study or supply another grant.

This is one bounded block: implement/test the offline transformation and evidence reuse, then—if the whole block and its new budget are authorized—assess only four new orders and publish the separate result. The offline checkpoint is an internal gate with a usable output, not another planned preparation project or per-task approval sequence.

## Objective and usable result

Determine whether a deterministic, score-blind format policy can obtain one valid machine-readable order from each of the **24 saved rank responses**, without inventing IDs or choosing between conflicting orders. Produce a reproducible comparison of **A, B and C-N**, where C-N means the original rank inference followed by this normalization policy.

This is a **post-hoc development fork within the benchmark track**. It is not completion, correction or rescue of the original strict-C experiment. That experiment remains inconclusive with four failures and no seed; its [report](../../../../../docs/phases/phase-2/PHASE2B_REPORT.md), decision `6cc0d324f9be864a9747140c4d6bd41a42606f31e38ee772e5c35aac62e381fc` and all recorded scores remain unchanged.

The offline checkpoint delivers a working normalizer, all-24 input/disposition manifest, exact reuse proofs, four separately derived unscored outputs, negative tests and a mocked judging/reporting path. A completed paid portion adds four native assessments and a separately identified retrospective development decision. Neither establishes prospective format reliability, held-out creativity or recursive improvement.

## Fixed scope and inputs

Parent: closed study `38132ee3a935af4ac975c3fda84154d1a85b1bcb510925f409993a15d3103d8b`, report commit `95ac4e2e2bdc3ceb5c6749d0eaabd3d22eb5c799`, immutable tracked evidence under `evidence/phase2b-expansion/report/`.

Use all 24 raw, known, settled rank results and their original B parents. Apply one policy to every response, including the 20 already accepted under strict C. The already exposed corpus is expected to yield 20 unchanged orders and four newly derivable orders. That is an acceptance expectation for these inputs, not a claim of generalization or permission to special-case them.

| New native-assessment candidate | Repeat | Original strict failure |
|---|---:|---|
| `curated-2`: Easter romcom in rural Kansas | 1 | Prose before one JSON order |
| `curated-63`: influential nineteenth-century people | 1 | Two identical orders separated by correction prose |
| `curated-29`: twenty-fifth-birthday gift | 1 | Same repeated-order pattern |
| `curated-29`: same gift task | 2 | Same repeated-order pattern |

The [planning worksheet](../../../../phase2b-rank-format-definition-v1/worksheet.json) binds exact input/parent IDs, hashes and proposed reuse references. No new prompts, responses, plans or rank calls are needed. Do not access WildChat, confirmation rows, human forms or new corpora.

## Normalization policy N1 — fixed before implementation

The normalizer receives only the saved visible rank text and its ten parent response IDs, plus provenance needed to validate that input. It must not consume native scores, rankings chosen by another model, human judgments or task-based preferences.

1. Require a known, accounted response from the declared rank role/model, with `end_turn`, the exact original parent reference and ten distinct parent IDs. Reject refused, truncated, empty, unknown or mismatched input. Require strict UTF-8 text of at most **65,536 bytes**.
2. Scan left to right, with JSON string/escape awareness. Outside complete objects, permit prose and code fences. An opening `{` starts a strict object candidate; do not skip malformed candidates to hunt for a later valid object. An unmatched structural delimiter, or an outside `[`/`]`/`}`, rejects the response. Do not unwrap arrays or search inside an invalid enclosing object.
3. Bound candidate-object structural nesting to **two levels** (object plus its ID array) and the number of candidate objects to **16**. Enforce these limits while scanning, before unbounded recursive parsing. Reject invalid encoding, excess size/depth/count and malformed boundaries explicitly.
4. Every candidate must be exactly `{"order": [ten strings]}`. Reject additional fields, duplicate decoded keys, nonfinite constants, wrong types, duplicates/missing/foreign IDs or any deviation from an exact parent-ID permutation. Equivalent JSON escaping is allowed only when it decodes to the exact ID; no trimming IDs, case folding, Unicode normalization, typo correction, sorting or ID reconstruction.
5. Require at least one candidate, and require **all candidates to decode to the same ordered-ID tuple**. Repeated identical objects may collapse. Two distinct permutations, or a valid object plus any invalid object, reject the entire response. Never select first, last, majority, a claimed “correction,” or the most useful order.
6. Ignore surrounding prose as nonauthoritative. This establishes a unique machine-readable order under N1; it does not establish the author's intention if prose contradicts that object. No LLM adjudication or semantic interpretation of the prose is added.

Record the raw response/result hashes, original strict status, policy/code identity, candidate offsets and diagnostics, normalized-order hash or explicit rejection reason. Offsets use Unicode code-point indices into the retained raw text. Do not overwrite raw text or fabricate a canonical JSON provider response. The normalized record is a **derived artifact**, not another model outcome.

The observed rank texts span 371–1,576 UTF-8 bytes. Those observed sizes and seven already inspected valid fragments do not validate arbitrary future inputs. If implementation reveals a defect in N1, stop and version an amendment before further judgments; do not silently adjust the policy until every observed case passes.

## What we will build and reuse

**Small owned implementation:** the normalizer, a cross-study derivation/reuse validator, a four-order native-assessment entry point and a separate comparison/report. Use standard-library parsing and existing artifact/accounting/native-evaluation primitives; add no dependency, generalized cache, benchmark framework or new generation engine.

Keep new code outside the frozen 26-file package, or deliberately create and verify a new release if a change there proves essential. Leave the original loader, strict rank parser, source/launcher, study, journal, decision and reports byte-identical. The current full-pilot controller cannot simply be pointed at this new scope: it reconstructs strict C and requires its original study/worklist. Do not weaken those checks.

The existing generic `phase2_dispatch.Dispatcher`, AM-1 control policy, pinned direct SDK transport and `NativeAssessment` offer the intended reuse seams. The generic AM-1 live boundary requires its own fixed study-derived journal path; retain that canonical-path guard for the new identity rather than redirecting or appending to the closed release journal. A narrowly adapted host entry must preserve actual image/mount/source/grant inspection and the pre-key handshake. All adapter, binding, mock and publication work belongs to this block, not an unnamed prerequisite afterward.

### Explicit evidence reuse

| Evidence | Required treatment |
|---|---|
| 48 A/B portfolios and native assessments | Reference the unchanged original objects and actual accounted requests. |
| 20 already valid C portfolios and native assessments | Reuse only after proving the N1 order is identical and verifying complete output/evaluator compatibility. Keep their original portfolio and assessment hashes. |
| Four newly derivable C-N orders | New derived-output identities bound to the parent B, original rank result, N1/code hash and new study; fresh native assessment required. |
| Four original strict-C failures | Remain failures, permanently, in the original study and reports. |

Compatibility binds exact task/prompt, response IDs/texts/statuses/order, source portfolio and assessment hashes, native exported input, evaluator implementation/upstream revision, prompts/schemas, role models/settings, patience and ordering parameters, and accounted request/result evidence. Replay each reused assessment on its original object. Never edit its `portfolio_sha256`, retag it as newly judged, or copy scores onto a different portfolio hash.

A new compatibility manifest links each C-N comparison row to the original evaluated object or new derived object. A native-evaluation bridge may retain the existing internal C slot convention under the new study identity; the public method label is C-N. Cross-study derivation must have its own validator—do not falsify parent/study equality to make the old permutation validator pass.

Freeze the new method, all 24 order mappings, all 68 reuse proofs, source/runtime identity, four-assessment worklist, report/decision policy and budget before any new judging. If any of the 20 C reuse mappings differs, or any required compatibility proof fails, stop offline. Do not silently rejudge additional orders, discard cases or enlarge the paid scope.

## Required offline checks and paid entry gate

| Check group | Required runnable evidence |
|---|---|
| Positive normalization | Strict JSON unchanged; prose/fence wrappers; repeated identical objects; equivalent JSON whitespace/escapes. |
| Ambiguity and invalid structures | Reject two distinct orders, valid-plus-invalid objects in either order, nested/wrapped payloads, malformed/unmatched delimiters, duplicate decoded keys, extra fields and nonfinite values inside candidates. |
| IDs and resources | Reject missing/duplicate/foreign/nonstring IDs, normalization/typo attempts, no object, invalid UTF-8, and size/depth/candidate-count overflow. No first/last/score-based selection. |
| Saved corpus | Exactly 24 dispositions, 20 unchanged existing orders and four separately derived orders; unchanged IDs/texts and original strict failures. Treat this as consumed-corpus replay, not a held-out parser test. |
| Reuse/derivation integrity | Forged hashes, changed text/task/order/status/evaluator/profile or mismatched parent/study references fail before any paid dispatch. No rewritten native-assessment identities. |
| Native/accounting path | Actual pinned-SDK MockTransports with fake keys, blocked sockets and network none; head-count cases 1/5/10 produce exactly 8/24/44 new native calls. Exact native requests/folding, group/quality malformed/refusal preservation, no Sonnet/probe calls. |
| Recovery and closure | Durable intent before dispatch, one owner, bounded reservations, unknown-liability halt, zero retries/replacements, zero-call settled resume/replay, source preservation and complete explicit missingness. |

Use synthetic fixtures with no invented real ratings. These checks prove the bounded implementation, not model quality or future normalization success. Freeze negative fixtures/expected outcomes before implementing the normalizer. The paid path remains disabled until this whole offline gate passes; if it fails, deliver the usable offline artifacts and an explicit incomplete/hold report.

Implementation planning allowance: **4–8 focused hours** for this narrow block, with a scope review at four hours. If essential compatibility/launch work cannot fit eight hours, stop at the offline checkpoint and revise the scope before more engineering or paid work. Do not turn four missing orders into a new general execution platform.

## Further native assessment, if authorized

There are **44 maximum new request slots**: four grouping calls and ten possible quality-head slots per derived order. A successful assessment uses **8–44 calls**: four groupings plus 4–40 quality calls. Nonheads are explicitly unnecessary; failures may yield fewer calls. The earlier 991 requests stay shared historical evidence, not fresh attempts. No new answer, plan or rank inference occurs.

| Role | Model/API and unchanged controls |
|---|---|
| Four grouping calls | `gpt-5.6-luna`, Chat Completions, native strict grouping schema; effort, output cap, temperature and seed omitted |
| Quality heads | `claude-opus-5`, Messages, adaptive thinking, effort `high`, `max_tokens=16000`, native strict score schema; service tier/geography omitted |

Preserve the same NoveltyBench v1.1 prompts/folding/arithmetic, patience 0.8, `seed=None` delivered ordering, pinned image/SDKs/upstreams and AM-1 payload/financial controls. No model substitution, schema change, new temperature setting, fallback, repair or extra token-count/auth/model-list probe. One call in flight; 90-second HTTP timeouts; zero retries/replacements. A timeout or unknown usage retains its reservation and stops the paid stage. Known malformed/refused native results remain non-scored and cannot satisfy completion.

Bind the authorization and four-order journal to the new study/source/policy/worklist identity, using the existing masked-key/temporary-stdin model, supported public PAYG profile and actual container inspection. Read no ambient keys, write no raw keys and forward no host credential environment. A new journal is justified by the newly authorized scope; it must link the historical spending and cannot clear old liabilities or masquerade as unused old allowance.

## Cost and proposed budget

**This definition costs $0 API spend.** The offline implementation/checkpoint also requires no real model calls. Fees for the assistant session, local electricity and voluntary human work are outside the API worksheet.

The four corresponding **B** assessments previously cost **$0.367313** for four grouping and 39 quality calls. This is a useful observed shape, not the price or partition of the newly ordered outputs. Across the completed pilot, mean accounted costs were $0.000977 per grouping and $0.009267 per quality head. Applying those averages gives these conditional marginal scenarios:

| Future quality heads across four orders | New calls | Additional accounted-cost scenario |
|---|---:|---:|
| 4 | 8 | $0.041 |
| 20 | 24 | $0.189 |
| 40 | 44 | $0.375 |

These are not representative future-cost estimates or bounds. A deliberately longer-output scenario—40 quality calls, 1,000 ordinary input tokens and 16,000 billable output tokens each, a 1.1 accounting uplift, plus $0.01 per grouping—costs **$17.86 additional**. Output includes thinking; reaching its cap can produce truncation rather than a valid score.

**Proposed new cap: $30 additional, currently unapproved.** The unchanged reservations are **$1.661880 per grouping** and **$11.44 per quality**. The cap must cover settled marginal cost + unresolved marginal liability + the next reservation. With no liability, another quality call cannot start after marginal settled cost exceeds **$18.56**. $30 accommodates the stated long-output scenario and the next-call reserve; it does not guarantee completion under every admitted request or provider billing outcome. It is not expected or guaranteed spend.

Keep shared historical cost **$5.983504** and new marginal spend separate, count every actual call once, and report their sum. The proposed combined accounted ceiling would be **$35.983504**. Original unused $125 headroom supplies no authority for this new variant. C-N's attributed generation/planning/ranking cost includes the original B cost plus **all 24 original rank calls**, including the four originally invalid texts: **$1.621512**. Normalization does not make those paid calls free; reused judgments are not charged again.

Pricing was searched/opened on 2026-10-28: [Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna) ordinary input/output $0.20/$1.20 and [Opus 5](https://platform.claude.com/docs/en/models/opus-5/overview) $5/$25 per million tokens. Cache/geographic categories remain in the conservative envelope; see [OpenAI pricing](https://developers.openai.com/api/docs/pricing) and [Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing). Recheck profile/rates before a future launch. This supplies no account/invoice guarantee or grant. Exact arithmetic is in the worksheet.

## Deliverables and completion criteria

1. A versioned N1 implementation with runnable positive/negative checks, raw-input/disposition manifest and new derivation identities, without changing the parent.
2. An explicit **68-assessment reuse manifest**, 20 exact unchanged-C proofs and four separately derived outputs; native export/import and all identities verified.
3. The narrowly scoped, offline-proved four-order assessment path and source/runtime/grant-bound launch handoff. No live authority is inferred from passing tests.
4. If paid work is authorized: four fresh native assessments, all 44 slots classified, complete reconciled marginal accounting and no unresolved liability; every failed or undispatched outcome preserved.
5. `PHASE2B_RANK_FORMAT_REPORT.md` and a verified tracked evidence archive under a new `phase2b-rank-format-v1` namespace: models/settings/sampling, policy, all dispositions, provenance/reuse, costs, failures, report replay and a separate post-hoc decision or explicit incomplete outcome. Commit the report/packet locally; no external publishing.

**Offline checkpoint complete:** policy/tests pass, all 24 saved inputs have their expected disposition, 68 reuse proofs pass, four unscored derived outputs exist, and the mocked journal/launcher/reporting gates work without SDK network/key access. This is independently usable; it is not the completed C-N comparison.

**Full follow-up complete:** those gates plus four actually scored new orders and exact saved-evidence replay establish a 72-row **new comparison view**: A 24, B 24, C-N 24, with reconciled accounting and a reproducible separate decision. Old strict C remains 20/24 and its old decision remains inconclusive. Any new non-scored order, rejected normalization, failed reuse or unresolved liability yields an incomplete/inconclusive follow-up without replacements or complete-case selection.

## New decision policy and limits

Freeze `rank-format-development-v1` before new judgments: track `benchmark`, lineage `posthoc-C-N-v1`, parent the original inconclusive decision. Compute paired prompt means with two repeats and equal weight across all 12 prompts. Compare A/B/C-N only with complete compatible coverage; rank highest exact mean utility, then lower attributed generation/planning/ranking cost, then A/B/C-N. Do not add a gain floor, significance rule or favorable-outcome requirement after observation. Original strict C is reported alongside as failed, not silently renamed.

A selected procedure is an **exploratory development starting point**, potentially useful in a separately defined Phase 3A. It is not a fresh validation result: the policy was designed after seeing the original failures and A/B results. Reusing scores does not create new independent evidence. Four judgments arriving later also carry timing/model-alias uncertainty. Preserve the observed native limitations: 38/151 shared-head scores differed and one identical B/C text set received different partitions. Do not tune the normalizer or repeat judgments to resolve a preferred winner.

## Exclusions and exit

Out: new answer/plan/rank generation, provider-enforced rank-schema experiments, semantic prose adjudication, ID repair, strategy/model/effort sweeps, new data/benchmarks, native judge changes/calibration, CrPO/MuCE/Bayesian surprise, human collection, recursive adaptation, held-out confirmation, generic plugin/cache/runner infrastructure and rewriting historical evidence. Human evidence remains optional and is not a completion gate.

Stop after this block and its report. No automatic top-up, extra cohort, parser amendment, rerun-until-success or Phase 3A follows. Before implementation, review this definition and explicitly authorize its chosen offline/paid scope; a whole-block approval can cover implementation, the internal gate and the stated $30 paid stage without per-task approvals. If only offline work is authorized, deliver that checkpoint and leave judging disabled.
