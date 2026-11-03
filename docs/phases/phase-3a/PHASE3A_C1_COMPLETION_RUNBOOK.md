# Phase 3A C1 completion operator runbook

This is the handoff for the single combined block in [the accepted definition](PHASE3A_C1_COMPLETION_DEFINITION.md). It is outside the frozen execution-source inventory. **Verification V3 is a candidate until its actual gate passes. No live-readiness or scientific-completion claim follows from this runbook or a mock result.** V1 and V2 remain retained, unaccepted attempts.

## Working directory and offline proof

Use only the project root. The existing pinned Docker image is required; the verifier does not download or rebuild it.

The fresh V3 verification command is:

```powershell
Set-Location -LiteralPath 'C:\Users\arvik\code\research\Buddha2'
python -B -m followups.phase3a_c1_completion_v1.verify --output runs/phase3a-c1-completion-v1/verification-v3
```

The verifier requires a new directory. Do not execute that command again once its output exists, delete failed candidates, or reuse their identities. It runs contained network-disabled SDK/OpenCode fixtures, the complete paired mock matrix, saved replay, affected tests/static checks, preservation, the actual PowerShell mock resume, and provider configuration inspection without keys or provider startup. Accept only a final `release/offline-gate.json` whose six referenced groups pass and bind the exact current study/source/runtime. Check the independent scientific acceptance as well. Mock scores select no real method.

## One provider launch

Before keys, confirm the exact V3 gate and source still validate, the approved models/rates/control dossier applies, and the same previously declared Anthropic/OpenAI accounts and public-PAYG billing profile remain in scope. An account or billing change needs reconciliation before dispatch. A positive balance alone is insufficient. No additional budget question is needed: the accepted block allows $205.86 new exposure, including $20 counted readiness and the overlapping $50.86 first checkpoint. The unreleased historical $11.44 remains carried separately; maximum cumulative exposure is $227.787885. These are ceilings, not expected spend or a promise of completion.

Run this once in an interactive PowerShell console after acceptance:

```powershell
& 'C:\Users\arvik\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe' -NoProfile -File '.\phase3a-c1-completion.ps1' -Action provider -Stage all -Study 'phase3a-c1-completion-v1/verification-v3/release/study.json' -Grant 'phase3a-c1-completion-v1/verification-v3/release/live-grant.json' -Live
```

`-Study` and `-Grant` are **bare paths relative to this project's `runs` directory**; do not prepend `runs/`. Wait for source/configuration validation and the masked Anthropic and OpenAI prompts. Enter each key there, never in chat, command arguments, files or environment-setting commands. One credential-entry session supplies the controller for readiness, both review barriers and the conditional remainder. The controller keeps keys in RAM; the launcher suppresses provider stream display/retention. Preserve its printed launch-record prefix and do not close its console while it waits for reviews.

## Reviews within the same running controller

Read the frozen V3 `release/study.json` to obtain the exact study SHA. The new public live output directory is:

`runs/phase3a-compat-c1-v1/completion-v1/<study-SHA>/live/`

The fresh canonical live journal is physically under `runs/phase3a-r2-v1/<study-SHA>/live/journal/`; this is the declared reuse of the ledger path seam, never the stopped R2 study. The new allowance claim is `runs/phase3a-c1-completion-v1/live-study.json`.

The controller pauses for up to 30 minutes at each barrier, without new calls while awaiting that review. A trusted operator/AI reviewer can inspect the public records from another console. Human readers are optional and are not a prerequisite. Do not open private credential bindings or writer locks.

1. **Readiness:** inspect `barrier-readiness.json`, `branches/p3a-01-adaptive.json`, and the actual saved SYSTEM/MISSION, delivered context, tool transcripts, harvested consumed strings and final notes named by its proof. Confirm all four native executions, normal INV/DOM/AGG completion before terminal control, complete evidence delivery before decision, edit/notes verification, and settled authoritative accounting. Read the actual reasons for each edit or KEEP_BASE against its evidence; mechanical delivery alone does not establish attention or grounded reasoning. Normal, evidence-grounded KEEP_BASE is eligible. Judge creative utility only later; it cannot control this review.
2. **First pair:** inspect `barrier-first.json`, both original first-pair branches, `seals/p3a-01.json`, available native primary/duplicate assessments and authoritative accounting. Verify counted readiness was reused once, exact request/model/source identities, selection blindness, seal-before-judging, stage/fallback classifications, native scoring, and settled accounting. Known diagnostic failure is classified, not replaced. A negative contrast or diagnostic disagreement does not bar continuation. An engineering review may unlock only originally planned unattempted assessments inside the same total pool; no unknown hold can be unlocked.

Only after the corresponding inspection passes, create its new `inspection-readiness.json` or `inspection-first.json` **in that live output directory**, without overwriting an existing record. Bind the exact `study_sha256`, the barrier's `evidence_sha256`, `fixture: false`, `no_quality_continuation_gate: true`, and substantive `notes` identifying the checked evidence and any limitations. The readiness inspection additionally requires `evidence_grounded_decisions: true`; the first-pair inspection requires `engineering_checks_passed: true`. Do not publish affirmative flags when evidence is missing or a check failed. These are trusted review attestations, not settings to toggle to make progress.

The running controller checks the identity, publishes the durable readiness/engineering review, and continues within the same grant and journal. The first adaptive output stays the same primary with the same costs; there is no replacement generation or second readiness pool. If a review fails, preserve the evidence and stop; do not manufacture a passing inspection.

## Stops, recovery and reporting

- **Known readiness failure:** an unfinished session or the pinned turn-eight terminal request creates `readiness-failure.json`. The doomed terminal request is blocked before intent/provider dispatch; any already admitted work must be settled. No fixed arm or external judgment follows. Do not infer a charge for an unadmitted request or launch another readiness attempt automatically.
- **Unknown delivery/usage, pending intent or integrity hold:** preserve all records and the full reservation, stop further admission, and reconcile before any continuation. Do not resend, recreate a grant/study to bypass the hold, remove the claim, or equate a failed launcher with no charge.
- **Interruption/timeout:** first inspect the exact journal and public launch records. The same source-bound controller validates saved work before reuse; a zero-call completed replay is covered offline. No cold resume of a partially paid editor conversation is promised. Do not relaunch while an owned controller is still running, and do not treat automatic retry as authorization for a fresh attempt.

After normal full execution, public `reports/final/` contains seven JSON reports (`rows`, `coverage`, `analysis`, `summary`, `accounting`, `protocol`, `readiness`) and `PHASE3A_REPORT.md`. Launch records are under `runs/phase3a-c1-completion-v1/launcher/`. If execution stops early, build the validated snapshot/report through the source-bound reporting command, without providers, into a fresh report directory; retain missingness and holds rather than editing rows.

Full scientific completion requires all eight primary finals valid/scored, known new accounting with no reservation/pending/unknown request, a validated readiness review and at least one authentic live native path, plus a classified duplicate diagnostic. Missing prerequisites keep the pooled mean/method selection null. The four paired differences and mean are descriptive for four exposed development prompts. They do not establish held-out generalization, human alignment or equal-realized-compute causation. Finish with saved native/report replay, preservation and a committed public packet. No automatic repeat, Phase 3B, new strategy or model upgrade follows.
