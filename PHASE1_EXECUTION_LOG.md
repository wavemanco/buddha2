# Phase 1 live execution log

2026-10-25, America/Los_Angeles. Working root: `C:\Users\arvik\code\research\Buddha2`.

**Current status: Phase 1 complete, diagnostic-only evaluator.** All 48 scheduled judgments completed, costing $0.112696 from reported usage; no retries, replacements or unresolved reservations. The user-approved readiness exception, final freeze and committed predictions are recorded below. Audit labels were opened only after prediction commit `8e5765d`. See [PHASE1_REPORT.md](PHASE1_REPORT.md). Earlier sections retain the successive historical checkpoints.

## Authorization

The user explicitly replied **“Authorize up to $5 for Phase 1 (Recommended)”** to the prepared checkpoint's authorization question. This authorizes the frozen Sonnet 5.5 calibration/audit: 48 scheduled judgments, at most 52 generation attempts, and a $5 ceiling including unresolved reservations. The first two calibration presentations remain the readiness checkpoint before expansion. Later phases are not authorized.

The immutable [authorization record](evidence/phase1-live/authorization.json) binds the grant to the existing staged bundle, canonical digest `1abe96e47ceaae4101ba5e4b6d7e793740f94f9f54c382effbfabc6ba89149d3`, at `runs/phase1-live-r05`. A matching record is in that run's `controls/authorization.json`. The original [preparation report](PHASE1_PREPARATION_REPORT.md) and frozen specification remain historical evidence; their pre-authorization wording is superseded by this user reply without changing the population, model, rubric or thresholds.

## Initial preflight snapshot

- Confirmed current worktree at checkpoint commit `68feb6a` before recording authorization; frozen package hashes still match the staged bundle.
- Rechecked the first-party published Sonnet 5.5 price: $2/$10 per million input/output tokens. [Model documentation](https://platform.claude.com/docs/en/models/sonnet-5-5/overview), [pricing](https://platform.claude.com/docs/en/about-claude/pricing).
- Checked only the exact `ANTHROPIC_API_KEY` variable's availability in this process and Windows user/machine environments. It is absent in all three. No credential value, credential file, home directory or original project was read.
- No live container, token-count request or generation request was started. Generation charges and unresolved liabilities remain zero. No audit labels were opened.

## Masked PowerShell credential setup

At the user's request, `phase1-key.ps1` provides a masked `Read-Host -AsSecureString` prompt. It saves only DPAPI ciphertext in the dedicated Windows user environment entry `BUDDHA2_PHASE1_ANTHROPIC_DPAPI`, outside project/container mounts. The raw key is decrypted only for a child launch environment, never placed in command arguments, logs, project files or command history. The temporary encrypted entry will be cleared at Phase 1 closure.

Synthetic credential checks passed: hidden-input contract, DPAPI roundtrip, no plaintext output, refusal to overwrite an existing entry, missing-key refusal before launch and exact cleanup. No test made a provider request. The user entered their key in the opened PowerShell window and replied Ready. The helper's `run` action retains the fixed run/stage and $5 cap and preserves the first-two gate. A child PID is surfaced for interruption recovery.

```powershell
.\phase1-key.ps1 -Action set
.\phase1-key.ps1 -Action status
.\phase1-key.ps1 -Action run -Stage calibration
.\phase1-key.ps1 -Action clear
```

The `set` action never calls the provider. `run` is paid execution under the already recorded grant and readiness/audit gates. `clear` removes only the helper's dedicated encrypted entry.

## First two actual calls

Exactly two calibration calls completed for $0.004754, zero retries and zero unresolved reservations. They returned the requested model/settings and complete accounting. The first output parsed correctly; the reverse-order output added prose before JSON and remains `malformed`. The automatic readiness gate requires both statuses `ok`, so the run is stopped. No further calls, human-label access or audit inference occurred. See [PHASE1_READINESS_REVIEW.md](PHASE1_READINESS_REVIEW.md) for evidence and the proposed bounded exception, which requires explicit review before continuation.

## Original next-action record

The earlier credential prerequisite is resolved. The spending grant remains valid; do not ask for it again. The new prerequisite is review of the observed readiness-format failure and a concrete continuation decision. Do not retry the malformed result, add experiments or open held-out labels while waiting.

At that checkpoint Phase 1 remained incomplete pending the declared calibration/audit, replay and requirement-by-requirement report. These requirements were subsequently completed as follows.

## Approved continuation and final audit

The user explicitly approved the documented readiness exception. The active [exception](evidence/phase1-live/readiness-exception-approved.json) and [operator review](evidence/phase1-live/readiness-review.json) retained both first outcomes, including the malformed failure, without changing the automatic writer/parser, model/settings, selected data, audit floors or $5 ceiling. Exactly 22 further calibration presentations completed; there were no replacements or retries.

Full calibration had 11 `ok` and 13 `malformed` outcomes at $0.060460 total. The one preplanned rubric wording revision reinforced JSON-only formatting; creative criteria remained byte-identical. The [calibration review](evidence/phase1-live/calibration-review.json), report and final audit freeze were committed in `56f09d9` before audit dispatch. Calibration was not rerun.

All 24 audit presentations then completed with `ok` status, costing $0.052236. Before label opening, the complete immutable audit prediction set and pre-unseal record were committed in `8e5765d`. The subsequent offline report found human agreement on both orders for 4/12 prompts and order consistency for 8/12, below the frozen 9/12 and 11/12 floors. Five ties and one abstention remained zero-credit outcomes. The resulting evaluator is diagnostic-only.

## Replay, accounting and cleanup

The completed phase used 48 generation requests and 48 separately logged free token-count requests: 22,528 input and 6,764 output tokens, $0.112696 at the frozen tariff, zero retries and zero liabilities. This is usage-based cost, not an independent provider-invoice check. Offline replay of calibration, audit and inspection reproduced assessment/execution bytes with zero new calls. Sanitized runtime records show network-none/no-key analysis.

The helper's dedicated encrypted Windows user environment entry was cleared and status confirmed absent. The original folder, protected Phase 0 source/evidence and both pinned upstream trees remain untouched. No later phase started. See [replay verification](evidence/phase1-live/replay-verification.json), [cleanup](evidence/phase1-live/credential-cleanup.json) and the final report's P1-1 through P1-8 evidence table.
