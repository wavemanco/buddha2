# Phase 1 closeout: usable evaluator, diagnostic-only outcome

2026-10-25, America/Los_Angeles. Project: the project root.

**Phase 1 is complete. The frozen evaluator failed its held-out screen and remains diagnostic-only.** All 48 scheduled presentations completed with known usage and no retries, replacements or unresolved reservations. Usage-based API cost was **$0.112696** under the authorized $5 ceiling. This completes the declared evaluator study; it does not validate the critic for research decisions or show that any generation strategy works.

| Held-out requirement | Observed | Frozen floor | Result |
|---|---:|---:|---|
| Both response orders choose the human-higher response | **4/12 prompts (33.3%)** | 9/12 | Missed |
| Both decisive orders choose the same response identity | **8/12 prompts (66.7%)** | 11/12 | Missed |

The first proportion's 95% Wilson interval is **13.8–60.9%**; the second is **39.1–86.2%**. The independent sample is 12 audit prompts, not 24 presentations or 48 total requests. Both gates use all 12 prompts. Ties and abstentions earn zero; they are not counted as consistent merely because they recur.

## What is usable

The project now has a callable two-response evaluator, a deterministic MuCE preparation route, separate calibration/audit labels, immutable request/result accounting, an audit freeze, and offline replayable analysis. The [final rubric](../../../configs/phase1/rubric-audit.md), [model profile](../../../configs/phase1/profile.json), [audit report](../../../evidence/phase1-live/audit-report.json) and [replay verification](../../../evidence/phase1-live/replay-verification.json) preserve the actual outcome.

The pair contract preserves prompt, response identities, presentation order, input hashes, rubric/settings identities, explicit status, choice/reason and usage. It does not manufacture a ten-response portfolio or Native NoveltyBench quality score. The original fixture kit remains available separately.

From this project root, with the existing pinned Docker image, these commands inspect/recompute saved results without credentials or provider access:

```powershell
.\phase1.ps1 offline inspect --run /results/phase1-live-r05
.\phase1.ps1 offline analyze --prepared /results/phase1-prepared --run /results/phase1-live-r05 --stage calibration
.\phase1.ps1 offline analyze --prepared /results/phase1-prepared --run /results/phase1-live-r05 --stage audit
```

These commands were exercised after the paid work. Both assessment files and the complete execution tree remained byte-identical, with 48 total provider calls before and after. Their runtime records show networking disabled and no provider key forwarded. Keep the local prepared data and run journal for this replay; the versioned evidence does not include the full source dataset/private label files. Different effective code, inputs or image require a fresh run identity.

## Frozen population and access sequence

The user approved **Metaphors only, overall creativity**, before selection, after inspection showed the proposed four-family creativity quota could not be assembled. We selected 24 normalized prompt groups from 46 eligible groups, one eligible pair per group, deterministically split 12 calibration/12 audit. Each pair appeared in two inverse orders, in separate requests without the other judgment. Cross-stage normalized prompt overlap is zero. All 24 groups are reserved from subsequent method confirmation.

Source: MuCE `full_agreement/train`, revision `a02181e394c41602a95d0678b0ce9d880e994289`; Parquet SHA-256 `701ea8d6c0eeb20625d2809a96b5b377e2be22f28f0a22d1dfcafa820aa173ec`. Preparation retained source/rating context, used the frozen minimum five-point preference gap, and excluded the published Metaphors examples. See [preparation decisions](PHASE1_DECISIONS.md) and the [preparation manifest](../../../evidence/phase1/preparation-manifest.json). Source IDs repeat; identities therefore bind full score-free source/context/prompt/response content rather than treating a source ID as globally unique.

The following controls separate development from audit observation:

1. All 24 calibration presentations completed before calibration label analysis. The calibration report and review were retained.
2. The single permitted wording revision changed only the rubric's final JSON-output paragraph. Creative comparison criteria, parser, model/settings, selected data and audit floors stayed unchanged. No calibration rerun occurred. The [review](../../../evidence/phase1-live/calibration-review.json) and [freeze](../../../evidence/phase1-live/audit-freeze.json) were committed in **`56f09d9`**, before audit dispatch.
3. All 24 audit predictions were finalized and written immutably before resolving audit labels in analysis. The [prediction set](../../../evidence/phase1-live/audit-predictions.json), [pre-unseal record](../../../evidence/phase1-live/audit-pre-unseal.json) and runtime were committed in **`8e5765d`** before root invoked audit analysis. The audit assessment was absent at that checkpoint.
4. Only then did the offline analyst verify and open the separate audit labels. No further tuning, generation, replacement or model calls followed. These audit labels are now consumed for this evaluator; they cannot serve as a fresh holdout for a revised critic.

