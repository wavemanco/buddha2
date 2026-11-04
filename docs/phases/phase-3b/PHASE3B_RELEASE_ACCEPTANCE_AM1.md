# P3B-RA1-AM1 — Bootstrap test contract and complete acceptance resumption

Version 1.0 — 2026-11-03, America/Los_Angeles.

**Status: proposed, not approved or implemented.** This document supplies no permission for another run or code change. Its proposed authorization covers the complete remaining [RA1 block](PHASE3B_RELEASE_ACCEPTANCE_DEFINITION.md), including independent acceptance and publication, rather than a test-only milestone. The accepted-kit objective is unchanged and remains unachieved.

## Objective and reason for the change

Give the single positive cold-start functional/privacy test a declared, bounded **30-second total allowance with one second reserved for cleanup**. Then execute complete release acceptance under the remaining RA1 allowances. Keep its real spawned worker, real imports, all three assertions and unchanged production controls.

RA1's first current-source Linux set failed: source `1bc052cbcdd1223e7c88bafc109b87fb754209c7acb836848dfb95a92d9e93f2`, four tests started, one failed, zero errored and 122 unrun. The typed result was `canonical_timeout`; the worker stopped and its exact container was removed. [Independent review](../../../evidence/phase3b-ra1-v1/reviews/unit-suite-1-failure-review-v1.json) confirms the failure. No specific slow import or causal repair is established.

The current test passes `deadline=now+4, cleanup=1` to the frozen collector. Its frame-receipt window is therefore approximately three seconds. The production [visibility checkpoint](../../../followups/phase3b_seq2_v1/workflow.py) uses a 600-second total with the collector's default 15-second cleanup reserve. The unit failure does not establish failure of that production window.

Static inventory identifies exactly one positive cold `core_view.collect` call in the current 126-case S2 suite: `BootstrapTests.test_fresh_spawned_core_worker_uses_the_same_import_boundary`. Its three assertions check worker cleanup, canonical completion and one private-dotenv access denial. It has no separate elapsed-time assertion. Historical packages' tests are outside this current discovery and remain untouched.

**This openly changes an acceptance requirement.** The new pass would establish the functional/privacy behavior under a 30-second total, not satisfy the old three-second receipt condition. Thirty seconds is a prospectively chosen functional-fixture allowance, not an empirically estimated percentile or a proven reliability bound. Preserve BD1's uncertainty and the failed RA1 invocation in every resulting report. Do not claim a performance improvement or identify a historical cause from a later pass.

## Scope and deliverables

1. Record explicit user approval, this amendment's raw hash and its original RA1 parent. Preserve the original definition, authority, failed source and receipts. Bind the amended requirement into the new effective source and prospective review.
2. Change only the current positive bootstrap test's total allowance from four to thirty seconds, retaining the one-second cleanup argument and the same three assertions. Leave all production code, timeout/IPC negative tests, historical test packages and the 24 A0 frozen controls byte-identical.
3. Pass affected current-source Ruff, Mypy and Bandit checks. Freeze and independently review the complete 126-ID unprofiled preflight. The next Linux admission is **set 2 of 3**, followed by its actual matching Windows cases only if Linux passes. No standalone positive bootstrap run, import profiling, warm-up or same-source retry is included.
4. If preflight passes, freeze and admit the current release candidate, then complete every remaining original RA1 requirement: main and separate supervised S13 worklists, saved replay, all twelve current groups, both real SDK-free I1 export handshakes, independent source/gate acceptance, actual archive/manifest/index acceptance, extracted-only cold replay, read-only accepted-packet resolver proof, runbook, accounting and reviewed publication.
5. Deliver the original accepted offline kit and handoff if all requirements pass. Otherwise preserve the exact failed/missing requirements in a reviewed incomplete outcome. A test pass or stopped dossier does not achieve the accepted-kit objective.

## Exclusions

No production deadline, collector, SDK guard, IPC contract, cleanup rule, upstream/runtime/dependency, scientific method, model, strategy, prompt, judge, score access or held-out population changes. No fake worker, assertion removal, skipped test, fallback, forced edit, additional recursion arm or weakened financial/containment requirement. No instrumented worker, positive diagnostic probe, repeated benchmark experiment, MuCE/CrPO work, human collection, real credentials or paid calls. Inspect remains a passive exporter/viewer.

## Completion criteria

The independently reviewed amendment diff implements only the permitted test-budget change and explicit approval/source binding. All 126 current cases must be reconciled across actual Linux and Windows execution, and all twelve groups and every original packet/replay/resolver/handoff requirement must pass for the final same-source candidate. No preflight or earlier-source pass may be retagged as its release gate. Report the amended test allocation alongside the old failed allocation.

## Cost, counters and stop rules

**API cap remains $0.** No fresh keys or paid transition, including after success. Historical liabilities remain unchanged.

Carry forward the complete existing RA1 effort ledger and conservative charges without deduction or reset. Its four-hour planning target has now been crossed: root and the earlier reviewer remained marked ACTIVE across an unobserved continuation gap, and their entire intervals are retained as a conservative upper bound. Do not describe that arithmetic as precisely measured focused work or claim the original milestone reviews were met. The [reconciliation](../../../evidence/phase3b-ra1-v1/effort-continuation-reconciliation-v1.json) records the limitation.

This proposal therefore also requests a **fresh prospective continuation target of two aggregate focused engineering hours**, including at least **45 minutes for closure**, on top of the retained historical total. This is an explicit material continuation decision, not restoration of the original unused target. Review at 60 and 90 additional focused minutes, at the two-hour target and before expensive admissions; stop new admissions if more than roughly 45 further focused minutes or an unsupported expensive attempt is required. Negligible finishing overruns remain accounting notes. Automated waits may take many elapsed hours. Use actual per-actor transitions, conservatively charge uncertain intervals, and settle missing actors with an explicit host attestation. The target remains a review policy, not a seconds-level abort; all financial/runtime/counter stops remain hard.

At proposal time, one of three preflight sets is consumed; candidate, main, S13, saved and cold counts are all zero. Maximum totals remain **three preflight sets, two candidates, two main entries, two S13 starts, two saved replays and two extracted cold runs**, with the original per-candidate restrictions. This amendment adds no repetition allowance. New source/candidate identities and all original preservation/freshness proofs remain required.

Retain every original RA1 hard stop except the explicitly amended positive unit-test budget. If the amended bootstrap times out, preserve the failure; no further clock increase or unchanged retry follows under AM1. Another remaining set requires a specific evidenced eligible correction under the unchanged recovery rules. A required production/frozen-control change or an exhausted/infeasible complete path stops admissions for a new decision. Success stops after the first fully accepted kit. No outcome automatically starts the paid Phase 3B pilot.
