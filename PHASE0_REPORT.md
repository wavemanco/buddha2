# Phase 0 handoff

Date: 2026-10-24, America/Los_Angeles  
Specification: [frozen phase definitions](specifications/archive/phase-definitions-0.3.md), revision 0.3  
Status: complete — P0-1 through P0-8 verified; later phases unstarted

Historical evidence note added during the planning refresh: the exact [Phase 0 decisions](specifications/archive/phase0-decisions-0.3.md) and specification match the saved manifest. Current phase definitions are revision 0.4; existing run manifests, assessments, logs and example archive remain unchanged. Historical resume requires the original effective inputs (commit `6bafb25`); archiving the old specification does not make current-spec resume compatible. No replay occurred during this documentation update.

## Delivered scope

An offline command-line integration kit connects **unchanged, pinned upstream Harness²** to one deterministic task adapter and one inspectable strategy. Its selected portfolio can be exported, imported and assessed independently. This establishes execution and artifact boundaries; it makes no scientific performance claim.

Work is confined to `C:\Users\arvik\code\research\Buddha2` and its dedicated Docker image. The protected `C:\Users\arvik\code\buddha2` was not written, copied, used as a command working directory or mounted. The claim is based on the work performed and inspected runtime mount restrictions; no before/after hash audit of the original folder was performed.

Use the commands in [README.md](README.md). Read the [retained example report](runs/example/report.md) and [portfolio](runs/example/portfolio.json), or retain the complete [189-file example archive](evidence/phase0-example.zip), including native harnesses and traces. The archive contains only synthetic run output. The [acceptance manifest](evidence/acceptance.json) binds the final command/test records, source verification, example identity and archive hash.

## Implementation and reproducibility

- Harness²: commit `1cfe254e8d25b15f37048c3730134686abe60335`, Apache-2.0. Native `schedule.run_task`, `OpencodeSubstrate` materialization, probing/composition and trivial selection are invoked through an external adapter.
- NoveltyBench: commit `64a23be6b18ec1dacc298830aab276061b6e143c`, MIT. A separate subprocess imports native `load_instances`, `utility_fields` and `summarize`; these algorithms are not copied into the project.
- [upstreams.lock.json](upstreams.lock.json) records every tracked upstream source file's hash. Setup, runtime checks and tests reject changed source. Runtime mounts keep both checkouts read-only.
- Linux/amd64, Python 3.12.15, hash-locked CPU dependencies. [environment.json](evidence/environment.json) identifies the actual image, all 91 installed package versions and retained license-notice hashes. [DECISIONS.md](DECISIONS.md) records source/image pins, license decisions and execution boundaries.
- The strategy is an ordinary [directory of native harness files](strategies/planner). The local launcher executes a known helper against the actual staged files. Markdown policy changes produce controlled synthetic output differences. This is not a model implementing the strategy.
- Immutable output, native exchange, assessment and completion records bind their content identities. The manifest includes effective files/prompts, task/configuration, roles, source pins, dependency locks, specification/decisions and immutable runtime image ID. This provenance does not promise bit-identical regeneration with future live providers.

## Acceptance evidence

| Requirement | What is verified | Evidence |
|---|---|---|
| P0-1 | Native parallel `agg`, `k=1`: four executor rollouts, three deterministic editor/composer calls and native trivial selection. Materialized policy affects subprocess output. | `test_engine.py`; native-control-flow acceptance check; retained example engine traces. |
| P0-2 | Inspectable strategy; complete file hashes; Markdown and Python both change identity; an altered executable helper is refused. | `test_artifacts.py`, `test_engine.py`; retained staged harnesses and materialization records. |
| P0-3 | Ten responses, task ID, texts, order and companion IDs survive native exchange. Duplicate text remains valid; duplicate IDs fail. | Exchange tests; native loader integration; retained export/import artifacts. |
| P0-4 | Separate mechanical/native assessments bind the same output. Native synthetic distinctness is **5**; observed utility **4.346485261239211** matches the frozen oracle **4.346485261239209** to 12 decimal places. Native summary agrees too. | `test_evaluation.py`; reassessment acceptance check; retained assessment records. |
| P0-5 | Malformed/missing/incompatible artifacts fail explicitly; native fixture evidence requires exact known task, ordered texts and grading profile. Completion evidence is validated before claiming completion. | Boundary tests, rebinding regressions and completed-run corruption checks. |
| P0-6 | One declared checkpoint after output/export and before assessments resumes idempotently. Changed effective inputs or corrupted finalized evidence are refused. | Checkpoint/resume acceptance tests; retained checkpoint example. |
| P0-7 | Credential-free runtime has OS-level network denial, including subprocesses. Non-fixture invocation refuses before dispatch. Only the new root/read-only source and its run-output directory are mounted. | Parent/subprocess containment tests and actual Docker runtime inspection records. |
| P0-8 | Documented setup, demo, inspection, export, import, assessment and recovery commands work; sample output and source-integrity evidence are retained. | Final workflow logs, test/check logs and records linked below. |

