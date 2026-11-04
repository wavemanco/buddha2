# Buddha2

**A research project testing whether AI can improve its working method—not just produce more answers.**

Buddha2 compares ordinary model generation, fixed strategies and genuine recursive adaptation. It uses Google's actual [Harness²](https://github.com/google-research/harness2) engine through external adapters. It does not train model weights.

The central question is:

> For a given model and kind of task, which fixed strategies help, and does recursive adaptation improve further with the same techniques and comparable resource allowances?



## What we compare

| Approach | What changes? |
|---|---|
| **Base model** | The model answers using the declared generation protocol. This establishes the starting point. |
| **Fixed strategy** | A designed procedure plans different approaches, generates answers and orders or selects them. Its instructions stay fixed during the task. |
| **Recursive adaptation** | Harness² asks a model to propose changes to that procedure, executes probes, combines the evidence and selects an output. The procedure can change during the task. |

Our current solver produces a portfolio of ten answers. Adaptation is restricted to three instruction fields: planning, answering and ranking. Starting techniques, model settings and limits are declared before a study. Equal allowances do **not** imply equal actual spending or computation; we report both.

The software we build to make experiments reliable—accounting, isolation, history checks, launchers and reports—is outside the experimental adaptation loop. Its engineering improvements are not reported as learned strategy improvements.

## Current evidence

Status snapshot: **3 November 2026**. [CURRENT_SPEC.md](docs/research/CURRENT_SPEC.md) tracks subsequent execution and decisions.

