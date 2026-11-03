# Phase 2 live-readiness checkpoint

Date: 2026-10-26, America/Los_Angeles. Executed under frozen specification **0.14**, starting at commit `d09ebebaf255fb1b52fee3483ada52765d750dcb`.

**Outcome: checkpoint complete, change required. Gate 1 fails under the unchanged controls. Gate 2 was not started.** No launch candidate, preflight, actual-SDK mock trace or live-ready authorization packet was built. Production code remains unchanged and real dispatch remains disabled. No provider endpoints, SDK clients, credentials, human collection or Phase 2B experiments were used; experiment/API cost was **$0**.

The local byte estimate does not establish the promised conservative 8k/64k provider-input bound. Current documentation identifies hidden formatting and billable schema instructions, but supplies no bound that certifies this estimator for these five exact request roles. Grouping also has documented cache-write pricing which the current usage/settlement path does not support. These findings justify the specified no-go; they do not prove that no possible conservative bound could ever be established.

The preferred next decision is [AM-1: separate payload safeguards from financial reservations](PHASE2_LIVE_READINESS_AMENDMENT.md). It is a concrete **unaccepted proposal**, not an implemented fix or a request to spend money now.

## What was reviewed

The parent preparation is `runs/phase2-r012/frozen-study/study.json`, identity `84fcfa743a45ac8dd2cf2e4b4d7ecec1e76b9e8b42b633c90a0325ff0623df92`. Preserve its 12 curated development tasks, two repeats, A/B/C procedures, role profiles, native v1.1 arithmetic, human sample and both decision policies. No task selection, generation or held-out inspection occurred. The first live block would still be the first task/repeat 1: 20 answers, one plan, one rank, three group requests and up to 30 quality-head requests, at most 55 requests within the existing study.

Source pins remain Harness² `1cfe254e8d25b15f37048c3730134686abe60335` and NoveltyBench `64a23be6b18ec1dacc298830aab276061b6e143c`. Pinned SDKs are `anthropic==1.4.0` and `openai==1.107.0`. This review traced the local SDK invocation and existing tests; it did not invoke SDKs or claim to capture their effective wire bytes. Tests that substitute SDK modules do not prove the actual SDK/server serialization path.

Exact source hashes, observations and code references are in [sources.json](../../../evidence/phase2-readiness-r014/sources.json); the machine-readable five-role dossier is [request-contracts.json](../../../evidence/phase2-readiness-r014/request-contracts.json).

| Role | Exact local/native request contract | Established and missing evidence |
|---|---|---|
| Answer | Sonnet 5.5; system plus original task, optionally only its own B angle; adaptive/low, standard/global, total output cap 4,096. | Local renderer/profile established. Dynamic angle and provider formatting are not certified by the byte estimate. |
| Plan | Same Sonnet profile; system plus original task. The angle JSON schema is a local parsing contract, not an API structured-output schema. | Local body established; no documented conservative framing bound for the estimator. |
| Rank | Same Sonnet profile; task plus all ten saved response IDs/texts; local permutation parser; output cap 4,096. | Dynamic generated content makes static prompt checks insufficient. No hidden-framing bound established. |
| Group | Native system/user with all ten ordered answers and strict Partition `response_format.json_schema`; Luna; effort/output cap omitted, output reservation 128,000. | Native body/omissions established. Structured schema/rendered context is not certified by local JSON bytes; exact route's cache-write usage/SDK handling remains unsupported. |
| Quality | Native system/user with original task and one group-head response; Opus 5 adaptive/high; output cap 16,000 and strict Score `output_config.format`. No explicit cache-control/service/geo fields. | Native body established. Additional provider-generated schema instructions are billable and lack a certified bound in the current estimator. Default tier/usage behavior remains a live-only unknown. |

For every role, the assumed input-token limit is **8,000** for answer/plan/quality or **64,000** for rank/group. `build_request` strips those local fields from the transmitted body. `input_bound` uses canonical request JSON UTF-8 bytes plus 2,048 and explicitly marks `provider_verified: false`. Returned usage is checked against the limits after a request; that can detect an overrun but cannot prevent an under-reserved paid call. [Dispatcher source](../../../src/buddha2/phase2_dispatch.py), [strategy renderer](../../../src/buddha2/phase2.py), [native assessment boundary](../../../src/buddha2/phase2_native.py).

## Gate 1 decision and evidence limits

