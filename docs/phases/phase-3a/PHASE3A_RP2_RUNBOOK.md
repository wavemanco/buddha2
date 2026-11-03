# P3A-RP2 runbook

November 2, 2026. Use only the project root. This runbook implements the already approved RP2/AM1 block; it supplies no additional paid repetition or bypass of acceptance guards.

## Before fresh keys

Require the complete source-bound twelve-group offline gate, independent source acceptance, actual public archive audit and independent extracted-only cold replay acceptance. Verify the exact archive/manifest/receipt bindings before the launch. See [offline report](P3A_RP2_OFFLINE_REPORT.md), [definition](PHASE3A_RP2_RECOVERY_DEFINITION.md) and [AM1](PHASE3A_RP2_AM1_DEFINITION.md). Do not resume a retired run or use the distinct fake-key rehearsal study for provider execution.

The accepted main study is `bc86391000266d413276de0f9ca8fb7f4f5b65632aa509d650f8236a48735be8`, source549 `517b8efcdfc68bbb3e6ac6d260dc2e7e0541fdb02ea46784afc4ca5e2d300ed8`, implementation `9ef1d3c`. Inputs are `phase3a-readiness-recovery-v1/verification-v3/release/study.json` and the adjacent `live-grant.json` beneath `runs`. Source/prompt/model/settings/criteria remain fixed after observation.

The approved fresh global exposure cap is $190, including unknown/next-call reservations; included checkpoint $50.86, readiness/inference cell $20, assessment pool $45.86. These overlap. Maximum 775 new attempts; historical known $29.874161 and old holds $22.88 remain unchanged. Maximum cumulative exposure $242.754161. A reservation is a conservative admission bound, not guaranteed spend. There is no calibrated expected full-run cost.

## Start and attachment

Dispatch a dedicated keyless agent first and verify it is actually running. Give it this runbook, the exact accepted release, [SUPERVISION.md](../../../followups/phase3a_readiness_recovery_v1/SUPERVISION.md) and all public handoff paths. It must independently monitor startup rather than wait for the parent to receive a chat acknowledgement. It receives no credentials, provider transport or authority to change grants/scores.

Only after acceptance, open a NEW interactive PowerShell window using this command with the actual dispatched canonical supervisor handle replacing the placeholder:

```powershell
& 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -File 'C:\Users\arvik\code\research\Buddha2\phase3a-readiness-recovery.ps1' -Action provider -Study 'phase3a-readiness-recovery-v1/verification-v3/release/study.json' -Grant 'phase3a-readiness-recovery-v1/verification-v3/release/live-grant.json' -SupervisorAgent '/root/ACTUAL_AGENT_HANDLE' -Stage all -Live
```

Use the pinned bootstrap instead of an uninstalled `pwsh` command. Wait for the two masked prompts; validation may take several minutes. The user enters Anthropic/OpenAI keys directly there for the same declared public-PAYG accounts. Never put keys into chat, arguments, files or tool output. One entry covers the whole controller and its review/export pauses; key references are discarded at stop/closure. This is not a physical RAM-zeroization claim.

Let `R` be the project root and `N=R\runs\phase3a-readiness-recovery-v1\native\bc86391000266d413276de0f9ca8fb7f4f5b65632aa509d650f8236a48735be8\live`.

After `N\supervision\request.json` appears, make a NEW actual `collaboration.list_agents` observation. Publish its exact running-agent result immediately through the keyless trusted host publisher as specified in SUPERVISION.md. Use the request's sealed `sha256` field for `observation.request_sha256`; retain the raw file SHA separately for operator audit. Bind the source/runtime/policy/launcher/grant, inspected controller/container and nonce. No real transport, live claim, credential binding or intent precedes the consumed ACK. The observation expires after 30 seconds; the request's nonrenewable attachment deadline is 1,800 seconds. Missing/stale/foreign/replayed observations stop the launch with no calls. Attachment does not replace later substantive reviews.

