# Continuing interrupted experiments

Buddha2 keeps one logical study across separately identified executions. A continuation reads verified completed work from immutable predecessor records and sends only missing requests. It does not reopen a closed execution or start the whole experiment again.

The current implementation uses the existing accounting journal, Harness² caches and Phase 4 controller. It adds no workflow framework, database or dependency. Harness² and NoveltyBench remain unchanged.

Offline verification completed on 9 November 2026: 166 checks passed across a retained interrupted test run and its targeted completion; Ruff, Mypy and Bandit passed. The actual saved study validated 38 native segments and reconciled all 2,651 requests/$44.975462 without changing the original records. The final packet was prepared and its attempt to obtain a live grant without amended approval was rejected. See the [sanitized acceptance evidence](../evidence/phase4-cm1-v1/resumability-v1.json). No new provider call or paid restart occurred.

## What survives a stop

| Saved work | Continuation behavior |
|---|---|
| Settled provider response | Return the original result when slot, role and effective request match; no provider dispatch. |
| Completed native author stage and harvested edit | Reuse the original reply, workspace evidence and edit after checking its task, instructions, input inventory and source binding. |
| Completed solver rollout | Validate and reuse its original response records and output. |
| Known optional probe failure | Retain the failed probe and continue the native schedule when that failure is allowed. Do not fabricate its missing output. |
| Complete generation pair or passed cost qualification | Adopt it by reference after validating its committed result and provenance. |
| Partial fixed portfolio or assessment | Reuse known requests and execute only missing requests under the declared policy. |
| Uncertain provider delivery | Quarantine that unit. Retain its full reservation and never automatically resend it; independent units may continue within the remaining budget. |
| Missing or changed immutable journal | Refuse preparation: spending cannot be reconciled safely from unverifiable records. |

The cause of interruption does not determine whether a committed result survives. Its identity and evidence do. Continuations can themselves be continued; ancestry is flattened and each physical execution is counted once.

An unfinished OpenCode conversation is a separate boundary. Completed author stages are reusable; arbitrary mid-tool process restoration is not implemented. If a paid author conversation lacks a completed stage, it is explicitly quarantined rather than restarted invisibly. A stage that never admitted a request may prepare locally again.

## Checks before spending

The offline compatibility command verifies the predecessor journals, task identities, producer requests, native stage evidence, completed selections and original model/strategy/judge settings. Every retained result remains attached to its original execution and source. A successor records its own code identity and the explicit compatibility proof; old evidence is not relabelled as newly produced.

The coordinator carries settled spending, calls and reservations forward once. New allowances use the remaining total, allocation, cell and admission ceilings. An uncertain or invalid delivery cannot receive another intent through either the continuation wrapper or a raw child ledger. The generation barrier still precedes every external judgment. Reporting combines the executions without regenerating answers.

Known formatting/read diagnostics, cost-matching misses, negative scores and valid KEEP decisions do not authorize repetition. Required inputs, actual request identities, judge isolation and financial guards remain mandatory.

## Resume versus recovery

Resume reuses valid saved work. Recovery of an invalid model artifact changes the method and needs an explicit amended policy.

`required-plan-rank-once-v1` permits one new attempt after a structurally invalid or unfinished required plan/rank. It applies to fixed candidates and mandatory native base/checkpoint portfolios. The replacement uses a distinct `.recovery1` slot. The original failure and charge remain recorded. A valid original always wins.

This policy does not retry an unfavorable score, refusal, empty/truncated answer, optional probe or unknown delivery. It does not add a third editor attempt. Recovery is disabled by default; it must be declared in the successor method, finite worklist and spending authorization. Existing dollar and cumulative admission ceilings remain hard, so enumerating possible recovery slots does not authorize executing them all.

## Prepared Phase 4 continuation

The accepted source is `8c32d27d…c6de200`; the prepared successor study is `4b18a63c…5188ca5`. Their full identities and the scope digest are in the acceptance evidence. The local provenance packet remains private under the [publication policy](PUBLICATION.md).

| Scope | Bound |
|---|---:|
| Frozen confirmation prompts | Same original 24; no replacements |
| Previously settled usage retained | $44.975462 / 2,651 calls |
| Remaining dollars inside the existing $1,200 total | $1,155.024538 |
| Remaining development / inference / assessment allocations | $88.704375 / $816.320163 / $250 |
| Remaining admissions inside the 40,914 cumulative ceiling | 38,263 |
| Enumerated future slots, including conditional alternatives | 41,095 |
| Historical liability, separate and unavailable for spending | $22.88 |

Both passed qualifications stay closed. The completed pair, complete native arms, author stages and valid candidate prefixes remain part of this logical study. The declared recovery policy may fill a malformed required plan/rank using its one distinct recovery slot; it does not regenerate successful answers or discard the original failure. Judging still follows the all-generation barrier, and reporting retains all 24 cases, primary metrics and grouping sensitivity.

The call quota can be reached before every conditional slot is exhausted. These ceilings bound execution; they are not a guarantee of completion or guaranteed spending. No quota or allocation is silently raised.

Execution requires approval of the amended recovery method: the original definition specifies no automatic retries. One whole-study decision should cover the prepared missing-work continuation, existing launch acceptance, fresh keys after acceptance, official assessments, passive Inspect delivery and closure. Compatible later execution segments must retain the same logical cases, recovery allowance and cumulative caps; a new model, sampling rule, retry ceiling or scientific criterion needs a separately declared change. The user approved this complete continuation on 9 November 2026; see the [decision receipt](../evidence/phase4-cm1-v1/continuation-authorization-v1.json). Launch acceptance is complete with 110 checks, all 16 mandatory regressions, independent review and the actual Windows handshake; see [acceptance](../evidence/phase4-cm1-v1/continuation-launch-acceptance-v1.json). Fresh masked keys are next. No new calls have begun.

