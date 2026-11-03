# Inspect AI fit for Buddha2

**Research only, 2026-10-30.** Source snapshot: [Inspect commit 7340817a6fb5eb20c14520d13ce8c146d2d893c8](https://github.com/UKGovernmentBEIS/inspect_ai/commit/7340817a6fb5eb20c14520d13ce8c146d2d893c8). This note deepens the platform comparison in RESEARCH.md without modifying that committed document. No installation, prototype, provider call or runtime compatibility test was performed. H1's scoped OpenCode correction remains the active work; Inspect adoption is a separate possible checkpoint.

## Recommendation

Inspect is a credible candidate for reducing evaluation bookkeeping and improving visibility while retaining actual Harness². Start, if separately authorized, with **closed-output evaluation and logging**, not by putting a new provider proxy into the current pilot. The distinction is practical: passive assessment leaves the proven native request path intact, whereas Agent Bridge translates requests through Inspect's provider implementations. Many defaults are configurable; some remaining differences need a real equivalence test.

This is not a recommendation to replace Harness² with Inspect's built-in agent. Our engine, fixed strategies, adaptation contrast and native NoveltyBench assessment remain distinct from the infrastructure hosting their records.

## What could be replaced, and what stays

| Existing responsibility | Inspect opportunity | Boundary to retain |
|---|---|---|
| Task selection, model/strategy comparison bookkeeping and progress presentation | Candidate replacement by tasks, samples, evaluation scheduling and logs. | Frozen samples, arm order, budgets and method identities remain ours until an adapter proves exact mapping. |
| Repeated report navigation and transcript inspection | Candidate replacement or supplement by Inspect's viewer, structured logs and dataframe tools. | Canonical artifacts and hashes remain authoritative; an imported view cannot rewrite them. |
| Assessment attachment and rescoring presentation | Custom scorers can expose existing native assessments; later compatible assessments can be separate additions. | Upstream NoveltyBench performs its own partitioning, scoring and arithmetic. No substitution of Inspect's generic model-grading rubric. |
| Generic sandbox setup and command supervision | Potential later reuse after an ownership/cancellation comparison. | Current credential handling, filesystem exclusions, exact process ownership and bounded cleanup are not automatically replaced. |
| Provider transport and financial admission | No immediate replacement recommendation. | Keep the intent/result/unknown ledger, conservative reservations, no-resend policy, joint caps and H1 history invariant. |
| Scientific validity and phase decisions | Metadata and views can make these easier to inspect. | Held-out isolation, authentic-path criteria, disclosed strategies, failure classification and review gates remain explicit project policy. |

Inspect supports [custom scorers and scoring policy](https://inspect.aisi.org.uk/scoring.html). Its [separate scoring workflow](https://inspect.aisi.org.uk/scoring-workflow.html) can defer assessment, score saved logs, and retain prior scores when appending. Those facilities fit our separate-assessment model, but its overwrite options must not be used for closed project evidence. Human-augmented decisions would still require our versioned lineage rules.

For visibility, [runtime tracing](https://inspect.aisi.org.uk/tracing.html) records action starts/ends and can identify running, cancelled, failed or timed-out work. This could reduce manual diagnosis. It does not independently prove provider billing, model quality or preservation of an opaque child's internal state.

## Actual Harness² and OpenCode integration

The [Agent Bridge documentation](https://inspect.aisi.org.uk/agent-bridge.html) offers two routes: an in-process Python bridge and an HTTP proxy for agents in a sandbox. Neither requires replacing the external agent's reasoning algorithm. The sandbox route targets a local endpoint, normally port13131, and can serve Anthropic, OpenAI Chat/Responses and Google-compatible requests.

The [Python bridge implementation](https://github.com/UKGovernmentBEIS/inspect_ai/blob/7340817a6fb5eb20c14520d13ce8c146d2d893c8/src/inspect_ai/agent/_bridge/bridge.py#L728) patches asynchronous SDK requests only when the model name explicitly targets Inspect; it rejects streaming through that in-process route. A native Harness² invocation can be hosted by a custom solver, but Python patching alone will not intercept the Bun/OpenCode CLI's HTTP traffic. That child needs the sandbox proxy or must remain outside the bridge. Routing the child and its Python parent through a new proxy is an integration change, not automatic coverage from adding a context manager.

A passive alternative is simpler: run or read our existing native workflow outside Inspect's providers, then attach its outputs and canonical assessment references to Inspect samples. If direct provider integration later proves valuable, Inspect also supports a [custom ModelAPI extension](https://inspect.aisi.org.uk/extensions-model-api.html), including raw request/response records and control over message collapse and retry classification. Delegating to our protected transport is therefore an option, though it adds an adapter that must justify itself.

## Roles, exact settings and omissions

Inspect's [model roles](https://inspect.aisi.org.uk/models.html#model-roles) support per-role models/configuration. An undeclared role falls back to the evaluation model, so declaration alone is not an isolation boundary. The sandbox bridge also sends unmatched names to its active model unless explicitly routed. A future integration must reject unknown names and keep grader routes unavailable to the adaptive editor, rather than accept these fallbacks.

| Project role | Frozen identity/settings to preserve | Proposed integration requirement |
|---|---|---|
| Planning, answers and ranking | Sonnet5.5; adaptive/low;4096 output; standard-only/global controls. | Explicit solver role and exact request comparison. |
| Native editor and fixed selector | Opus5; adaptive/high;16000 output; standard-only/global controls. | A separate role/context for these allowed calls. |
| Duplicate grouping | Luna; native Chat construction; omit maximum tokens, effort, temperature and seed. | Force Chat, keep each omission absent, and forbid global generation settings from filling it. |
| Answer quality | Opus5; high/16000; native tier/geography omissions. | Separate from editor despite the same model ID; keep its native request construction and role boundary. |

The shared Opus5 ID makes a single name-to-model alias insufficient for differing editor and quality controls. Separate bridge instances or an explicitly owned role resolver can distinguish them. Routing must use declared execution context, not infer a role from grader prompt contents. The [resolver implementation](https://github.com/UKGovernmentBEIS/inspect_ai/blob/7340817a6fb5eb20c14520d13ce8c146d2d893c8/src/inspect_ai/agent/_bridge/util.py#L1224) supports explicit aliases and a resolver, but defaults must be checked.

Current source recognizes the relevant Claude families and accepts provider model IDs, which is implementation support rather than evidence of account access. The [OpenAI implementation](https://github.com/UKGovernmentBEIS/inspect_ai/blob/7340817a6fb5eb20c14520d13ce8c146d2d893c8/src/inspect_ai/model/_providers/openai.py#L206) prefers Responses for GPT-5-family names but offers `responses_api=False`. For a tools-free grouping call, Chat remains selectable. Its [completion-parameter builder](https://github.com/UKGovernmentBEIS/inspect_ai/blob/7340817a6fb5eb20c14520d13ce8c146d2d893c8/src/inspect_ai/model/_openai.py#L590) emits maximum tokens, seed, temperature and reasoning effort only when non-null; the base ModelAPI supplies no default maximum. Thus Luna's omissions are supported in principle, provided no task/global override populates them. This has not been exercised here.

## Configurable defaults versus unresolved fidelity

| Concern | Existing configuration capability | What is still unproved |
|---|---|---|
| Client effort/token settings are dropped by default | `forward_generation_config=True` forwards them. Model and active-evaluation config still override client values. | Final body and omitted-field equivalence across all four roles. |
| Tier and geography | The bridge withholds client tier in favor of evaluation/provider configuration. Per-role provider body settings can declare the needed controls. | Correct explicit values versus native omissions, including same-ID Opus roles. |
| Anthropic thinking display | Provider-model `extra_body` is merged last and can replace the complete thinking object with the intended display setting. This is distinct from GenerateConfig's narrower passthrough. | SDK-assembled wire body, stream shape and unchanged experimental settings. |
| Automatic mismatched-block dropping | Replacing that thinking object can remove the generated `block_binding` setting. | The provider still automatically adds its binding-controls beta header for Sonnet5.5; no public constructor/config switch to suppress that generated header was found at this snapshot. Exact original header omission is therefore not established. |
| Unknown model routing | Explicit aliases/resolvers exist. | Fail-closed handling and editor/grader separation need adverse tests; default routing is not suitable evidence. |

Sources: [configuration merge](https://github.com/UKGovernmentBEIS/inspect_ai/blob/7340817a6fb5eb20c14520d13ce8c146d2d893c8/src/inspect_ai/agent/_bridge/util.py#L1155), [Anthropic bridge parsing/settings](https://github.com/UKGovernmentBEIS/inspect_ai/blob/7340817a6fb5eb20c14520d13ce8c146d2d893c8/src/inspect_ai/agent/_bridge/anthropic_api_impl.py#L262), and [Anthropic request construction](https://github.com/UKGovernmentBEIS/inspect_ai/blob/7340817a6fb5eb20c14520d13ce8c146d2d893c8/src/inspect_ai/model/_providers/anthropic.py#L1412). The latter selects summarized display by default and adds binding controls automatically; its model-argument body override provides the capability described above. This is a reason to test configuration, not a claim that the defaults are unavoidable or that a configured bridge is equivalent.

Exact header omission might require a custom provider/transport boundary rather than the stock provider's settings. That possibility is not implemented or recommended inside H1. The [dependency manifest](https://github.com/UKGovernmentBEIS/inspect_ai/blob/7340817a6fb5eb20c14520d13ce8c146d2d893c8/pyproject.toml) also requires current provider SDK generations, including Anthropic>=2.0 and OpenAI>=3.4, so any trial belongs in a new isolated, pinned environment rather than upgrading H1's dependencies.

## Signed empty thinking: positive evidence, bounded claim

Inspect has relevant structural support. Its [Anthropic bridge](https://github.com/UKGovernmentBEIS/inspect_ai/blob/7340817a6fb5eb20c14520d13ce8c146d2d893c8/src/inspect_ai/agent/_bridge/anthropic_api_impl.py#L529) uses the native provider's block conversion. That converter retains empty summaries and opaque signed/redacted data; cached raw blocks and recorded tool positions support reconstruction.

More decisively, the existing [progress-update/interleaving regression](https://github.com/UKGovernmentBEIS/inspect_ai/blob/7340817a6fb5eb20c14520d13ce8c146d2d893c8/tests/model/providers/test_anthropic.py#L3723) builds two empty signed thinking blocks separated by tool calls and asserts the replayed type order and signatures. Other tests cover interleaved visible reasoning. This is stronger than a generic claim of reasoning support.

It does not establish our full stream → OpenCode storage/normalization → sandbox proxy → next request → cold resume path. Internal replay state, block order, signed-prefix ownership and any synthetic placeholder behavior still require end-to-end tests. The current open [Sonnet5.5 bridge issue5970](https://github.com/UKGovernmentBEIS/inspect_ai/issues/5970) concerns a reported multi-tool-loop prefill failure; [issue5300](https://github.com/UKGovernmentBEIS/inspect_ai/issues/5300) concerns Bedrock signature handling. These are distinct paths and reporter evidence, not proof that our direct Anthropic route fails or that either issue is fixed.

## Accounting, retries, cancellation and recovery

Inspect's [limits](https://inspect.aisi.org.uk/setting-limits.html) cover cost, tokens, turns and time. Cost uses reported usage/model price data; this is not our pre-dispatch maximum-liability reservation contract. Working time excludes certain waits and can undercount concurrent work, while sample limit exits may still be scored. Our absolute clocks, classification and assessment budgets therefore remain explicit.

The [GenerateConfig source](https://github.com/UKGovernmentBEIS/inspect_ai/blob/7340817a6fb5eb20c14520d13ce8c146d2d893c8/src/inspect_ai/model/_generate_config.py#L204) defaults model retry counts to unlimited when unspecified; attempt/stream-idle timeouts can feed that retry policy. A prospective provider trial must explicitly set Inspect retries to zero and audit SDK/transport retries, refusal retries, fallbacks and sample/eval retries separately. [Handling Errors](https://inspect.aisi.org.uk/handling-errors.html) documents sample retry options and their distribution-shift risk. No retry setting itself settles an uncertain charge.

The [sandbox bridge cleanup](https://github.com/UKGovernmentBEIS/inspect_ai/blob/7340817a6fb5eb20c14520d13ce8c146d2d893c8/src/inspect_ai/agent/_bridge/sandbox/bridge.py#L308) owns its proxy lifecycle and cancellation scope. That is useful process discipline; it does not prove that an arbitrary native child, SDK worker or externally accepted request was cancelled or unbilled. Keep our owner/deadline/cleanup evidence until matching tests pass.

[Checkpointing](https://inspect.aisi.org.uk/checkpointing.html) saves registered state and selected sandbox files at turn boundaries. It does not preserve arbitrary process memory, running tools or external effects; nested limits are not restored automatically, and scoring-only recovery has different limit semantics. Native Harness²/OpenCode resumability would need explicit cooperation. A restored Inspect checkpoint must never authorize resending one of our unresolved intents.

## One proposed offline fit trial, after H1

**Objective:** determine whether Inspect provides useful evaluation visibility with less custom work, while staying out of the provider path. **Proposed bound:** one engineering session of up to four hours, then a go/no-go note; API cost$0. This is a proposal, not execution authorization.

Use one completed native H1 fixture record and one recorded history-failure case. Import copies into a new Inspect task/log with `model=None`; attach existing native output/assessment references, original role/settings metadata and failure status. No generator or judge runs. Label imported model identities as originating from the native evidence, not models served by Inspect. Keep the scientific fold external.

Deliver a minimal import adapter, a viewable log, a field-by-field comparison and a removal/benefit ledger. Acceptance requires:

1. Original outputs, assessments, evidence and frozen hashes unchanged.
2. Both cases retain exact status/missingness; the failed case cannot become an eligible success or fabricated score.
3. Network and SDK constructors blocked, zero provider/token-count calls and zero credentials read.
4. Role/config/usage/cost fields agree with canonical records, with omission distinct from null or default.
5. Two saved replays agree; unknown names and unsupported mappings fail rather than trigger inference.
6. Name the custom modules/operator steps replaced, and count adapter/configuration/dependency work added.

A useful result could justify replacing reporting or experiment-bookkeeping glue. A failure or net increase in complexity is also a valid conclusion. Live bridging, provider equivalence, internal native checkpointing, new paid pilots and platform migration remain separately defined decisions. This source study promises none of those results.
