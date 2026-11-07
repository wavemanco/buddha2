# Engineering audit and simplification

Date: 4 November 2026. The reviewed cleanup and offline component verification are complete; that engineering work made zero provider calls. The [subsequent Phase 3B live attempt](phases/phase-3b/PHASE3B_LIVE_ATTEMPT_REPORT.md) stopped incomplete during round two. This audit is evidence of the integration's tested offline behavior, not of adaptation improving benchmark results.

## What this repository does

Buddha2 compares base generation, a fixed strategy, and actual Google Harness² adaptation, then evaluates saved outputs through NoveltyBench. The intended load is one research operator and one accounted study owner, with native worker threads. It is not a general execution platform or an unattended production service.

The scientific question remains: for a given model and task family, does native adaptation improve on the same fixed techniques under comparable inference allowances? Development work and held-out confirmation remain separate.

## Scope and non-negotiable boundaries

This review covers only code created for Buddha2: adapters, strategy contracts, provider/accounting boundaries, launchers, reports, tests, and release machinery. Harness² and NoveltyBench source, algorithms, pins, datasets, and scoring protocol are unchanged. Research records, completed results, frozen manifests, notices, and the fourteen classified historical originals are preserved. MuCE, CrPO, human review, and additional creativity criteria are deferred and excluded from this review.

The preceding offline acceptance run was settled on the user's scope redirection. It is incomplete, not a passing release and not a scientific failure. Its actual main and saved-replay passes and partial supervised evidence remain historical observations. No new paid calls are authorized by this cleanup.

## Why time was being consumed

These are observed intervals from the current offline execution records, not a profiler result:

| Work | Observed time | What it establishes |
| --- | ---: | --- |
| In-gate 126-test tally | 17 minutes 17 seconds | Test execution was material even before the study worklist |
| Capacity checks plus full four-prompt, two-arm mock worklist | 91 minutes 22 seconds | Combined cost; the two components were not separately timed |
| Main matrix to preservation receipt | About 20 seconds | Final preservation receipt followed the matrix |
| Saved replay after the main worklist | About 35 minutes | Zero new model/mock calls and zero new journal results; substantial work occurred outside inference |

The main matrix represented 1,364 mock requests for the configured multi-stage experiment. That request count is not itself a measure of wrapper overhead. The code review did establish repeated source hashing, historical archive verification, complete journal folding, and reopening prior request-audit files. Their individual shares of elapsed time are unmeasured.

The planning failure was cumulative scope control: successive repair and release requirements became the immediate objective, while the usable experiment entry point remained incomplete. A narrow specification for each addition did not control the size or utility of the whole system.

## Findings and decisions

### Must fix

1. **Checkpoint strategy attribution was missing** ([report](../followups/phase3b_seq2_v1/report.py)).
   - **What this is:** The c2/c1 report should distinguish changed instructions from another sample using unchanged instructions.
   - **Problem:** It read an attribution field that no code produced, so the field was always null.
   - **Fix:** Implemented attribution from the recorded seed/c1/c2 effective strategy hashes, with the sampling limitation retained.
   - **If skipped:** Readers could attribute a new sample's score difference to an edit that never happened.
2. **Exact ties were labelled fixed-strategy wins** ([report](../followups/phase3b_seq2_v1/report.py)).
   - **What this is:** The report names the direction of the paired mean difference.
   - **Problem:** The nonpositive branch treated zero as a fixed win and could select it as the method.
   - **Fix:** Implemented an explicit tie/no-selection result and fixture assertions.
   - **If skipped:** A scientifically neutral outcome would be misreported as a win.
3. **The public CLI omitted the current native experiment** ([entry](../src/buddha2/experiment.py)).
   - **What this is:** Codex needs one clear route to prepare, launch, inspect and report an experiment.
   - **Problem:** The main command primarily exposed the earlier offline kit and Phase 2; the current route required knowledge of internal modules.
   - **Fix:** Added a thin `experiment` entry delegating to the existing implementation, without another scheduler, server or provider client.
   - **If skipped:** Useful integration code would remain difficult to operate from Codex.
4. **Publication formatting could prevent execution** ([authority and source boundary](../followups/phase3b_seq2_v1/support.py)).
   - **What this is:** The original approved definition has a recorded identity; the public reader copy has reorganized links.
   - **Problem:** Four code paths hashed the physical Markdown, so editorial link changes broke approval validation despite unchanged executable settings.
   - **Fix:** Kept the approved definition ID and unchanged authority record; bound executable code/configuration separately. Removed Markdown as an execution input. Method, cap, attempt and model-setting changes still reject.
   - **If skipped:** An organized public clone could not prepare the otherwise identical experiment.
5. **The new inspection command initially missed capture-name variants** ([inspection](../src/buddha2/experiment.py)).
   - **What this is:** Read-only inspection must reject captured/private paths before metadata or contents are accessed.
   - **Problem:** Exact `source` checks missed names such as `prior-source` and `source-snapshot`.
   - **Fix:** Independent review caught this before publication. One lexical helper now serves source inputs and inspection, with negative path and import-origin regressions.
   - **If skipped:** A supposedly safe metadata command could enter an excluded capture directory.

### Should fix

