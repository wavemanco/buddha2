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

Status snapshot: **4 November 2026**. [CURRENT_SPEC.md](docs/research/CURRENT_SPEC.md) tracks subsequent execution and decisions.

A separately authorized **offline artifact-binding correction** now follows the native engine's actual return and saved-file priority. It binds the actual artifact, write witness and strategy while treating final-chat prose differences as diagnostic. Offline checks passed 145 unique methods across pinned Linux and the Windows host, with independent review. See the [audit correction](docs/ENGINEERING_AUDIT.md#durable-native-artifact-binding-correction). The stopped R2 result remains incomplete; no fresh live kit, grant or paid continuation is created.

**Latest Phase 3B R2 attempt closed incomplete:** 513 calls/**$14.094285**, zero new unresolved liability. The first paired prompt completed, but a later selector stopped because our artifact contract compared differing prose despite the same declared candidate B. The exploratory first-pair scores remain distinct from the final globally held result (zero primary/assessment targets scored). There is no completed four-prompt comparison or gain claim. See the [R2 attempt report](docs/phases/phase-3b/PHASE3B_READ_AUDIT_R2_LIVE_ATTEMPT_REPORT.md). No paid repeat follows automatically.

The first task and assessment protocol is [NoveltyBench](https://github.com/novelty-bench/novelty-bench). It measures answer quality and useful variety using its established model-based assessment procedure. Benchmark scores are not a general measure of creativity or human preference.

The completed **Phase 3A development pilot** compared fixed best-of-six with one native Harness² adaptation step on four already-exposed prompts:

| Procedure | Mean benchmark utility | Inference cost across four prompts |
|---|---:|---:|
| Fixed strategy, best-of-six | 6.326 | $2.57 |
| Native one-step adaptation | 5.795 | $12.65 |

Best-of-six means generating six fresh ten-answer portfolios and selecting one unchanged portfolio. These costs exclude external assessment and earlier attempts.

Fixed won all four prompt comparisons. All four native paths completed normally; the selected strategy changed on two prompts. This is a small development result, not held-out confirmation or evidence that recursive adaptation never helps. See the [full Phase 3A report](docs/phases/phase-3a/PHASE3A_RP2_LIVE_REPORT.md) for exact values, provenance, failures and costs.

**Phase 3B's first live attempt stopped incomplete.** The comparison is two-round native refinement (`seq,k=2`) against fixed best-of-twelve on the same four development prompts. The first prompt produced c1 and entered round two, then our read-proof checker stopped execution. The attempt made 122 provider calls costing **$12.528747**, with no new unresolved liability. The fixed arm and benchmark assessment were not reached, so there is no two-round performance conclusion. Closure, passive Inspect export and byte-identical zero-call report replay completed; see the [stopped-attempt report](docs/phases/phase-3b/PHASE3B_LIVE_ATTEMPT_REPORT.md).

The subsequent offline review identified a valid OpenCode size-limit footer that our parser rejected. The user approved a [narrow amendment](docs/phases/phase-3b/READ_AUDIT_AMENDMENT.md): perform the full read audit, report gaps separately and retain the essential execution safeguards. The canonical kit passed 119 pinned-runtime component tests and independent offline acceptance; those checks do not establish provider success or an adaptation benefit.

**The authorized diagnostic-read attempt also closed incomplete:** 35 calls, **$1.063902**, zero new unresolved liability and no benchmark scores. A hard mutation-binding check falsely rejected moved cache annotations despite matching strategy bytes; read gaps did not cause this stop. All eight reports replayed byte for byte and exact-owner cleanup completed. See the [diagnostic-read attempt report](docs/phases/phase-3b/PHASE3B_READ_AUDIT_LIVE_ATTEMPT_REPORT.md). No further calls or paid repetition are authorized by this outcome. The subsequent four-file correction passed 27 focused offline tests and the saved-sequence counterfactual; see the [audit addendum](docs/ENGINEERING_AUDIT.md#offline-false-stop-correction). These checks supply no fresh live-readiness pass or paid-run authority.

A [completed engineering audit and cleanup](docs/ENGINEERING_AUDIT.md) removed 194 obsolete first-party files (42,847 lines), detached current execution from historical release archives, and corrected report attribution and tie handling. Both canonical and public source profiles passed the same 101 offline component tests and independent readiness review. The cleanup verification itself made zero provider calls; the subsequent live attempt is reported above. Upstream code and the experimental comparison are unchanged; additional evaluators and human review are deferred.

## How the pieces fit

- **Harness² runs adaptation.** We keep the upstream engine pinned and unchanged.
- **Strategy adapters define the procedure.** Fixed and adaptive arms begin with the same declared techniques.
- **Benchmark adapters supply tasks and assessments.** NoveltyBench is the first protocol; it is not the project's universal objective.
- **Our experiment layer controls execution and evidence.** It owns provider calls, budgets, provenance, failure handling and replay.
- **[Inspect AI](https://inspect.aisi.org.uk/) provides passive records and a viewer.** Our adapter exports saved artifacts into it. Inspect does not make our provider calls or control spending.

Replacing an engine, benchmark, strategy or compatible evaluator requires a new identity and compatibility checks. We use bounded interfaces rather than build a general plugin platform ahead of evidence.

## Use from Codex

Codex can invoke the same project CLI through its terminal tools. No additional MCP server is needed for this entry point. From this source checkout, with `src` on `PYTHONPATH`:

```text
python -B -m buddha2 experiment --help
python -B -m buddha2 experiment inspect --study PATH_TO_STUDY_JSON
```

Inspection shows sealed study metadata without model calls or opening historical source captures. `prepare`, `grant`, and `report` delegate to the existing experiment code; `launch` uses the inspected provider boundary. Native execution remains in the pinned Linux environment. Paid execution requires current offline evidence, independent review, applicable spending authority, and fresh keys. The CLI does not supply any of those automatically.

## Start here

- [Engineering audit, cuts and practical delivery schedule](docs/ENGINEERING_AUDIT.md)
- [Current status and decisions](docs/research/CURRENT_SPEC.md)
- [Research method and interpretation](docs/RESEARCH_METHOD.md)
- [Concrete Phase 3B scope, completion criteria, caps and stop rules](docs/phases/phase-3b/PHASE3B_DEFINITION.md)
- [Completed Phase 3A result](docs/phases/phase-3a/PHASE3A_RP2_LIVE_REPORT.md)
- [Pinned environment and original implementation decisions](docs/phases/phase-0/DECISIONS.md)
- [Historical README, preserved verbatim](docs/archive/README_LEGACY.md)

This is a staged research repository, not an unattended production service. Fixtures and tests are offline by default. Paid runs use a separately accepted, source-bound launcher, an explicit grant and fresh masked key entry. Follow the current runbook when it is accepted; historical launch commands do not authorize another run.

## Public source release

GitHub contains the source, specifications, reports and reviewed text evidence from this project. Private credential bindings, locks, raw logs, run archives, installed environments and selected third-party reference/data captures remain local. Historical reports may link to those local artifacts. Replaying a frozen study also requires its provenance packet and pinned runtime; a public clone is a source release. See [publication notes](docs/PUBLICATION.md) for the exact boundary.

## Attribution and licensing

Harness² is Apache-2.0 licensed; NoveltyBench, Inspect AI and the OpenCode base used here are MIT licensed. Their code and notices remain their owners'. Exact revisions, additional dependencies, bundled-license exceptions and research references are documented in [Attributions](docs/ATTRIBUTIONS.md).

**Buddha2's own code and documentation are licensed under [Apache-2.0](LICENSE).** It includes an explicit contributor patent grant and matches the native Harness² engine's license. Third-party code, datasets, models and runtime components retain their separate terms; see [NOTICE](NOTICE) and the attribution guide.
