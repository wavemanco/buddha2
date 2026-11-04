# P3B-RA1 — Release acceptance stopped before candidate admission

Date: 2026-11-03 Pacific / 2026-11-04 UTC.

**The offline release kit is not accepted.** Current-source component checks passed, but the first complete Linux unit-preflight attempt failed at the original spawned-worker bootstrap check. Four tests started: three passed, one failed, zero errored; 122 of the 126 declared methods were not reached. No Windows set, release candidate, main campaign, supervised S13, saved replay or extracted replay started. Real API spend was **$0**.

The [RA1 definition](PHASE3B_RELEASE_ACCEPTANCE_DEFINITION.md) and [direct authority](../../../evidence/phase3b-ra1-v1/authority.json) required a complete independently accepted kit. This stopped outcome does not satisfy that objective. The [outcome](../../../evidence/phase3b-ra1-v1/outcome-v1.json), [dossier](../../../evidence/phase3b-ra1-v1/dossier-index-v1.json) and [retained-product runbook](PHASE3B_RA1_RUNBOOK.md) identify the useful work and the remaining gap.

## What was built and checked

RA1 connected the existing unfrozen release seams: a new source-bound configuration and authority, separate counters and effort accounting, guarded unit-only entry, typed post-collector diagnostic capture, candidate operator, versioned packet destinations and read-only accepted-packet resolver. Existing Harness², benchmark, model, strategy, scientific-method and frozen runtime controls were retained. The earlier OR1 and BD1 execution allowances were not reopened.

The current component invocation, `ra1-component-v3`, passed five new pure RA1 regressions, actual Windows executable/argument propagation and direct-script import checks, actual contained read-only/exclusive-write and runtime-path checks, and all three affected Ruff/Mypy/Bandit commands. The component had fresh isolated writable runtime storage, a read-only project mount, no network and no model worklist or positive bootstrap call. These are component results, not the twelve-group release gate.

Preparatory failures remain visible:

- A sibling file initially named `operator.py` shadowed Python's standard-library module during effort-script startup. It was renamed `ra1_operator.py`, with an actual direct-script regression.
- The first component container was rejected before start because a guessed environment-name allowlist omitted legitimate variables from the pinned H1 image. Its owner was removed; a read-only name-only image diagnostic supported the versioned correction.
- The next component passed its five pure regressions but failed Ruff, Mypy and Bandit on concrete type/import/format findings. Versioned repairs preserved those diagnostics and every prior plan. The active observer plan is v2: it has a new explicitly pinned worker hash and a narrow independently reviewed AST-delta proof. It is **not** described as byte-identical to the earlier worker. No static check was skipped or ignored.

The current-source unit manifest then reconciled all 121 existing method IDs plus five new RA1 methods. Independent prospective review verified all 760 ordinary source hashes, the reconstructed 774-member source identity and the 24 unchanged A0 controls before admitting the first unit set.

## Actual preflight failure

Source identity: `1bc052cbcdd1223e7c88bafc109b87fb754209c7acb836848dfb95a92d9e93f2`.

The failed method was `BootstrapTests.test_fresh_spawned_core_worker_uses_the_same_import_boundary`. Its [saved result](../../../evidence/phase3b-ra1-v1/preflight-failure-v1.json) records:

| Field | Actual observation |
| --- | --- |
| Canonical status / error | `failed` / `canonical_timeout` |
| Report / visibility | `unavailable` / `failed` |
| Worker stopped / cleanup proof | `true` / `stopped` |
| Current preflight coverage | Four started; one failure; zero errors; 122 unrun |

The unchanged test gives the collector a **four-second total deadline and reserves one second for cleanup**, leaving approximately three seconds for receiving an accepted frame. No accepted frame arrived before that cutoff. This does not establish that the whole worker took more than four seconds or identify which spawn/import/guard/IPC stage consumed the interval.

Independent source tracing found no specific evidenced eligible correction. The post-collector capture executes after collection returns; moving entry imports alone was not demonstrated to repair the failure. There was no profiling, warm-up, clock extension, skipped assertion or same-source retry.

The [independent failure review](../../../evidence/phase3b-ra1-v1/reviews/unit-suite-1-failure-review-v1.json) confirmed the failure, source preservation, frozen controls and exact-owner absence. The failed container was `4f358b12e63435b06e1bc1fbc40e23b6005f412839583d60fb616d082c22dfe5`; removal and explicit independent “no such object” observations prove its absence. Component owners were also settled.

## Counters, preservation and limitations

| Admission | Consumed / allowed |
| --- | --- |
| Pre-freeze unit/Windows sets | **1 / 3**, consumed at Linux admission; no matching Windows invocation |
| Release candidates | **0 / 2** |
| Main campaigns | **0 / 2** |
| Supervised S13 starts | **0 / 2** |
| Saved replays | **0 / 2** |
| Extracted cold replays | **0 / 2** |

Unused allowances do not permit an unexplained retry. RA1's explicit stop rule applies when a timing/test failure has no specific evidenced eligible correction. No accepted gate, archive, packet receipt, launcher packet-resolution success, live grant activation or scientific comparison resulted.

The failed revision's 760 ordinary source files were copied to a new local preservation capture after every current hash was reconciled. The fourteen canonical historical offline stream entries were authenticated by their pinned classification receipt and retained as hashes; capture did not open or copy their contents. The [independent preservation review](../../../evidence/phase3b-ra1-v1/reviews/failure-preservation-metadata-review-v1.json) checked the capture metadata against the unit manifest and independently rehashed current ordinary source. It explicitly does not claim to have reread the retained capture tree. Historical evidence remains unchanged.

BD1's two unprofiled diagnostic timeouts, profiled pass and later complete unprofiled suite pass remain historical evidence. RA1's additional timeout does not establish their cause, a causal repair, a failure rate or general live reliability. No held-out material, human ratings, credentials or paid provider activity were used.

The engineering plan is about four aggregate focused hours with at least 45 minutes reserved for closure, a review target rather than a seconds-level abort. The stop was caused by the acceptance rule above, **not engineering-time overage**. The append-only accounting retains the 180-second bootstrap charge and 40-second conservative transition charge; the parent closure accounting and publication receipts govern final effort rather than this interim report.

**Next:** make a concrete diagnostic or control-continuation decision that preserves this failed invocation and states what new evidence would justify another admission. No such new experiment or changed clock is supplied by this report. The accepted-kit objective remains unachieved; a paid Phase 3B pilot remains downstream of full acceptance.
