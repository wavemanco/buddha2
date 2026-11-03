# P2-R — Complete Phase 2B Execution Kit

Frozen implementation scope: specification **0.18**, `PRE_PHASE2B_BLOCK.md`. The user goal **“complete P2-R”** authorized the entire offline block. Phase 2B, paid calls, real credentials and real human collection remain unauthorized/unstarted.

**P2-R is complete under frozen 0.18, closed in specification 0.19.** All R-1…R-9 requirements are covered by the [acceptance checklist](../../../evidence/phase2-release-r018/REQUIREMENTS.md) and [independent peer acceptance](../../../evidence/phase2-release-r018/independent-acceptance.json). The source-bound [release gate](../../../runs/phase2-release-r018/release/release-readiness.json) binds their exact evidence. This completes the offline execution kit, not the live Phase 2B experiment.

## Usable kit

The new `phase2-release` command and `phase2-release.ps1` implement the whole unchanged pilot: preparation, inspected nonsending preflight, counted first-block execution, review, cumulative expansion, exact resume, native reporting/replay and optional late-human attachment. [The runbook](PHASE2B_RUNBOOK.md) contains the operator sequence. Ordinary `phase0.ps1` commands remain offline; the separate provider mode requires explicit live authority and masked operator input after checked readiness.

The study contains all 24 blocks, 72 ordered native assessments and at most 1,320 request slots from the outset. One canonical journal holds the first block and all remaining work. Immutable study/budget policy and append-only grants/reviews are separate. A grant identifies the actual active or next authority; replaying an older grant cannot misdescribe a later allowance. A same-ID identical grant adds no credit, and changed/conflicting authority is refused.

Requests publish a durable intent before transport. Missing or ambiguous usage retains the reservation and stops. The runner does not retry, replace, repair or fall back. Budget stops preserve a usable partial report; failure records retain distinct attempt-prefix/authority contexts. The host holds a canonical launch-owner lock before credential readiness, inspects actual Docker configuration and attempts a bounded stop of only its verified owned containers on interruption. Force-kill and provider billing uncertainty remain explicit recovery limits.

## Scientific design preserved

The AM-1 parent, 12 development prompts, two repeats, A/B/C procedures, templates, five profiles, native NoveltyBench v1.1 construction/arithmetic, source pins and dependency locks are unchanged. A is independent base sampling, B is the fixed planner/generator and C is an exact B permutation chosen by the frozen reranker. The primary contrasts remain B−A and C−B. C's candidate cost includes its B parent, while the phase ledger charges each request once.

This block adds execution/recovery machinery, not recursive adaptation. Authentic Harness² one-step and successive recursive improvement remain separately defined later phases. CrPO/MuCE evaluator work stays deferred; Route H and fresh-output human review remain optional. Complete benchmark evidence can conclude without human readers, and later human forms create separate decisions without rewriting the benchmark root.

## Evidence and limitations

The delivered [study](../../../runs/phase2-release-r018/release/study.json) is `38132ee3a935af4ac975c3fda84154d1a85b1bcb510925f409993a15d3103d8b`. Its 26-file source digest is `5909e90bc49a3251ba431c8ccf677cdc02a2827f36271d9b0abed3a5421ef22c`; the host launcher is `489e7df6edf0bbd610e60c99b5bd6a17b38c78bd86d97cd58fed2bff02e4c479`. The AM-1 admission/accounting control remains `159448f1025bdd60c5ed84ea524a7c9b4e73d2acb49def5081394736c39d339a`; the new budget policy and launcher are separately bound into the new release/study, rather than changing that reused control's identity. The image remains `sha256:585a5539c6091592258ec19d0bf8e216b189405f95766b167df0d2e88e251366`.

All **271 project tests passed** in 929.806 seconds on this source, as did **five upstream checks**, Ruff, mypy across 26 package files, Bandit and dependency compatibility checks. [Full-suite evidence](../../../evidence/phase2-release-r018/runtime/full-suite.json) and [static/upstream evidence](../../../evidence/phase2-release-r018/runtime/final-static-checks.json) retain exact containment and outputs. A single Bandit B108 annotation covers the declarative, bounded `/tmp` mount literal; no global security check was disabled.

The [host integration](../../../evidence/phase2-release-r018/launcher-host-integration.json) proves first55, identical zero-call resume, actual image/mount/environment inspection, provider-configuration creation without startup, invalid-grant rejection before keys and bounded owned-container stop. The [first report](../../../runs/phase2-release-r018/reports/first/PHASE2_REPORT.md) retains three assessments/69 missing, null full-study means and an inconclusive decision. [Unreviewed expansion](../../../evidence/phase2-release-r018/runtime/unreviewed-expansion-rejected.json) correctly exits with an authority error. Neither a completed process nor fixture approval selects a real seed.

