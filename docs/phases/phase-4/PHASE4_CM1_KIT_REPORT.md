# P4-CM1 execution kit — offline accepted, frame certified

8 November 2026. **Offline acceptance, controlled eligibility intake and production provider preflight are complete. The accepted study is ready for fresh masked keys.** P4-CM1 has made zero paid provider calls and used no real provider credentials. Development cost qualification, confirmation generation and scientific assessment have not started. The [acceptance summary](../../../evidence/phase4-cm1-v1/offline-acceptance-v1.json) is the primary preparation record.

## Objective and frozen comparison

The [approved definition](PHASE4_COST_MATCHED_CONFIRMATION_DEFINITION.md) tests whether actual native Harness² two-round adaptation improves on a fixed strategy at approximately matched actual inference spending. The frozen confirmation sample contains 24 eligible WildChat prompt units.

| Component | Configuration |
|---|---|
| Adaptive procedure | Actual pinned Harness² `seq,k=2`: eight solver portfolios, six author stages and a blind choice between `c1` and `c2`. |
| Fixed control | Unchanged planning, ten-answer generation and ranking; twelve candidates per complete pool. Stop at the first completed pool boundary reaching 90% of settled adaptive inference cost, or eight pools. If multiple pools finish, choose blindly among their winners. All selection and overshoot costs count. |
| Models and protocol | Sonnet 5.5 at low reasoning for generation; Opus 5 at high effort with adaptive thinking for authors/selectors; unchanged pinned NoveltyBench v1.1 grouping and quality judges. Exact settings remain in the definition and [billing record](../../../evidence/phase4-cm1-v1/public-billing-v1.json). |
| Assessment | Preserve official results for fixed, `c1` and `c2`. Add two frozen grouping permutations and complete quality coverage, reusing official head judgments: at most 39 assessment requests per prompt unit. |
| Analysis | Paired utility is primary; distinctness is a required companion. Report quality, order, selection, actual edits/KEEP, sampling, losses, missingness and all costs. No favorable-subset selection or automatic repeat. |

This compares complete procedures under the declared cost rule. It does not isolate the causal effect of recursive edits, establish external originality or guarantee cost parity. The [reporting contract](../../RESEARCH_METHOD.md#required-contents-of-every-future-report) applies to positive, negative and inconclusive findings.

## Accepted engineering evidence

The accepted execution study is `13b9273ca9e0f7bd79d98cb8013429753cebe6341919c006a32e2fd67236f421`, with 207 effective inputs under source `618834cb1d4c0ce9bfd3edbe71aa0225c7a949b0a2b6fd1a4b00dbef529155e7`. Harness², NoveltyBench, their algorithms and their [pinned revisions](../../../upstreams.lock.json) remain unchanged.

| Evidence | Observed result |
|---|---|
| [Final collector](../../../evidence/phase4-cm1-v1/acceptance-collection-v1.json) and [independent offline review](../../../evidence/phase4-cm1-v1/independent-offline-review-v1.json) | 106 unique passing tests, all 16 mandatory regressions, no failures/errors/skips; all 207 effective inputs unchanged. The separate [code review](../../../evidence/phase4-cm1-v1/code-review-v1.json) retains its earlier code-only scope. |
| [Actual native journey](../../../evidence/phase4-cm1-v1/native-journey-v1.json) | Actual Bun/OpenCode and native `seq,k=2`: eight rollouts, six author stages, blind selection, 347 mocked SDK requests and 39 assessment requests. Separate generation/assessment child identities, zero held liability and zero-resend saved replay passed. This is one synthetic engineering unit, not scientific confirmation. Fixed usage was deliberately mocked to finish one complete control pool; it is not cost-matching evidence. |
| Passive Inspect exports: [native journey](../../../evidence/phase4-cm1-v1/inspect-native-journey-v1.json) and [missing case v2](../../../evidence/phase4-cm1-v1/inspect-missing-case-v2.json) | Both roundtrips passed with zero model/network attempts. The native view preserves 347 imported fixture events; the missing case preserves null native dates and empty usage/events. Export observation times are separate. No model/tool activity graph was fabricated. |
| [Final static checks](../../../evidence/phase4-cm1-v1/static-checks-v1.json) | Ruff, Mypy and Bandit passed on unchanged source. |
| [Windows pre-credential check](../../../evidence/phase4-cm1-v1/windows-precredential-v1.json) and [production preflight](../../../evidence/phase4-cm1-v1/provider-preflight-v1.json) | The actual Windows handoff and accepted production admission path passed without credentials or provider calls. Live credential validity and provider behavior remain untested. |
| [Public compatibility](../../../evidence/phase4-cm1-v1/public-compatibility-v1.json) | 89 passing tests across 14 explicit P4 modules, zero failures/errors/skips, plus passing Ruff/Mypy/Bandit. The long native journey was explicitly excluded from this second check. Its own 207-input public source identity is `4cfc3f4f8d1c6070bed7845303cc5c6bc278171f9da9c22b05d2da63ee354291`; three disclosed source projections distinguish it from the accepted execution source. |

The [P4 controller](../../../followups/phase4_cm1_v1/workflow.py) reuses the existing native execution, controlled transport, immutable accounting journal, Windows credential handoff and passive Inspect path. Serial child allocations, complete-pool fixed search, generation-before-grading, supplemental assessment and saved-result reporting implement this comparison. Producer-derived limits cover request admission, journal events, worker frames and native context/artifact readers. Valid partial checkpoints survive known incomplete runs without invented selection or authenticity claims.

These are local verification results. No repository GitHub Actions workflow is configured, so no remote-CI-green result is claimed. Public preparation computes its own source identity; copied acceptance evidence does not relabel a different source checkout as the frozen execution study.

## Certified frame and budget

[Controlled intake](../../../evidence/phase4-cm1-v1/controlled-intake-v1.json) verified 1,000 source rows and 1,000 unique prompt units, excluded 263 known-exposed units, certified **737 eligible units**, and fixed **24 selections** by the prespecified hash rule. No task text was printed. The [frozen manifest](../../../evidence/phase4-cm1-v1/eligibility-manifest-v1.json) and [eligibility report](PHASE4_CM1_ELIGIBILITY_REPORT.md) preserve the scope and limits. Recorded project exposure coverage is established; semantic independence, unrecorded exposure and pretraining freshness are not proven.

The approved ceiling remains **$1,200**: $100 for exactly two exposed fixed-only cost qualifications, $850 confirmation inference and $250 assessment. Each inference cell has a $75 ceiling nested inside its allocation and the total; the finite worklist allows at most **40,914 admissions**. These are overlapping limits, not guaranteed spending. Historical $22.88 held liability remains separate and unreleased.

## Next step

After publication of the reviewed kit, request fresh masked keys and execute the already-approved block under its dedicated supervisor. First run the two exposed fixed-only cost qualifications. Only if they pass may the frozen 24-prompt confirmation proceed, followed by native assessment, prespecified sensitivity analysis and closure. No further funding approval is needed within the authorized scope and caps.

No new framework, model training, evaluator calibration study or added benchmark is included. Preserve official partitions, all sampled cases and costs. Unfavorable results, matching misses, valid KEEP decisions and diagnostic read gaps remain reportable; financial, provenance and unresolved-delivery guards still apply. Failed gates do not authorize hidden repeats or method changes.
