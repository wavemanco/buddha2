# P3B-BD1 — Bootstrap diagnostics and unit preflight

Version 1.0 — 2026-11-03, America/Los_Angeles.

**Status: defined, not implemented or authorized for execution.** The instruction to proceed with defining this checkpoint authorizes this specification and its publication. It supplies no test run, code repair, new release candidate or spending authority. OR1 remains closed and stopped.

## Objective and usable endpoint

Make the spawned-worker failure observable and establish a complete unit-test preflight **before another release freeze**. The usable output is one offline, unit-only command that retains structured diagnostics, reconciles every test outcome, proves cleanup and returns a clear ready/not-ready decision.

This checkpoint does not deliver the accepted Phase 3B kit. A pass permits defining its next release campaign; it starts neither that campaign nor the paid pilot.

## Starting evidence

The [OR1 stop report](PHASE3B_OR1_STOP_REPORT.md) and [independent stopped review](../../../evidence/phase3b-or1-v1/independent-stopped-outcome-v1.json) establish the following:

- The last source contains 735 files, with source identity `5b356fd87ca860a16ad3d18feed54dfb2592405ebd082b2088f568c5df50164e`.
- Static and preservation checks passed. The fail-fast Linux suite ran four tests, with one failure and zero errors. Capacity and matrix work were not reached.
- In [the bootstrap test](../../../followups/phase3b_seq2_v1/test_bootstrap.py), the worker-stopped assertion passed; `canonical_status` was `failed` instead of `complete`. The test uses a four-second deadline and one-second cleanup allowance.
- The log did not retain the collector's returned error classification. Its exact historical cause remains unknown. BD1 cannot recover that lost information retrospectively.
- All three OR1 candidates and two main starts were consumed. All ten known owners are independently absent. BD1 does not reset those counters, reopen their ledgers or reuse their execution grants.

Static inspection of the current S2 package finds 19 `test*.py` files and 118 declared test methods: 115 expected Linux executions and three Windows-only cases. This is an inventory to reconcile against actual discovery, not a substitute for executing the tests. New meaningful regression cases must be declared and included before their outcomes are observed.

The three baseline host cases are:

- `followups.phase3b_seq2_v1.test_launch_s2.LaunchBoundaryTests.test_actual_windows_bootstrap_rejects_private_input_before_metadata`
- `followups.phase3b_seq2_v1.test_launch_s2.LaunchBoundaryTests.test_actual_windows_bootstrap_rejects_foreign_phase_before_metadata`
- `followups.phase3b_seq2_v1.test_or1_admissions_s2.OR1AdmissionTests.test_host_evidence_writer_outside_runtime_base_is_exclusive`

## Scope: one bounded offline block

### 1. Bind the baseline and cases before running

Use `evidence/phase3b-bd1-v1` and fresh outputs beneath `runs/phase3b-seq2-v1/bd1-unit-preflight-v1` in the designated research checkout. The latter maps to the existing permitted `/results/phase3b-seq2-v1` runtime root; no broader filesystem permission is needed. Give each invocation its own absent-before-use child directory. Preserve the OR1 source, records, failures and financial history unchanged. Record the direct BD1 execution instruction, this definition's hash, source hashes, exact case IDs, commands, environment allowlist, runtime and output paths before the first invocation.

Use the existing pinned H1 image `sha256:ce1d4ab2241ce9d141a5447c3da15fb44f62e521c3e2bbe49b74611ff36e3800`, actual upstream pins and native import boundary. Retain the existing 4 GiB memory, two-CPU and 256-process limits, 1 GiB temporary filesystem, read-only root, dropped capabilities and no-new-privileges policy. Keep the code mount read-only, network disabled, credentials absent, and writes confined to fresh BD1 outputs. Inspect each exact owned container before execution and prove its subsequent removal. Never enumerate unrelated containers or mount a parent directory, home, credentials or Docker socket.

### 2. Retain the actual diagnostic without changing the verdict

First retain the existing collector result through a small test-message or external observer change. Prefer the fields already returned by [core_view.collect](../../../followups/phase3b_seq2_v1/core_view.py): canonical/report/visibility statuses, bounded error-type fields, worker-stopped/cleanup proof and the fixture import-privacy counts. Record source, command, process exit and elapsed-time evidence separately. Use typed, allowlisted fields; no raw provider text, arbitrary exception payloads, secret environment values or new telemetry framework.

