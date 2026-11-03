# Buddha2

A new research project comparing base-model sampling, fixed strategies, and genuine recursive harness adaptation.

The proposed core question is when, and by how much, native Harness² adaptation improves on a frozen strategy procedure with the same declared techniques and a comparable total inference budget. Base-model and fixed-strategy comparisons establish the reference points. Phase 3A tests one authentic step; Phase 3B explicitly tests successive native refinement before any claim about repeated recursive improvement.

**Status: Phases 0, 1 and 1A complete; Phase 1's evaluator is diagnostic-only.** The [Phase 1 report](PHASE1_REPORT.md) records all 48 judgments and $0.112696 usage-based API cost, with zero retries or unresolved reservations. On the 12 held-out prompts, both-orders human agreement was 4/12 (required 9) and order consistency was 8/12 (required 11). The critic missed both frozen floors. Predictions were committed before audit-label access; offline replay reproduced the reports unchanged. The user-approved readiness exception and single calibration-only format revision are recorded explicitly. The temporary encrypted key was cleared. The [Phase 0 report](PHASE0_REPORT.md) and its evidence remain unchanged. Subsequent experiments are unstarted and unauthorized.

**Phase 1A data readiness is complete under frozen specification 0.7.** The [report](PHASE1A_DATA_READINESS_REPORT.md) reconciles all 16,948 cached train rows and 48 historical response mappings, provides an [eight-pair inspection packet](evidence/phase1a-data-readiness-r07/inspection-packet.md) with its frozen shortfall, and records source, policy and exposure limits. MuCE is usable for development against its published labels; CrPO measurement reproduction is conditional; human agreement on new outputs is not established. Experiment spend was $0, with no model inference or new human ratings and no published held-out row contents opened.