Label separation is an application/workflow boundary, not a claim that the host operator was technically incapable of reading local files. Model containers had no source-rating, calibration-label or audit-label mount. Public-data pretraining contamination cannot be ruled out.

## Readiness exception and calibration

The first two actual calls returned `ok` and `malformed`, costing $0.004754. The second response put prose before JSON; the unchanged strict parser rejected it. The original automatic gate requiring two `ok` results **did not pass**. Technical route, model controls, usage, accounting and containment were verified, and execution stopped for review.

The user explicitly approved the [documented operator readiness exception](../../../evidence/phase1-live/readiness-exception-approved.json): continue the remaining 46 scheduled presentations while retaining the malformed result as a failure, with the same parser/model/data/floors and $5 cap. The [operator review](../../../evidence/phase1-live/readiness-review.json) records this deviation. This was an explicit exception, not an automatic readiness pass. No extraction, repair, retry or replacement was made. The first-two judgment digest remains unchanged; existing write-once records preserve the original outcomes.

Full calibration returned **11 `ok`, 13 `malformed`**. All 11 decisive parsed choices matched the human reference, but coverage was only 11/24 (45.8%); that selected subset is not evidence of evaluator validation. Both-orders agreement/consistency were 3/12 each. Calibration floors were development diagnostics only.

The preplanned single wording revision reinforced that the entire response must be one JSON object and all explanation must be inside `reason`. Initial rubric SHA-256: `892e9656c07b6f08c26b8902732f911e6d57d87e1a03bed32916a750b518591a`; final: `5ef028c3c44d259b952b22e5416782406e4d041a45fe54b47483058bc1ba01f6`. Audit format validity was 24/24, but different prompt sets and no calibration rerun mean we cannot attribute that difference causally to the wording change.

## Audit detail and interpretation

All 24 audit outputs were `ok` under the frozen parser: **18 decisive, five ties, one abstention**. Nine of the 18 decisive choices matched the human reference (50% conditional agreement); decisive coverage was 75%. Correctness on both orders was 4/12, and consistency on both decisive orders was 8/12. No refusal, truncation, missing result, transport error or unknown usage occurred.

The critic chose position A 10/18 times (55.6%). It chose the longer response 17/18 times, including all nine wrong decisive choices; the remaining choice selected the shorter response correctly. Length means Unicode code points in original text. These are descriptive, dependent presentation-level diagnostics. They do not establish a causal position/length bias or show that length alone explains disagreements.

This screen measures agreement with the selected aggregate MuCE human preferences. It does not establish universal creative quality or prove every source preference is correct. The small sample, selected preference gaps, one task family, unavailable individual-rater reliability and uncertain pretraining exposure limit interpretation. No audit expansion or tuning-until-pass was attempted.

The final critic **must not be treated as a validated creativity evaluator**. If retained in later work, its judgments are explicitly diagnostic. It is not validated for absolute scores, portfolio diversity, factual correctness, CrPO novelty/surprise dimensions, Bayesian surprise, official Native NoveltyBench judging, or preferences over new model-generated responses.

## Accounting and actual runtime

| Stage | Generation requests | Input tokens | Output tokens | Usage-based cost, USD |
|---|---:|---:|---:|---:|
| Calibration, including first two | 24 | 10,435 | 3,959 | 0.060460 |
| Held-out audit | 24 | 12,093 | 2,805 | 0.052236 |
| **Total** | **48** | **22,528** | **6,764** | **0.112696** |

Cost is reported usage multiplied by the frozen first-party tariff ($2/$10 per million input/output tokens), not a provider-invoice audit. There were 48 separately logged free token-count requests, zero retries/replacements, zero unresolved reservations and no hidden SDK retries. Every count matched actual input usage; maximum observed input/output counts were 550/278, below the enforced 8,000/2,048 ceilings. Malformed calibration outputs remain paid outcomes. The ceiling included unresolved reservations; none remained at closure. Taxes, funding minima and operator time are excluded.

All 48 returned exact `claude-sonnet-5-5`. Requests used adaptive thinking, medium effort, 2,048 output-token maximum, explicit global geography and standard-only service; observed usage was global/standard with standard speed and no cache or server-tool activity. Unique provider message/request IDs are retained. Provider compatibility was exercised through installed Anthropic SDK 1.4.0 and effective API version 2023-06-01, directly to the fixed first-party endpoint.

