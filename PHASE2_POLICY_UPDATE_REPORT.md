# Phase 2 policy update

This offline update implements the two research tracks in frozen specification 0.12. A benchmark decision can select a seed with no human submissions. A later human assessment produces a separate decision on the same saved outputs. All human decisions reference the original benchmark root; assessment supplements link their predecessors.

The original Phase 2A execution path and its source archive remain historical artifacts. The new `phase2-policy` command validates original execution sources separately from the current assessment implementation. It never relabels old portfolios or regenerates answers. A refreshed preparation binds both policies before any future generation, with the original twelve prompts, two repeats, templates, profiles and human sample unchanged.

## Use

From `C:\Users\arvik\code\research\Buddha2`, use the existing offline launcher:

```powershell
.\phase0.ps1 run phase2-policy inspect --study /results/phase2-r012/frozen-study/study.json
.\phase0.ps1 run phase2-policy decide --study /results/phase2-r010/frozen-study/study.json --run /results/phase2-r010/walkthrough-complete --track benchmark --cutoff 2026-10-26T20:00:00Z --output /results/phase2-r012/benchmark
```

The second command replays the synthetic demonstration's benchmark decision. Its selected real method remains null; its synthetic method is A. This is software evidence, not a performance result. The current command exposes no live execution or provider transport.

`human-packets` prepares local blinded forms plus a separate private mapping. It contacts nobody and does not activate collection. A later authorized checkpoint uses `human-import` with a JSON list of submission envelopes and an agreed window; `decide --track human-augmented` attaches the resulting assessment and original benchmark `--parent`. A supplement adds only a previously missing reader; it cannot revise an earlier form. Missing or compromised humans affect only the optional decision. Human notes never modify native scores.

Submission envelopes contain `form`, `delivered_at`, `first_exposed_at` and `received_at`. Each timestamp uses `YYYY-MM-DDTHH:MM:SSZ`. The initial `--window` JSON binds both reader IDs to `delivered_at` and `due_date`; due dates must fall within seven calendar days of delivery. `--previous` preserves the earlier assessment and window. Late forms require a previously closed window and enter a separately versioned supplement. Empty assessments retain missingness; an absent window explicitly means collection is unactivated.

The demonstration under `runs/phase2-r012` includes `benchmark`, `human-pending`, `human-window-closed`, `human-late`, `human-decision`, `packets`, input examples and `demonstration.json`. Its late dates and forms are simulated. An invented concern on A produces a separate synthetic B decision while preserving the benchmark A decision and identical execution/native-assessment identities.

`compatibility` compares two decisions and explicit continuation contexts (`--parent-context`, `--candidate-context`). Each context binds task/output, effective method, model/settings, budget policy, information access and native mode. A changed seed or context requires a divergent future execution. Shared evidence is never independent replication. Changed continuation after opened confirmation cannot support a new confirmatory claim on that consumed material.

## Evidence and limits

Verification passed: **203 project tests** (including 105 Phase 2 tests), **five upstream Harness² tests**, Ruff, mypy over all 19 source files, Bandit's medium/high-severity checks and `pip check`. The public-command demonstration made zero generation/provider requests. Running the original source bytes from the retained archive also replayed all 72 historical native assessments, identical original analysis/coverage and 960 unchanged journal attempts, without generation or provider calls. Current documentation closes the unchanged 0.12 implementation in revision 0.13.

| Specification 0.12 completion check | Evidence |
|---|---|
| Native comparison can select without humans | `test_benchmark_selects_without_humans_and_preserves_historical_identity`; public `benchmark/decision.json` has synthetic A and `human_status: not-required`. |
| Missing, late or compromised humans cannot block benchmark | Separate `human-pending` decision; focused human/decision tests cover missingness, recognition, ineligibility, ambiguity and malformed evidence; benchmark replay is identical. |
| Later forms add a bound independent decision | Public `human-import`/`decide` demonstration; `human-late` references its closed-window predecessor and exact ordered outputs, while `human-decision` references its verified benchmark root. |
| Concerns affect human selection; shared defects affect both | Synthetic A concern selects B only on the human track; native-forgery/accounting tests reject both tracks and cannot-judge tests leave only human selection inconclusive. |
| Shared versus divergent parents are explicit | Continuation tests cover matching identity, changes in every context field and fresh-confirmation requirements; public divergent continuation names both decision parents and disclaims independent replication. |
| Existing safeguards and preservation survive | Full project/upstream suite and static/security checks; old source archive, 2,218 run files, pinned inputs and historical manifests verified before packaging. |

The implementation plan is [PHASE2_POLICY_UPDATE_PLAN.md](PHASE2_POLICY_UPDATE_PLAN.md). Requirement-by-requirement completion, runtime records, test/check results, preservation counts and the frozen package identity are recorded in `evidence/phase2-r012/closeout.json` and `manifest.json` after verification. The exact execution specification is `evidence/phase2-r012/specification-0.12.md`; older completed reports/manifests retain their original meanings.

Native journal records from the old run do not carry wall-clock result times. The decision cutoff records the operator's declared snapshot boundary; it is not independent proof that native evidence existed before a particular time. Human receipt/exposure chronology is validated, but the supplied metadata and eligibility remain attestations. Compatibility contexts likewise check declared identities, rather than independently establish their truth or authorize execution.

A changed future assessor must preserve its own revision and use the retained source bundle or an explicit compatibility review to replay an older human-assessment chain. An old execution does not need to be relabelled to obtain a new assessment. Every affected track must address a discovered source, scoring, leakage or accounting defect.

No provider/token-count calls, experiments, actual human ratings or spending are part of this update. The original folder was never accessed. Live Phase 2B remains unstarted and unauthorized: input-admission proof, grouping billing, provider access and applicable spending authorization remain separate prerequisites. Reader availability is optional. CrPO stays deferred and Route H optional/unstarted.