The current [OpenAI counting documentation](https://developers.openai.com/api/docs/guides/token-counting) includes formatting absent from local field tokenization. It documents a Responses-format counting endpoint; this does not establish conservative equivalence for the unchanged Chat Completions grouping body. No counting request was made.

[Anthropic counting documentation](https://platform.claude.com/docs/en/build-with-claude/token-counting) offers structured counting and describes it as an estimate in its FAQ. [Structured-output documentation](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) says the provider injects additional billable system instructions. Those facts do not establish that the current 2,048 allowance bounds the complete quality-request expansion. No Anthropic counting or inference endpoint was used.

The [Luna model page](https://developers.openai.com/api/docs/models/gpt-5.6-luna) lists a 1.25-times ordinary-input cache-write price. The [caching guide](https://developers.openai.com/api/docs/guides/prompt-caching) distinguishes writes from reads. Current `_account` rejects grouping cache creation, and `DirectSDKTransport` marks extra nonzero grouping usage details unsupported. It therefore halts rather than silently treating writes as free; retaining the old reservation does not certify its size. Exact Chat Completions usage normalization must be supported before live use, without copying a Responses-only example by assumption.

No provider account/model access, actual settings acceptance, returned schema, delivery behavior or real billing was established. No local credential-presence check was needed or performed. A known input/output model limit or an existing green fixture suite is not substituted for the missing financial/admission proof. The [recorded decision](../../../evidence/phase2-readiness-r014/gate1-decision.json) was reached within the two-hour feasibility ceiling; work after it was limited to the required dossier, proposal, cost arithmetic and closure.

## Conditional cost worksheet

The dated [cost sheet](../../../evidence/phase2-readiness-r014/cost-sheet.json) preserves the original sheets and recomputes only a sensitivity case: unchanged, **unproved** 8k/64k inputs; original output envelopes; standard/global text service; all grouping input charged at its documented $0.25/M write rate. Sonnet uses its conservative $2.50/M five-minute write allowance and $10/M output; quality assumes no writes, at $5/M input and $25/M total output. [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing).

| Quantity | Historical envelope | Write-adjusted conditional arithmetic |
|---|---:|---:|
| Group request | $0.166400 | $0.169600 |
| First block, at all assumed ceilings | $15.180320 | $15.189920 |
| Full study, at all assumed ceilings | $364.327680 | $364.558080 |
| Working token scenario | $21.679200 | $21.722400 |
| Higher token scenario | $106.358400 | $106.444800 |

These are **not certified maximum costs, launch reservations, actual spend, or prices for AM-1's proposed larger input envelopes**. Thinking/nonvisible output must be included, not added again as a separate visible-output charge. Read/write/base input must not be double-counted. Long-context or nonstandard service/region modifiers are outside this scenario; unsupported categories keep launch blocked. Native quality requests have no cache-control field; the no-write projection does not price a possible write at zero. Current code does not settle quality writes either.

Integer microUSD arithmetic was independently checked with a Decimal calculation; see [cost-review.json](../../../evidence/phase2-readiness-r014/cost-review.json). The $5 first-check and $125 full-pilot figures remain unapproved proposals, include liabilities, and do not guarantee completion. Neither they nor this conditional worksheet can unlock dispatch.

## Amendment and draft launch conditions

AM-1 retains the exact admitted payload sets as measurable JSON-byte safeguards and replaces the unsupported input-token claim with a separately justified maximum-billable-input reservation. Its formula, evidence requirements, pricing-tier treatment, acceptance checks, tradeoff and identity/comparability consequences are in the proposal. It must not assume a context-window number bounds all billing without supporting evidence. If that proof is still unavailable, the amended role remains blocked. This is not a claim that the missing proof has already been solved.

No grant-ready packet exists. [Draft conditions](../../../evidence/phase2-readiness-r014/draft-launch-conditions.json) explicitly record `authorized: false`, `live_access_verified: false` and `launch_candidate_ready: false`. Before a future launch there must be an accepted control amendment, evidence that its financial bounds and exact-route accounting work, a new frozen source/control/study identity, the still-unbuilt narrow Gate 2 candidate and offline verification, and an applicable separately authorized ceiling. Live account/settings/billing checks would then belong to the counted Phase 2B block, followed by review before any expansion. No provider calls are authorized by this report.

## Research tracks and phase status

**AI only** means the `benchmark` track using native benchmark assessments and complete accounting; it does not require human replies. **AI + Human** means `human-augmented`: the same immutable output/native-assessment archive plus optional later eligible independent human evidence and a separate decision. Both share this technical readiness gate. Human review cannot repair missing billing/admission proof, and absent readers do not block the benchmark track. These are research lineages in one implementation, not two Git forks or automatically duplicated experiments.

Phases 0, 1, 1A, original 2A and the offline decision-policy update retain their completed historical status. This checkpoint closes with a change-required decision. AM-1 is proposed/unaccepted; Phase 2B remains unstarted; later adaptation/confirmation phases remain separately defined. Route H is optional/unstarted and CrPO deferred. Current phase definitions record that sequence and both tracks, while exact revision 0.14 is archived unchanged.

## Completion evidence

| Requirement | No-go-branch disposition |
|---|---|
| LR-1 | Parent study, 19 effective package files, selected inputs and historical manifests/source pins verified unchanged. |
| LR-2 | Completed five-role admission review; no conservative bound established; exact missing evidence and AM-1 documented. Gate 1 fails. |
| LR-3 | Completed source-backed billing review and independently checked conditional cost sheet; exact-route settlement/input bound still uncertified, so no launch reservation is issued. |
| LR-4 | **Not built**, as required after Gate 1 fails. No runner, actual-SDK mock trace or first-block outputs. |
| LR-5 | **Not built** as a new launch candidate. Existing unconditional real-dispatch block is preserved; no launch authorization or access claim. |
| LR-6 | No-go report, amendment, conditional worksheet/review, draft conditions, acceptance record and preservation manifest delivered. |

Acceptance and preservation counts are in [closeout.json](../../../evidence/phase2-readiness-r014/closeout.json) and [manifest.json](../../../evidence/phase2-readiness-r014/manifest.json). Production source/tests/dependencies, native algorithms and old runs were not changed. No runtime/model/mock experiment was run; existing historical 203-project/five-upstream test evidence is preserved, not presented as fresh readiness verification. Document links, Unicode, file integrity, cost arithmetic and no-go requirements were checked for this closure. 