The first task and assessment protocol is [NoveltyBench](https://github.com/novelty-bench/novelty-bench). It measures answer quality and useful variety using its established model-based assessment procedure. Benchmark scores are not a general measure of creativity or human preference.

The completed **Phase 3A development pilot** compared fixed best-of-six with one native Harness² adaptation step on four already-exposed prompts:

| Procedure | Mean benchmark utility | Inference cost across four prompts |
|---|---:|---:|
| Fixed strategy, best-of-six | 6.326 | $2.57 |
| Native one-step adaptation | 5.795 | $12.65 |

Best-of-six means generating six fresh ten-answer portfolios and selecting one unchanged portfolio. These costs exclude external assessment and earlier attempts.

Fixed won all four prompt comparisons. All four native paths completed normally; the selected strategy changed on two prompts. This is a small development result, not held-out confirmation or evidence that recursive adaptation never helps. See the [full Phase 3A report](docs/phases/phase-3a/PHASE3A_RP2_LIVE_REPORT.md) for exact values, provenance, failures and costs.

**P3B-OR1 stopped incomplete; no accepted offline kit.** All3frozen candidates and2main-entry starts were consumed. The final source735 candidate passed static/preservation checks but its fail-fast suite stopped after4tests,1failure and0errors at the spawned-worker bootstrap assertion before capacity or model generation. The worker stopped; its canonical status was failed rather than complete, and the exact sanitized cause was not retained. No diagnostic rerun, source fix or further admission followed. S13, saved and cold replay starts remain0; final gate/physical/extracted acceptance are absent. There were no real API calls, keys or paid work. See the [OR1 stop report](docs/phases/phase-3b/PHASE3B_OR1_STOP_REPORT.md); the stopped outcome is independently reviewed, accounting retains all holds, and the accepted-kit goal remains unachieved. It compares actual two-round native refinement (`seq,k=2`) with fixed best-of-twelve on the same four development prompts. Round two starts from the first composed strategy; native selection may choose either checkpoint. Both checkpoints are assessed after selection is sealed. No Phase 3B paid pilot has started, and fresh keys follow complete independent acceptance.

**BD1 unit preflight passed:** all 121 current tests are covered by the final Linux run and three actual Windows cases on the same source. Earlier diagnostics failed, so the exact cause and intermittent-failure risk remain unresolved. This is not full Phase 3B kit acceptance. See the [reviewed BD1 report](docs/phases/phase-3b/PHASE3B_BD1_REPORT.md) and [closed runbook](docs/phases/phase-3b/PHASE3B_BD1_RUNBOOK.md). No new campaign or paid call follows automatically.

**P3B-RA1 stopped incomplete; the offline release kit remains unaccepted.** The first current-source Linux preflight started four of 126 cases: three passed, one failed with `canonical_timeout`, and 122 were unrun. Component checks passed five new regressions and Ruff/Mypy/Bandit; no Windows set, release candidate, main campaign, supervised S13, saved replay or cold replay started. API spend was $0. Read the [stopped report](docs/phases/phase-3b/PHASE3B_RA1_REPORT.md) and [retained-product runbook](docs/phases/phase-3b/PHASE3B_RA1_RUNBOOK.md). [RA1-AM1](docs/phases/phase-3b/PHASE3B_RELEASE_ACCEPTANCE_AM1.md) proposes a declared test-budget change and complete acceptance continuation; it is not approved or implemented. The original failure and conservative effort overage remain disclosed. No paid pilot or new test admission follows automatically.

Earlier fixed-strategy and evaluator studies are recorded separately. The MuCE-based creativity evaluator missed its predefined agreement/consistency checks and remains diagnostic-only. Human review and further CrPO work are optional, deferred extensions.

## How the pieces fit

- **Harness² runs adaptation.** We keep the upstream engine pinned and unchanged.
- **Strategy adapters define the procedure.** Fixed and adaptive arms begin with the same declared techniques.
- **Benchmark adapters supply tasks and assessments.** NoveltyBench is the first protocol; it is not the project's universal objective.
- **Our experiment layer controls execution and evidence.** It owns provider calls, budgets, provenance, failure handling and replay.
- **[Inspect AI](https://inspect.aisi.org.uk/) provides passive records and a viewer.** Our adapter exports saved artifacts into it. Inspect does not make our provider calls or control spending.

Replacing an engine, benchmark, strategy or compatible evaluator requires a new identity and compatibility checks. We use bounded interfaces rather than build a general plugin platform ahead of evidence.

## Start here

- [Documentation index: research, phases, operations and history](docs/index.md)
- [Current status and decisions](docs/research/CURRENT_SPEC.md)
- [Research method and interpretation](docs/RESEARCH_METHOD.md)
- [Concrete Phase 3B scope, completion criteria, caps and stop rules](docs/phases/phase-3b/PHASE3B_DEFINITION.md)
- [Completed Phase 3A result](docs/phases/phase-3a/PHASE3A_RP2_LIVE_REPORT.md)
- [Pinned environment and original implementation decisions](docs/phases/phase-0/DECISIONS.md)
- [Historical README, edited reader reference](docs/archive/README_LEGACY.md)

This is a staged research repository, not an unattended production service. Fixtures and tests are offline by default. Paid runs use a separately accepted, source-bound launcher, an explicit grant and fresh masked key entry. Follow the current runbook when it is accepted; historical launch commands do not authorize another run.

## Public source release

GitHub contains the source, specifications, reports and reviewed text evidence from this project. Private credential bindings, locks, raw logs, run archives, installed environments and selected third-party reference/data captures remain local. Historical reports may link to those local artifacts. Replaying a frozen study also requires its provenance packet and pinned runtime; a public clone is a source release. See [publication notes](docs/PUBLICATION.md) for the exact boundary.

## Attribution and licensing

Harness² is Apache-2.0 licensed; NoveltyBench, Inspect AI and the OpenCode base used here are MIT licensed. Their code and notices remain their owners'. Exact revisions, additional dependencies, bundled-license exceptions and research references are documented in [Attributions](docs/ATTRIBUTIONS.md).

**Buddha2's own code and documentation are licensed under [Apache-2.0](LICENSE).** It includes an explicit contributor patent grant and matches the native Harness² engine's license. Third-party code, datasets, models and runtime components retain their separate terms; see [NOTICE](NOTICE) and the attribution guide.