Do not replace the real collector, synthesize its success, swallow an exception or change any existing bootstrap assertion/expectation: stopped worker, complete canonical status and the import-privacy denial count. Only its diagnostic message may change. Preserve the four-second/one-second limits and all existing inner timeouts. Any additional classification must identify an observed branch rather than infer a timeout from duration or an import failure from a generic failed status.

Bind the original first-four-test order and the actual spawn/import context: entry module, executable, working directory, Python path, containment and resource limits. A convenient `python -c` reproduction is not automatically equivalent to the original composed entry. Review any unit-only entry adaptation before invocation and record its differences. The worker must still use actual multiprocessing spawn.

Report the result as **reproduced with observed classification**, **not reproduced in the bounded attempts**, or **diagnostic evidence insufficient**. Do not claim a cause or repair merely because a later run passes.

### 3. Make only eligible preflight/fixture corrections

Within this block, bounded corrections to diagnostic presentation, the unit-only operator and unfrozen fixture paths/contracts may proceed without per-defect permission. Trace the whole affected path, preserve the failed attempt, add a meaningful regression check, record the new source identity and independently review the correction before another counted invocation. A source change never resets the counters below.

The existing [byte-identity integrity test](../../../followups/phase3b_seq2_v1/test_offline_timeouts_s2.py) freezes `core_view.py`, other experimental controls and named authority/launcher inputs against A0. **BD1 does not authorize editing those frozen files, changing their expected hashes or skipping that test.** If the observed cause needs such a change, stop with **change required** and deliver the specific prospective amendment needed. The same applies to upstream edits, new dependencies, changed clocks or weaker guards. This boundary is known before implementation; it is not an unexpected per-defect approval gate.

Move the host writer test's temporary parent from its old OR1 fixture prefix to a fresh BD1 fixture prefix when necessary, while preserving its actual host-evidence-outside-runtime-root and exclusive-write proof. No historical OR1 file or ledger may be used as writable test state.

### 4. Run the complete unit preflight, without entering the main campaign

Reuse the production unit-discovery/execution path in [verify.run_tests](../../../followups/phase3b_seq2_v1/verify.py). Do not enter `verify.inside`: that continues into capacity and the main matrix. Prefer a minimal explicit unit-only phase in the existing unfrozen composed entry, retaining its ordinary main/replay guards unchanged and validating the BD1 output namespace separately. Review and record any other minimal implementation choice against the spawn-context requirement. A general runner or second verification framework is not in scope.

Reconcile exact discovered IDs against the declared inventory. Retain passing, failing, erroneous, skipped and unrun cases; a fail-fast partial run counts as an attempted suite and cannot be called complete. A final passing run must execute every current Linux-applicable case without new exclusions. Run the three named Windows-only methods on the actual Windows host using the same final source; no skipped host case may be treated as passed. Bind any added regression cases and their platform disposition explicitly.

The existing unit suite includes native Harness² components, subprocesses, real SDKs with fixture transports and synthetic results. Those declared **mock** calls are allowed and must remain distinguishable from real provider activity. Keep the existing capacity boundary/denial units, fixture-grant construction/rejection cases and patched negative workflow-call tests. These are not permission to execute an actual main/capacity/S13 full lifecycle or worklist, create/consume an execution grant outside the declared unit fixtures, or resume a historical study under the name of a test preflight.

Use a fresh source-bound development record for every invocation. Preflight results are not OR1 gate records and cannot be retagged to assemble a release pass. A later full acceptance still requires all twelve current-source groups, both genuine supervised exports, independent source/gate review, a physical archive audit and extracted-only zero-generation replay.

### 5. Close and publish one useful result

Deliver the unit-only command/runbook, sanitized diagnostic record, case reconciliation, eligible diffs and regressions, unchanged-control/source/history checks, exact-owner cleanup, independent review, cost/effort accounting and a plain-language outcome report. Publish the reviewed source/specification/report and safe evidence using the existing organized repository layout. Preserve raw immutable evidence bytes and the documented narrow publication-format exceptions; exclude credentials, raw streams, mutable ledgers and retained source captures before metadata/content access.

## Invocation, time and cost limits

