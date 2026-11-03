# Phase 3A offline execution kit

Completed 2026-10-28 under frozen [Phase 3A definition 1.0](PHASE3A_DEFINITION.md) and the [subsequent whole-phase authority](../../../evidence/phase3a-v1/authorization.json).

**The offline kit is complete and ready for fresh masked operator key entry. The scientific Phase 3A pilot is not complete: no real provider requests, real credential access or Phase 3A API spending have occurred.** The approved $220 phase ceiling includes the $65 first-pair checkpoint. Neither the offline gate nor its simulated results establish real model behavior or effectiveness.

## What was built

The kit executes four exposed development prompts, one repeat and two fresh arms: native Harness² `agg,k=1` from C-N, and fixed C-N best-of-six with a blind whole-portfolio selector. Both receive the same allowed dollar/request/input/output resource vector. Their allocations and realized costs can differ; unused allowances expire. This compares complete procedures under equal allowed resources, not equal realized compute.

Actual pinned Harness² `schedule.run_task` and native `Proposer(opencode)` perform INV and DOM authoring, both probes, AGG composition and the sole eligible `agg1` final. OpenCode is the real pinned CLI. Only the three declared system-template strings are editable; Python, tools, skill packages, shared memory and the engine algorithm are outside the authoring surface. Valid explicit unchanged proposals are permitted and recorded. Automatic fallbacks remain classified and cannot alone establish an authentic live path.

The fixed arm generates six independent fresh C-N candidates and selects one unchanged whole portfolio using its declared Opus selector. It cannot merge, rewrite, reorder again or replace failures. Both selected finals are sealed before either is assessed. Eight primary native NoveltyBench assessments and the fixed p3a-01 duplicate diagnostic are scheduled; the duplicate never replaces its original primary score.

| Source | Definition 1.0 requirements covered |
|---|---|
| `followups/phase3a_v1/strategy.py` | Three-field surface validation; byte-conformant original C-N seed; fresh planning/ten answers/N1; six candidates and whole-portfolio selection; strict saved-request reconstruction |
| `native.py`, `editor.py`, `editor-tools.json` | Actual upstream engine and CLI; task-local authoring; journal-bound stage proofs; bounded tool access, conversations and transport replay |
| `accounting.py`, `transport.py` | Per-cell and phase reservations; explicit pinned SDKs/models; no ambient keys or SDK retries; durable unknown/integrity halt; every real HTTP request accounted |
| `workflow.py`, `cli.py` | Four paired blocks; seals; first engineering review and remaining continuation; native assessment; all-outcome coverage, exact replay and reporting |
| `launch.py`, `phase3a.ps1` | Actual source/authority/image/mount/network inspection; source-bound gate; masked credentials only after the Ready handshake; suppressed provider streams |
| `tests/`, `Dockerfile` | Conformance, native path, repair/attack/failure/resume checks and the pinned runtime |

See the [runbook](PHASE3A_RUNBOOK.md) for the one-phase execution sequence and exact PowerShell command.

## Frozen release

| Binding | Value |
|---|---|
| Study | `1628a958477de938f55bd925cfa08150a1067ef8233ae937ae79e9bcbbcfe42a` |
| Effective source | `583b2e816863f98c050615dc501273f9f11f2f3caad0b0dcd5795285bf71dbf4` |
| Offline gate | `3ea3fb515d345c6ab5e1e002b18c42aa27c3193b01ef4c3445a29163adc43444` |
| Live grant | `2624ec1f39037596bb24af75df7dc976fa18630d4b9951805576ace7a39e2f65` |
| Runtime image | `sha256:8792a096b4881d47ab19cc7cbf6a74a232f9ff7cedc978fe93f902a71522d4f2` |
| Harness² | `1cfe254e8d25b15f37048c3730134686abe60335` |
| NoveltyBench | `64a23be6b18ec1dacc298830aab276061b6e143c` |
| OpenCode | `23fb5e0516c99ac04a1aa46c193efda2e1b9bb24` |
| Bun | `1.3.11`, exact binary and lock hashes in runtime provenance |

The [study and retained 142-file source](../../../runs/phase3a-v1/release-v3/study.json), [gate](../../../runs/phase3a-v1/release-v3/readiness.json), [live grant](../../../runs/phase3a-v1/release-v3/live-grant.json) and [runtime provenance](../../../evidence/phase3a-v1/runtime-provenance.json) retain the exact bindings. Only the declared, hash-pinned local OpenCode compatibility patch is applied to the separate runtime copy; pinned upstream checkouts and the Harness² algorithm remain unchanged.

## Offline evidence and its limits

- The final 66-test suite passed: 65 Linux tests and one host-only skip. That host test separately passed on actual Windows PowerShell, with zero skips. The preserved 271-test suite passed in its earlier pinned image with isolated new output storage. Ruff, mypy and Bandit passed for the new code. These checks do not prove live provider availability.
- The contained full host SDK-mock matrix completed **619 known simulated HTTP requests**, with **40 fresh C-N rollouts**, **eight selected primary finals**, **nine scored fixture assessments**, four native R=4/P=3 paths and **zero unknown or pending requests**. All fixture authenticity flags remain false. The 727 slots are the maximum worklist, not a required number of calls.
- Role counts reconcile exactly: 40 plans, 400 answers, 40 ranks, 36 editor HTTP requests, four fixed selectors, nine groupings and 90 head-quality judgments. All 619 intent/result/wire pairs and the 1,239-event hash chain reconcile. Every one of 1,332 retained raw files matches its hash and length.
- One physical host first-stage cold resume and one current-source SDK-mock CLI remaining-stage resume each added **zero** requests and retained the same evidence identity. This is not a claim of two host cold resumes.
- Seven report files were independently regenerated twice from 1,484 hash-verified copied inputs at identical absolute `/results` paths in bounded Linux tmpfs. All seven outputs are byte-identical, with zero model/network attempts and unchanged original source/data. This saved-evidence replay is distinct from the physical host cold-resume check.
- Actual native CLI tool reads/writes, a valid no-change proposal, duplicate HTTP delivery and native second-shape repair were exercised with SDK mocks. Forbidden reads/writes/shell use and untrusted filesystem inputs were checked. Unknown delivery, usage, profile and integrity outcomes halt durably; the same uncertain request is not resent.
- The nine evidence-bound gate groups passed. Root and an independent reviewer checked the gate's 1,396 distinct referenced artifacts and all 142 current/retained source hashes. The post-gate ordinary PowerShell provider configuration was inspected while unstarted, then removed with absence confirmed; no credential or provider activity occurred.

