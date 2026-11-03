# Phase 2B execution runbook

Use PowerShell **7.2 or later** (`pwsh`), Docker Desktop's Linux engine and only the project root. This runbook supplies commands, not spending authority. The frozen P2-R definition is specification 0.18; closure evidence and the release identity are in `PHASE2B_EXECUTION_KIT_REPORT.md`.

## Operator inputs before a future live launch

Obtain an explicit grant for this release and stage. Proposed limits are $20 first stage and $125 **cumulative** for the pilot; neither is currently authorized or guarantees completion. Confirm the dated public-price review still applies and both accounts use the supported direct public PAYG profile, without private/priority/fast/custom endpoint or project billing overrides. Confirm current model availability as an operator declaration; do not make extra provider probes. Actual access, settings and usage are observed in the counted first block.

The two keys are supplied only through the launcher's masked prompts after its inspected, source/grant-bound handshake. Do not put keys in commands, environment variables, files, Docker arguments or chat. An existing process environment is not searched for keys. Credential fingerprints bind subsequent execution to the same pair without retaining the keys.

## Prepare and inspect

The delivered release is `runs/phase2-release-r018/release/study.json`. Its retained source, launcher, cost sheet, nonauthorizing packet and completed `release-readiness.json` belong together. Do not run preparation into that existing directory after changing code. Any effective change requires a new identity, verification and compatibility assessment.

```powershell
Set-Location 'C:\Users\arvik\code\research\Buddha2'
.\phase0.ps1 run phase2-release inspect --study /results/phase2-release-r018/release/study.json
```

Inspect `PHASE2B_EXECUTION_KIT_REPORT.md`, the requirement checklist, price review, cost sheet and launch packet before approving anything. Ordinary `phase0.ps1` commands run without network and cannot send provider calls.

## First counted block — only after an applicable user grant

The following grant command records the operator's already obtained approval and account/profile confirmation. Choose the approved amount in micro-USD, at most 20,000,000. It is a cumulative ceiling, including unsettled reservations. Do not execute this command merely to try the kit.

```powershell
.\phase0.ps1 run phase2-release grant-template --study /results/phase2-release-r018/release/study.json --stage first --grant-id live-first-001 --cap-micro-usd 20000000 --authorize-live --confirm-public-payg --output /results/phase2-release-r018/grants/live-first-001
pwsh -NoProfile -File .\phase2-release.ps1 -Action preflight -Study phase2-release-r018/release/study.json -Grant phase2-release-r018/grants/live-first-001/grant.json -Stage first
pwsh -NoProfile -File .\phase2-release.ps1 -Action provider -Live -Study phase2-release-r018/release/study.json -Grant phase2-release-r018/grants/live-first-001/grant.json -Stage first
```

The first stage stops after its one task/repeat: at most 55 calls and three ordered native assessments. It cannot select a seed from the full 72-order study. Do not assume a zero process exit means the block is complete: read the saved status, missingness, failures and unresolved reservation.

Use the actual study hash from inspection as `<STUDY_HASH>` below. Live results use one fixed journal at `runs/phase2-release-r018/<STUDY_HASH>/live`; changing an output directory cannot create another allowance.

```powershell
.\phase0.ps1 run phase2-release report --study /results/phase2-release-r018/release/study.json --run /results/phase2-release-r018/<STUDY_HASH>/live --cutoff <UTC_CUTOFF> --output /results/phase2-release-r018/reports/live-first
```

## Review and cumulative expansion

Review the actual first-stage trace/settings, A/B/C native assessments, coverage, journal and usage accounting. Every first-stage slot must be classified and no liability may remain. Favorable utility is not required. The review command independently replays these requirements; `--approve` cannot bypass them. An incomplete first block stays incomplete without replacement calls.

After that review and a separately applicable expansion grant:

