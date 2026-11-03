# P3A-RC1 — Offline ranking-contract checkpoint

Definition **1.0**, 2026-10-31, America/Los_Angeles. **Defined only. Implementation, tests, saved-response replay and experiments under this checkpoint have not started.** The current user request authorizes specification updates only: no code or paid calls. A later instruction to execute this unchanged checkpoint can cover its complete bounded offline scope without separate approvals for its internal tasks.

## 1. Placement and objective

This is a **new offline follow-up within the Phase 3A research workstream**, outside the closed P3A-HI block. It is not Phase 3B, a reopening of the old controller or another paid attempt. P3A-HI's sections 7–10 distinguish a faithfully closed failed attempt from the unmet scientific milestone and prohibit automatic paid repetition or silent post-observation method changes.

The [closed P3A-HI result](P3A_HI_LIVE_REPORT.md) remains two of eight primary portfolios scored, $7.882971 in new known cost and zero new holds. Its two older unknown liabilities remain $22.88. The malformed p3a-02 rank reply remains rejected. Neither the unused $205.86 ceiling nor the standing budget policy starts a fresh study.

**Objective:** define and, if subsequently authorized, prove a minimal shared ranking interface that avoids asking the ranker to copy long canonical identifiers, while preserving every answer, strict rejection of invalid/ambiguous orders, and equal contract access for fixed and adaptive procedures. This is human-authored experiment engineering, not learned Harness² improvement. Short identifiers are a prospective delivery hypothesis, not a demonstrated live reliability or quality gain.

**Usable output:** a small reusable offline rank-input/rank-result adapter, a frozen acceptance corpus, source-bound pass/change-required evidence and a precise integration handoff. Given an immutable ten-answer parent, its sealed map and matching request/result provenance (or an explicitly synthetic fixture), the tool can return a validated canonical permutation or an explicit rejection without generating or judging anything. It is not a provider-ready pilot kit.

## 2. Inputs and preservation

Use only the project root. 

The bounded inputs are:

1. The frozen [HI definition](PHASE3A_H1_INTEGRATED_PILOT_DEFINITION.md), closed report, accepted public outcome/packet and their source identities. Preserve the 356-file frozen source, historical definitions, grants, reports and archives. Retain the separate accepted [Inspect display repair](../../operations/inspect/INSPECT_DISPLAY_V2_REPORT.md).
2. The single saved p3a-02 composed-rank failure: exact raw reply, original canonical IDs, recorded N1 rejection and public request/result hashes in `runs/phase3a-h1-integrated-v1/verification-v4/reviewer/live-primary-failure-v1/`. Read only its named public dependencies when needed.
3. The exact existing [N1 implementation](../../../followups/rank_format_v1/normalizer.py), its [policy definition](../phase-2/PHASE2B_RANK_FORMAT_DEFINITION.md), shared C-N renderer/strategy path, canonical portfolio/permutation functions and current seed.
4. One already exposed saved ten-answer **method-B parent**: follow the selected p3a-01 fixed primary's recorded selected-candidate identity (`candidate-06`) to that candidate's exact saved `parent_B`. Require the selected primary's `parent_sha256` to match `e2307d9d007495e9381fe723edacf437f998e57cf15b09d98a97c83688645408` and authenticate the saved B record against that identity; preserve its original generation order. The selected primary itself is already ranked method C and must not be relabelled or used as a B parent. Use the recorded B parent solely as a mechanical mapping fixture, with deterministic test permutations unrelated to scores. No other prompt or portfolio corpus is needed.

Exclude private basenames (`credential-binding.json`, `.writer.lock`, `.env`, `auth.json`, `credentials.json`) and all real/unknown provider stdout/stderr variants before metadata or content access. Reject linked/escaped paths. No recursive sweep of provider workspaces or logs. No credential, environment, account, access or token-count probe.

Prospective implementation belongs in a new `followups/phase3a_rank_contract_v1/` namespace, with fresh `runs/phase3a-rank-contract-v1/` and `evidence/phase3a-rank-contract-v1/` outputs. Do not edit the frozen implementations or make historical validators accept changed artifacts.

## 3. The one prospective contract: RC1

This checkpoint has **one candidate**, not a strategy/format tournament. Retained N1 behavior is its historical control. Do not add a second candidate automatically if RC1 fails.