The fixture ledger's **355,193 micro-USD ($0.355193)** is simulated accounting, not real spending or a live cost forecast. Real Phase 3A API spending is **$0** at this closeout. The fixture mean and scores are mechanical test data and establish no scientific advantage.

Raw evidence is indexed in [raw-run-manifest.json](../../../runs/phase3a-v1/release-v3/raw-run-manifest.json); the [resume record](../../../runs/phase3a-v1/release-v3/resume-check.json), [report snapshot proof](../../../runs/phase3a-v1/release-v3/report-snapshot-proof.json), [launch index](../../../runs/phase3a-v1/release-v3/launch-record-index.json) and [post-gate configuration](../../../runs/phase3a-v1/release-v3/post-gate-configuration.json) retain their specific coverage and hashes.

## Timing and retained prototypes

The first/remaining host fixture execution containers lasted about 109.74 and 318.98 seconds. The physical cold-resume execution container lasted about 745.94 seconds, with about 191.22 seconds of preceding preflight and additional host overhead. These are observed container/preflight times on this host, including validation and any credential-entry interval. They are not model-only timing or general performance estimates. The frozen report intentionally leaves journal-derived wall time null and points to the retained host records; no inference-only duration is invented.

V1 is an incomplete offline prototype: the reviewed first-pair prefix contains 163 known fixture requests/327 events, followed by twelve settled requests in an incomplete continuation, for **175 total/351 events**. Its original retirement record is preserved, and the full archive documents both the reviewed prefix and later continuation. V2 completed the 619-request fixture matrix and report replay under its own identity. Its 120-second pre-key wait failed safely before key entry on a full saved dataset; a measured 600-second local overlay passed. Production v3 uses that one-token host-only wait overlay and the corresponding host test. Provider HTTP timeouts remain 90 seconds and editor conversations remain bounded at 600 seconds. Models, prompts, budgets and scientific scope did not change.

The [v1 archive inventory](../../../evidence/phase3a-v1/v1-prototype-archive.json) and [v2 archive inventory](../../../evidence/phase3a-v1/v2-mock-archive.json) retain exact versions and CRC/member hashes. The final archive retains their evidence without relabeling either prototype as a live pilot.

## Authority, costs and live continuation

Each of eight inference cells has $20, 96 HTTP attempts, four million aggregate input tokens and 786,432 output tokens, including next/open reservations. Assessment has a separate $60 pool. The included first checkpoint is $65 = two $20 cells plus a $25 sublimit within that same assessment pool. No transfer or spending-to-equalize is allowed. An Opus call needs an $11.44 conservative reservation; settlement releases the unused reservation when usage is known.

The frozen conditional cost scenarios were independently recomputed. The working scenario is $15.89389, or $22.62589 if every editing stage needs its second shape conversation. Lean/heavier scenarios remain in the worksheet. These are demand assumptions, not measured forecasts, invoices, guaranteed spending or guaranteed completion under local caps.

The first counted pair stops for engineering review of identity, accounting, isolation and native trace. Neither favorable utility nor a changed file is a continuation condition. After that review, the remaining three pairs use the same whole-phase authority. Fresh masked keys are required because earlier credentials were discarded. Real keys remain outside the editor, files, command line, environment and retained streams.

Full scientific completion requires eight scored primary finals, known accounting and at least one complete real model-backed INV/DOM/probe/AGG/final path. Valid explicit unchanged proposals count; fallback-only paths do not. If all eight are scored but authenticity is unproved, retain individual outcomes and keep the primary mean null/mechanism-unverified, as the frozen reporter specifies. Failed/missing/uncertain outcomes are retained without replacement. The duplicate is classified diagnostically and never selects a better primary assessment.

## Preservation and exit

All 1,137 previously tracked files and the original 1,130-file pre-definition baseline remain byte-preserved. The ten historical working-tree CRLF/LF differences are pre-existing and remain unchanged. All 13 earlier phase reports are already committed; the prior-evidence audit verifies retained archives/manifests and the original strict versus C-N lineage. 

The verified [offline execution kit archive](../../../evidence/phase3a-v1/offline-execution-kit-v3.zip) and [member manifest](../../../evidence/phase3a-v1/offline-execution-kit-v3.manifest.json) retain the source, native Python/license dependencies, definitions, grants, gate, raw fixture outputs, reports, launcher records and verification scripts. The Docker image and full benchmark datasets are not embedded; exact runtime/source pins and the supported local runtime remain required. The [closeout](../../../evidence/phase3a-v1/closeout.json) binds this report and archive after verification.

The usable result is the frozen inspected execution kit and complete replayable fixture evidence. **Actual Phase 3A remains pending the counted live run and its final report.** Phase 3B successive `seq,k=2`, held-out confirmation, CrPO/MuCE, human readers, Bayesian surprise, additional strategy/model/benchmark families and external publication remain separately scoped.
