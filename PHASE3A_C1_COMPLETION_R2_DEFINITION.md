# Phase 3A C1 completion R2 — coordinated deadline recovery

Definition **1.1**, 2026-10-29, America/Los_Angeles. **Authorized complete R2 block, implementation active.** The user requested: "based on what we have done till now, if R2 needs redefining, do that and then (or otherwise) proceed to complete the R2 block." This satisfies the new-slice/method check-in. The standing completion objective and automatic sub-$250 cap approval remain in force; no further mini-phase or funding approval is required inside this block. Exact definition1.0 is preserved in [the archive](specifications/archive/phase3a-c1-completion-r2-definition-1.0.md) and commit `772945a` with its original proposal review.

The authorization covers implementation, offline verification, first adaptive readiness, first-pair review, remaining pairs and closure, including necessary prospective refinements and in-scope corrections. No planned software prerequisite is deferred until after a paid check. New masked keys are required only after the complete kit is accepted. No further paid run starts automatically from the old controller or grant. A definition-level review is not proof that the implementation or live path works.

## Objective

Complete the same four-prompt, actual Harness² native `agg,k=1` versus fixed C-N best-of-six development comparison with coordinated transport/conversation deadlines. Preserve both unresolved historical liabilities and all failed observations. Obtain all eight valid primary scores, the classified duplicate diagnostic, settled new accounting and at least one authentic live native path. A zero or negative effect remains a valid result.

R1's inner timeout is observed; its underlying connect/read/write/pool cause and failed-call duration are unknown. Its normally completed grounded DOM KEEP_BASE supports only that session's format compliance. Neither fact licenses continuing the blocked R1 study. See [the R1 live report](PHASE3A_C1_COMPLETION_R1_LIVE_REPORT.md).

## Scope and exact intervention

Keep the R1 SYSTEM/MISSION reminder, strict saved-notes envelope, evidence requirements, normal KEEP_BASE eligibility, same four exposed prompts/order, exact model IDs/efforts/output limits/tier/geography and native scoring unchanged. Keep actual pinned Harness², OpenCode, NoveltyBench, image and installed dependencies. No model request-body change, upstream streaming, extra editor turn, shape attempt, candidate or judge is included.

The intervention is one source-bound deadline/diagnostic profile:

| Boundary | Prospective contract |
|---|---|
| Provider call | **240-second completion window**, beginning with the post-lock pre-intent budget computation and including intent persistence, worker startup/IPC, SDK operation and parent-side normalized receipt validation; no clock reset at a lower layer. Separate this from per-I/O settings and later cleanup; zero retries. Apply to both arms' provider calls, including native assessment calls. Transport introduces no model-body change. |
| Per-I/O limits | Connect 10s, pool 10s, write 30s, read 240s. These are inactivity/operation limits, not an alternative total-call clock. |
| Authoring subprocess/admission clock | Preserve the native **600-second authoring subprocess cap** and OpenCode 590-second per-fetch limit. Native context copying precedes that subprocess timer; relay draining follows it, so it does not bound the whole parent call. Start a separate conservative 600-second absolute admission clock **after acquiring `editor._SERIAL`, before invoking that labeled conversation**, once per native label. Waiting behind another editor does not consume this clock; no per-turn or local-retry reset is allowed. Record setup/subprocess/cleanup distinctions. |
| Editor call budget | Carry the absolute monotonic conversation deadline through the relay/queue. **After acquiring the serialized admission locks, immediately before intent**, recompute `min(240s, remaining conversation time minus 30s)`. Require at least 30s of operation budget; otherwise stop locally before a new intent/provider call. A stale pre-queue allowance cannot authorize dispatch. No borrowing from another conversation or editor round. |
| Cancellation and settlement | After the completion deadline, allow **at most 60 seconds for cancellation/cleanup**. Stop new admission immediately. If no authoritative complete response/usage is captured before the single terminal result is committed, persist one unknown result retaining full reservation and stop the execution owner/its owned workers. Do not wait indefinitely, return the controller to ready, abandon an owner able to append later, or dispatch again. Local cancellation/worker termination does not prove provider nonexecution. Never resend. |
| Diagnostics | Immutable per-slot transport audit: policy/source identity, effective total/I-O budgets, monotonic elapsed time, UTC start/end, completion/cancellation category and safe timeout subtype when observable. No raw keys, headers, exception prose or payload copies. Unknown subtype remains unknown. |

