# Phase 1 offline checkpoint

2026-10-25, America/Los_Angeles. New project: the project root.

**The evaluator kit and frozen population are ready for review. No model requests or provider spending have occurred. Phase 1's live audit remains pending.**

## What is usable now

The command-line kit prepares reproducible pairs, stages label-free critic inputs, executes a complete synthetic calibration/audit workflow, and replays saved analyses without requests. It keeps the pair contract separate from Phase 0's ten-response portfolios and synthetic Native NoveltyBench grading.

| Piece | Location |
|---|---|
| Current bounded specification | [PHASE_DEFINITIONS.md](../../research/PHASE_DEFINITIONS.md), revision 0.5; exact [archive](../../../specifications/archive/phase-definitions-0.5.md) |
| Decisions and deviations | [PHASE1_DECISIONS.md](PHASE1_DECISIONS.md) |
| Approved deterministic selection | [selection.json](../../../configs/phase1/selection.json) |
| Exact initial evaluator | [rubric.md](../../../configs/phase1/rubric.md), [profile.json](../../../configs/phase1/profile.json) |
| Frozen aggregate population | [preparation manifest](../../../evidence/phase1/preparation-manifest.json) |
| Source evidence | [feasibility](../../../evidence/phase1/feasibility.json), [conversion](../../../evidence/phase1/conversion.json), [provenance](../../../evidence/phase1/preparation-provenance.json), [source notes](../../../evidence/phase1/source-notes.md) |
| Staged code/input identity | [evaluator bundle](../../../evidence/phase1/evaluator-bundle.json) |
| Exact tested source bytes | [runtime source snapshot](../../../evidence/phase1/runtime-source.zip), SHA-256 `0c1f2d62312a831bd8325380434be827ef14a084b9ee916f4c3111921272a822` |
| Implementation | [pair contract/analysis](../../../src/buddha2/pairs.py), [MuCE preparation](../../../src/buddha2/muce.py), [runner](../../../src/buddha2/phase1_runner.py), [workflow](../../../src/buddha2/phase1.py), [launcher](../../../phase1.ps1) |

The real staged bundle is `runs/phase1-live-r05`; the private preparation, including separate labels and original selected rows, remains in `runs/phase1-prepared`. These run directories are intentionally untracked. Source data are retained locally rather than included in a public release. The source snapshot preserves exact runtime bytes and hashes, including existing line endings; a checkout that normalizes them needs a fresh run identity.

## Approved population and its limitation

Source inspection disproved the original four-family overall-creativity proposal. The user explicitly chose **Metaphors only, preserving overall creativity, 24 groups from 46 eligible groups**, before selection. The prior definition 0.4 remains archived. No evaluator outcome prompted this revision.

| Item | Frozen value |
|---|---|
| Dataset | CNCL-Penn-State/MuCE, revision `a02181e394c41602a95d0678b0ce9d880e994289` |
| Data read | `full_agreement/train` only, 16,948 original rows; no other data split opened |
| Construct/family | Literal `creativity`, Metaphors; 978 source rows before eligibility/exposure filtering |
| Eligibility | Same complete source/task/rating context, distinct nonempty responses, documented human score gap >=5 on 10–50 scale |
| Available groups | 46 after excluding one exposed example group |
| Selected groups | 24 unique source/effective prompt groups, one pair each |
| Split | 12 calibration / 12 audit; prompt-disjoint |
| Presentations | Both orders per pair; 24 calibration + 24 audit |
| Seed | 20261024; stable hashed group/pair/split/order selection |
| Manifest SHA-256 | `45f5fabb5d284bf87a5e90614e1b6a559ceb8beec71ef7e8299de79b5d7bdc20` |
| Pair/worklist SHA-256 | `3137768e71936f75b091064b88d2068484c2bfd5d247ff8ee900c40c85bfa908` / `ba82f50d7964318b63a1bbdc891cc6fc39e525a12536632f07f75c70d45e536e` |

Preparation necessarily read source ratings to form eligible pairs. Revalidation hashed separate label files without displaying or interpreting their winners. Audit winners have not been inspected for tuning or reported afterward. The critic inputs contain no ratings, source names or preferred identity. All selected groups are excluded from later method confirmation.

This can screen a **Metaphors pairwise evaluator**, not establish general creativity validity, quality judgments over new LLM outputs, absolute CrPO dimensions or whole-portfolio scores. Public-data pretraining contamination cannot be excluded. Individual rater reliability is unavailable. The dataset card declares MIT, but row-to-original-source license/provenance details were not independently re-audited; see the source notes.

