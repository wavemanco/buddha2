# P3B-LA1 — launcher repair and complete offline acceptance

Version 1.0 — November 3, 2026. **Defined for review; implementation and execution have not started.** The user's present request authorizes this specification update only. A subsequent instruction to execute LA1 authorizes the entire unchanged offline block, including its internal reviews, without separate approvals for each task.

## Objective and usable output

Repair the Windows process launch, verify the actual export handshake, and finish all offline acceptance required for the Phase 3B two-round Harness² comparison. Deliver one accepted, inspectable offline kit with a reproducible handoff, or an honestly classified stopped preparation with preserved evidence. A stopped preparation is a delivered failure dossier, not successful kit completion.

This is one engineering block continuing [P3B-S2](PHASE3B_DEFINITION.md) and the [C2 correction](PHASE3B_EXPORT_CONTRACT_CORRECTION_DEFINITION.md). It changes no scientific condition and runs no paid experiment. Its endpoint is offline acceptance; keys and live execution are outside LA1, even if every check passes.

## Starting evidence

- The [C2 stop report](PHASE3B_EXPORT_CONTRACT_CORRECTION_STOP_REPORT.md) and [independent stop verification](../../../evidence/phase3b-seq2-c2-v1/independent-operator-stop-v1.json) record an actual launch setup failure before the candidate driver, tests or containers started.
- C2 source658 `ea2e2ad1d1f8e40ce8e0bf2284feb78b84619b998c5ff2485aaf727f311b751a`, candidate v3 and its prospective review remain unaccepted at runtime. The source is retained at research commit `225fb06`; its public projection is `2472385`.
- The error split a Python executable path containing `Program Files`. Source inspection identifies `os.execve` argument handling as the likely cause; no independent reproduction has confirmed it. The recorded outer exit code zero does not establish child success.
- The three S2 wire constants and six workflow sites are already corrected. The generation-free boundary fixture, negative cases, exact-owner controls and separate main/replay drivers already exist. Reuse them; do not rebuild the experiment layer.
- Earlier source-specific passes inform review only. LA1 requires actual acceptance under its new effective source and study identity; no prior group becomes a current-source pass by relabelling.

## Scope and execution order

### 1. Diagnose and repair the launch before expensive work

Trace both the outer host invocation and the repository operator through the actual driver. Reproduce the failure with harmless child scripts on Windows using the actual interpreter path containing spaces. Record the received arguments, child status and parent status. If the proposed diagnosis is unsupported, investigate within the repair limit below and report the evidence rather than treating it as established.

Use the existing standard-library managed-subprocess pattern with a sequence of arguments, `shell=False`, the exact interpreter, explicit working directory and sanitized environment. Propagate the real child exit code. Retain child ownership, deadlines, cancellation and cleanup; simply adding an untracked child is insufficient. Do not relocate Python, rely on short-path aliases, hand-quote shell strings or add a dependency. If a different process model is necessary, stop for review before expanding this definition.

Before source freeze, exercise actual Windows children for:

| Case | Required outcome |
| --- | --- |
| Interpreter path, script path and arguments containing spaces; quoted and Unicode arguments | Exact argument count and values survive end to end |
| Child success and deliberate nonzero failure | Parent returns the corresponding outcome; wrapper success cannot mask child failure |
| Missing executable or script | Explicit failure before experiment work; retained diagnostic evidence |
| Clean environment | Required Windows/import settings arrive; an explicit synthetic forbidden sentinel does not; no real secret is read or printed |
| Timeout and cancellation | Exact child is stopped and observed settled; any genuinely started owned worker/container is accounted for and cleaned up |
| Candidate authentication | Changed source, missing/foreign review or mismatched manifest is rejected before driver work |

Use harmless local scripts for process tests. They must not load project workflows, create Docker containers or attempt network/provider activity. The later real boundary run supplies the integrated operator test. Reuse existing cleanup fixtures where they already exercise the required behavior. Expected negative cases are recorded as expected failures, never converted into positive runtime evidence.

### 2. Freeze and review one candidate

Preserve C2's exact source, reviews, failure and closed effort records before editing. Use the existing originals-only snapshot policy: authenticate the canonical fourteen classified offline originals before stream metadata access and retain zero auxiliary stream copies. Lexically exclude private names, caches and all other stdout/stderr paths before metadata or content access. Keep all work inside the designated research checkout; never scan or mount its parent.

Bind LA1's definition and subsequent execution approval, repaired code, regression cases, commands, runtime, policy and launcher to a new source/study identity and a fresh run root, proposed as `runs/phase3b-seq2-v1/verification-v4`. The root must be absent before use. Review exact source hashes and contained host commands independently before execution. Avoid circular source/manifest bindings; reuse the existing identity and packet machinery.

Routine launcher checks may iterate within the initial repair allowance before this freeze. After freeze, the candidate and criteria are immutable for this campaign.

### 3. Exercise the real export boundary first

Run the existing generation-free, separately identified partial fixture through the actual core producer, separate SDK-free Inspect exporter, real acknowledgement and real owner settlement for both first-prompt and closure checkpoints. Preserve each original 600-second window. No hand-written positive acknowledgement or patched success result qualifies.

Run the declared strict negatives: legacy request/result/owner labels, wrong study/checkpoint/snapshot/deadline, expired or late request, closed-owner tombstone, missing/still-running exporter proof, and denial of generation/provider grants for boundary-only fixtures. Verify all exact H1, child and I1 owners settle. This boundary must pass before the main matrix starts.

### 4. Finish every remaining offline acceptance obligation