Use the smallest supported standard-library/pinned-SDK mechanism for a cancellable completion window. An owned process using a private in-memory pipe can bound an uncooperative SDK call; existing asynchronous SDK calls remain available inside that worker. Reuse frozen request-validation/accounting/event helpers and the native engine. Where the frozen code lacks a callable normalization or post-lock dispatch seam, a small explicit new-source adapter may preserve that logic with equivalence/regression checks. Keep the old source bytes and global policies unchanged; do not monkeypatch their globals or re-enter a non-reentrant file lock. Do not implement a second orchestrator or generic gateway.

The actual-model request recorded at admission must equal the body sent by the pinned SDK. Fresh namespaces, source identities and generated evidence naturally differ from R1; the transport adds no prompt, model parameter, streaming flag or evaluator intervention. Preserve complete response/model/usage behavior. Small pure normalization adaptation must match the frozen normalizer on valid/invalid/cache/tier cases. A narrow dispatch transaction may add only the post-lock deadline/admission hook, typed deadline terminalization and required audit/stop latch while delegating the original validation, reservation, result, replay and event arithmetic.

If persistence/IPC consumes the remaining window after an intent is committed but before SDK invocation, do not send that request or invent a zero-usage response. Reuse the conservative unknown/full-reservation terminal outcome and stop; audit `sdk_invoked=false`, definite egress-not-started and the local deadline phase. If SDK invocation occurred without wire certainty, egress remains unknown. Distinguish admitted attempts, SDK invocations and observed mock-wire calls; the frozen summary field `provider_calls` continues counting admitted attempts and must be labeled accordingly. Such uncertainty is not a known invoice or proof that a provider executed the request.

The completion deadline does not bound cancellation cleanup; cancellation may be delayed or suppressed. Record both durations. The capture timestamp is authoritative in the parent coordinator after complete receipt, normalization and frozen model/usage/accounting validation. A worker's earlier timestamp or HTTP arrival alone cannot rescue a parent receipt after the deadline. Parent capture at monotonic time `<=` the absolute operation deadline is eligible for ordinary processing. An authoritative capture after that deadline, but before the one terminal result is committed, settles known usage/accounting only: retain the original late result and audit, do not forward its output or restore scientific success, and stop the study with a typed known deadline failure. Once an unknown result is committed, a later callback cannot rewrite it, settle/release its reservation or unlock anything; any later authoritative reconciliation is a separate procedure outside this block. Test both sides of the exact boundary, the result/timeout commit race, cancellation-suppressing late results and cleanup that outlives the outer caller. No late output becomes a rescue or replacement.

Before a late known result can expose a ready ledger state, durably record a source/slot-bound global stop latch under the same admission locks. Commit its ordinary known accounting result once, then its typed halt, without forwarding the late output. A crash between result and halt must still reject every later admission/replay continuation through the latch; it must not turn late accounting into a successful response. Other integrity validation remains fail-closed. Saved reports distinguish this known deadline stop from genuine unknown or integrity failures.

The implementation must make the 60-second owner-stop disposition real, including an uncooperative SDK task and prevention of late journal writes. Pipe send/receive, partial frames, worker join and helper cleanup must not bypass the deadline through a blocking operation. Workers/helper readers receive no journal/audit paths or append capability; only the parent commits one terminal result. Transfer credentials only in ephemeral memory/private pipe, never command-line/environment/file credentials. On cleanup failure, durably commit the full-held unknown before stopping the owning execution; use existing owned-container termination where appropriate. If the host cannot stop an owner, retain the hold and report an operational blocker rather than asserting cleanup succeeded. No OS-failure guarantee is implied.

The 30-second margin is operational headroom, not a claim that every failure can be cleaned up within it. Exercise cleanup beyond the margin: keep admitted liability and forbid further calls/success claims while it is unresolved. An operating-system/network failure can still leave uncertainty. The block reduces a known deadline mismatch; it does not promise future provider success.

R1's 24 attempts remain closed and unavailable for completion. R2 needs a fresh effective source/study/worklist/grant/claim and physical output namespace, with all model-backed primaries generated afresh. The R1 journal remains `blocked-unknown`; a new claim/review does not unlock it. The new authority explicitly carries its $11.44 liability plus the older $11.44. Do not reuse the R1 base portfolio or DOM session as an R2 primary. Bind the accepted R1 closure manifest, source and public archive before freezing R2.

Implementation scope is `followups/phase3a_c1_completion_v3/`, evidence/runs `phase3a-c1-completion-v3`, native audits `phase3a-compat-c1-v1/completion-v3/<new-study-SHA>/{mock,live}`, and launcher `phase3a-c1-completion-r2.ps1`. A fresh-SHA live journal may retain the frozen core's literal `phase3a-r2-v1/<new-study-SHA>/live/journal` seam. Reject all old study/source identities. The accepted R1 source is `33cc36cb56fa75b6b427add09934a943515dd40e57cccfb4d4cfcb92a8b4bc1c` (221 files), closure archive `baf5b8413e5f45305c6e1df306542e04a314039312de3ed66b138284b2798527`; preserve it and all earlier history. Exact model/prompt/strategy/native pins remain those in the R1 definition/source, including image `sha256:8792a096b4881d47ab19cc7cbf6a74a232f9ff7cedc978fe93f902a71522d4f2`.

