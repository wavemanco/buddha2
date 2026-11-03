# P3A-RP1 runbook

Status: **the accepted kit's single paid attempt has ended; do not relaunch it**. See [live report](P3A_RP1_LIVE_REPORT.md) for the incomplete result and closeout. The instructions below are retained as the historical accepted operator handoff; their frozen archive copy is unchanged. A corrected method/fresh repetition requires its separately versioned definition and authority. See [offline report](P3A_RP1_OFFLINE_REPORT.md) for the original receipts and archive hashes.
The launcher additionally requires independently accepted, exact source/gate/packet receipts.
This document does not bypass those guards or reopen a stopped grant.

## Scope and identities

Use only the project root. 
The complete method, models, exclusions,
scientific completion criteria and stop rules are in
[definition 1.0](PHASE3A_RC1_PILOT_DEFINITION.md).

| Item | Current candidate |
|---|---|
| Code commit | `3994430` |
| Verification root | `runs/phase3a-rc1-pilot-v1/verification-v5` |
| Study | `e2fd01fab453fdbe4a30297f282301738a42484f238d6a52afe1105f93f62cca` |
| Source, 419 files | `64b839d569e3ddefa3d56e06fc5b431760aef15cdfb3fd38256e04f8565f519a` |
| Native image | `sha256:ce1d4ab2241ce9d141a5447c3da15fb44f62e521c3e2bbe49b74611ff36e3800` |
| Inspect image | `sha256:25b07e51ef9ae948e7f3de5314b91b1ec4c120219ceebfde4b4064525c40a03d` |

Current source uses shared RC1 labels in both arms, genuine authoritative result
ownership, unchanged N1 and canonical answers. Source and method remain frozen
during the live attempt. Existing failed preparations remain preserved separately.

## Cost and operator boundary

Fresh maximum exposure is **$200**, including open/unknown/next-call reservations.
The eight $20 inference cells, $45.86 assessment pool, $50.86 included first
checkpoint and $23.70 initial assessment sublimit all apply jointly. Maximum new
admissions are 775; 967 potential slots do not grant additional calls.

Historical known $24.463235 plus unreleased $22.88 holds remain separate. Full
new-cap cumulative exposure would be $247.343235. There is no calibrated expected
full-pilot cost; the definition's sensitivity examples are not guaranteed spend
or guaranteed completion. No new funding question is required under the user's
recorded policy, but accepted kit preparation and fresh masked keys are required.

Use the same ordinary public-PAYG Anthropic/OpenAI accounts. Public pricing
verification does not certify account access, credits, quota or invoices. Do not
paste keys into chat or use a provider probe/warm-up. The first adaptive primary
is counted readiness inside its own cell and the total cap.

## After final kit acceptance only

The agent opens one **new P3A-RP1** PowerShell window. Its two masked prompts
appear after source/runtime/packet checks. One entry covers readiness, reviews,
remaining pairs and closure; keys are held in process memory, then references are
cleared and owned processes closed at stop/closure. This is not a physical RAM
zeroization guarantee.
An old window, key, controller or unused allowance is never resumed.

For an operator starting the same accepted release manually, use Windows
PowerShell; no `pwsh` command needs to be installed on PATH:

```powershell
& 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -File 'C:\Users\arvik\code\research\Buddha2\phase3a-rc1-pilot.ps1' -Action provider -Study 'phase3a-rc1-pilot-v1/verification-v5/release/study.json' -Grant 'phase3a-rc1-pilot-v1/verification-v5/release/live-grant.json' -Stage all -Live
```

This command is conditional on acceptance; do not start a second concurrent
owner. The launcher rejects absent/foreign acceptance, grant, source or paths
before key readiness. The code preserves the native first-readiness and first-pair
review barriers, then continues only the already-defined remaining work.

**This is a supervised command.** The agent running this chat is responsible for
servicing both canonical review barriers and both Inspect export requests. A
manual operator using the command must arrange a concurrent agent or second
operator for those duties; starting the controller alone does not provide them.
Readiness and first-pair review use actual canonical evidence within the original
30-minute review windows. Never fabricate a semantic-grounding approval or use a
quality score as a continuation threshold.

At both `first-pair` and `closure`, watch the exact public path
`runs/phase3a-rc1-pilot-v1/native/<study>/live/visibility/<checkpoint>/request.json`.
Within that request's original 600-second window, the agent/operator launches the
separate keyless exporter with mode `host`, its sibling `snapshot` directory,
a fresh output under `runs/phase3a-rc1-pilot-v1/visibility-exports/`, and `--ack`
pointing to the sibling `result.json`. The exporter validates the request and
claims its ownership path atomically; it cannot grant core continuation. Do not
launch or acknowledge an expired request, extend its deadline, or repair exports
while provider admissions are running. Offline repair of the same frozen data
uses a new output identity after the owner is paused/closed and makes no calls.