Historical r010 replay under retained r012 source reproduced the closed benchmark decision; retained AM-1 source resumed its old first block with zero new HTTP calls. Current source correctly rejects the old AM-1 identity. [Historical r010](../../../evidence/phase2-release-r018/runtime/historical-r010-replay.json), [AM-1 resume](../../../evidence/phase2-release-r018/runtime/historical-am1-resume.json) and [strict rejection](../../../evidence/phase2-release-r018/runtime/current-source-historical-rejected.json) provide the separate evidence. No historical compatibility guard was weakened.

The full inspected host rehearsal completed **24 blocks/72 portfolios/72 native assessments/1,320 requests**, with **1,265 new requests at expansion** and zero on unchanged full resume. The snapshot remained `90594f24458f937a0e061ba022059d2bba6e04dacc4e176805e24d8ed2a97fe3`; the benchmark decision remained `e90fa9c8ec55313ae022e5c438d821fec4107a6ddbae14bdebe83c31259b14f1`. [Independent full verification](../../../runs/phase2-release-r018/full-verification.json) confirmed byte-identical public reports, exact native/coverage/analysis/decision replay, the unchanged first55 prefix, two cumulative grants in one journal and independently priced settlement. It forbade SDK, socket and dispatcher construction during replay; none occurred.

| Actual synthetic requests | Count |
|---|---:|
| Answers | 480 |
| Plans | 24 |
| Rankings | 24 |
| Native grouping | 72 |
| Native quality heads | 720 |

All 1,320 slots were `ok`; all 72 orders were `scored`; unresolved reservation was zero. The fixture ledger sums to **1,028,952 micro-USD**, a fabricated usage/accounting exercise, while actual API spend was **$0**. The [full benchmark report](../../../runs/phase2-release-r018/reports/full/PHASE2_REPORT.md) and [public replay](../../../runs/phase2-release-r018/reports/replay/PHASE2_REPORT.md) conclude only for synthetic software evidence. Their synthetic A selection is not a real seed or a result about the strategies. Runner tests additionally exercised the five-group partition: 40 requests and 15 correctly undispatched nonheads.

The [late-human public-command rehearsal](../../../runs/phase2-release-r018/late-human-rehearsal/PASS.json) passed with zero new requests and zero actual humans. It preserved closed-window missingness, appended the original late R2 form, retained R1 and the predecessor assessment, and created a separate compatible human decision. All **1,647 protected study/run/benchmark files** remained byte-identical; the benchmark root and native scores did not change. The deliberately fabricated concern changed only the synthetic human branch's selection, demonstrating branch separation without claiming human validity.

[Historical preservation](../../../evidence/phase2-release-r018/preservation.json) checks the 11,794-file pre-P2-R baseline. Only the six declared current documentation/CLI integration files may differ; frozen reports, source bundles, archives, run artifacts and locks remain unchanged. [Scientific/source review](../../../evidence/phase2-release-r018/scientific-preservation-review.json) separately verifies the parent fields, locks and 26-file release bundle.

The [continuation archive](../../../evidence/phase2-release-r018/p2r-execution-kit.zip), [manifest](../../../evidence/phase2-release-r018/manifest.json) and [package review](../../../evidence/phase2-release-r018/package-review.json) supply the frozen handoff. This is a continuation snapshot requiring the retained parent studies, pinned upstream checkouts and immutable installed image; it is not a standalone installer. The usable [release bundle](../../../runs/phase2-release-r018/release) and runbook are the execution kit.

Earlier failed engineering checks and superseded development candidates remain retained; they are not scientific outcomes. Docker Desktop stopped during component work and was restarted; no provider work was active. A preparation attempt during a temporary symlink tampering test was correctly rejected and subsequently succeeded after cleanup, without changing the guard.

No real provider request, token-count/auth/model-list probe, real key read, human collection or experiment/API spend belongs to this block. Actual provider account/model access, acceptance of native settings and real returned usage/billing remain unknown until the separately authorized counted first block. Mock scores and synthetic human forms establish software behavior only; they select no real seed or validated strategy.

## Money and remaining operator decisions

The [dated public-price/profile review](../../../evidence/phase2-release-r018/pricing-profile-review.json) supports unchanged AM-1 per-request reservations: answer/plan/rank $2.540960, grouping $1.661880 and quality $11.440000. The summed maximum first/full liability envelopes remain **$404.086760/$9,698.082240**. These are conservative sums, not expected spend. Serial usage settlement releases/replaces reservations; unknown usage retains its liability and halts.

The proposed **$20 first-stage/$125 cumulative** limits are unapproved stop ceilings and do not guarantee completion. A $125 cumulative grant leaves $123 after $2 settled. Actual expected live spend has not been measured by this release. The launch packet contains no paid grant or credentials.

After complete P2-R acceptance, the expected next actions are operator confirmation of the supported accounts/profile/current prices, an applicable stage grant and explicitly supplied keys; then Phase 2B's counted first block, saved review, separately granted expansion and final report using this already-built kit. No planned expansion or reporting engineering is deferred to that point. An unforeseen integration defect stops live work and is repaired/reverified within this kit's scope, with honest identity/compatibility handling.