## Exact evaluator and cost proposal

Use first-party Anthropic at `https://api.anthropic.com`, exact model `claude-sonnet-5-5`, medium effort, adaptive thinking, `service_tier=standard_only` and explicit `inference_geo=global`. Each independent request has one system rubric and one user JSON object with `prompt`, `A` and `B`; no tools, history or earlier judgments. Output is JSON `{"choice":"A|B|tie|abstain","reason":"short explanation"}`. Unknown/malformed/refused/truncated outcomes retain explicit statuses.

The exact initial rubric SHA-256 is `892e9656c07b6f08c26b8902732f911e6d57d87e1a03bed32916a750b518591a`. The complete first calibration request is saved locally at `runs/phase1-live-r05/controls/first-request.json`; its canonical hash is `78f9df853836eb2685da39493e319a8af1f647c7ac1e2b9c4f609f70e2c613f3`. Preview wrote this artifact without contacting the provider.

The existing immutable Linux/amd64 image is `sha256:585a5539c6091592258ec19d0bf8e216b189405f95766b167df0d2e88e251366`, Python 3.12.15, Anthropic SDK 1.4.0. Its default API version is 2023-06-01. SDK argument support was checked offline; actual provider/account/control compatibility remains unverified. No dependency installation or new runtime image was needed. Parquet conversion used already-installed host PyArrow 24.0.0/Python 3.13.12; the core selector and evaluator use the supported container runtime.

| Envelope | Value |
|---|---|
| First readiness checkpoint | First calibration pair in both orders: 2 presentations, included in the 48 |
| Planned judgments | 48, with at most four explicitly unaccepted transient retries; 52 attempts maximum |
| Per request | <=8,000 counted input tokens; <=2,048 output tokens including thinking |
| Per-attempt reservation | 36,480 micro-USD = $0.03648 |
| First two maximum reservations | $0.07296 |
| Illustrative 48-judgment spend | $0.45–$1.37 |
| All 52 attempts at token-price maxima | $1.89696, conditional on the declared tariff/usage bounds |
| Proposed authorization | **$5 total including unresolved reservations; not yet authorized** |