Execute one complete current-source acceptance campaign using the existing helpers. Required groups remain exactly `static`, `matrix`, `replay`, `tests`, `windows-tests`, `launcher`, `inspect`, `preservation`, `regression`, `native-fixtures`, `semantics` and `supervision`. The launch and real-boundary evidence supplements these groups; it does not replace them.

Include the full four-prompt native SDK-mock matrix and capacity/semantic checks; current project and actual Windows tests; fresh keyless S13 supervision and lifecycle; both real timed Inspect exports; resource, financial, privacy and native-failure regressions; and complete source/history preservation. All mock traffic uses fixture credentials and transports. Real provider endpoints and real credential access remain disabled.

Keep the expensive main matrix and actual zero-call saved resume/report replay as separate commands. The existing prospective ceilings are 21,600 seconds for main and 7,200 seconds for replay; retain all shorter native/HTTP/startup/review/export clocks. Before execution, record exact commands and each finite operation/cleanup deadline. Automated waiting does not authorize extending a clock or rerunning a command.

Only after the twelve groups pass, obtain independent source/gate review, inspect the actual physical archive and its raw hash/inventory/member hashes/CRC, then perform the extracted-only cold replay with SDK/socket/process generation guards. Verify unchanged inputs, identical saved reports and exact-owner cleanup. Cold replay must mount the extracted packet, not the working checkout. Seal the final handoff only after these actual checks pass.

This permits one main-matrix execution, one full S13 rehearsal and one final extracted-cold acceptance replay for the frozen candidate. Internal tests and expected negative fixtures remain those predeclared for the campaign. A required post-freeze failure ends the campaign; there is no automatic source correction, second candidate or repeat.

## Deliverables and successful completion

1. Minimal launcher correction and runnable actual Windows regressions, with diagnosed behavior and faithful child-status propagation.
2. New source/study/command identities, direct authority and independently reviewed prospective execution plan.
3. Actual two-checkpoint boundary evidence and all twelve current-source passing acceptance groups, with every required case covered and every owned process/container settled.
4. Independently accepted physical packet and extracted-only zero-call replay; final source-bound offline gate, operator handoff and saved-data reports.
5. A concise completion or stop report, final effort accounting and reviewed publication to the existing GitHub repository. Keep its organized public layout and publication exclusions; canonical local provenance remains intact.

Success requires all five deliverables and all applicable integrity checks. Static review or mock success alone cannot certify live providers or show that recursive adaptation improves quality. An accepted kit is usable for later authorized execution. If the block stops, deliver the partial implementation and evidence, exact missing criteria and next decision, without marking the kit or scientific phase complete.

## Engineering limit and cost

**Proposed execution allowance: two aggregate focused engineering hours (7,200 seconds), across the parent and every agent combined.** This is a hard best-effort ceiling, not a completion estimate or two hours per participant. It begins only after a subsequent instruction authorizes execution. This planning update is not that approval and does not consume or reopen the closed prior allowance. No unused historical time transfers.

The first 30 aggregate focused minutes bound launcher diagnosis, repair and its cheap Windows regressions. If that milestone cannot pass within the limit, stop and close. Within the overall two hours, reserve at least the final 20 aggregate focused minutes for cleanup, independent outcome review, documentation and publication; retain more if the actual remaining closure tasks require it. The work portion therefore ends by 100 focused minutes at the latest. At 60 focused minutes, publish a progress/remaining-work review inside this same block; no new approval is required if scope and capacity still fit.

Record active/wait/done transitions prospectively in a new append-only ledger, separately from the closed prior ledger. Sum concurrent agents. Check effective remaining effort before and after short slices and before every long command. If a transition is missed, conservatively charge the whole bounded uncertain interval, retain that hold and report it; never reconstruct an unsupported precise total or reset the allowance. Automated tool/runtime waiting can take several elapsed hours and does not count as focused work. Analysis, repairs, reviews, coordination, report writing and publication do count. Do not start a required slice unless its supported review/supervision needs and closure reserve fit.

**API cost and cap: $0.** No real keys, account probes, token-count endpoints, model/judge calls, human collection or paid pilot launch. Local compute and assistant sessions are separate costs. The historical $180 paid-pilot ceiling and retained liabilities are unchanged; this offline block neither spends them nor authorizes an automatic transition into live work.

## Exclusions and stop rules

No engine, benchmark, model/reasoning setting, prompt, strategy arm, task panel, scoring procedure, financial limit or historical liability change. No new platform, dependency, generic launcher framework, provider bridge, benchmark, CrPO/MuCE or human-evaluation work. Preserve the existing strict S2 contracts and actual Harness² engine. No context truncation, validation bypass, fabricated acknowledgement, fallback success or retagging of historical results.

Stop admissions, preserve the outcome and settle exact owners if:

- the initial repair milestone or cumulative engineering/closure-capacity limit is reached;
- any required check fails after source freeze, including the boundary or an archive/cold-replay check;
- source/history, privacy, containment, ownership, clock, accounting or identity integrity is uncertain;
- a required change exceeds this launcher/acceptance scope or needs a weaker criterion, additional run, new dependency or different process model;
- the user pauses the work.

Cleanup remains mandatory after a stop, using the protected reserve; unresolved cleanup is a failed outcome. Preserve partial command output and the real child/parent statuses. Unknown owners or non-specific inspection errors cannot establish absence. No automatic repeat, new source amendment, clock extension or paid work follows a failure or a successful offline closure.

## Exit decision

**Pass:** publish the accepted offline kit and current handoff, then stop. A later live-execution decision must assess supervision capacity and accepted-source applicability before any fresh masked keys.

**Stop:** publish the classified preparation failure, retained partial work, effort and missing criteria, then stop. Any further execution needs a concrete continuation decision. Neither outcome starts another phase automatically.