## Deliverables

1. One corrected, source-bound whole-run kit and usable runbook, preserving the original folder and every closed source/result/claim/packet.
2. Total-deadline propagation from authoring conversation through relay admission into the actual pinned SDK; unchanged strict authoring/scoring, accounting, all eight primaries and duplicate, review barriers and first-case counted reuse.
3. Meaningful offline checks using actual SDK mock transports: delayed connection/headers/body, response at/before/after the deadline, queued calls whose post-lock allowance expires, late-turn budget clamping/pre-intent rejection, cancellation suppression and late cleanup/settlement, complete usage captured exactly once, unknown/no-resend/full-reserve behavior, late-known accounting without output forwarding and unchanged actual request bodies.
4. Complete native/OpenCode mock matrix, affected suite/static checks, Windows host guard coverage, source/history preservation, exact zero-call saved replay and actual host mock/configuration checks. Three independent reviews and an independently verified public packet precede fresh key entry.
5. One fresh live pilot through counted adaptive readiness, first-pair engineering review and conditional remaining pairs. Utility/human replies do not gate continuation. Report all failures, unused slots, known cost/liability and native evidence; close even an early stop honestly.

## Exclusions

No release/reconciliation of either unknown, continuation/resend of R1, paid access probe, replacement judge, automatic repeat, new provider/model/effort, upstream streaming, new creative strategy, parser tolerance, forced edit, larger sample, shared library, held-out evaluation, human/CrPO/MuCE work, Phase 3B, broad plugin framework or unrelated performance change. No changes in or access to the original Buddha2 folder.

## Completion criteria

**Offline gate:** all actual deadline/cancellation/admission/normalization/accounting invariants pass, including adverse late settlement, with zero provider calls. The full four-pair fixture matrix scores eight primaries plus the diagnostic, never claims live authenticity, resumes without calls and reproduces all saved report bytes. Host/configuration and independent packet checks pass under the fresh five identity bindings. Preserve skips/limitations explicitly; do not re-label old test outputs as current.

**Live gate:** the first adaptive path has all four valid native rollouts and three normally completed eligible editor stages, complete delivered evidence, valid consumed harvest/notes, known settled accounting and a grounded independent review. It counts once as the first primary. Then seal/judge/review the first pair and run the remaining three under the same frozen study. Complete only with all eight primary scores, classified diagnostic/failures/noncalls, no new unresolved/pending liability and an authentic live path. Otherwise retain null pooled mean/method selection and close the failure. No criterion is relaxed because timeouts or KEEP_BASE occur.

**Usable end product:** accepted reusable kit even if live work stops, immutable live evidence, independent reviews, native/report replay, preserved accounting and a committed closure packet. A failed/incomplete pilot does not fulfill the scientific objective and supplies no next-repeat authorization.

## Cost and authority

Offline provider/API cost is **$0**; local compute/assistant effort is separate. Reuse the exact per-cell/token/attempt limits and source-bound control policy. Reconfirm current official prices/models and payload/control applicability before paid dispatch; do not add a paid token-count/access check.

| Limit/accounting | Amount |
|---|---:|
| Fresh R2 total ceiling | **$205.86** |
| Included first checkpoint | **$50.86** |
| Eight inference cells | **$20 each**, 96 attempts / 4M billable input / 786,432 output per cell |
| Included assessment pool / first sublimit | **$45.86 / $23.70** |
| Prior known cost | **$12.231444** |
| Prior held liability, two unknowns | **$22.88** |
| Prior current maximum exposure | **$35.111444** |
| **Maximum cumulative exposure with R2** | **$240.971444** |

The fresh 775-attempt maximum includes counted readiness; with 885 prior attempts, cumulative maximum is 1,660. The standing sub-$250 policy covers the proposed ceiling. This is a new scope-bound authority, not the unused balance of a stopped grant. No money is transferred between joint pools and neither unknown is treated as free.

The earlier seven-turn hypothetical demand sensitivity was $34.802890 under stated token/cache/head assumptions. Rebind it to the final R2 source and measured fixture payloads; it remains a conditional scenario, not a forecast. Do not use the $0.951801 partial R1 spend to predict a full pilot. Total deadlines and joint reservations may still cause an early stop below the cash ceiling.
