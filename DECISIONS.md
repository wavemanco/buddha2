# Phase 0 implementation decisions

Revision: 0.3 — 2026-10-24, America/Los_Angeles  
Authorization: the user has requested **Complete Phase 0**, followed by **Refresh the spec. Make sure original Buddha2 folder remains untouched.** This refresh precedes implementation. Phases 1 onward and all paid/model calls remain unauthorized.

## 1. Folder boundary

The sole project/work-output root is `C:\Users\arvik\code\research\Buddha2`. The protected original is `C:\Users\arvik\code\buddha2`. Canonical path comparison verified that these roots neither coincide nor contain one another.

Do not write, move, delete, initialize Git, install dependencies, or run project commands in the original folder. Do not copy its code, dependencies, datasets or results. Public upstream sources will be obtained independently. Do not reuse the existing legacy Buddha runtime images as the new environment.

Setup/build context must be confined to the new root. Runtime mounts must include only explicitly approved paths beneath the new root; never mount `C:\Users\arvik\code`, the user home, the original folder, the Docker socket, or host credential directories. Resolve and validate mount/output paths before invoking Docker. Reject links/path traversal that escape the new root. Capture the actual runtime mount configuration in acceptance evidence.

## 2. One supported environment

Docker Desktop's Linux engine is available on this host; use Linux/amd64 and Python 3.12.15. No WSL-specific execution path or Windows port is required.

Base image: `python:3.12-slim-bookworm@sha256:57d96f71de145a98e7ceca18ee4ade77bba4103a33a72dfaea026b23625c6bf0` (Linux/amd64 manifest). The parent image-index digest observed during refresh was `sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70`. Record the built image ID and installed package lock in the completion evidence; never rely on a mutable tag alone.

Dependency setup may access source/package registries. Fixture execution must use `--network none`, no provider credentials, a read-only code/upstream mount, a bounded temporary workspace, and writes confined to the new project's run-output directory. Test subprocess isolation as well as the parent process. Set Python bytecode output off for read-only source trees. Do not pass the host environment wholesale to the container.

## 3. Pinned upstream sources and dependency ceiling