The existing Linux/amd64 Python 3.12.15 image was `sha256:585a5539c6091592258ec19d0bf8e216b189405f95766b167df0d2e88e251366`. Live runtime records show read-only root filesystem, capabilities dropped, no-new-privileges, bounded memory/CPU/process/tmpfs, read-only `src` and only the staged run writable. No home, source data or private labels were mounted. Bridge networking allowed provider access; no domain-specific OS egress restriction is claimed. Raw live streams were not retained; sanitized evidence contains only environment names and stream hashes.

The user-requested masked PowerShell helper stored DPAPI ciphertext outside the project; it passed the plaintext key only to the child launch environment. The dedicated encrypted entry was cleared after paid work; [cleanup evidence](../../../evidence/phase1-live/credential-cleanup.json) records it absent. No further live action is needed for this phase.

## Requirement-by-requirement closure

| Check | Evidence and disposition |
|---|---|
| P1-1 Frozen population | Approved narrow population; deterministic selection/exclusions, source/context/content identities and 12/12 separation; retained preparation and audit access sequence above. Complete. |
| P1-2 Usable evaluator | Pair contracts, callable versioned rubric/profile, saved judgments, final report and actual replay commands. Diagnostic-only applicability is explicit. Complete. |
| P1-3 Real critic route | First-two live evidence verified controls/accounting/containment and exposed malformed output. Automatic gate failed; explicit user-approved operator exception permitted expansion with that failure retained. Complete under the recorded exception. |
| P1-4 Complete accounting | All 48 unique scheduled presentations finalized; no extra/replaced calls, retries or liabilities; token totals and tariff arithmetic independently checked. Complete. |
| P1-5 Fixed audit calculation | Final evaluator frozen before audit; predictions committed before label opening; both fixed 12-prompt gates and Wilson intervals applied without pooling calibration. Complete; both scientific floors missed. |
| P1-6 Replay and boundaries | Frozen implementation passed 98 project tests, five upstream tests, static checks and separate Windows launcher/helper checks; saved calibration/audit replay and inspection made zero calls and changed no assessment/execution bytes. Complete. |
| P1-7 Decision report | Counts, coverage, failures, costs, uncertainty, order/length/family scope and fallback are recorded here and in immutable machine-readable reports. Complete. |
| P1-8 Preserved scope | Protected Phase 0 source/evidence/decisions/launcher and both pinned upstream trees remain unchanged. No generator, strategy or adaptation experiment was performed. Complete. |

The 98 tests and static checks describe the already verified frozen code; code was unchanged during live execution/closure. Those tests do not establish scientific validity or invoice accuracy. The [offline verification](../../../evidence/phase1/verification.json) and exact [runtime source archive](../../../evidence/phase1/runtime-source.zip), SHA-256 `0c1f2d62312a831bd8325380434be827ef14a084b9ee916f4c3111921272a822`, preserve that evidence. [Independent cold review](../../../evidence/phase1-live/independent-closeout-review.json) rechecked all 45 recorded offline evidence hashes, package/source-snapshot identity, split/presentation structure, provider controls/accounting, committed predictions and audit arithmetic. The review did not reopen raw human label/source/private files. The [closeout integrity check](../../../evidence/phase1-live/closeout-integrity.json) separately confirms frozen package hashes, historical archives, unchanged protected source/launchers/evidence, clean pinned upstream worktrees and documentation links.

Run ID: `7328a4c95367863bdb5b1cebafc0b9dc997b37431f274966352c48266265bf1b`. Canonical staged bundle digest: `1abe96e47ceaae4101ba5e4b6d7e793740f94f9f54c382effbfabc6ba89149d3`. Full requests/results remain locally under `runs/phase1-live-r05/execution`; versioned [pre-replay hashes](../../../evidence/phase1-live/pre-replay.json) bind that execution tree. No public dataset redistribution was performed; original-source licensing/participant permissions remain outside this phase's independent verification.

## Next decision, outside this phase

Do not repeat calibration, add another critic or enlarge the audit automatically. Refresh the concrete Phase 2 definition before implementation or new spending. Its fixed-strategy comparisons can use native benchmark evaluation and a predeclared blinded human sample; a successful MuCE critic is not a prerequisite. This failed critic cannot serve as validated external truth or be silently converted to a portfolio score. Any use inside a strategy is itself an intervention requiring independent assessment.

Phase 2, new benchmark integrations, CrPO measurement additions and native Harness² recursive-improvement experiments remain unstarted. The governing base-model/fixed-strategy/adaptation question and the eventual repeated native refinement milestone are unchanged.
