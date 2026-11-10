# Buddha2

**Saved-work continuation is implemented and verified offline.** The runner retains the stopped study's 2,651 calls/$44.975462, reuses verified completed work and carries old/new costs once. All 166 selected checks and scoped static checks pass. See [resumption and its limits](docs/RESUMPTION.md) and [acceptance evidence](evidence/phase4-cm1-v1/resumability-v1.json).

P4's scientific comparison remains incomplete: three of its original 24 cases started, one generation pair completed, and no grading ran. The same 24-case continuation is approved within the existing caps and independently accepted: 110 launch checks plus the actual Windows handshake passed. Fresh keys were entered and the supervisor attachment was consumed; the approved missing-work continuation is starting. Startup is not a scientific result. See [startup evidence](evidence/phase4-cm1-v1/continuation-startup-v1.json). See [launch acceptance](evidence/phase4-cm1-v1/continuation-launch-acceptance-v1.json). See the [closed live report](docs/phases/phase-4/PHASE4_CM1_LIVE_REPORT.md).

Phase 3B's four-prompt development pilot is complete. Selected native adaptation averaged distinctness 10/10 and utility 7.417; fixed best-of-twelve averaged 7.75/10 and 6.113. One password prompt's semantic grouping result drives the positive average utility gap. See the [results and limits](docs/phases/phase-3b/PHASE3B_REMAINING_PAIRS_LIVE_REPORT_V2.md).


[Explore the system architecture](docs/architecture/README.md), including Harness², the current agent runner and model roles, our surrounding code, NoveltyBench and passive Inspect.

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

**Completed 7 November 2026:** actual Harness2 `seq,k=2` versus fixed best-of-twelve on four exposed development prompts. All eight primary aliases and twelve assessment targets are scored.

| Arm | Mean distinct@10, four prompts | Mean utility, four prompts | Inference cost, three new prompts |
|---|---:|---:|---:|
| Fixed best-of-twelve | 7.75 | 6.112825 | $2.622912 |
| Selected native two-round adaptation | 10 | 7.417165 | $16.512431 |

The mean paired difference is +1.304340, with two wins and two losses. One password prompt's semantic-grouping result drives the positive mean. Mean c2-minus-c1 is +0.018056, including fresh sampling with an unchanged strategy on that prompt. Adaptive inference cost about 6.30 times fixed inference over the new three pairs. This is a descriptive development result, with no held-out, population or cost-efficiency claim.

The continuation used 1,026 settled calls/$19.981693 under its $350 cap, preserving the original assessed pair. The complete four-prompt comparison totals 1,387 calls/$31.221549. Zero-call replay matched all eight reports; both passive Inspect exports passed. See the [full result](docs/phases/phase-3b/PHASE3B_REMAINING_PAIRS_LIVE_REPORT_V2.md) and [closure evidence](evidence/phase3b-seq2-v1/remaining-pairs-live-outcome-v1.json).

<details>
<summary>Earlier execution and engineering history</summary>

The records below are earlier snapshots, retained with their original statements and links. The completed comparison above is the current outcome.