**Phase 2A remains complete under frozen revision 0.10, closed in revision 0.11/commit 9ef4024.** The [preparation report](PHASE2_PREPARATION_REPORT.md) and [frozen study](runs/phase2-r010/frozen-study/study.json) retain the three fixed procedures, native exchange/assessment and replayed synthetic example. Its historical 175 project tests/five upstream checks and zero provider calls/human ratings/API spend are unchanged. Current [revision 0.19](PHASE_DEFINITIONS.md#research-tracks-and-later-human-input) retains that completed implementation and records the live-readiness no-go and both research branches.

**Phase 2B will conclude from benchmark results without waiting for human readers.** A separate optional human-augmented decision can arrive later. Both share one implementation, the same 12 frozen development prompts/two repeats and the same saved generation/native-assessment archive. The benchmark track can select its seed and support later phase definitions independently; human review adds a separately dated assessment/decision rather than changing native scores or rewriting earlier results. Compatible downstream evidence can be shared; a changed seed/procedure forks future work from the last compatible parent, with a separately scoped budget. No second full matrix is automatic.

**The offline policy update remains complete under frozen revision 0.12, closed in revision 0.13.** The `phase2-policy` route separates benchmark and optional human decisions; its historical 203-test/public-command evidence and 2,218-file output archive are unchanged. See [report](PHASE2_POLICY_UPDATE_REPORT.md). AM-1 subsequently corrected admission/accounting under a new identity; use its [offline candidate](PHASE2_AM1_REPORT.md), and retained exact source for old replay. Live Phase 2B remains unstarted/unauthorized. P2-R now supplies the offline-verified host boundary; applicable operator inputs/grants and counted first-block provider observations remain. Readers are optional; old $5/$125 proposals are not grants, and the first counted block must stop for review before expansion.

**The original live-readiness checkpoint remains complete/change-required under frozen 0.14.** Its [report](PHASE2_LIVE_READINESS_REPORT.md) and historical [AM-1 proposal](PHASE2_LIVE_READINESS_AMENDMENT.md) are unchanged. The separately authorized [AM-1 offline follow-up](PHASE2_AM1_REPORT.md) is now complete under frozen 0.16, closed in 0.17: supported public-PAYG liability envelopes, unchanged payload/scientific requests, narrow actual-SDK mock runner, exact resume, 230 project tests/five upstream checks and $0 API spend. The host launcher and full execution kit were subsequently completed by P2-R; applicable operator inputs/grants and counted first-block provider observations remain. Phase 2B is still unstarted.

Optional [Route H](PHASE_DEFINITIONS.md#route-h--a-bounded-independent-human-reference-check-optional) remains the separate two-reader/eight-pair MuCE rubric diagnostic, defined under revision 0.9 and unstarted. It is not required for Phase 2 and does not replace its separately optional fresh-output human assessment. CrPO implementation, weights/calibration and frontier evaluator tournaments remain deferred.

The recursive execution base will be the actual upstream [Google Harness²](https://github.com/google-research/harness2), used through its existing interfaces. This project will supply external integrations and study definitions rather than reproduce its algorithm.

The research rationale is in [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md). Concrete objectives, usable deliverables, exclusions and completion gates are in [PHASE_DEFINITIONS.md](PHASE_DEFINITIONS.md). Phase 0's resolved source pins, runtime, protected-folder boundary and implementation shape are in [DECISIONS.md](DECISIONS.md). Later definitions are provisional and must be refreshed before starting each phase. The persistent working agreement is [AGENTS.md](AGENTS.md). Historical Phase 1 closeout hashes refer to commit `35cc481` and its [archived specification 0.6](specifications/archive/phase-definitions-0.6.md); Phase 1A closure documentation is at commit `bed3465` and [archived revision 0.8](specifications/archive/phase-definitions-0.8.md). Route H's [definition revision 0.9](specifications/archive/phase-definitions-0.9.md) is preserved. Current planning documents do not rebind historical evidence.

The completed **Phase 1 population** is 24 Metaphors creativity prompt groups from 46 eligible groups: 12 calibration and 12 audit, both response orders. Source inspection disproved the original four-family creativity quota, and the user approved this narrower population before selection. All 48 scheduled judgments completed under the $5 authorization. Calibration had 11 valid/13 malformed outputs; audit had 24 valid outputs, including five ties and one abstention. Different prompt sets and one permitted format revision prevent treating the formatting difference as a causal result. See [Phase 1 decisions](PHASE1_DECISIONS.md), the [initial rubric](configs/phase1/rubric.md), [final rubric](configs/phase1/rubric-audit.md) and [profile](configs/phase1/profile.json).

## Starting decisions

- This is independent of `C:\Users\arvik\code\buddha2`. No code, dependencies, datasets, or result files have been copied from that project.
- Retain Harness²'s native proposal, probing, composition, selection, and experience mechanisms. Keep upstream source unchanged.
- Separate task suites, strategies, execution, model configuration, and evaluation through small versioned interfaces.
- A benchmark can supply tasks and an evaluator. An evaluation-only extension can assess compatible saved outputs, including under additional criteria.
- NoveltyBench is the first benchmark integration, not a permanent boundary of the project. Other task protocols and compatible criteria enter through their own adapters and bounded phase definitions.
- Keep Native NoveltyBench evaluation external and version-pinned; preserve its native metrics and protocol.
- The completed MuCE screen checked agreement with published labels; human alignment on new outputs remains unvalidated. Keep further supplementary measurement work optional, with development and held-out assessment separate.
- Retain CrPO-inspired diversity, novelty, surprise and quality as measurement dimensions beyond NoveltyBench. Bayesian surprise is a deferred evaluator candidate; the [reference conversation](references/surprise-conversation.md) is background, not an implementation requirement.
- Give fixed and adaptive conditions the same declared technique access; require a budget-comparable fixed control for attributing gains to adaptation.
- Start with the original planner and isolated reranking. Lenny-derived procedures and Lluminate operators are optional strategy packages, introduced one family at a time rather than as prerequisites.
- Treat human steering as a separate condition, cache/scoring fixes as correctness requirements, and evaluator-guided strategy search as a separate supervised method.
- Work in bounded phases. Complete and review one slice before extending scope.

## Use the offline kit

The [Phase 2A kit](PHASE2_PREPARATION_REPORT.md#use-and-replay) is preserved under its original source identity. Use the current [policy route](PHASE2_POLICY_UPDATE_REPORT.md) to inspect the refreshed study or reassess saved historical outputs without generation:

```powershell
.\phase0.ps1 run phase2-policy inspect --study /results/phase2-r012/frozen-study/study.json
.\phase0.ps1 run phase2-policy decide --study /results/phase2-r010/frozen-study/study.json --run /results/phase2-r010/walkthrough-complete --track benchmark --cutoff 2026-10-26T20:00:00Z --output /results/phase2-r012/benchmark
```

This reproduces the new synthetic benchmark decision on the historical outputs. The original `phase2 inspect`/`phase2 replay` path requires its retained source bundle, study, exposure context and pinned image; current changed source correctly fails the old preparation identity. The unchanged preparation report retains its original export/import/replay instructions and limitations. Do not rewrite its manifests to use current code.

The retained `runs\example` and its archive belong to [frozen specification 0.3](specifications/archive/phase-definitions-0.3.md), at commit `6bafb25`. The current specification/code changes the effective identity: historical resume may correctly refuse it. Preserve those records; use a fresh namespace for current runs or the original checkout/image/inputs for historical resume. The commands below retain their earlier example namespace; choose an unused namespace or resume only with unchanged effective inputs.

Run these commands in PowerShell from `C:\Users\arvik\code\research\Buddha2`. Docker Desktop must be running with its Linux engine; the host needs Git and Python only for setup. Setup downloads the two public pinned checkouts, including their versioned assets, and hash-locked software dependencies. It does not fetch model weights or the MuCE dataset.

```powershell
.\phase0.ps1 setup
.\phase0.ps1 check
.\phase0.ps1 test
.\phase0.ps1 run demo --output /results/phase0-r04/example
.\phase0.ps1 run inspect --run /results/phase0-r04/example
```

New example files appear on the host under `runs\phase0-r04\example`. Read `report.md`, `portfolio.json`, `manifest.json`, the retained harnesses/trajectories under `engine`, and the separate assessment records. The complete [original example archive](evidence/phase0-example.zip) is also retained with the source. Every response, proposal and head score is explicitly synthetic. The fixture's native distinctness is 5 and utility is approximately 4.346485261239209; these numbers verify arithmetic, not model quality.

Export, import and assess the saved portfolio without generating answers:

```powershell
.\phase0.ps1 run export --portfolio /results/phase0-r04/example/portfolio.json --output /results/phase0-r04/exported
.\phase0.ps1 run import --source /results/phase0-r04/exported --output /results/phase0-r04/imported
.\phase0.ps1 run assess --portfolio /results/phase0-r04/imported/portfolio.json --output /results/phase0-r04/reassessed --grading /results/phase0-r04/example/grading.json --noveltybench /workspace/.upstream/novelty-bench
```

Omit `--grading` and `--noveltybench` for mechanical validation only. Native fixture arithmetic requires the matching declared synthetic evidence; arbitrary imported text is never assigned invented quality labels. `generations.jsonl` carries ordered texts; keep `identities.json` with it to preserve external response IDs, including duplicate texts.

Exercise the one supported interruption checkpoint:

```powershell
.\phase0.ps1 run demo --output /results/phase0-r04/checkpoint --stop-after-output
.\phase0.ps1 run demo --output /results/phase0-r04/checkpoint --resume
```

An existing completed run can be resumed idempotently with unchanged effective inputs. A changed strategy, source pin, package/lock/specification or image requires a new output directory; corrupted saved evidence is refused. Runtime inspection records and captured stdout/stderr are retained under `runs\runtime` and identify the exact image, mounts, offline restrictions and exit status. Full tests take several minutes on the Windows bind mount because negative resume cases recheck about 115 MB of pinned upstream files.

Only the new project is mounted read-only, with its `runs` directory mounted separately for output. The original folder is outside all write paths and runtime mounts. Phase 0 does not exercise live OpenCode, providers, model reasoning, official judges, real billing controls or scientific effectiveness.

## Use Phase 1

The live study is closed. Inspect or recompute its saved results without a credential or provider access:

```powershell
.\phase1.ps1 offline inspect --run /results/phase1-live-r05
.\phase1.ps1 offline analyze --prepared /results/phase1-prepared --run /results/phase1-live-r05 --stage calibration
.\phase1.ps1 offline analyze --prepared /results/phase1-prepared --run /results/phase1-live-r05 --stage audit
```

Keep the local prepared data and frozen execution bundle for replay. The [closeout report](PHASE1_REPORT.md) explains the diagnostic-only decision, limits and evidence. A revised evaluator requires a separately reviewed definition and fresh held-out material; do not tune against this consumed audit.

The original offline checkpoint commands remain available:

Use the same pinned Docker image and supported runtime. These commands require no credential or network:

```powershell
.\phase1.ps1 test
pwsh -NoProfile -File tests/test_phase1_launcher.ps1
.\phase1.ps1 offline fixture --output /results/phase1-fixture
.\phase1.ps1 offline inspect --run /results/phase1-fixture/evaluator
.\phase1.ps1 offline analyze --prepared /results/phase1-fixture/population --run /results/phase1-fixture/evaluator --stage audit
```

The synthetic workflow exercises the complete 12/12 process, readiness review, freeze, prediction commitment, analysis and replay. Its preferences and usage are visibly invented; it is software evidence only. Use a fresh output namespace after any code/image/input change.

The pinned real source is cached under `runs/phase1-preparation`; converted source and reader metadata are under `runs/phase1-source`. Reproduce the approved selection and stage only public critic inputs:

```powershell
.\phase1.ps1 offline prepare --source /results/phase1-source/muce-full_agreement-train.canonical.jsonl --metadata /results/phase1-source/conversion.json --output /results/phase1-prepared
.\phase1.ps1 offline stage --prepared /results/phase1-prepared --output /results/phase1-live-r05
.\phase1.ps1 offline preview --run /results/phase1-live-r05
```

`runs/phase1-live-r05/plan.json` contains the 48 label-free presentations and fixed profile. `initial-rubric.md` is exact; `controls/first-request.json` shows the first calibration request. `bundle.json` binds code and staged inputs. Separate label/private files remain in `runs/phase1-prepared`; do not copy them into the live bundle. The completed predictions/results, final rubric freeze and separate assessments are retained in the run. Preparation/staging commands above document reproduction of the original checkpoint; they do not reset a completed run or authorize a new live study.

Live commands in the historical preparation report describe the bounded route, not authorization for another run. The launcher requires an explicit live switch, a single staged run, a supplied provider key and a numeric authorized cap. It mounts only source code and that run. The automatic two-valid-results readiness gate did not pass in this study; the user explicitly approved the recorded operator exception, retaining the malformed result unchanged. Offline analysis commits all audit predictions before reading its labels. Actual provider compatibility/accounting was exercised for this critic only; generator, native judge and recursive proposer/executor paths still need their own readiness evidence.

**Usable AM-1 commands and limitations:** see [the report](PHASE2_AM1_REPORT.md#usable-candidate-and-commands), [candidate study](runs/phase2-am1-r016/candidate/study.json) and [current phase sequence](PHASE_DEFINITIONS.md#current-phase-sequence-and-research-branches). Public commands remain offline-only. No provider calls, real credentials or new spending were authorized or used.

**[P2-R — Complete Phase 2B Execution Kit](PHASE2B_EXECUTION_KIT_REPORT.md) is complete** under frozen 0.18, closed in revision 0.19. It supplies every known software prerequisite: complete pilot/expansion, cumulative staged authority, inspected host launcher, new-release reporting/replay and optional late-human compatibility. All 271 project tests/five upstream checks pass; the full 1,320-request/72-assessment mock lifecycle and exact zero-call resume/replay pass. Provider calls, real credential access, actual human collection and API spend were zero. The original folder remains untouched.

Use the [runbook](PHASE2B_RUNBOOK.md) and [nonauthorizing release packet](runs/phase2-release-r018/release/launch-packet.json). Only applicable operator inputs/grants remain before Phase 2B’s counted first block → review/cumulative expansion grant → remaining pilot/report, all using the completed kit. Phase 2B and later adaptation are unstarted/unauthorized; readers stay optional and CrPO deferred. No paid grant is supplied by this closure.