Final verification:

- **43 project tests passed, zero skips**, in 562.019 seconds: [complete test log](evidence/runtime/bbafe040de724dfaa43309b3ef64eeca.stderr.log), [actual runtime inspection](evidence/runtime/bbafe040de724dfaa43309b3ef64eeca.json).
- **Five unchanged upstream Harness² tests passed**. Ruff, mypy, medium-or-higher Bandit and `pip check` also passed: [check output](evidence/runtime/613affdab62c4daf8ea30ffc545a917c.stdout.log), [upstream test log](evidence/runtime/613affdab62c4daf8ea30ffc545a917c.stderr.log), [Bandit report](evidence/bandit.json).
- The documented [setup](evidence/setup.log), demo, inspection, export, import, native reassessment, mechanical-only assessment, interruption checkpoint, resume and completed-run resume all passed. Nine runtime command records and their logs are retained in the [acceptance manifest](evidence/acceptance.json); the readable command logs are under `evidence/workflow`.
- At closure, before/after acceptance snapshots and final source verification matched **114 Harness² files and 169 NoveltyBench files**; both upstream Git worktrees were clean. The example's original specification/decision hashes match the preserved snapshots. Its complete package-file hashes also matched at closure; this planning refresh changes no package code.
- The actual example image is `sha256:585a5539c6091592258ec19d0bf8e216b189405f95766b167df0d2e88e251366`. Its 91 installed package versions match the dependency-audit inputs, including the explicitly documented CPU Torch exception.

Review corrected two boundary defects before closure: inspection previously trusted a completion file's existence, and numeric fixture labels could be rebound to unrelated text. The final regressions cover strict completion/report/assessment integrity and exact declared task/text/profile compatibility. The test setup uses three disposable native-trace copies for these corruption checks; it preserves every case while avoiding repeated full copies through the Windows mount. Verification is local; no remote CI was configured or run.

## Dependency and security findings

The first audit found vulnerable upstream-version runtime dependencies. Those findings remain in [the initial audit](evidence/dependency-audit-initial.json) and [initial Torch advisory query](evidence/torch-cpu-advisory-initial.json). Only runtime dependencies were upgraded; upstream source and acceptance thresholds remain unchanged.

The patched environment uses Transformers 5.20.2 and official CPU Torch 2.14.1+cpu. [The patched installed-environment audit](evidence/dependency-audit.json) reports no known vulnerabilities for the packages it could identify. Its explicit exception is the local-version CPU Torch wheel; [the separate official PyPI metadata query](evidence/torch-cpu-advisory.json) found no listed advisories for underlying release 2.14.1. This does not establish absence of undisclosed vulnerabilities or directly audit that custom-version wheel.

Ruff, mypy, `pip check` and Bandit at medium-or-higher severity/confidence are part of the documented check command. This is not a claim of zero findings at every Bandit severity. [License review](evidence/dependency-license-review.json), the [MIT wheel check](evidence/mypy-extensions-license.json) and installed notice hashes are retained. MPL-covered packages and copyleft base utilities remain unmodified local dependencies with their notices; no distribution decision was made.

## Limits and next decision

No model/provider calls, model-weight downloads, MuCE data pulls/calibration or comparative experiments occurred. Public upstream checkouts include their versioned benchmark assets; source/package downloads and advisory queries were setup/security work. Fixture execution itself was network-disabled and used only the declared synthetic task.

Unverified: live OpenCode execution, model-backed proposal/selection/reflection, official grouping/quality judges, live transport and billing enforcement, semantic quality, successive recursive improvement, another benchmark, and arbitrary future upstream compatibility. The single recovery checkpoint does not promise arbitrary-crash exactly-once execution.

The mechanical evaluator accepts compatible arbitrary fixture portfolios. Native synthetic arithmetic applies only to the exact declared example and frozen evidence. Neither route evaluates real creativity. Fixture policy changes and native upstream tests establish software behavior, not adaptation effectiveness.

Phase 1 remains unstarted. Its next usable output would be a bounded MuCE evaluator-calibration report, after refreshing its eligible prompt pairs, evaluator role/rubric, audit split, denominators/thresholds, failure rules and spending ceiling. Later fixed-strategy, one-step adaptation, successive-refinement and held-out comparisons retain their separate phase gates. New strategies, benchmarks and criteria require bounded adapters and checks; no general plugin platform was built.