| Element | Frozen prospective rule |
|---|---|
| Canonical identity | Existing `response-<hash>` IDs, answer texts, statuses, request IDs and generation order remain unchanged in canonical portfolios. Duplicate answer texts are allowed; canonical IDs must remain distinct. |
| Rank-only labels | Assign ASCII strings `r01` through `r10` by the existing generation order, freshly within each parent portfolio. Labels are local handles, never new canonical response IDs. |
| Model input | Use the existing rank request renderer and JSON keys. Its ten response entries expose the short labels as their `id` values, with exact original texts and order. Preserve the seed's three strings, ranking criteria, message wording, model/settings and omissions. No provider-enforced schema or additional fixed prompt paragraph is introduced here. |
| Requested reply | One object such as `{"order":["r03","r01","r02","r04","r05","r06","r07","r08","r09","r10"]}`: ten string labels, each supplied label exactly once, no extra keys. This is an illustrative permutation, not a target semantic ranking. |
| Acceptance policy | Invoke the **unchanged N1 implementation** with the ten short labels as its expected IDs. Preserve its existing bounded wrapper/prose/fence and repeated-identical-candidate behavior, 65,536-byte UTF-8 limit, structural depth 2, maximum 16 candidate objects, and every rejection rule. The requested single-object format is not a claim that N1 becomes a new stricter single-object parser. |
| Translation | Only after N1 accepts, translate its label permutation through the precomputed bijection and pass the resulting canonical-ID order to the unchanged canonical permutation function. No text rewriting, trimming, deduplication, identity regeneration or answer replacement. |
| Invalid/ambiguous output | Reject duplicate, missing, foreign, wrong-case/confusable or non-string labels; malformed/extra-key objects; conflicting valid orders; and any valid-plus-invalid candidate mixture. Never choose the first/last/claimed corrected object, perform fuzzy ID repair, ask for a second rank call or fall back to generation order. |
| Editable surface | Mapping, label assignment, schema and validation are external immutable execution controls. Keep all three declared strategy fields editable, including `rank_system`; do not freeze or remove the ranking adaptation dimension. Contract violations remain failures rather than permission to accept a different shape. |
| Shared use | The same helper and contract serve every fixed candidate and native adaptive rollout. Preserve their different selection topology: fixed best-of-six versus the native composed final. No special adaptive rescue or extra fixed candidate. |

The mapping record binds contract version, parent portfolio hash, ordered canonical IDs/labels, study/run/candidate-or-rollout identity and consumed strategy identity. Seal the mapping before rank dispatch. A separate request provenance record links its digest to the complete effective rank request hash; a result derivation links raw reply hash, N1 disposition, accepted label order, translated canonical order and output hash. Do not introduce a circular self-hash or put canonical identity metadata into an undisclosed model message.

The new output's `procedure_sha256` must identify RC1's rank-I/O profile/mapping rule, exact N1 revision and consumed strategy; it must not masquerade as the legacy C-N procedure. Retain the existing model `settings_sha256`. Bind each particular map instance through the derivation/output provenance separately from the method definition. A shared method change still requires fresh future study identities and separate reporting from historical C-N/HI outcomes.

Short aliases repeat across parents, so N1 shape acceptance alone cannot establish response ownership. Decoding must verify the exact parent, map, rank-I/O profile and rendered request/result binding before permutation. A syntactically valid reply paired with a stale parent/map/request must fail. Retain the existing slot/study/request identity checks in later live integration; an unbound raw reply is only a mechanical fixture, never an eligible live result.

Keep alias-level N1 diagnostics and canonical derivation separate. Never rewrite the original provider reply to pretend it emitted canonical IDs. Keep the canonical mapping in runtime provenance; do not add editor instructions or workspace files. Existing factual execution views must faithfully show the new rank inputs/replies with refreshed hashes and their lossless request association, without benchmark scores, grader text or additional quality guidance.

Every test-created rank reply/permutation is explicitly synthetic and unscored in its new derivation record, even when the parent answers were provider-backed. Preserve the parent's original source flags; do not invent a paid rank request/result, mark a test permutation as model-produced, or promote it to a primary.

## 4. Scope of the later offline work

If execution is subsequently authorized, perform these internal tasks as one checkpoint:

1. Authenticate the named parent artifacts and reproduce the saved rejection under its **original long-ID input and original N1**. Record the exact failed disposition without rescuing or rescoring it.
2. Freeze the RC1 contract, finite fixture inventory and expected dispositions before writing its implementation. Trace the existing fixed/native caller seams and list the precise future request/provenance/replay changes.
3. Implement the minimum shared formatter/mapping/validator adapter outside frozen source, reusing N1, the real request renderer and canonical portfolio/permutation functions. Exercise it through fixed-candidate-shaped and native-rollout-shaped offline fixtures; do not copy Harness² orchestration or make a generic plugin framework.
4. Run the bounded mechanical acceptance matrix below in the existing network-disabled environment, with no keys or provider/model construction. Preserve rejected preparations, raw fixture inputs, decisions, mappings, hashes and zero-call saved replay.
5. Obtain one independent review of the shared contract, unchanged historical evidence and exact accepted artifact set; deliver a concise report/runbook and pass/change-required decision. Local commit is included; publishing is not.

This scope proves deterministic rank I/O and identity preservation. It does **not** include full native/OpenCode/SDK launch integration, a four-prompt rehearsal or a live-readiness certification. The handoff must name the remaining seams—shared execution, effective request hashing/admission, rollout/replay validators, editor evidence, source/runtime/study/worklist identities and passive Inspect projection—rather than describing the prototype as ready to launch.

