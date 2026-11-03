# AM-1 offline correction and first-block candidate

Date: 2026-10-26, America/Los_Angeles. Execution definition: frozen revision **0.16**. Parent commit: `b149953`.

**AM-1 is complete as an offline candidate under frozen revision 0.16, closed in revision 0.17. The evidence check passed in 358 seconds; the correction and first-block runner passed verification.** The actual pinned SDKs have completed the mock first block and exact zero-call resume. No real provider requests, credentials, human work, Phase 2B experiment or API spend occurred. The public command is offline-only; a provider-enabled host launcher is not part of this candidate and has not been built or tested.

## What changed and why

The earlier 0.14 checkpoint remains a completed no-go under its unchanged controls. Its local byte estimate did not prove 8k/64k provider input limits. AM-1 replaces that unsupported claim with two separate controls: the same measurable payload limits, and independent context-wide financial reservations. It does not turn the old estimate into a verified tokenizer.

The canonical request JSON acceptance sets remain exactly **5,952 UTF-8 bytes** for answer/plan/quality and **61,952 bytes** for rank/group. All request content and structured schemas count toward them. Prompts are never truncated or replaced to fit.

For reservations, the documented full-context relationship supports conservative maximum input envelopes of **1,000,000 tokens** for the exact Claude roles and **1,050,000** for Luna. Output is reserved separately without subtracting it from input, deliberately overestimating possible joint usage. This combines documented relationships into an operational bound; it is not an account check or a guarantee against provider misbilling. See [independent admission review](../../../evidence/phase2-am1-r016/admission-review.json), [billing arithmetic](../../../evidence/phase2-am1-r016/billing-review.json), [gate decision](../../../evidence/phase2-am1-r016/gate-decision.json) and [final code review](../../../evidence/phase2-am1-r016/final-billing-code-review.json).

