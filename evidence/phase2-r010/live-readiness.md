# Phase 2A live-readiness review — 2026-10-25

**Offline preparation does not establish permission or readiness for Phase 2B.** No provider or token-count endpoint was called. The retained dispatcher refuses real dispatch even when supplied a nominal grant; there is no override switch for the missing proof.

## Input admission: not established

The software candidate is the UTF-8 length of canonical request JSON plus 2,048 framing units. It is explicitly unverified for real providers. It is deterministic for fixtures and rejects candidate inputs above 8,000 units for answer/plan/quality or 64,000 for rank/group. That does not prove that all provider-added framing, structured schema representation and hidden input categories fit those token budgets. We did not install a tokenizer or infer a certified bound from a character ratio.

OpenAI documents that its Responses token-count endpoint includes formatting absent from locally tokenized text, and that tools and schemas complicate local counting. The pinned native grouping call uses Chat Completions, so a Responses-only count would also need a compatibility argument. These observations support keeping the proposed local allowance unverified; they do not prove that no conservative offline bound could ever be established. [OpenAI token counting](https://developers.openai.com/api/docs/guides/token-counting).

Anthropic documents a structured message-count endpoint and describes counting as an estimate. That endpoint was not used: the frozen 2A scope excludes provider token counting. Its existence does not certify this offline candidate. [Anthropic token counting](https://platform.claude.com/docs/en/build-with-claude/token-counting).

Before 2B, establish a documented conservative bound for the exact bodies and providers, or review a separate change to the admission method and permission scope. Preserve this study identity and any attempted evidence if effective controls change. Do not silently set a verification flag, shrink native prompts, add grouping output caps, change API routes or loosen the original limits.

## Billing and caps: reservations tested; live certification outstanding

The dated sheet retains the frozen model envelope and prices. Sonnet reserves 5-minute cache-write input at $2.50/M and output at $10/M; its current cache-hit price is $0.10/M. Opus 5 uses $5/M input and $25/M output. These are standard global prices, without batch/fast-mode assumptions. [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing).

Luna uses $0.20/M input, $0.02/M cached input and $1.20/M output, reserving its documented 128,000 output maximum because the unchanged native body omits an output cap. Confirm the applicable grouping cache-write policy before certifying a live reservation. Unknown billable categories or unsupported cache writes remain liabilities and halt execution. [Luna model and pricing](https://developers.openai.com/api/docs/models/gpt-5.6-luna).

The $125 total and included $5 first-check limits are proposals, not grants or completion guarantees. Full configured maxima remain $364.327680 and $15.180320 respectively, under the declared envelope. No real provider billing behavior or delivery timeout has been validated in 2A.

## Other prerequisites

- Presence-only checks found neither provider key in the process, Windows user or machine environment. No key values were printed. Account/model access was not tested; see `credential-readiness.json`.
- Bind two eligible independent volunteer readers and availability for the fresh-output check before a full 2B pilot. No one was contacted and no human ratings were collected.
- Obtain applicable spending authorization for a reviewed frozen package, then perform the counted first block and stop to review it before expansion.

Route H remains optional and unstarted. CrPO, MuCE calibration, model tournaments and actual Harness² adaptation remain deferred. None of those is needed to resolve this admission decision.