**Assessment-only reuse is prepared offline.** The existing CLI can prepare and verify an immutable packet for the saved first prompt: 25 existing judgments are reusable and eight c2 quality judgments remain. Both complete cached assessments replay exactly; generation and the closed run stay unchanged. All 30 selected offline checks pass. The packet has no execution authority or live executor. See the [reuse preparation](docs/ENGINEERING_AUDIT.md#assessment-only-reuse-preparation).

**Preflight now requires regression coverage and checks the current producer/evaluator size contract.** Shared limits drive validation and maximum-size requests through the real benchmark builders. All 75 selected offline checks pass, including changed-limit and missing-regression tests; financial guards and saved generation are preserved. See the [preflight update](docs/ENGINEERING_AUDIT.md#mandatory-preflight-regressions-and-contract-checks). No new paid run has started.

Status snapshot: **6 November 2026**. [CURRENT_SPEC.md](docs/research/CURRENT_SPEC.md) tracks subsequent execution and decisions.

**Historical generation attempt closed incomplete: 353 calls/$11.082350, with zero new held liability.** The first prompt's native two-round path completed normally and fixed best-of-twelve also returned. That closed attempt's final evidence remains globally held: zero of eight primary outputs and zero of twelve assessment targets are scored in its historical projection. The separately completed first-pair assessment supplement is reported above; the four-pair comparison remains incomplete.

Local validation stopped the next quality judgment. A saved-input reconstruction measures **6,206 UTF-8 bytes against an outdated 5,952-byte quality-request cap**, 254 bytes over. The rejected body was not logged, so this is a reconstruction. No timing stop or provider failure caused the halt. Closure, the passive Inspect export and one zero-call replay are complete; all eight report files matched byte for byte. See the [attempt report](docs/phases/phase-3b/PHASE3B_TIMING_CONTINUATION_LIVE_ATTEMPT_REPORT.md) and [outcome receipt](evidence/phase3b-seq2-v1/timing-continuation-live-outcome-v1.json). The subsequent [focused evaluator-admission fix](docs/ENGINEERING_AUDIT.md#evaluator-admission-correction) is verified offline: 45 focused checks pass, including the real saved requests and allowed output-size envelope. Financial guards and completed generation are preserved. No paid continuation or new live kit was created.

**The preceding continuation closed incomplete: 161 calls/$5.877824, with no benchmark result.** The first prompt's native selector used its available admission time on read calls; its next request was rejected before dispatch, with about 56.948 seconds left against a 60-second requirement. The fixed arm and judges did not start. Canonical closure, the passive Inspect export and one saved-report replay are verified with zero additional model calls. See the [attempt report](docs/phases/phase-3b/PHASE3B_CONTINUATION_LIVE_ATTEMPT_REPORT.md) and [outcome receipt](evidence/phase3b-seq2-v1/continuation-live-outcome-v1.json).

The subsequent [timing correction](docs/ENGINEERING_AUDIT.md#conversation-time-controls) replaces that conversation cutoff with a warning, grace and an explicit continuation decision before another request. All 67 focused tests and scoped static checks pass. An [actual-native human rehearsal](evidence/phase3b-seq2-v1/timing-human-rehearsal-v1.json) also passed: after the user's Continue answer, the same Bun/OpenCode process resumed its unchanged pending request and completed five mocked-provider rounds normally. No SDK calls occurred while paused; the rehearsal spent $0 and left production source unchanged. The fresh four-prompt Phase 3B comparison was approved within $146.435242 total/$26.094077 included first-prompt caps. Its [current-source acceptance](evidence/phase3b-seq2-v1/timing-continuation-offline-acceptance-v1.json) passed 151 checks and both actual host-launcher gates at $0. That kit was used for the latest stopped attempt above. [CURRENT_SPEC.md](docs/research/CURRENT_SPEC.md) records the boundary.

A separately authorized **offline artifact-binding correction** now follows the native engine's actual return and saved-file priority. It binds the actual artifact, write witness and strategy while treating final-chat prose differences as diagnostic. Offline checks passed 145 unique methods across pinned Linux and the Windows host, with independent review. See the [audit correction](docs/ENGINEERING_AUDIT.md#durable-native-artifact-binding-correction). The stopped R2 result remains incomplete; no fresh live kit, grant or paid continuation is created.

**Earlier artifact-contract R2 attempt closed incomplete:** 513 calls/**$14.094285**, zero new unresolved liability. The first paired prompt completed, but a later selector stopped because our artifact contract compared differing prose despite the same declared candidate B. The exploratory first-pair scores remain distinct from the final globally held result (zero primary/assessment targets scored). There is no completed four-prompt comparison or gain claim. See the [R2 attempt report](docs/phases/phase-3b/PHASE3B_READ_AUDIT_R2_LIVE_ATTEMPT_REPORT.md). No paid repeat follows automatically.

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

</details>

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
python -B -m buddha2 experiment phase4 --help
python -B -m buddha2 experiment inspect --study PATH_TO_STUDY_JSON
```

Inspection shows sealed study metadata without model calls or opening historical source captures. `prepare`, `grant`, and `report` delegate to the existing experiment code; `launch` uses the inspected provider boundary. Native execution remains in the pinned Linux environment. Paid execution requires current offline evidence, independent review, applicable spending authority, and fresh keys. The CLI does not supply any of those automatically.

## Start here

- [P4 closed outcome, costs and confirmed stop cause](docs/phases/phase-4/PHASE4_CM1_LIVE_REPORT.md)
- [P4 offline preparation evidence](docs/phases/phase-4/PHASE4_CM1_KIT_REPORT.md)
- [Current Phase 3B result and loss analysis](docs/phases/phase-3b/PHASE3B_REMAINING_PAIRS_LIVE_REPORT_V2.md)
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