[Claude context documentation](https://platform.claude.com/docs/en/build-with-claude/context-windows) links ordinary and cached input to the window. [OpenAI context documentation](https://developers.openai.com/api/docs/guides/conversation-state), the [Luna model page](https://developers.openai.com/api/docs/models/gpt-5.6-luna) and the exact [Chat Completions reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) support the grouping envelope and cache-write categories. The dossier records the dated rates/defaults and distinguishes direct documentation from inference.

The new versioned policy requires explicit usage categories, preserves grouping cache writes through the pinned SDK, validates breakdowns without double charging, and retains the entire reservation for unknown delivery, missing usage or unsupported categories. It includes applicable public PAYG tier/long-context/geographic premiums. Usage-priced receipt amounts explicitly identify themselves as conservative public-price upper bounds where geography is inherited, rather than invoice amounts. Private or unknown billing profiles are unsupported.

The shared dispatcher retains its legacy default contract. New callers must explicitly choose AM-1 and bind its control identity and public PAYG profile in the grant. Old current-source compatibility checks remain strict: the changed dispatcher correctly invalidates that route for historical studies. Their retained exact source still replays them without relabelling generation identities.

## Usable candidate and commands

Frozen candidate: [study.json](../../../runs/phase2-am1-r016/candidate/study.json), identity `d4287971e712a15a08ffba0e8e1de3b1bcd89e8f5c7e049c860fde02e1910475`. Its 22 retained package files match current effective source. Control identity: `159448f1025bdd60c5ed84ea524a7c9b4e73d2acb49def5081394736c39d339a`.

The [offline snapshot kit](../../../evidence/phase2-am1-r016/am1-offline-kit.zip) and [package record](../../../evidence/phase2-am1-r016/package-record.json) retain the candidate, examples, tests, dossier and handoff. This is a continuation snapshot requiring the existing pinned image/upstreams and retained parent records, rather than a standalone installation.

From the project root:

```powershell
.\phase0.ps1 run phase2-am1 inspect --study /results/phase2-am1-r016/candidate/study.json
.\phase0.ps1 run phase2-am1 preflight --study /results/phase2-am1-r016/candidate/study.json
.\phase0.ps1 run phase2-am1 mock-first-block --study /results/phase2-am1-r016/candidate/study.json --output /results/phase2-am1-r016/mock-distinct
```

Inspection/preflight send nothing and read no credentials. Repeating the final command resumes the retained example without new HTTP calls. For a fresh synthetic example use a new output directory. These commands do not perform live generation.

The runner admits only the first frozen task/repeat-1 worklist block, independently of a grant's expansion flag. It retains the full twelve-task/two-repeat study denominator. An outer owner lock spans generation, assessment and reporting; the dispatcher also locks each durable request. Nonfixture use requires a single canonical study journal under literal `/results`, the fixed `/workspace` layout and the pinned image/Python/installed SDKs. A future host launcher must independently verify the actual image and physical mounts; environment/path checks alone do not attest them.

## What the offline evidence shows

| Check | Observed result |
|---|---|
| Exact SDK boundary | Actual Anthropic 1.4.0 and OpenAI 1.107.0 constructors, serialization and parsing, with their installed `httpx2`/`httpx` MockTransports; fake keys only; external sockets blocked. No SDK-module substitution. |
| All ten heads per order | 55 mock HTTP requests, three native assessments, zero outstanding reservations, 1,265 remaining request slots and 69 missing assessments. Decision inconclusive; no seed. |
| Unchanged resume | Identical snapshot and files; zero new mock HTTP requests. |
| Five groups per order | 40 mock requests; 15 quality slots correctly `not_needed_nonhead`; the same 1,265 remaining study slots and 69 missing assessments. |
| Malformed plan | One known paid synthetic outcome preserved; dependent B/C requests skipped, A assessed; no replacement plan. |
| Missing cache usage | Full liability retained; dependent work stops; unchanged resume does not redispatch. |
| Boundary/failure checks | Payload equivalence including Unicode/schema/dynamic content; independent monetary oracle; missing/mismatched grants, private profile, too-small budget, expansion, interruption, concurrent owner, wrong model/tier, unknown categories and saved-artifact tampering. |
| Missing credentials | Four empty/whitespace-key cases reject before SDK construction, with no real key lookup. |
| Historical compatibility | The retained r012 source replays the unchanged r010 saved native evidence and benchmark decision; no generation or provider calls. |

Safe per-slot wire bodies/responses are in [mock-distinct/wire](../../../runs/phase2-am1-r016/mock-distinct/wire) and [mock-pairs/wire](../../../runs/phase2-am1-r016/mock-pairs/wire). Headers/keys are not captured. The snapshot directories contain journal state, coverage, separate execution/native assessment/analysis/decision records and failures. Synthetic ledger values ($0.042873 distinct; $0.026373 pairs) are fixture arithmetic, not spend or a prediction of real cost.

There were useful failed engineering checks: the SDK mock initially exposed the different installed HTTP clients; initial static checks exposed import/typing errors; one narrow run was invalidated by source changes while it was running. Those issues were corrected and retested. An early full-suite run was stopped because its baseline preceded the final source changes; it is not counted as a passing check. The superseded development candidate remains retained separately. No failed scientific outcome was observed or rewritten.

All **230 project tests** passed in 698.445 seconds on the final source, as did **five upstream checks**, Ruff, mypy (22 source files), Bandit and dependency compatibility checks. The focused AM-1/SDK/policy run passed all 34 tests. See [full-suite evidence](../../../evidence/phase2-am1-r016/runtime/full-suite.json), [focused checks](../../../evidence/phase2-am1-r016/runtime/am1-and-policy-tests.json), [static/upstream checks](../../../evidence/phase2-am1-r016/runtime/final-checks.json) and [acceptance review](../../../evidence/phase2-am1-r016/acceptance-review.json).

## Financial implications

| Reservation | USD |
|---|---:|
| Answer / plan / rank, each | 2.540960 |
| Group, each | 1.661880 |
| Quality, each | 11.440000 |
| Sum across all 55 possible first-block requests | 404.086760 |
| Sum across all 1,320 possible full-study requests | 9,698.082240 |

These sums are conservative liability envelopes, **not expected expenditure or requested spending**. Serial settlement normally releases most of each reservation; an unresolved request instead retains its reservation and stops. A smaller grant can therefore permit a completed run but cannot guarantee completion under the full envelope. The old proposed $5 first-check cap cannot admit even one quality request under AM-1. The old $125 figure is also still a proposal, not a grant or a full-envelope guarantee. No new monetary ceiling has been approved.

The [cost sheet](../../../runs/phase2-am1-r016/candidate/cost-sheet.json) and [unapproved authorization packet](../../../runs/phase2-am1-r016/candidate/authorization-request.json) make these limits explicit. Actual account/model access, current billing-profile compatibility, real settings acceptance and returned usage must be checked during a separately authorized counted first block. No extra auth/counting/model-list probes are implied.

## Preservation and remaining boundary

 Frozen prior studies, results, reports, source archives, evidence, upstream checkouts and dependency locks remain preserved. The baseline comparison and final acceptance record give exact counts/hashes.

One mutable working file, `runs/checks/bandit.json`, was overwritten by the standard check command. Its before/after hashes are disclosed; it is not a frozen historical study artifact. Later checks were routed into the new namespace. Do not describe every old working file as byte-identical. Historical closed verification evidence remains unchanged.

The slice delivers a usable **offline candidate**, not live certification or a provider-enabled host launcher. Before paid work, define and verify that narrow launch boundary against the frozen candidate, confirm the public PAYG prerequisites/current prices and obtain a separate applicable grant. Only the counted first task/repeat-1 block may then run, followed by review; full-pilot expansion remains unbuilt/unapproved. Human readers remain optional for the benchmark track; Route H is unstarted and CrPO deferred. No strategy or recursive-adaptation effectiveness conclusion follows from mocks.