Pricing was rechecked against [official model documentation](https://platform.claude.com/docs/en/models/sonnet-5-5/overview) and [pricing](https://platform.claude.com/docs/en/about-claude/pricing): $2/$10 per million input/output tokens. This excludes tax, account funding minima and operator time. A free count endpoint checks exact request content before generation; actual usage is checked afterward. Counted/server token agreement and live billing remain assumptions until observed. Unknown liabilities are retained and stop dispatch, rather than being written off.

## Readiness, audit and replay gates

The first live command stops at two calibration presentations. Before continuing, inspect actual returned model identity, supported controls, valid parsing, token count/usage, request IDs, reservation/accounting and immutable recovery. A readiness record binds those two saved judgments. SDK retries are disabled. Official HTTP error documentation does not prove zero charge for 429/529; this transport conservatively stops and reserves on every live HTTP error. No automatic live retry is enabled.

After 24 calibration presentations, open calibration labels for diagnostics. Keep or make at most one wording revision to the rubric; do not change model/settings or rerun calibration. Freeze that final rubric with calibration evidence before any audit inference. All 24 audit predictions must be saved and committed before analysis opens audit labels. Recompute reports offline without sending requests.

Audit floors remain **>=9/12 prompts with both orders human-correct**, and **>=11/12 prompts choosing the same underlying response in both decisive orders**. Ties, abstentions, refusals, malformed/missing outcomes earn zero in the fixed denominators. Report Wilson intervals, coverage, presentation preferences, length patterns, failures and total journal accounting. Calibration results do not count as audit evidence.

The launcher enforces a pinned image, read-only code, a single writable output root, resource limits and redacted evidence. Offline execution uses network `none` and no provider credential. Future live execution mounts only `src` and the staged evaluator run; home, raw dataset and held-out label files are absent. It accepts only explicitly supplied `ANTHROPIC_API_KEY`, without home-file discovery or ambient proxy/provider settings. No key was read during preparation. OS-level provider-domain egress restriction is not claimed. Live standard-output/error content is suppressed and hashed; provider requests/results remain in the run journal with no key/authorization headers.

## Verification and acceptance status

**All 98 project tests pass**, including **55 Phase 1 tests**: 15 pair-contract/analysis, 11 MuCE preparation, 21 runner/accounting and 8 workflow tests. They include a complete synthetic 12/12 run, no-call replay of both stages after completion, label gates, source/hash corruption, effective-prompt alias leakage, fixed denominators, concurrency, count limits, all-attempt ceilings, stale freeze and unresolved-delivery recovery. Runnable PowerShell launcher checks pass, including prohibited arguments/paths, a contained synthetic workflow and recorded mount/network/credential properties. Ruff, mypy, Bandit medium/high, dependency consistency and five unchanged upstream tests also pass. The full suite took 559.468 seconds on the supported runtime.

See the retained [full regression runtime](../../../evidence/phase1/full-test-runtime.json), [Phase 1 test runtime](../../../evidence/phase1/phase1-test-runtime.json), [static checks](../../../evidence/phase1/static-check-runtime.json), [preparation runtime](../../../evidence/phase1/preparation-runtime.json), [staging runtime](../../../evidence/phase1/staging-runtime.json), [preview runtime](../../../evidence/phase1/preview-runtime.json) and [verification summary](../../../evidence/phase1/verification.json). The full command records and synthetic artifacts remain under `runs/runtime-phase1` and the launcher fixture namespace. Raw human responses/labels are not copied into the versioned evidence directory.

| Requirement | Current status |
|---|---|
| P1-1 frozen population | Offline evidence ready |
| P1-2 usable evaluator | Software/fixture route ready; live route unverified |
| P1-3 actual critic readiness | Pending first 2 authorized calibration calls |
| P1-4 complete real accounting | Pending real execution; controls checked with synthetic transports |
| P1-5 audit calculation | Fixed calculation tested; no real audit predictions/results yet |
| P1-6 replay/boundaries | Offline checks pass; live limitations stated |
| P1-7 scientific decision report | Pending calibration/audit; this is a preparation report |
| P1-8 preserved scope | Original project, Phase 0 source/evidence and upstreams preserved |

## Commands and the next decision

From the new project root:

```powershell
.\phase1.ps1 test
pwsh -NoProfile -File tests/test_phase1_launcher.ps1
.\phase1.ps1 offline fixture --output /results/phase1-fixture
.\phase1.ps1 offline prepare --source /results/phase1-source/muce-full_agreement-train.canonical.jsonl --metadata /results/phase1-source/conversion.json --output /results/phase1-prepared
.\phase1.ps1 offline stage --prepared /results/phase1-prepared --output /results/phase1-live-r05
.\phase1.ps1 offline preview --run /results/phase1-live-r05
```

Reuse is idempotent only with unchanged code/image/inputs; otherwise choose a fresh run namespace. Raw source download is a public preparation operation, distinct from network-disabled evaluator execution. Its exact URL/hash is retained in the conversion metadata.

**Future commands below require authorization and an explicitly supplied provider key. They were not executed.** The cap shown is the proposed $5, expressed as micro-USD:

```powershell
.\phase1.ps1 live -Live -LiveRun phase1-live-r05 judge --run /results --stage calibration --cap-micro-usd 5000000
# Inspect the first two saved results/accounting before recording an actual review:
.\phase1.ps1 offline inspect --run /results/phase1-live-r05
.\phase1.ps1 offline readiness-review --run /results/phase1-live-r05 --decision "Record the observed controls, usage and readiness decision here."
.\phase1.ps1 live -Live -LiveRun phase1-live-r05 judge --run /results --stage calibration --cap-micro-usd 5000000
.\phase1.ps1 offline analyze --prepared /results/phase1-prepared --run /results/phase1-live-r05 --stage calibration
# Choose the retained or once-revised rubric after calibration, then freeze it:
.\phase1.ps1 offline freeze-audit --run /results/phase1-live-r05 --rubric /results/phase1-live-r05/initial-rubric.md --decision "Record the calibration-based rubric decision here."
.\phase1.ps1 live -Live -LiveRun phase1-live-r05 judge --run /results --stage audit --cap-micro-usd 5000000
.\phase1.ps1 offline analyze --prepared /results/phase1-prepared --run /results/phase1-live-r05 --stage audit
```

Do not edit `initial-rubric.md`: it is bound by the original bundle. If calibration warrants the one permitted wording revision, save a separate `controls/final-rubric.md` and supply that path to `freeze-audit`; the final text is then retained in the freeze record. Stage reports keep their own accounting; the audit report also includes full-phase totals, so replaying calibration after audit does not change its saved report.

Review the frozen population, rubric/profile and controls, then approve a ceiling or request a bounded correction. The specification explicitly requires this checkpoint review before paid launch. If authorized, use the first two already-planned calibration presentations for readiness, inspect them, and continue only if the actual path satisfies the controls. No extra canary study, strategy experiment or Phase 2 work is implied.