6. **Current execution depended on historical acceptance campaigns** ([source boundary](../followups/phase3b_seq2_v1/support.py)).
   - **What this is:** Source identity should identify the effective current program and inputs.
   - **Problem:** It authenticated a 549-member ancestor map and old authorities, failed-candidate receipts, archives, reviewer copies and retained source. Missing old material could prevent current work.
   - **Fix:** Replaced that runtime prerequisite with an explicit current code/helper/configuration manifest and distinct v2 source/study identities. Old prepared studies reject before source reads; historical records remain unchanged.
   - **If skipped:** Every small repair or publication change could trigger another historical reconstruction campaign.
7. **Obsolete copies overwhelmed the implementation** ([retirement manifest](reviews/phase3-first-party-retirement-2026-11-04.json)).
   - **What this is:** Successive implementation versions accumulated as active-looking source packages and launch commands.
   - **Problem:** Static imports and string references showed large obsolete groups kept mandatory only by ancestor attestation.
   - **Fix:** Removed exactly 181 Python files and thirteen closed Phase 3A launchers: 194 files, 42,847 lines, 2,571,754 bytes. Reused helpers, privacy initializers and the adapter reached through a hash reference remain.
   - **If skipped:** Readers and tools would continue carrying tens of thousands of lines outside the current experiment.
8. **The paid gate required an entire publication campaign** ([current gate](../followups/phase3b_seq2_v1/support.py)).
   - **What this is:** Admission must verify the current code, settings and actual offline evidence before keys or spending.
   - **Problem:** The old gate required one RA1 candidate, twelve campaign groups, ZIP hashes and packet receipts; it could not accept a new current profile without repeating that machinery.
   - **Fix:** Replaced it with six current component receipts and one separate independent review, bound to the exact study/source/runtime/policy/launcher. No artifact is generated merely because validation code exists. Container, key, money, unknown-liability, no-resend and information guards remain.
   - **If skipped:** The experiment would stay blocked on release packaging that neither scientific engine requires.
9. **Journal and source verification repeat expensive work** ([accounting](../followups/phase3b_seq2_v1/accounting.py), [workflow](../followups/phase3b_seq2_v1/workflow.py)).
   - **What this is:** The ledger reconstructs prior events/audits, and study loading verifies current inputs.
   - **Problem:** Complete journal reconstruction repeats inside a live run and grows at least quadratically with requests. Historical source/archive reconstruction compounded that cost.
   - **Fix:** Removed the historical reconstruction and reduced the effective input map. Retained locked full journal replay: a cache would need to preserve out-of-band review additions, stop checks and prior-byte corruption detection. No unsafe cache, database or checkpoint service was added.
   - **If skipped:** The known journal cost remains. Its individual runtime share is unmeasured; it is an explicit remaining optimization, not a reason to drop financial validation or delay the small scientific comparison.

The three proven unused current aliases/helpers were also removed. Their small saving is separate from the 194-file retirement. This review does not claim that every helper in a retained legacy namespace is minimal; those namespaces still supply live contracts, transport and validation functions.

## What stays

- Actual upstream `schedule.run_task`, native sequential recursion, native proposal/composition/selection, and the project portfolio adapter.
- The native OpenCode proposer and its accounted relay. OpenCode owns the agent/tool loop; Buddha2 must not replace it with another agent framework.
- Native NoveltyBench request construction, strict folds, arithmetic and summaries, with assessment outside adaptation.
- Bounded editable strategy fields, valid ordered portfolios, response identities, and rank permutations.
- Exact model/settings records; reservations before requests; actual usage settlement; retained uncertain charges; no silent fallback or automatic resend.
- Information boundaries that prevent external judgments from becoming adaptation inputs.
- One usable command path and a compact outcome/cost report. Optional existing Inspect viewing remains separate from paid execution.

## Existing frameworks: research revisited

The previous [framework research](../evidence/phase3a-history-compat-h1/RESEARCH.md) and [Inspect fit note](../evidence/phase3a-history-compat-h1/INSPECT_AI_FIT.md) were reviewed, together with current primary documentation. The passive Inspect trial has already been completed. Its [report](operations/inspect/INSPECT_VISIBILITY_I1_REPORT.md) records eight added files, eighty locked wheels, and zero existing modules removed. Repeating that trial would repeat completed work.

