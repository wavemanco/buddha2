# P4-CM1 live attempt — closed incomplete

The controller closed at **02:01:31 UTC on 9 November 2026** (18:01:31 PST on 8 November), with status `paused-integrity-or-liability` and `ContractError`. All 2,651 requests are accounted for at **$44.975462**, with **zero new held liability**. The failure came from our context adapter's handling of a supported optional-probe failure. No repair, restart or additional model call followed. See the [reviewed outcome](../../../evidence/phase4-cm1-v1/live-outcome-v1.json).

**There is no scientific comparison result.** Three of 24 confirmation units started; 21 remained unopened. One generation pair completed, but no external grading ran. Official quality, distinctness, utility and grouping sensitivity are all **UNEVALUATED**.

Under the frozen rules, completing the remaining units would still leave the prespecified complete 24-pair confidence interval unavailable: p4-01 has no fixed selection. That missing arm must remain recorded; silently replacing or repairing that case would change the declared experiment.

## What ran and what it cost

Both exposed fixed-only cost qualifications passed. The frozen comparison then reached:

| Scope | Known requests | Native inference | Fixed inference | Total accounted cost | Result |
|---|---:|---:|---:|---:|---|
| Two development qualifications | 1,887 | — | $11.295625 | $11.295625 | Both passed |
| p4-01 | 229 | $7.619981 | $0.630482 | $8.250463 | Native completed; fixed candidate 5 failed with `invalid_plan`, leaving no fixed selection |
| p4-02 | 472 | $10.672328 | $13.590601 | $24.262929 | Both generation arms completed |
| p4-03 | 63 | $1.166445 | $0 | $1.166445 | Native partial; no accepted c1/c2 or fixed output |
| **Total** | **2,651** | **$19.458754** | **$25.516708** | **$44.975462** | Assessment spend: **$0** |

Allocation totals are development **$11.295625**, confirmation inference **$33.679837**, assessment **$0**. These are usage-based public-PAYG accounting figures, not an invoice. Historical **$22.88** held liability remains separate; it is not spending by this attempt. The financial ceilings were not exhausted.

For p4-02, fixed inference cost **27.3443% more** than native inference, outside the prespecified ±20% per-pair matching band. That miss is retained as a result of the allocation rule. It was not the global halt trigger and does not establish quality or efficiency superiority. No case was discarded to improve matching.

The three started units are now recorded exposures. The pre-run eligibility manifest remains a historical freeze; the other 21 selected units were unopened. The [definition](PHASE4_COST_MATCHED_CONFIRMATION_DEFINITION.md), source identity and existing records remain unchanged.

## Confirmed stop cause

An optional `inv1` probe finished its twelve accounted requests with known failure `ranker_not_finished`. Native Harness² intentionally writes the failed probe's `rollout.md` and omits `produced.md`. Our C1 context layout nevertheless required `pool/inv1/produced.md` unconditionally. Its inventory check found **38 actual files versus 39 expected**, with that sole missing path and no size/path anomaly, and escalated it to `c1_contract_input_violation`.

This was a false escalation by our adapter of a legitimate optional-failure representation. Once the durable global halt existed, the controller correctly obeyed it. The independent closure audit reproduced the rejection with one invocation of the frozen validator; the saved input inventory hash remained `bcd51c8e51a9ab8f507b72a32a5a13c28cd464a3067acd62146445f598fa7970`. Its original receipt hash and verdict are bound in the [outcome record](../../../evidence/phase4-cm1-v1/live-outcome-v1.json).

Relevant frozen paths are our [context contract](../../../followups/phase3b_seq2_v1/contract.py), [adapter](../../../followups/phase3b_seq2_v1/adapter.py), [native wrapper](../../../followups/phase3b_seq2_v1/native.py) and [controller](../../../followups/phase4_cm1_v1/workflow.py), together with [upstream failed-candidate context handling](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/harness2/core/context.py#L319-L332). No source or upstream fix was performed.

## Preserved work and closure evidence

The independent audit reconciled all five child accounting/provenance chains and verified all **207 effective inputs unchanged**, under source `618834cb1d4c0ce9bfd3edbe71aa0225c7a949b0a2b6fd1a4b00dbef529155e7`, study `13b9273ca9e0f7bd79d98cb8013429753cebe6341919c006a32e2fd67236f421`. Accepted selections remain saved for the first two units. Without judgments, no quality/order decomposition, selection gain, distinctness comparison or benefit from edits/KEEP can be estimated.

Both passive Inspect exports passed: [first pair](../../../evidence/phase4-cm1-v1/inspect-first-pair-live-v1.json) and [closure](../../../evidence/phase4-cm1-v1/inspect-closure-live-v1.json). Closure preserves 24 cases, 764 dated imported events and actual model usage. Two cases have saved outputs, one of them lacks the fixed output. The 22 missing-output cases include the failed started case and 21 unopened cases. Official scores remain absent. Both SDK-free exports made zero model/network calls and preserved their input snapshots; no server or alternate UI route was started. Raw output/viewer bundles remain local.

The provider controller is absent. Reported launcher metadata records an exited state and exit code zero, with no retained launcher streams; this does not make the scientific study successful. Its credential function's `finally` cleanup clears in-memory key variables. The visible parent PowerShell window may remain open. No key material was read for this report.

**Full saved-report replay v3 passed**, keyless and network-disabled with read-only saved inputs. The existing report path reconstructed source, costs, journals and native/fixed provenance and returned the same stopped outcome: 2,651 requests/$44.975462/new held liability zero, with zero new provider calls. This verifies the stopped run, not scientific completion. See the [replay receipt](../../../evidence/phase4-cm1-v1/saved-closure-replay-v3.json) and [root closure verification](../../../evidence/phase4-cm1-v1/root-closure-verification-v1.json). The two earlier $0 wrapper failures at import/configuration and runtime-environment setup remain preserved; no production source fix was made for them.

One already-exposed `dev02` prompt was accidentally displayed once during early review, as disclosed in the audit. That incident did not display held-out/provider content. The prior [offline acceptance](../../../evidence/phase4-cm1-v1/offline-acceptance-v1.json), 106-test collector, 89-test public compatibility and static checks remain historical engineering evidence; they did not cover this legitimate failed-probe context. No repository CI workflow or remote-CI-green claim is added.

## Next action

The proposed next step is a focused offline compatibility repair for this exact optional-failure context, followed by replay of the saved failing context and saved successful contexts. Preserve mandatory checkpoint, provenance and financial guards; do not fabricate a missing deliverable. This repair has not been implemented, and no new block, restart or paid continuation is authorized by this report.