| Upstream | Commit | License | Role |
|---|---|---|---|
| [Google Harness²](https://github.com/google-research/harness2/tree/1cfe254e8d25b15f37048c3730134686abe60335) | `1cfe254e8d25b15f37048c3730134686abe60335` | Apache-2.0 | Actual native orchestration and substrate materialization |
| [NoveltyBench](https://github.com/novelty-bench/novelty-bench/tree/64a23be6b18ec1dacc298830aab276061b6e143c) | `64a23be6b18ec1dacc298830aab276061b6e143c` | MIT | Native generation loader and utility/summary arithmetic |

Keep both source trees unchanged. Record executed import paths and before/after tracked-source integrity. Source installation/import must not modify upstream files or generate results inside their trees.

Harness²'s core has no required third-party runtime dependencies at this pin. NoveltyBench's native loader eagerly imports CPU Torch, Transformers and text-scoring libraries; preserve those native imports rather than stubbing modules or extracting/transplanting functions. No weights or datasets are needed for the selected offline functions.

The direct NoveltyBench subset is `numpy==2.2.6`, `pandas==2.3.2`, `pydantic==2.11.7`, `tqdm==4.67.1`, `openai==1.107.0`, `anthropic==1.4.0`, `sacrebleu==2.5.1`, `rouge-score==0.1.2`, `transformers==5.20.2`, and official CPU `torch==2.14.1+cpu`. Resolve/pin the transitive closure and inspect its licenses before enabling it. This is a declared CPU-only offline dependency environment, not the full upstream CUDA resolution. Do not install the entire benchmark requirements file or model-serving stack.

Security amendment during implementation: the initial upstream-version subset used Transformers 4.56.1 and CPU Torch 2.7.1. The actual audit found known Transformers vulnerabilities, and a separate underlying-version advisory query found Torch vulnerabilities hidden by the auditor's inability to identify the `+cpu` local version. Preserve [the initial audit](evidence/dependency-audit-initial.json) and [Torch query](evidence/torch-cpu-advisory-initial.json). Upgrade only those runtime dependencies to official stable releases whose current PyPI metadata has no reported vulnerabilities ([Transformers](https://pypi.org/pypi/transformers/5.20.2/json), [Torch](https://pypi.org/pypi/torch/2.14.1/json)). Rebuild the lock, inspect licenses, and rerun native compatibility and audit checks. No upstream algorithm, acceptance threshold or scientific intervention changes.

License decision before use: `tqdm==4.67.1` contains MPL-2.0-covered contributions alongside MIT code ([exact license](https://github.com/tqdm/tqdm/blob/v4.67.1/LICENCE)). Keep it unmodified and retain notices in this local research environment. The Linux base also includes standard copyleft OS utilities; retain their notices. No distribution/commercial packaging decision is made here. Flag any additional copyleft package discovered before adding it; do not silently substitute a new dependency.

The first transitive resolution additionally identifies `certifi==2026.10.23` and development-only `pathspec==1.1.1` as MPL-2.0 packages. Record the same unmodified/local-use and notice-retention decision before enabling them. The package-metadata inventory is [dependency-license-review.json](evidence/dependency-license-review.json); bundled wheel notices will also be retained/inspected after installation. PyPI metadata did not classify `mypy-extensions==1.1.0`; direct inspection of its hashed wheel confirms MIT, retained in [the wheel-license evidence](evidence/mypy-extensions-license.json). Pinned build-tool requirements are installed first; the complete lock is installed without dependency resolution or build isolation so temporary build environments cannot add unrecorded packages.

## 4. Minimal implementation shape

Use an ordinary Python package and explicit adapters, not a plugin framework:

- A command-line entry point exposing fixture demo/resume, portfolio inspection, native export/import and independent assessment.
- An artifact module handling validated records, content identities and immutable finalization using standard-library files.
- An external Harness² adapter and deterministic proposer fixture using the native scheduler/substrate contracts.
- A NoveltyBench assessment boundary invoking native loading/arithmetic in a separate process with its pinned source on the import path. A mechanical assessment is the second route.
- One strategy directory, small fixture assets and meaningful boundary/integration tests. Add setup/container files and a Windows launcher only to support the single selected Linux environment.

The command spellings and file count may follow the smallest correct implementation; all functional operations above are acceptance requirements. No generic registry, custom provider gateway, database, queue or new execution engine is needed.

## 5. Exact fixture execution boundary

Call upstream `schedule.run_task` with one synthetic task, `k=1`, `modes=('agg',)`, `pool_policy='finals'`, `library=None`, and explicit deterministic proposer **and** selector arguments. No real proposer can be constructed or used as fallback.

Use native `OpencodeSubstrate` materialization with `install_mode='workspace_config'` and a deterministic local launcher. The launcher must read the actual staged harness and produce a controlled output difference when that harness changes. Calling this fixture does not install or launch OpenCode itself.

Expected native evidence: four executor rollouts (`base1`, `inv1`, `dom1`, `agg1`), three deterministic editor/composer calls (`inv1.a1`, `dom1.a1`, `agg1.a1`) and native trivial selection. Unexpected fixture labels fail explicitly. A real selector session, reflection or provider dispatch is not expected. Preserve materialized-source hashes and native traces.

## 6. Artifact and assessment boundary

Preserve a validated task record, ordered ten-response portfolio, stable unique response IDs, effective harness files/trace references and a run manifest. Identity binds the task/configuration, every effective file including Markdown/prompts, fixture policy and upstream pins. Assessment identity additionally binds its evaluator revision, settings and evidence. No raw credentials belong in any record.

Native `generations.jsonl` contains task ID, prompt, model label `fixture-no-model` and ordered response strings. Preserve external response IDs in a companion mapping by output hash and index. Duplicate response text is valid; duplicate IDs are not. Imports must validate the mapping instead of deduplicating by text.

Protocol profile: explicitly synthetic offline NoveltyBench v1.1, patience `0.8`, ten responses. Frozen partitions/head scores are supplied externally, never generated by a fake judge and never exposed as proposer task evidence. Invoke unchanged native `load_instances`, `utility_fields` and `summarize`. Export, import and reassessment must not regenerate outputs.

The independent arithmetic oracle will include partition `[0,0,1,1,2,2,3,3,4,4]` and head scores `[9,null,8,null,7,null,6,null,5,null]`: expected distinctness `5` and utility `4.346485261239209`. Validation rejects invalid lengths, missing head scores, nonfinite/out-of-range values and incompatible/missing evidence before native arithmetic. Imported arbitrary text can receive mechanical validation; synthetic native scoring requires the frozen grading profile, exact task and ordered response-text identities, plus the matching full portfolio hash. Rebinding a supplied hash cannot assign these synthetic labels to another output. These identities check fixture compatibility, not semantic quality.

The single recovery checkpoint is after finalizing output/export/identity records and before finalizing assessments. Resumption may replay local deterministic work; it must not duplicate final records or reuse changed inputs silently. No arbitrary-crash exactly-once guarantee is promised.

## 7. Evidence and exit

The implementation must satisfy P0-1 through P0-8 in [PHASE_DEFINITIONS.md](PHASE_DEFINITIONS.md), including exercised setup/demo/inspection/export/import/assessment commands, malformed-input tests, source integrity and OS-level offline containment. Deliver the working kit, sample output/report and requirement-by-requirement evidence.

Phase 0 completion cannot be claimed from this refreshed specification, import checks or a copied native demo. Actual execution and acceptance evidence are still required. Live models, official judges, semantic quality, real provider/billing controls and recursive-improvement effectiveness remain unverified. Phase 1 does not begin automatically.