| Limit | Proposed allowance and counting rule |
| --- | --- |
| Standalone bootstrap diagnostics | At most **three** invocations total, including the baseline. Count at invocation before worker work; startup failures count. A fixed first-four-test prefix counts as one such invocation. No concealed repeated-positive loop. |
| Full contained unit suites | At most **two** starts total, at most one per development source revision. A failed, timed-out or partial suite counts. Each includes its normal bootstrap case; that is additional to the three standalone invocations. Stop after the first complete final-source pass unless a subsequent authorized fixture change invalidates it. |
| Actual Windows sets | At most **two** starts, each containing exactly the final inventory's Windows-only cases and any declared Windows regressions. Startup failures count. A changed source needs a matching final Linux pass and Windows set. |
| Other checks | Only prospectively listed diagnostic-negative/regression cases and affected static checks. They cannot contain an uncounted positive bootstrap repetition or full worklist. |
| Focused engineering | **Two aggregate hours: 7,200 seconds across all agents**, including review, accounting and publication. No old ledger or unused time transfers. |
| Initial diagnostic gate | Within the first **30 focused minutes**, obtain a source/context-bound, sanitized actual result or stop as diagnostic-incomplete. A non-reproduced failure may be reported honestly; an absent diagnostic cannot pass this gate. |
| Closure reserve | Protect at least **20 aggregate focused minutes**, or more if the supported closure estimate requires it. Implementation therefore ends by 100 focused minutes at the latest. Record an internal progress/capacity review at 60 focused minutes. |
| Runtime clocks | Existing inner clocks and cleanup rules remain unchanged. Unit-only outer ceilings: 120 seconds per standalone diagnostic command, 7,200 seconds per Linux suite or Windows set; Docker create/inspect and exact-owner cleanup remain bounded by the existing 60-second limits. A shorter existing case limit always wins. No renewals or retries that hide a timeout. |
| Real API cost and cap | **$0.** No real keys, provider/account/token-count probes, generation, judging or human collection. Existing local compute and assistant sessions are separate costs. |

These are ceilings, not a completion forecast. Automated waiting may exceed two hours of elapsed time, but commands remain finite and supervised. Mark active before analysis/work and wait only during actual passive waiting; charge whole uncertain intervals conservatively. Use one authoritative aggregate engineering ceiling. Internal estimates may be revised transparently within it; they are not additional grants or reasons to reset accounting. Before each expensive command, its supported supervision/review and closure must fit the remaining allowance.

## Deliverables and completion criteria

**Ready** requires all of the following:

1. A reproducible unit-only entry with reviewed spawn/import-context fidelity, actual pinned containment and no path into main/capacity/S13 work.
2. A retained, typed diagnostic for the actual bootstrap observation and meaningful checks that errors remain observable. State the precise observed cause when established; explicitly retain **not reproduced/cause unresolved** otherwise.
3. Any eligible correction has an explained diff and a regression that would catch its defect. No frozen-control, assertion, clock or expected-hash relaxation occurred.
4. One complete final-source Linux unit-suite pass, reconciled by exact IDs, plus all corresponding actual Windows cases passed on that same source. No added skip, hidden error, silent retry or mixed-source pass.
5. Real provider requests/cost are zero; every known owner is settled; historical evidence, upstream sources and frozen controls remain unchanged.
6. Independent review accepts the evidence and its limits; source, runbook, report, final accounting and reviewed publication are delivered within the limits.

Passing these checks does not establish why an unreproduced historical failure happened or prove the absence of intermittent failures. Such uncertainty remains in the handoff for the next release decision. It cannot be described as a demonstrated causal repair.

**Change required** means evidence identifies a need outside the eligible correction scope, including a frozen-control change. Deliver the actual failure classification, affected boundary and a concrete amendment proposal; the unit-preflight gate remains unpassed unless every requirement above passed independently. **Stopped incomplete** means time, invocations, observability or closure capacity ran out before a defensible ready/change-required result. Retain every partial result and missing case in either outcome. A useful diagnostic dossier is not a passing preflight.

## Exclusions and stop rules

No new release freeze or candidate, main/capacity/S13 campaign, accepted-kit packet, saved-study/cold replay, paid pilot, model/strategy/benchmark change, held-out opening, CrPO/MuCE, human review, platform migration, viewer feature or unrelated refactor is included.

Stop experimental/test admissions immediately if a counted limit or supported closure capacity is exhausted; a frozen-control/clock/upstream/dependency/guard change is required; source/history/privacy/containment or exact ownership becomes uncertain; a real provider attempt occurs; or the user pauses. An admitted final command may finish only within its unchanged clock and the remaining supervision/closure allowance. Never overwrite a run root, borrow an old pass, edit expected hashes, forge completion, or rerun unchanged failures until green.

**Exit:** publish the independently reviewed ready, change-required or stopped-incomplete dossier and stop. A ready result leads to a separately defined complete release-acceptance block; the other outcomes lead to a specific amendment or stop decision. None authorizes another release campaign or paid call automatically.