## 5. Deliverables and completion criteria

| ID | Required evidence |
|---|---|
| RC1-1: historical fidelity | The named saved reply still yields the original N1 rejection; all historical parent files and the 356-file frozen source remain unchanged. No newly valid historical primary or score is created. |
| RC1-2: deterministic identity | Exactly ten local labels form a bijection to the exact parent IDs; mapping is deterministic in generation order and cannot be rebound across parent/run/strategy/request identities. Reject wrong size, duplicate IDs, tampered mapping/hash and foreign parent identity. Specifically reject a stale cross-parent reply/map even when its alias permutation is syntactically valid. Identical answer texts with distinct IDs remain distinct. |
| RC1-3: valid mappings | Identity, reverse and one fixed nontrivial permutation pass using both synthetic data and the one saved mapping fixture. The real canonical permutation function preserves every answer's exact bytes, identity/status/request reference and cardinality. Literal alias/ID strings inside answer text remain untouched; no global text substitution. |
| RC1-4: unchanged rejection policy | Explicit positive cases cover N1's existing wrappers and repeated identical valid candidates. Negatives cover missing/duplicate/foreign labels, numeric/Boolean values, wrong case/confusables, duplicate/extra keys, malformed/deep/oversized input, object overflow, conflicting permutations and invalid-plus-valid correction patterns in both orders. No coercion, repair or answer fallback. |
| RC1-5: shared surface/settings | Both caller-shaped fixtures use one implementation and identical rules. Actual rendered message/settings comparisons isolate the ID-value substitution. The three seed strings remain exact, and a synthetic `rank_system` edit is still consumed without granting authority to change the runtime schema. |
| RC1-6: reproducibility/isolation | Replaying the same saved fixture produces identical mapping/disposition/output identities with zero calls. Tampered provenance is rejected. Actual offline containment and affected unit/lint/type/security checks pass; no dependency installation or credentials are needed. |
| RC1-7: usable handoff | Independent review and a source-bound report list passed/failed checks, precise method delta, preserved history and all remaining integration requirements. No live-readiness or scientific-effectiveness claim is made. |

**Pass:** all seven requirements are supported and the reusable offline tool plus its exact evidence/runbook are delivered. A live model need not be consulted and no favorable semantic ranking is required.

**Change-required/no-go closure:** if the selected approach cannot satisfy the scope/invariants within the limit below, retain the original failure, whatever verified replay/analysis/prototype/check results were completed, and a specific blocker/decision report. Mark any unperformed or unproved check explicitly. This honestly closes the bounded checkpoint; it does not count as accepted implementation, Phase 3A scientific completion or authority to try another method.

## 6. Exclusions

No new model/provider/SDK/token-count calls, local model inference, answer generation, semantic ranking experiment, judging or human collection. No response-schema provider setting, model/effort/token/tier/geography change, new prompt-quality rules, editable-surface reduction, parser leniency, rank repair/retry/fallback or old-output rescue. No new cohort, prompt replacement, held-out contents, CrPO/MuCE/Bayesian-surprise work, strategy search, shared experience, `seq,k=2`, benchmark/Harness² algorithm changes, new dependencies, generic infrastructure or broader Inspect Activity instrumentation. No historical accounting change, new grant, launcher or paid run.

## 7. Cost, effort and stop rules

**API budget and expected API cost: $0.** This planning update makes no call. Later authorized offline execution also has a zero-provider-call requirement. Assistant-session charges, local compute and engineering time are separate; the prior study's unused allowance supplies no authority.

Proposed execution limit: **two elapsed working hours for the whole offline checkpoint**, including review and reporting, not two hours per agent. Start that clock only after implementation is authorized. At 45 minutes, report progress and whether the single candidate still fits; no extra permission is needed to finish unchanged work inside the limit. Do not start a new implementation/test batch after 100 minutes; reserve the final 20 minutes to settle owned local work, retain evidence, finish independent review and report. At two hours, stop with pass or change-required; incomplete review cannot be called a pass. No automatic extension or new prerequisite chain.

Stop earlier on a source/provenance mismatch, unavailable offline containment, a required dependency/provider/credential change, a need to relax N1 or historical eligibility, altered answer identity/content, asymmetric contracts, or integration that requires a broader rewrite. Preserve the failure and report the smallest required amendment. Routine local fixes and reruns of affected offline checks are permitted only within the same contract/time limit, with failed artifacts retained. Do not tune against scores, add cases/operators until something wins, or substitute a new candidate automatically.

**Next after a pass:** define one fresh, separately versioned Phase 3A pilot block that includes all remaining execution integration, source-bound offline acceptance, one counted four-prompt comparison, internal reviews and closure. Refresh its exact models/settings, call counts, resource/cost ceilings and stop rules before starting it. That later block must use RC1 in both arms, regenerate all primaries, retain historical costs/holds and keep old results separate. Do not add unnamed readiness stages or reopen P3A-HI. Phase 3B and held-out confirmation remain later, separately defined work.