```powershell
.\phase0.ps1 run phase2-release review --study /results/phase2-release-r018/release/study.json --review-id live-first-review-001 --cutoff <UTC_CUTOFF> --approve
.\phase0.ps1 run phase2-release grant-template --study /results/phase2-release-r018/release/study.json --stage expansion --grant-id live-expansion-001 --cap-micro-usd 125000000 --authorize-live --confirm-public-payg --output /results/phase2-release-r018/grants/live-expansion-001
pwsh -NoProfile -File .\phase2-release.ps1 -Action preflight -Study phase2-release-r018/release/study.json -Grant phase2-release-r018/grants/live-expansion-001/grant.json -Stage expansion
pwsh -NoProfile -File .\phase2-release.ps1 -Action provider -Live -Study phase2-release-r018/release/study.json -Grant phase2-release-r018/grants/live-expansion-001/grant.json -Stage expansion
```

Expansion reuses the first ledger and executes only the remaining 23 blocks. A $125 cumulative grant leaves $123 after $2 settled, not $143. The full worklist has at most 1,320 requests/72 assessments, including the first block. Another within-policy top-up needs its own explicit approval, a new grant ID and the current predecessor; it never resets cost. Above-policy changes require a recorded amendment and compatible new verification.

## Stop, interruption and recovery

Use Ctrl+C to interrupt the host. The launcher attempts a bounded stop of its own validated container and retains the handle/termination evidence. If the host is forcibly killed or Docker becomes unreachable, inspect the saved `runs/phase2-release-r018/launcher` handle on recovery. Compare that container's actual image, mounts and command with the saved inspection before stopping only that verified owned container; an ID alone is a handle, not authority. Never start a second launcher while the first container is running. A surviving provider request can remain billable.

Every request has a durable intent before dispatch. Unknown delivery/usage retains the full reservation and halts; closing a console, changing a grant, restarting Docker or moving directories does not release it. Do not delete, truncate, edit or manually relabel journal records. Investigate an unresolved outcome before any further live work; the current kit intentionally refuses dispatch rather than guessing a settlement. No automatic retries, replacements, response repair or fallback are allowed.

With unchanged source, inputs, stage, active grant and keys, repeat the exact provider command to resume. Settled slots are replayed from saved evidence, and a completed stage adds zero calls. A changed credential pair or stale historical grant is rejected. The report commands need no keys or SDK construction and remain available for partial/failed runs.

## Report, replay and optional later humans

```powershell
.\phase0.ps1 run phase2-release report --study /results/phase2-release-r018/release/study.json --run /results/phase2-release-r018/<STUDY_HASH>/live --cutoff <UTC_CUTOFF> --output /results/phase2-release-r018/reports/live-final
.\phase0.ps1 run phase2-release replay --study /results/phase2-release-r018/release/study.json --run /results/phase2-release-r018/<STUDY_HASH>/live --cutoff <SAME_UTC_CUTOFF> --output /results/phase2-release-r018/reports/live-replay
```

Use the same cutoff to reproduce the exact closed decision. Reports retain all 72 denominators, native scoring, paired prompt means/contrasts, missingness, generation/assessment costs and liabilities. Complete benchmark evidence can conclude without human readers. Synthetic rehearsals never select a real seed.

`human-packets`, `human-import` and `human-decide` use this same study/run. They prepare local forms or attach explicitly supplied submissions; they contact nobody. Activation of real collection remains separately authorized. Bind the original delivery/window/eligibility before exposure, preserve each reader's first form and attach late forms through `--previous`. A human decision requires `--parent` pointing to the original closed benchmark decision. Save every assessment/decision in a new directory. It supplements that branch without editing scores, outputs or the benchmark decision. The synthetic public-command demonstration is under the P2-R evidence namespace.

## Offline rehearsal

`-Action mock` uses fake keys, actual pinned SDK MockTransports, blocked sockets and network `none`. `-Action provider-config` creates, inspects and removes the proposed bridge configuration without starting it or reading keys. A fixture grant cannot authorize provider mode. Both operations belong to software verification and establish no real account/model/billing compatibility.

The Docker boundary is not a domain allowlist firewall. The checked SDK endpoint/redirect configuration and provider controls are narrower application guards; no OS domain-level egress enforcement is claimed. Host Docker administration remains trusted. Keep historical source bundles and run manifests unchanged; old replay uses the retained version rather than weakening current guards.