| Component | Reuse now | Do not build |
| --- | --- | --- |
| [Harness² adapter and scheduler](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/harness2/core/spec.py) | Actual recursion and native execution seams | A second recursion engine or generic strategy plugin platform |
| [NoveltyBench](https://github.com/novelty-bench/novelty-bench/tree/64a23be6b18ec1dacc298830aab276061b6e143c) | Native generation exchange and separate assessment | A copied grader or an invented replacement metric |
| [Inspect](https://inspect.aisi.org.uk/eval-logs.html) | Existing optional viewer; its logs, resume and orchestration are available if they replace named custom modules | Another passive-viewer spike, or a model bridge added only for visibility |
| [Harbor](https://docs.harborframework.com/agents/custom-agents) | Relevant reference for sandboxed agents and separate verification | An immediate migration for this text experiment |

A full Inspect runner replacement is a multi-day integration, not a free speed fix. Its [agent bridge](https://inspect.aisi.org.uk/agent-bridge.html) can change effective generation parameters. Its [cost limits](https://inspect.aisi.org.uk/setting-limits.html) do not by themselves reserve maximum liability for a request whose receipt is lost. Automatic [model retries](https://inspect.aisi.org.uk/models-concurrency.html) and [task retries](https://inspect.aisi.org.uk/eval-sets.html) require explicit configuration for this experiment. Keep the current protocol and paid boundary while cutting redundant machinery.

No new framework or dependency was added for this simplification. Harness² is Apache-2.0; NoveltyBench and Inspect are MIT; Harbor is Apache-2.0. Existing attribution remains applicable. No upstream upgrade accompanies this work.

## Delivery and next research step

The cleanup was organized around the following focused-work targets across agents. These are planning estimates, not a retrospective time measurement or a guarantee.

| Work | Target | Usable result |
| --- | ---: | --- |
| Audit, dependency trace, prior-research review | First 60–90 minutes | Evidence-backed keep/cut/reuse map and concrete correctness findings |
| Effective-source decoupling, justified deletions, report fixes, tests | Next 2–4 hours | Reduced current implementation with preserved records and guards |
| Clear Codex entry to that same implementation | Then 1–2 hours | Working commands for preparation, execution, inspection and results, delegating to the same implementation |

Those outputs are now implemented and component-reviewed. No additional server, framework migration or nested acceptance campaign is planned. This cleanup spent $0 on APIs.

At cleanup closure, the handoff was the defined four-prompt Phase 3B development comparison: actual native `seq,k=2` against fixed best-of-twelve, with the same declared techniques, separate external assessment and recorded actual spending. The user subsequently authorized that attempt. It stopped incomplete during the first prompt's second round. The [stopped-attempt report](phases/phase-3b/PHASE3B_LIVE_ATTEMPT_REPORT.md) now records the current next decision about the reproduced read-format rejection. This historical handoff does not authorize another paid attempt or a new release campaign.

Only after a completed comparison should its observed outcome determine whether a larger development comparison is warranted. Held-out confirmation and broader model/strategy comparisons remain later research decisions. The completed four-prompt Phase 3A pilot is evidence about one-step adaptation; the two-step effect and held-out benefit remain unmeasured.

## Current operating contract

The current source manifest contains 162 effective inputs. A new study binds the current code, portable four-prompt development inputs, strategy, runtime, policy and declared original definition ID. Human-facing Markdown is separate. Historical studies and receipts are never rebound to this source.

Before live admission, `offline-readiness.json` beside that study must reference six actual sealed component receipts: `financial`, `transport`, `message_history`, `strategy`, `native_contract`, and `source_coverage`. Every receipt records its real command, unique executed test IDs, a positive test count, zero failures/errors/skips, no real credentials or provider calls, and the same five bindings. A separate `independent-review.json` identifies a different reviewer and binds the exact readiness bytes and seal. Missing, stale, private-path or foreign evidence rejects before a live claim or keys. These are local experiment records, not a new execution framework.

Optional Inspect display is not an admission prerequisite. Canonical report/checkpoint validation, actual owner/container inspection, budget and unknown-result handling remain in execution. A component pass does not establish live provider success or a scientific improvement.

## Verification and limits

The audit traces the active native, strategy, editor, provider/accounting, assessment and reporting paths, plus callers, tests and static/dynamic references used for the retirement map. The historical code is reviewed for reachability and duplication; it is not all reviewed line by line. Upstream and deferred evaluator code are outside the cut.

Actual verification:

- The pinned Linux runtime passed **101 unique component tests in each of the canonical and public source profiles**: financial 16, transport 21, message history 12, strategy 8, native contract 15 and source coverage 29. There were zero failures, errors or skips. These are the same 101 cases against two profiles, not 202 different cases.
- Both profiles passed actual authority validation, portable study preparation, independent receipt/source review and the existing current-readiness validator. Exact owned test containers were removed. No real credentials or provider calls were used, and no paid grant was created.
- Ten CLI tests passed in each profile. Root/experiment help and read-only historical metadata inspection ran successfully. Ruff, Mypy on the changed modules, Bandit and scoped whitespace checks passed. The earlier tool/setup failures and superseded test attempts remain recorded; they were not relabelled as final passes.
- All 39 pinned Harness² Python files and 17 pinned NoveltyBench Python files matched the upstream lock. Their revisions, source and algorithms were unchanged. Current source identities are `c6eb4157c15ff859e70a0411b9b92f227ccfdf94dd1da94f38d1cdac21ef08c1` (canonical) and `97f16655087287dd32a1f491d17219e83adc9284c49570b46f32b7ca413e1ca8` (public). The public profile differs only in two pre-existing documentation-path literals. Exact Git attributes preserve the tested bytes in publication.

See the [independent cleanup review](reviews/engineering-cleanup-review-2026-11-04.json) and [retirement manifest](reviews/phase3-first-party-retirement-2026-11-04.json) for evidence pointers and exact scope.

Static reachability is not runtime correctness. Component readiness is not live provider success, evaluator validity or evidence that adaptation improves results. The previous full release matrix was not repeated, and the new paid comparison and held-out evaluation were not run. Removed historical commands require their historical revision/source kit; they are not current entry points. Locked journal replay remains a known, unprofiled runtime cost.

Verdict: retain the native research integration and financial/information boundaries; remove historical campaign prerequisites and obsolete first-party copies before adding capabilities.

## Offline false-stop correction

The correction reuses existing validators and unittest; it adds no dependency or paid experiment. [Anthropic documents moving cache breakpoints](https://platform.claude.com/docs/en/build-with-claude/prompt-caching), while [tool/thinking history must remain intact](https://platform.claude.com/docs/en/build-with-claude/thinking-tool-workflows). Mutation binding now omits only top-level cache_control on tool-call/result blocks. Nested payload fields, tool identities, inputs, results and strategy content remain bound.

Live normal-final and saved-selector comparisons share native CRLF and surrounding-whitespace normalization; substantive output and candidate-choice changes still reject. [Behavior-focused testing](https://testing.googleblog.com/2013/08/testing-on-toilet-test-behavior-not.html) and existing [unittest subtests](https://docs.python.org/3/library/unittest.html#distinguishing-test-iterations-using-subtests) vary observation and completion independently. The [record/replay pattern](https://vcrpy.readthedocs.io/en/latest/usage.html#record-modes) uses existing exchanges without installing VCR.py.

All **27 focused tests** passed with zero failures/errors/skips (300.834 seconds collector; 299.761 seconds unittest). Three regressions failed before correction. The actual DOM1 counterfactual reconstructed the model edit, generated a fresh t09 witness, preserved it through t11 and passed normal verification. Ruff passed four files, Mypy three; Bandit found zero issues with known comment warnings. A broader 122-test run was interrupted after seven passes; no full-suite pass is claimed.

The [correction receipt](../evidence/phase3b-seq2-v1/false-stop-correction-offline-v1.json) binds the new 163-input identities. Earlier acceptance results remain historical. Both paid attempts stay incomplete. This correction creates no study, readiness pass, grant or paid-run authority.

## Durable native artifact-binding correction

The separately authorized offline correction binds the native engine's actual returned output. The unchanged native engine gives a nonempty saved file priority and otherwise returns its actual stdout aggregation. Normal-proof v2 is created after that native return, binding it to the real saved artifact, successful model-write witness and strategy. Final-chat prose differences are diagnostic; saved author `Stage.notes` and selector candidate choice remain bound. Changed native return/artifact, missing file and missing witness still reject. No upstream code, dependency, prompt, model or budget changed.

The original production bug was reproduced RED. A relay integration test runs actual unchanged `Proposer._opencode`, simulating only its subprocess, through three passing cases: saved-file priority, empty-file stdout aggregation and altered-file rejection. The separate saved-only counterfactual binds all ten recorded exchanges, ledger chain, history, tool inputs and results. Current normal and saved-information verification pass; all four negative controls reject. Its 22 historical files and four verifier-source hashes remain unchanged. It is a counterfactual, not a new native completion or requalification of the stopped study.

Final normal-module groups verified **145 unique methods**: financial 22, transport 21, message history 31, strategy 20, native contract 16 and source coverage 35. Linux collected 145: 143 passed and two Windows-only methods skipped. Both Windows methods separately passed on the actual host in a credential-free child (0.841 seconds); there were no final failures or errors. The native-contract group took 611.749 seconds. Independent review covered all five changed files and their live/saved callers with no blockers; that reviewer did not rerun tests.

The initial combined stdin-runner trial completed naturally with 145 tests, one multiprocessing spawn setup error at `/workspace/<stdin>` and two platform skips, with no assertion failures. Final verification uses the individual normal-module group results. Initial read-only Ruff-cache setup and type-check observations preceded final correction. Final Ruff passes five changed files, Mypy three production files, and Bandit finds zero issues in those production files with only existing `nosec` warnings. No public H1 run is claimed.

The [safe correction receipt](../evidence/phase3b-seq2-v1/artifact-binding-offline-fix-v1.json) binds canonical source `dda19ddcbe4990a119fd0267776ac81fde2618c0dfea1767ceae6cdc7d956d32` and projected public source `516a14ce15aefa77514b03681adc7910dac5fdb484453e281a442854c640665c`, each with 163 inputs. Their sole existing source projection is two documentation-path literals in `__main__.py`. Proof v2 and the new source identity naturally invalidate earlier readiness. No fresh live kit, grant, paid continuation or repaired historical result is supplied. The R2 outcome remains closed incomplete with all final rows held; its earlier first-pair scores remain exploratory.

## Conversation time controls

Authorized 5 November 2026 by the user's instruction to proceed with the focused timing correction. This changes the existing control path, not the experimental adaptation algorithm.

**Objective:** an elapsed conversation-time threshold should lead to a warning, bounded grace and a user decision, preserving the same native conversation and next request. It must not turn the observed 56.948-versus-60-second admission shortfall into an automatic whole-run failure.

**Scope and usable deliverables:** coordinate the external adapter's soft clock, native subprocess and local HTTP limits; add an identity-bound continuation decision at the existing pre-intent boundary; expose that decision through the existing experiment CLI; record the policy and decisions in source-bound evidence and reports. The supervisor contract must identify the warning/pause files and require an actual user answer. No new service or plugin is introduced.

| Control | Prospective behavior |
|---|---|
| Warning | Observed at a request boundary after 480 seconds; the supervisor notifies the user. |
| Conversation allowance | 600 soft seconds plus 300 automatic grace seconds, including local setup. |
| Review | At the next request boundary after that allowance, publish a paused request before any intent or SDK call. Wait up to 1,800 seconds for an explicit continue/stop decision. |
| Continue | Preserve the same native child, conversation, history and request slot. Grant 600 seconds from acknowledgement; waiting and overdue setup do not consume that new allowance. Recheck source/readiness and financial guards before dispatch. |
| One-slot permission | A valid timing gate covers exactly the next slot and its mandatory validation. Slow file checks do not revoke that permission. Another review is scheduled at a subsequent request boundary. |
| Stop / no answer | Record the explicit operator stop or expired review, close incomplete and preserve accounting. Never infer approval, restart or resend. |
| Actual provider operation | Keep the existing 240-second completion and 60-second cleanup bounds, unknown-charge holds and no-resend behavior. |
| Native/local outer limits | Finite process ceiling 65,700 seconds, derived from the 24-request limit and maximum waits/work; local relay-fetch ceiling 65,690 seconds. These are containment ceilings, not work, spending or continuation grants. External provider I/O limits remain unchanged. |

Requests, decisions and ACKs use immutable files under the current run's `timing-controls/` directory, outside proposer context. They bind the source, study, accounting policy, launcher, conversation and slot. The host command is `python -B -m buddha2 experiment timing --request <host-request.json> --decision continue|stop`; it changes no financial authorization. The decision is effective only when the controller ACKs it. An already admitted provider call settles under its original budget before a later pause.

**Exclusions:** paid calls or fresh keys; any new live study, grant or paid repetition; upstream Harness2/NoveltyBench edits; model, prompt, strategy, token, request or dollar-limit changes; historical-result rescue; a new runner, scheduler, framework, dashboard or MCP server. Inspect's separate 600-second export window is unchanged.

**Completion:** reproduce the saved shortfall with fake time; prove warning/grace/continue/stop/expiry and late-setup behavior; prove zero intents/SDK calls while paused, unchanged next-slot/history and guard checks after continuation; retain legacy audit parsing and hard-cap/unknown-liability negatives; exercise the pinned native wrapper and MockTransport path; pass focused tests and static checks; independently review the change and preserve old artifacts. Offline verification does not establish human-in-the-loop live completion.

**Cost:** $0 API spend. This correction creates a new effective source/profile; earlier readiness cannot admit it. The stopped study stays closed. Prospective paid work still needs its applicable definition, kit and repetition authorization, carrying all prior charges and holds.

**Verified outcome:** 67 unique methods passed in the pinned, keyless H1 runtime with networking disabled, zero failures/errors/skips (128.750 seconds in unittest; 133.493 seconds observed). The source stayed `26898c3788418aa17dc21a3e6b269abdf61348ac0feeaf57c846a2353fa18178` across all 163 effective inputs before and after testing. Ruff passed 16 changed production/test files; Mypy and Bandit passed 12 production files, with existing Bandit comment warnings only. Independent code review found no blockers. Two deliberately failing regressions exposed slow notice/ACK writes; both now pass. Pinned SDK mocks and real ledger paths verify zero intents or SDK calls while paused, continuation on the same slot, post-wait source guards, and hard financial/unknown-charge handling. The native-wrapper integration simulates its subprocess; it does not claim a live human continuation or a complete new acceptance campaign. The earlier 65-test run remains separate evidence preceding the final fixes. See the [safe offline receipt](../evidence/phase3b-seq2-v1/timing-correction-offline-v1.json).

**Operational follow-up:** the missing complete timing-path demonstration subsequently passed with the actual unchanged native Bun/OpenCode subprocess, local relay, Ledger and Transport. The user's actual Continue answer was applied through the existing host CLI. The same child, identified by PID and process start time, survived a 78.425-second pause, resumed the identical pending request/slot/history and completed five mocked-provider rounds with a normal selector result. No intents or SDK calls occurred while paused; all five history and transport audits passed, with zero external provider calls, spend or held liability. The ACK granted exactly 600 seconds from acknowledgement. Production source and the 163-input identity stayed unchanged; no code repair or fresh study was needed.

The fixture aged only the clock's elapsed-time input by 900.01 seconds, keeping the real timing policy unchanged. This exercises the boundary without waiting fifteen minutes. The pause precedes the first model response; it demonstrates survival of the initial pending history, followed by normal five-round history handling. It does not demonstrate a pause after a long model conversation, a real external provider operation or full current-study acceptance. The controller continuously observed the owned child while paused. Independent review verified the completed records and journal; the reviewer did not independently capture pre-decision PID/journal state. The [safe operational receipt](../evidence/phase3b-seq2-v1/timing-human-rehearsal-v1.json) preserves these limits alongside the earlier component-only receipt.

**Historical pre-run handoff:** the user has now approved proceeding with existing source-bound acceptance, fresh keys afterward, and one fresh four-prompt comparison through reviews, Inspect exports and closure. Remaining caps are $146.435242 total/$26.094077 included first prompt and 1,513 new requests. The only code changes for preparation roll attempt/authority/claim identity and carried-forward accounting; the existing algorithms, models, timing policy and execution path stay fixed. Keep historical charges, holds and incomplete results intact. No new infrastructure block or automatic further repetition is authorized.

**Current-source acceptance:** the six existing groups pass 151 unique methods: financial 22, transport 38, message history 31, strategy 8, native contract 16 and source coverage 36 (34 Linux plus two actual Windows). There are 149 actual Linux passes and two actual Windows passes, with no failures/errors/skips in the completed set. The initial Windows scratch invocation executed zero tests due to double encoding; its failed observation is retained and supplies no pass. No actual methods were rerun by that correction. Ruff passed eight changed Python files; Mypy and Bandit passed five production files with existing comment warnings only. The source stayed `da77ba399f3f55fad784d136a7271ee22716bf36282122608ea2ec5bf1b9a203` / 163 inputs. Independent readiness validation, actual PowerShell configuration and explicit provider-mode host-bind preflight all pass; all four owners are independently absent. No archive/cold campaign, framework, credentials or provider calls were added. See the [accepted-kit receipt](../evidence/phase3b-seq2-v1/timing-continuation-offline-acceptance-v1.json). That kit was used for the stopped attempt below.

## Timing-corrected attempt outcome

The single approved comparison is **closed incomplete after 353 settled calls/$11.082350**, with zero pending requests, durable unknowns or new held liability. The first prompt's native `seq,k=2` path passed normal readiness: eight rollouts, six authoring stages and its selector. Fixed best-of-twelve generation and selection also returned. Assessment did not close, and no first-prompt review opened. Final projection globally holds the evidence: 0/8 primary and 0/12 assessment targets scored; no scientific comparison or improvement conclusion follows.

The stop was a local admission check, rather than a timing stop or provider failure. One keyless H1 reconstruction identifies the next adaptive c2 `quality.02` request as 6,206 canonical UTF-8 bytes, exceeding the inherited Phase 2 quality cap of 5,952 by 254 bytes. All other request-profile predicates passed; reconstructed earlier `quality.00` and `.01` hashes match their admitted records. The rejected request was never sent and its body was not logged. Preserve this distinction between reconstruction and captured evidence.

Canonical closure and the passive closure Inspect export completed within the original window. One saved-report replay produced eight byte-identical files with unchanged journal and source, zero provider calls and zero blocked SDK/socket/process attempts. All exact run, preflight, exporter and forensic/replay owners are independently absent. Earlier studies, the accepted source and the old $22.88 hold remain unchanged. The [attempt report](phases/phase-3b/PHASE3B_TIMING_CONTINUATION_LIVE_ATTEMPT_REPORT.md) and [outcome receipt](../evidence/phase3b-seq2-v1/timing-continuation-live-outcome-v1.json) retain the detailed accounting and limits.

Next is a decision on the obsolete local quality byte cap. This closure authorizes no code repair, new study, keys, further calls or paid repetition; unused funds do not reopen the stopped ledger.

## Evaluator admission correction

The user authorized this focused offline correction and reviewed publication after the timing-corrected attempt stopped. The existing Phase 3B shared validator now uses evaluator-specific local wire ceilings. The historical AM-1 policy remains byte-unchanged; planner, answer and rank admission still use it. Live admission and saved-request validation share the corrected function.

The existing portfolio contract permits a 100,000-character prompt and ten answers of up to 100,000 characters each. Canonical UTF-8 JSON uses at most six bytes per valid character. The pinned native renderers insert those texts directly, without another JSON-escaping layer. Their measured fixed wrappers give these complete upper bounds:

| Evaluator request | Maximum contract payload | Local ceiling |
|---|---:|---:|
| Quality: prompt and one answer | 1,200,935 bytes | 2,097,152 bytes (2 MiB) |
| Group: prompt and ten answers | 6,601,333 bytes | 8,388,608 bytes (8 MiB) |

These are finite resource ceilings derived from the accepted text contract, not provider-token estimates or provider-acceptance guarantees. The frozen generator still requests at most 4,096 output tokens; characters and tokens are not equated. Model/settings validation, full-context reservations, monetary/token/request ceilings and unknown-charge holds are unchanged. Quality still reserves $11.44 and grouping $1.661880 before a request; these are maximum-liability reservations, not expected spend.

The new regression first reproduced the inherited rejection, then passed after the correction. **45 unique focused checks pass:** 42 logic/native/financial/strategy cases plus three source-binding checks. They include actual maximum-size ASCII, Unicode, JSON control-character and quoting cases; exact-ceiling and one-byte-over rejection; frozen-profile negatives; and the existing financial and unknown-liability checks. The real pinned benchmark builders also admitted all 25 saved evaluator requests and 33 requests rebuilt from the completed c1/c2/fixed portfolios. The reconstructed missing request retains its exact 6,206-byte size/hash, corroborated by the preceding two admitted requests. No judge was called.

All nine blocked SDK/socket/subprocess seams recorded zero attempts. Ruff passed both changed Python files; Mypy and Bandit passed the one changed production file. Independent review found and resolved one test-fixture initializer binding gap. Only source-manifest entries changed afterward; final source checks passed without repeating the 42 logic tests. The resulting source profile has 165 inputs. The 29 explicitly retained files, including journal, reports, native outputs and embedded fixed candidates, are unchanged. No broader artifact scan or complete test-suite campaign was run.

See the [safe correction receipt](../evidence/phase3b-seq2-v1/evaluator-admission-offline-fix-v1.json). This $0 offline correction creates no fresh live acceptance, grant or scientific result. The closed attempt and prior charges/holds stay intact. Next is a decision on compatible assessment-only reuse of completed generation; a paid continuation requires its own current identity/accounting and applicable authority.

## Mandatory preflight regressions and contract checks

The existing six-receipt gate now requires 16 named regression tests covering cache annotations, authoritative saved output, read formatting/diagnostics, timing/continuation, signed history, financial holds and producer/evaluator compatibility. It rejects an otherwise-green packet missing any required test, even when every receipt, manifest and independent review is freshly resealed. Additional tests remain allowed. Source/runtime binding and independent review retain their existing rules; no new runner, dependency or receipt schema was introduced.

The portfolio validator and native importer now share explicit prompt/answer character-limit declarations, preserving their current 100,000-character values. The maximum-size tests read those declarations. Gated provider preflight also constructs an explicitly synthetic portfolio using those current limits and the worst canonical-JSON escaping character. It passes real pinned benchmark grouping and all quality requests through the same production admission guard. This runs after accepted offline evidence and before accounting state opens, without cached success, client construction or dispatch. Current maxima remain 6,601,333 grouping bytes and 1,200,935 quality bytes; consumer ceilings remain 8 MiB and 2 MiB.

The changed-limit test derives counterexamples from current consumer ceilings instead of fixed example lengths. Today those are 349,526 prompt characters and 139,811 answer characters. Each changes only a producer limit: the real preflight rejects the incompatible request before accounting, and the consumer ceilings stay unchanged. A normal positive control reaches the accounting sentinel. Before the hook was added, both incompatible cases incorrectly reached that sentinel; the retained RED observation demonstrates the test detects the missing check.

**Verification:** 75 unique selected methods pass, covering all 16 mandatory IDs. These include contract/portfolio/native checks, financial and liability negatives, omission of each required test, source binding, timing and client-history regressions. Ruff passed six Python files; Mypy and Bandit passed four production files. Pure checks recorded zero attempts at all nine blocked SDK/socket/subprocess seams. Client integration cases used mock SDK transports and a local fixture relay inside the network-isolated runtime. An initial invocation wrongly blocked that relay and used an unreimportable stdin entry point for a spawned worker. The failed observation is retained; only the two affected methods were rerun through normal unittest module execution and passed, with no source changes for that recovery. No external provider calls occurred.

All 39 explicitly retained historical files, including completed generation, closed journal/reports and prior fix evidence, are unchanged. Independent code/evidence review passed and the exact owned worker is independently absent. The [safe receipt](../evidence/phase3b-seq2-v1/preflight-contracts-offline-v1.json) binds the 165-input source. These checks address current contracts and tested failure classes; they do not establish universal plugin compatibility or live provider success. No fresh live kit, paid continuation or scientific result was created. Compatible assessment-only reuse remains the next separate decision.

## Assessment-only reuse preparation

The new `experiment assess-saved` operation prepares or verifies an immutable packet for the approved closed first prompt. It uses existing native request builders/folding, journal-chain validation, accounting normalization and file seals. It creates no ledger, executor, provider client or generation run.

| Saved target | Compatible observations | Pending judgments |
|---|---:|---:|
| Fixed selected portfolio | 11 | 0 |
| Adaptive c1 | 11 | 0 |
| Adaptive c2 | 3 | 8 quality heads, 02 through 09 |
| Total | 25 | 8 |

The packet has a new outer identity while retaining original generation-study, portfolio, assessment, slot, request and result identities. The approved parent outcome, tiny data certificate, exact original journal hashes/chain, pair seal and original readiness record anchor the inputs; no archived source or old release campaign is executed. The unchanged evaluator base and assessment wrapper must match their original source hashes. All 33 rebuilt requests pass current admission. Every retained result matches its exact original request, normalized accounting and native response/model checks; quality JSON and score ranges remain strict. The two complete assessments must finalize exactly equal to the original stored records. No cached response is relabelled, copied into the packet or purchased again. The packet stores hashes/references and only the eight pending request bodies.

Inside the existing pinned runtime, prepare with `python -B -m buddha2 experiment assess-saved --study PATH --output /results/phase3b-seq2-v1/assessment-reuse/NAME`; verify read-only with `python -B -m buddha2 experiment assess-saved --packet PATH`. Preparation requires a fresh output directory outside the closed run. Verification rechecks the source, original inputs and entire rebuilt packet, rejecting resealed tampering, stale source, changed input hashes and private paths. The referenced original data must remain available. This operation is scoped to the approved parent, not arbitrary failed studies.

The actual public CLI prepared and verified packet `2611139c34dc5c1c73b540631dabe4fc0b85611728ae9e5cbc661561c0d1e217`. All 30 selected offline methods pass: six actual-parent preparation/negative checks and 24 CLI, native replay and source checks. All nine blocked SDK/socket/subprocess seams recorded zero attempts. Ruff passed four Python files; Mypy and Bandit passed two production files. Independent code/source/data review passed; the exact owned worker is independently absent. All 44 retained historical files are unchanged. The [safe receipt](../evidence/phase3b-seq2-v1/assessment-reuse-preparation-offline-v1.json) binds the 167-input source and packet/file hashes without publishing request bodies.

The original global hold and four-prompt incompleteness remain unchanged; this packet is a verified reuse plan, not score activation or live authorization. No keys or paid calls occurred. Future execution of the eight missing judgments needs separately controlled result accounting binding the new assessment packet to the original generation provenance, with applicable current authority. Generation and selection must not be repeated.

## Eight-judgment assessment-only execution

The follow-up uses the existing inspected launcher, masked credential entry, supervisor attachment and bounded SDK worker. `experiment assess-pending prepare --packet PATH --output PATH` freezes a new eight-request execution descriptor and grants; `experiment assess-pending report --study PATH --grant PATH` replays its separate journal. The launcher recognizes this explicit descriptor kind; ordinary comparison execution retains its existing route. No generic runner, dependency, model, grouping or generation path was added.

The new journal's run identity binds the accepted reuse packet, exact pending requests, current source, runtime, policy and direct eight-only authority. Result `study_sha256` continues to identify the original generation; new dispatch IDs identify this new execution. Original cached records are neither rewritten nor relabelled. Native folding can therefore combine the original grouping and first two c2 quality observations with the eight new quality results. Fixed and c1 must still match their original complete assessment hashes. New audit records live under the supplement's fresh root, never the closed run.

The supplement has at most eight serial attempts and a $15.011727 cap, preserving the remaining included first-prompt allowance inside $135.352892 remaining total funding. Each request requires an $11.44 conservative liability reservation before dispatch. Prior quality usage suggests about $0.12–$0.18 for eight similar judgments, rather than $91.52 guaranteed spending. Source/data compatibility, exact role/request identity, current six-receipt readiness and its 16 mandatory regressions, inspected containment, real supervisor attachment, one packet-wide allowance claim, known accounting and strict native response parsing remain required. Uncertain intents/results are never resent; known charges and unresolved reservations survive replay. No new reservation is admitted if it would exceed the remaining cap.

Offline acceptance exercises seven new execution tests, 25 CLI/launcher tests, all 16 mandatory regressions and nine native replay tests: 57 unique methods, zero failures/errors/skips. The actual saved packet also passes public CLI preparation and eight SDK-mocked quality requests followed by zero-resend replay. Mock results remain explicitly synthetic, with no live native scores. Entirely synthetic nonfixture records separately test the native merge/folding branch. The host check caught a changed bundled PowerShell executable before key entry; its valid Microsoft signature/version 7.6.9 was independently verified, and only the existing bootstrap fingerprint was updated. The unchanged launcher core remains hash-bound. The final record also supplies the host's existing readiness-display field with zero, because this supplement runs no generation readiness cell. Final-source tests and the saved-request rehearsal were repeated after these compatibility corrections; prior observations were retained. Ruff, Mypy and Bandit pass on the changed Python scope. The independent check of 46 specified historical files includes the original closed run and accepted packet.

The output is a first-prompt assessment supplement. It does not reopen the old global hold, change the c1 selection, finish the other three prompts or establish an adaptation-gain conclusion. A live result still requires fresh masked keys and observed, fully accounted provider responses. Raw grading requests, provider responses and local journals are not public publication inputs.

## Eight-judgment live completion

The approved eight-only supplement completed with eight unique quality requests and eight known responses, $0.157506 usage-priced accounting and no new held liability. It reused 25 original observations without generation, grouping, retries or selection changes. Native distinctness is 10 for all three portfolios; utility is 7.753090294662793 for fixed, 7.896478728064968 for selected c1 and 7.603188647901371 for c2. The new outcome is `c701a1d084bb4bce5c225b1c082c0dc812f303829635db0a4489a95735ce17d7`; the original closed outcome and held reports are unchanged.

Independent review checked the complete 16-event chain, eight exact native request/result bindings and bounded-worker audits, and recomputed $0.157506 from 15,532 input and 2,621 output tokens under the frozen billing envelope. The output total includes thinking once. There are no unknowns, late responses, retries or unresolved reservations. Fixed/c1 assessment object hashes exactly match the original complete cached assessments; the original score-blind c1 selection is retained. Native singleton-utility arithmetic was also independently recomputed.

One fresh pinned, keyless, network-disabled observer mounted both source and run data read-only, with only a separate verification sink writable. The ordinary report command's implementation reconstructed the full outcome exactly while all nine SDK/socket/process seams were blocked. Replay added no calls, changed none of 46 original files or 11 fresh journal/outcome/audit files, and preserved the 169-input source. The exact paid controller and replay observer are independently absent; no secret or provider body is published. See the [safe completion receipt](../evidence/phase3b-seq2-v1/assessment-only-execution-live-outcome-v1.json).

This closes first-prompt assessment only. The other three pairs remain unstarted, and this one prompt cannot establish general benefit, significance or held-out effectiveness. The next decision is continuation of those three pairs while preserving this completed pair; the eight-only worklist admits no further calls.