### Exact supervised handoffs

Let `R` be the research project root, `S` the study ID in the table above, and
`N=<R>\runs\phase3a-rc1-pilot-v1\native\<S>\live`.

| Signal under N | Operator action | Deadline |
|---|---|---|
| `barrier-readiness.json` | Inspect actual proof/native evidence; publish `inspection-readiness.json` only if supported. | Original 30-minute wait |
| `barrier-first.json` | Inspect the sealed pair and engineering/accounting evidence; publish `inspection-first.json` only if supported. | Original 30-minute wait |
| `visibility\first-pair\request.json` | Run the separate keyless export below. | Original request UTC deadline |
| `visibility\closure\request.json` | Run the separate keyless export below. | Original request UTC deadline |

Each inspection copies `study_sha256` and `evidence_sha256` from its barrier,
sets `fixture:false` and `no_quality_continuation_gate:true`, and records
substantive nonempty `notes`. Readiness additionally requires supported
`evidence_grounded_decisions:true`; first-pair requires supported
`engineering_checks_passed:true`. The controller creates `readiness-review.json`
and `first-review.json`; never fabricate those records. First-pair visibility
follows engineering review and assessment closure; keep watching afterward.

From R in a separate credential-free host process, substitute checkpoint C
(`first-pair` or `closure`) and a fresh export name E:

```powershell
python -B -m followups.phase3a_rc1_pilot_v1.inspect_adapter host --snapshot "<N>\visibility\<C>\snapshot" --output "<R>\runs\phase3a-rc1-pilot-v1\visibility-exports\<E>" --ack "<N>\visibility\<C>\result.json"
```

Use host Windows paths, not the request's container `/results/...` paths. Never
overwrite an inspection/ACK, copy a prior approval, reset a deadline or approve
based on quality scores. These are existing handoffs, not additional gates.

## Monitoring and closure

Inspect only named sanitized launcher inspection/result files and public native
branches, reviews, journal/audit and visibility records. Do not inspect private
basenames or real/unknown provider stdout/stderr, including their metadata. Never
restart or resend merely because observation times out; recheck the exact owner.

First-pair and closure exports are immutable, separate, keyless snapshots. They
show imported native evidence, model roles and real audit intervals/CSV. Task
dates identify the observed snapshot interval, not provider-server latency or an
invented controller completion. Activity's model-event chart remains unavailable;
use dated InfoEvents and native-audit.csv. Neither scores nor viewer status decide
continuation. Unproved child ownership is an integrity stop.

Scientific completion requires eight valid scored primaries, a qualifying normal
native path, classified duplicate and no new pending/unknown/unresolved liability.
Otherwise retain partial paired evidence and null pooled fields. Keep old holds
fully reserved. Close every attempt/noncall, replay eight report files with zero
calls, export reached checkpoints and independently verify the closure packet.
No automatic paid repetition or Phase 3B execution follows this attempt.

## Held-report closeout after owner settlement

After a canonical/ownership integrity stop, do not resume or regenerate. Retain
an exact public settlement receipt proving the provider CID/PID1, recorded
PowerShell PID/start identities and every claimed core/exporter owner have
terminated, with owned containers removed. Clear launch-key references. Preserve
the canonical stop, journal/audits, staging, snapshots and original statuses.

Only after that proof, one fresh keyless H1 reporting job may reconstruct the
held outcome using the current `workflow.snapshot(study, grant, False)` and
`report.write_report(data, fresh_output)`. Use network none, read-only source and
inputs, a fresh output mount and blocked model constructors, sockets and process
creation. Require `scientific_complete=false`, null pooled mean/direction/selection
and every unresolved liability retained. This is reporting of a failed attempt,
not eligibility recovery. If validation fails, retain closure as incomplete.

The closure packager requires all eight files under the live run's
`reports/final/`. Independently verify the held files before byte-exact adoption
into that previously absent directory. Preserve and validate existing finals;
never replace them. Partial/conflicting finals or unproved owner settlement stop
this procedure. No dispatch, retry, ranking, assessment, rescoring or liability
release is permitted. A separate I1 export may read a fresh immutable held
snapshot after settlement, without acknowledging an expired live request.
