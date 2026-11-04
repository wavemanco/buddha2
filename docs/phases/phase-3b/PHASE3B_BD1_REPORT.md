# P3B-BD1 — Bootstrap diagnostics and unit preflight

Date: 2026-11-03 Pacific / 2026-11-04 UTC.

**Ready: unit preflight passed.** The final unprofiled Linux run tallied all 121 declared methods: 118 executed, three exact Windows-only skips, zero failures and zero errors. The three skipped cases then passed on the actual Windows host with the same development-source identity. No case remains unrun across the two platforms.

The [outcome record](../../../evidence/phase3b-bd1-v1/outcome-v1.json), [81-reference dossier](../../../evidence/phase3b-bd1-v1/final-dossier-index-v1.json), [final preservation proof](../../../evidence/phase3b-bd1-v1/final-preservation-v1.json) and [six-owner absence record](../../../evidence/phase3b-bd1-v1/final-owner-absence-v1.json) bind the evidence. The [unit-only runbook](PHASE3B_BD1_RUNBOOK.md) records the actual commands and their closed authority.

This establishes unit-preflight readiness for this revision. It does not establish the cause of the earlier timeout variability, an accepted Phase 3B release kit or an advantage from recursive adaptation. No further release campaign or paid pilot starts automatically.

## What changed

The [approved definition](PHASE3B_BOOTSTRAP_DIAGNOSTIC_DEFINITION.md) was executed under [direct authority](../../../evidence/phase3b-bd1-v1/authority.json).

- Added a unit-only phase to the existing composed entry and reused the production `verify.run_tests` path without entering capacity, a main matrix or S13.
- Retained typed, allowlisted collector results after the real collector returns, on both success and failure. All three bootstrap expectations and the four-second deadline/one-second cleanup allowance remain unchanged.
- Confined each contained invocation's writes to its own fresh BD1 runtime directory. Enforced an absolute sixty-second cleanup limit and source-path checks before metadata/content access.
- Moved the Windows writer fixture's temporary parent into the BD1 namespace, preserving its outside-runtime-root and exclusive-write checks.
- Added three regression tests for diagnostic validation and the composed entry's import boundary. Moved eager workflow imports into their existing caller functions; ordinary guard statements remain unchanged. That change did **not** resolve the second diagnostic's timeout and is not presented as a demonstrated causal repair.
- Added bounded import-time observation through Python's existing profiler. Only typed module/timing records, unmatched-line counts and stream byte counts/hashes were retained; raw profile text was not published or stored as an artifact.

Affected Ruff, Mypy and Bandit checks, plus the three pure regression checks, passed in H1 after minor typing/import-order corrections. Failed preliminary checks remain retained. Frozen controls and upstream source were not changed.

## Observed results

| Invocation | Observation | Interpretation |
| --- | --- | --- |
| Standalone diagnostic 1, unprofiled | Four tests; one failure. Collector returned `canonical_timeout`; worker stopped. | The collector's finite wait ended without an accepted result frame in this invocation. Why that happened is unresolved. |
| Standalone diagnostic 2, unprofiled after lazy-import change | Four tests; one failure. Again `canonical_timeout`; worker stopped. | The entry change was not a sufficient fix. |
| Standalone diagnostic 3, import profiling enabled | Four tests passed; canonical completion and privacy-denial count verified. | Instrumented observation only. Profiling changes execution cost, and parent/worker/resource-tracker attribution is not established. |
| Complete Linux suite 1, **unprofiled** | 121 methods tallied: 118 executed, three expected host skips; zero failures/errors. | Complete Linux-applicable unit coverage on the final source. |
| Actual Windows set 1 | All three corresponding cases passed; zero skips, failures or errors. | Completes all 121 declared method IDs on the same final source. |

Actual counters are **three standalone diagnostics, one full Linux suite and one Windows set**. Output directory ordinals also include an unadmitted preparation; they are not additional executed attempts. No second full suite, second Windows set or further standalone diagnostic was run.

The initial structured-observation gate was independently recomputed at **1,785.760421 focused seconds including the bootstrap charge**, within its 1,800-second ceiling. This was an observability milestone, not an early preflight pass.

## Limits of the conclusion

The two unprofiled failures and later unprofiled full-suite pass must all remain visible. They do not prove that the timeout is eliminated or explain the historical OR1 failure, whose inner classification was not retained. The profiling pass does not demonstrate that profiling repaired anything. Further variability is a risk for the next release decision.

The suite uses declared SDK mocks and native-component fixtures; these are not real model requests or scientific study results. No real keys, provider/account probes, API spending, new held-out material or human ratings were used. **Real API spend: $0.**

## Preservation, accounting and handoff

Baseline and failed development revisions were preserved before edits. The 24 byte-frozen controls, bootstrap expectations and clocks remain unchanged. Historical source/results and closed ledgers were not rewritten. Exact-owner cleanup, source/history preservation, case reconciliation and independent final review are part of the closure dossier.

The single engineering ceiling is **7,200 aggregate focused seconds**, including review, accounting and publication. Known uncertain intervals are conservatively charged and remain unreleased. [Closure accounting](../../../evidence/phase3b-bd1-v1/closure-accounting-v1.json) retains all 424 seconds of conservative charges, including a 30-second final-handoff charge. Its snapshot is not an exact final usage claim; final handoff verifies the original 7,200-second ceiling after publication. There is no reset or transfer from OR1.

The deliverable is a guarded unit-only command, runbook and evidence record. Closed execution records supply no permission to run it again. A future complete release acceptance still requires all twelve current-source groups, actual supervised exports, independent source/gate and physical archive review, and extracted-only replay. BD1 records cannot be retagged to replace those checks.

**Next:** define that complete release-acceptance block around the accepted unit preflight, explicitly carrying the unresolved timing variability. No such campaign or paid call has started.