## Existing commands

These commands run inside the pinned, contained Linux runtime. `PREVIOUS`, `PROOF`, `RELEASE` and `APPROVAL` are explicit paths under `/results`; they are not shell variables or literal example paths to launch unchanged.

```text
python -m followups.phase4_cm1_v1.workflow compatibility --previous-study PREVIOUS --output PROOF
python -m followups.phase4_cm1_v1.workflow prepare-continuation --previous-study PREVIOUS --compatibility PROOF --output RELEASE --required-artifact-recovery
python -m followups.phase4_cm1_v1.workflow scope --study RELEASE/study.json
```

The first three operations are offline. They do not load keys, create a live spending grant or start generation. Omit `--required-artifact-recovery` for ordinary reuse without that amended policy. Mock predecessors require `--fixture`; live and mock ancestry cannot be mixed. A crashed predecessor without a closed outcome additionally needs verified owner-closure evidence; two owners may not run concurrently.

After the exact scope and method are authorized and the source-bound kit is accepted:

```text
python -m followups.phase4_cm1_v1.workflow grant --study RELEASE/study.json --output RELEASE/live-grant.json --continuation-authorization APPROVAL
```

The original study approval cannot authorize the changed continuation automatically. Its separate receipt binds the exact source, method, frozen 24 tasks, future-worklist digest, recovery rule, cumulative spending and remaining admissions. Fresh masked keys follow acceptance through the existing Windows launcher. No paid execution follows from these examples.

## Passive Inspect view for this continuation

The original single-execution snapshot builder cannot represent adopted generations or the original frame under an amended method. Its display failure is recorded without stopping generation or assessment. The separately versioned [continuation projector](../tools/inspect_continuation.py) reads a stable closed run, first validates it with the existing saved-report path, then creates a standard snapshot for the unchanged Inspect exporter. It preserves logical/physical identities, counts each physical journal once, and separates qualification usage from confirmation cases. It is outside the frozen experimental inputs and does not participate in provider calls or adaptation.

Four synthetic tests and scoped static checks pass; [evidence and limits](../evidence/phase4-cm1-v1/passive-projector-check-v1.json). The [portable-check supplement](../evidence/phase4-cm1-v1/passive-projector-portability-v1.json) validates the current test file in both the canonical and public checkouts, whose scientific source identities differ. Tests inject the saved-validator/ledger boundaries. Current ancestry has no assessment records; generalized inherited-assessment display is deferred. The actual continuation payload, Inspect roundtrip and viewer are checked at closure, not claimed from those tests. During execution, native progress and chat updates remain authoritative.

After a stable closed outcome, run inside the pinned environment:

```text
python tools/inspect_continuation.py --study RELEASE/study.json --grant RELEASE/live-grant.json --output SNAPSHOT
python -m followups.phase4_cm1_v1.inspect_export --help
```

The second command documents the existing passive export interface; neither example authorizes generation or judging.

## The stopped Phase 4 study

The closed execution spent $44.975462 on 2,651 settled calls, with no new held liability and no external assessments. The continuation must retain both passed qualifications, the completed generation pair, the reusable native stages and fixed candidate prefixes, all original failures, all 24 frozen tasks and the existing cost-band miss. It must not replace prompts or select work based on scores.

The original result stays closed and incomplete. A combined report can become complete when all required retained/new outputs and official assessments are present under the declared amended method. It must disclose that amendment, report distinctness and utility together, retain grouping sensitivity and every sampled case, and count all old and new costs. This establishes a reproducible logical study; it does not assert identical random draws to a hypothetical uninterrupted provider run.

See the [closed live report](phases/phase-4/PHASE4_CM1_LIVE_REPORT.md), [optional-probe correction](../evidence/phase4-cm1-v1/optional-probe-fix-v1.json) and [current specification](research/CURRENT_SPEC.md).

## Reuse-verifier correction — authorized 10 November 2026

The first continuation stopped after a 240-second answer timeout with unknown delivery. Its subsequent offline compatibility check exposed a separate verifier bug: inherited editor responses were compared against only the latest physical journal's requests. The user approved correcting that verifier, offline regressions and saved-work replay, independent acceptance, and the existing continuation through closure within the original $1,200 cumulative ceiling. No new scientific strategy, retry allowance, sample or funding was approved.

Each physical search must validate its own manifest-declared ancestry, carrying both original requests and responses. Later executions' rows cannot become evidence for an earlier search. Existing request hashes, source and journal pins, scope checks, duplicate-dispatch rejection and unknown-delivery quarantine remain mandatory. The prior 208-file source is archived exactly; new source and release identities must identify the correction. Fresh keys follow independent acceptance, never a relaunch of the closed controller.

Acceptance requires inherited-proof and repeated-resume regressions, exclusion of later author rows, rejection of missing/conflicting/foreign/tampered or uncertain ancestry, and replay of the actual saved prefix without calls or changes to old artifacts. The standard current-source launch gate then applies. Completed work, all charges and holds, the known failed case and the interrupted case remain preserved. Remaining safe cases can proceed, but the missing-data rule prevents a full-24 positive confirmation; available-case findings remain descriptive. Current stop accounting is in [the retained receipt](../evidence/phase4-cm1-v1/continuation-r01-stop-v1.json).

Current-source launch acceptance passed 113 tests, including all 16 mandatory regressions, with independent review and the actual Windows pre-credential handshake. The accepted continuation was later deferred. [Acceptance and limits](../evidence/phase4-cm1-v1/reuse-verifier-launch-acceptance-v1.json) · [Current status](research/CURRENT_SPEC.md#phase-4-continuation-deferred)