## Reviews and Inspect handoffs

| Signal beneath N | Required service | Deadline |
|---|---|---|
| `barrier-readiness.json` | Inspect actual readiness/native evidence; publish supported `inspection-readiness.json`. | Original 30-minute window |
| `barrier-first.json` | Inspect sealed first-pair execution, ownership and accounting; publish supported `inspection-first.json`. | Original 30-minute window |
| `visibility\first-pair\request.json` | Separate keyless contained Inspect export and exact ACK. | Original 600-second window |
| `visibility\closure\request.json` | Separate keyless contained Inspect export and exact ACK. | Original 600-second window |

Inspection records copy the exact barrier `study_sha256` and `evidence_sha256`, use `fixture:false`, `no_quality_continuation_gate:true`, the actual `supervisor_agent`, and substantive notes. Readiness requires supported `evidence_grounded_decisions:true`; first-pair requires supported `engineering_checks_passed:true`. Never invent affirmative flags or author controller-owned review records. Scores and required edits do not decide continuation. Reject missing mandatory evidence even if a branch otherwise seems useful.

From R in a separate credential-free host process with explicit project/src PYTHONPATH, export checkpoint C (`first-pair` or `closure`) to a fresh allowed output:

```text
python -B -m followups.phase3a_readiness_recovery_v1.inspect_adapter host --snapshot <N>\visibility\<C>\snapshot --output <R>\runs\phase3a-readiness-recovery-v1\visibility-exports\bc86391000266d413276de0f9ca8fb7f4f5b65632aa509d650f8236a48735be8\live\<C>\supervised --ack <N>\visibility\<C>\result.json
```

Use host paths and the request's original absolute deadline. Do not overwrite exports/ACKs or renew waits. Inspect is a passive visibility layer; native execution, provider calls, spending and canonical scores stay on the existing controlled path. Real imported audit intervals and model-role configurations are visible. Activity's model-event chart remains unavailable for imported InfoEvents; use dated timeline/native-audit.csv. Do not present historical/mock views as this fresh live study.

## Monitor, stop and close

Read only named public native branches, barriers, journal/audits, visibility records and sanitized launcher inspection/result files. Lexically skip credentials, writer locks, caches, `.env`, `auth.json`, `credentials.json` and any filename containing stdout/stderr before metadata or content access. Never inspect real/unknown provider streams. No account/access/token-count probes, broad home/parent mounts or Docker socket are permitted.

Preserve the same exact live owner while waiting. A tool timeout is not permission to restart. Unknown charges remain fully reserved and stop admissions. Irrecoverable-primary, financial/resource/deadline/history/ownership stops remain enforced. Settle the exact owner before intentionally leaving; never resend, unlock a stopped grant, change source after observation or start an automatic repeat.

At closure verify all eight canonical reports and exact zero-call replay, every attempted/noncall classification, duplicate status, native authenticity evidence and new/old accounting. Scientific completion requires eight fresh valid/scored primaries, at least one qualifying normal native path, classified duplicate and no NEW unresolved liability. Otherwise preserve partial evidence with null pooled/selection fields. Old held liabilities remain disclosed. Do not infer positive scientific results from kit/mocks/viewer success.

Export every reached checkpoint, independently audit the new closure packet and commit the report/receipts. If canonical reports were held by an integrity stop, reuse the existing owner-settled held-report closeout procedure in the [RP1 runbook](PHASE3A_RP1_RUNBOOK.md); it cannot restore eligibility or overwrite final reports. The new packager supports explicit `--mode live-closure --outcome ABS_PUBLIC_OUTCOME --review ABS_INDEPENDENT_REVIEW` with the accepted verification root. Both metadata arguments must be absolute public paths beneath `R\evidence\phase3a-readiness-recovery-v1`. A stopped attempt closes honestly without a pooled winner. After complete scientific/delivery closure, define Phase 3B separately before any further execution.
