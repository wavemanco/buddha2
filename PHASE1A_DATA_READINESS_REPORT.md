# Phase 1A data-readiness report

Completed 2026-10-25 under frozen specification 0.7. Project: `C:\Users\arvik\code\research\Buddha2`.

**The checkpoint is complete. MuCE is usable for development against its published labels; it is not currently sufficient as the sole reference for claims about human agreement on new outputs.** CrPO measurement reproduction is conditional on explicitly resolving implementation, access and training-overlap questions. Recommend defining one small independent human-reference check next (Route H). No next route has started.

Experiment cost: **$0**. No new model, provider, token-count, embedding or local inference calls; no new human ratings, weights, dataset row corpora, dependencies or images. Published held-out answer/label contents remain unopened. The original Buddha2 folder was not accessed, used as a working directory, copied, mounted or changed. Preservation checks cover the new project's pre-existing evidence and upstream files, without probing the protected original.

## Decisions and permitted claims

| Intended use | Decision | What this permits / what remains missing |
|---|---|---|
| Development-only agreement with published MuCE labels | Ready for this limited use | Compare frozen evaluators against source-aware derived preferences on a declared development population. This measures agreement with released labels, not independent human validation, general creativity or transfer to another task family. Define models, reasoning settings, counts, decision rules and cost before calls. |
| CrPO measurement-only reproduction | Conditional | Public measurement code and a quality adapter are identifiable. A later slice must declare code-versus-formula fidelity, verify model access, terms, dependencies and compute, and distinguish reproduction from validation. Training membership is unknown. |
| Claims that a judge agrees with humans on new outputs | Not currently suitable as the sole reference | Individual rater records and final-label uncertainty are unavailable; some task instructions are transformed; one important source protocol remains unresolved. Independent reference evidence and transfer checks are needed before confirmation. |

The machine-readable decision record is [decisions.json](evidence/phase1a-data-readiness-r07/decisions.json). A conditional or negative validity decision satisfies this checkpoint; completion does not certify the dataset or any evaluator.

## Public releases are different artifacts

The user's distinction between original response records, SFT records and preference pairs is supported by pinned cards/metadata. These are different units, with potentially shared underlying responses.

| Release | Revision | Public primary split counts | Interpretation |
|---|---|---|---|
| [MuCE](https://huggingface.co/datasets/CNCL-Penn-State/MuCE/blob/a02181e394c41602a95d0678b0ce9d880e994289/README.md) | `a02181e394c41602a95d0678b0ce9d880e994289` | 16,948 train; 2,180 val; 2,004 test; 1,940 heldout_item; 187 heldout_task = **23,259** | Scored human response records. Only the existing train cache was read. |
| [MuCE-SFT](https://huggingface.co/datasets/CNCL-Penn-State/MuCE-SFT/blob/9b14581063a5e5fe2eb25bd78d94af790ca29166/README.md) | `9b14581063a5e5fe2eb25bd78d94af790ca29166` | 5,285; 669; 660; 415; 150 = **7,179** | Selected SFT conversation records, not another independent human study. Metadata only. |
| [MuCE-Pref](https://huggingface.co/datasets/CNCL-Penn-State/MuCE-Pref/blob/c586b786a08d29ef959bf5d4c3a3be67250842cd/README.md) | `c586b786a08d29ef959bf5d4c3a3be67250842cd` | 42,058; 4,880; 4,533; 3,521; 52 = **55,044** | Derived chosen/rejected pairs, not fresh direct human pairwise votes. Metadata only. |

MuCE-Pref also lists four sampled evaluation splits totaling 6,193 rows. Summing every named split gives 61,237 row references, not that many independent examples. The public original release does not establish release of the paper's advertised 245,030-response aggregate. The 14 task names and 195 prompt values were verified for the cached train split, not asserted for the entire advertised corpus. See [source semantics and release inventory](evidence/phase1a-data-readiness-r07/references/source-semantics.json).

## Integrity and the meaning of the scores

All **16,948** cached original train rows match between the pinned Parquet and its JSONL representation. All **48** historical selected-response mappings reconcile, and the Phase 1 pairs, labels and worklists reproduce exactly. No historical outputs were replaced. The source Parquet SHA-256 is `701ea8d6c0eeb20625d2809a96b5b377e2be22f28f0a22d1dfcafa820aa173ec`; the JSONL hash is `45c90e6a49b59b2cb6d5a48fb7818dac5cbfea2f6cb9c81b3dad9a85f91b0bde`.

The train population contains 7,532 creativity and 9,416 originality records. Those constructs remain separate. All are English. There are 647 absent/blank `FullPrompt` values, handled by the already frozen raw-prompt fallback. Source `ID` alone is unsafe as an identity: 2,983 source-ID values recur. Content/context identities reconcile uniquely. Nine normalized same-response/context groups carry more than one published score; that is a provenance caution, not automatically corruption. Detailed counts and policies are in [source-audit.json](evidence/phase1a-data-readiness-r07/source-audit.json).

The [CrPO paper](https://arxiv.org/html/2505.14442v2) describes rater selection and graded-response factor scoring, followed by independent rescaling within source subdatasets to integers 10–50. These scores are neither raw mean ratings nor a common ability scale across all sources. The release does not expose individual rater scores, retained-rater identities, final factor parameters or per-response uncertainty. A five-point gap is a curation rule, not a calibrated confidence interval. `full_agreement` does not supply direct votes on our newly constructed pairs. The paper's alpha 0.463 concerns a separate generated-output human study; it is not a reliability estimate for these MuCE labels.

For the 978 Metaphors creativity records, 647 are labeled `DiStefano2024crj_Meta` and 331 `MersealDissertation`. The first has a supported study-level association with [Automatic Scoring of Metaphor Creativity with Large Language Models](https://doi.org/10.1080/10400419.2024.2326343), but exact row-to-source-cohort lineage is unproved. Its original tasks involved remembered personal experiences. Public CrPO `prepare_full_prompt` constructs generic task instructions from concept labels: released `FullPrompt` is not established as the original participant or rater instruction. The original identity/instructions/rating procedure for `MersealDissertation` remain unresolved.

This creates a plausible criterion/context mismatch with an evaluator instructed to judge both originality and appropriateness. It does not show that source raters ignored appropriateness or that MuCE is generally unreliable. Source-study reliability mentioned in the documentary notes is not independently reconstructed for this final release. The cold reviewer did not independently verify the publisher's source-cohort ICC values; this report does not use them as a readiness gate.

## Pairing policy and available development material

The code review is pinned to CrPO commit [`9c0d71438687255b355216481064b1ced471ceeb`](https://github.com/mismayil/creative-preference-optimization/tree/9c0d71438687255b355216481064b1ced471ceeb). Its preference helper groups by task and `FullPrompt`; equality of source dataset, source scoring split and language is not enforced there. Rating-label equality is optional and defaults off. The paper specifies both scores at least 20, gap at least 5, and maximum matching 10. In code, that maximum caps accepted appearances per response index through greedy input order; it does not mean ten pairs per prompt.

Our inventory retains the full source/rating context and the same construct, excludes identical normalized responses, and counts all compatible pairs without the matching cap. Adding the score floor therefore gives a sensitivity inventory, **not an exact MuCE-Pref reproduction**. We did not silently pool separately scaled sources to imitate it.

| Metaphors creativity policy | Uncapped compatible pairs | Eligible normalized prompt groups | After known published-example exclusion | Remaining after all Phase 1 exclusions |
|---|---:|---:|---:|---:|
| Same source/context, gap ≥5 | 20,716 | 47 | 46 | 22 |
| Same source/context, both ≥20 and gap ≥5 | 1,887 | 41 | 40 | 22 |

The 22 groups are candidates, not untouched holdout material: every cached train row has been machine-read. Unused answer text/scores were not displayed for manual inspection. Exact membership in the released CrPO reward model's training data is unknown, and pretraining exclusion is unproved. No remaining train group can be advertised as an independent reward-model validation set on this evidence.

The [candidate inventory](evidence/phase1a-data-readiness-r07/candidate-inventory.jsonl) records 221 source contexts using IDs, hashes, context and counts without unused raw prompt/answer/score fields. The [exposure ledger](evidence/phase1a-data-readiness-r07/exposure-ledger.json) distinguishes existing Phase 1 exposure, published examples, machine-read train candidates, unknown reward-training overlap and metadata-only published held-out pointers.

## Bounded inspection: eight pairs, with the shortfall preserved

The [frozen sampling policy](evidence/phase1a-data-readiness-r07/sampling-policy.json) was recorded before displaying packet texts. It deterministically ranks candidate pairs using SHA-256, namespace `phase1a-inspection-v1`, seed 20261025 and sorted content IDs, then greedily accepts one pair per already exposed prompt group with four slots per score stratum. Selection does not read Sonnet outcomes. Display orientation alternates the canonical ID; it does not balance the preferred answer.

The 24 exposed groups contain 3,078 eligible pairs: 185 with both scores ≥20, 2,854 mixed-floor pairs, and 39 with both below 20. The frozen procedure selected **eight**: four high/high, four mixed, zero low/low. The low/low candidates occupy only two groups, so four unique low groups were impossible. Both groups had already been accepted as mixed earlier in the frozen ranking. The four low-stratum vacancies remain explicit; there was no quota redistribution, reranking, outcome-based resampling or consumption of new prompt groups. The specification permits a reported shortfall.

- [Inspection packet](evidence/phase1a-data-readiness-r07/inspection-packet.md): eight pairs without scores, source labels or old Sonnet judgments.
- [Private score key](runs/phase1a-data-readiness-r07/private/inspection-key.json): separate and intentionally untracked; its SHA-256 is `4deda3ec24f3df5a4aaeeb89cdc04aeadd5eb0cf88d9a5027624a43b69301202`.
- [Pre-key qualitative notes](evidence/phase1a-data-readiness-r07/inspection-notes.pre-key.json): bound to the packet before root key display. These are assistant-assisted analyst observations, not independent human ratings. Prior familiarity with some examples prevents a strict blindness claim.
- [Historical disagreement appendix](evidence/phase1a-data-readiness-r07/historical-disagreements.md): all eight old audit prompts without both-order human-label agreement, including saved reasoning. This appendix is explicitly selected by outcome and is separate from the deterministic inspection sample.

The examples show why criterion clarification matters. For tight jeans, “fitting” scores 11 and “not roomy” 22; for a dark night, “lonesome” scores 34 and “is a cloak of shadows” 45. Some orderings are easier to interpret than others under our rubric. Neither case inspection nor saved model disagreements can isolate a dataset error, model weakness or rubric mismatch, and neither supports a dataset-wide error-rate estimate. A score floor of 20 is not a semantic-validity test.

## CrPO measurements: identified, not executed

The [asset review](evidence/phase1a-data-readiness-r07/references/asset-metadata.json) records source captures, revisions, roles, access and license limits.

| Measurement role | Identified asset | Material limitation |
|---|---|---|
| Learned quality score | `CNCL-Penn-State/CrPO-RM-gemma-2-9b-it`, revision `a32828b8279a98065dba47da627e0cafcce8960b`, with required Gemma-2-9B instruction base | Public PEFT sequence-classification adapter; base-model access is gated. Exact reward-training membership and historical base revision are not bound by a member manifest. |
| Novelty/diversity | `jinaai/jina-embeddings-v3`, revision `ab036b023d30b4d1138c4c3bfa9f0c445ab455d6` | Reference/grouping and preprocessing matter; metadata declares CC-BY-NC-4.0. Nothing enabled or downloaded. |
| Surprise | `google/gemma-2-27b-it`, revision `aaf20e6b9f4c0fcf043f6fb2a2068419086d77b0` | Gated model; tokenization and scoring conditions matter. Perplexity is not Bayesian surprise. |

Three static fidelity choices must be declared before reproduction: select the paper's trained quality adapter rather than the evaluator CLI's Skywork default; distinguish code's whole-conversation perplexity from the paper's response-conditional description; distinguish code's factor-of-two novelty scaling from the written equation. These are source observations, not executed comparisons or proven impact estimates. Model cards alone cannot establish measurement equivalence for replacement models. No terms were accepted, weights fetched, hardware feasibility tested or authors contacted.

## Verification and completion criteria

| Frozen criterion | Completion evidence |
|---|---|
| D1A-1: Source and meaning | Pinned paper/code/cards, release inventory, source-study mapping and explicit unknowns in the two reference indexes. |
| D1A-2: Integrity and policy | All 16,948 rows and 48 historical mappings reconcile; construct/context rules and both eligibility policies counted. |
| D1A-3: Reproducible inspection | Frozen policy, exact eight-pair selection, separate key, notes and explicit four-pair shortfall. |
| D1A-4: Exposure and fresh candidates | Ledger and metadata-only inventory; zero new groups consumed; no false reward-training or pristine-holdout claim. |
| D1A-5: Use-specific decision | Ready / conditional / not-suitable decisions above, with prohibited claims and one next route. |
| D1A-6: Handoff and preservation | This report, packet, immutable evidence, replay, preservation record and closeout manifest. Zero experiment spend and no access to the protected original. |

The checkpoint added only its audit helper and three boundary tests under its evidence namespace; package, configurations and existing tests were unchanged. **29 relevant checks passed**: three sampling-rule checks and 26 frozen MuCE/pair regressions. Ruff, mypy and Bandit medium/high checks passed; Bandit retained low-severity assertion notes. These checks ran in the existing pinned Python 3.12 container with networking disabled, a read-only root and read-only new-project mount, no provider credentials forwarded, and bounded resources. See [checks-final.json](evidence/phase1a-data-readiness-r07/checks-final.json).

The all-row Parquet reconciliation uses the already installed host Python 3.13/PyArrow 24.0.0 reader. Deterministic replay recomputes seven output files and compares their bytes. From this project root, with the existing cache and private Phase 1 artifacts available:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B evidence/phase1a-data-readiness-r07/test_reproduce.py
python -B evidence/phase1a-data-readiness-r07/reproduce.py --verify
```

The helper forbids socket connections, DNS resolution and subprocess creation during audit execution. It is an audit utility, not a newly enabled evaluation or strategy plugin. Verification and preservation details are bound by [closeout.json](evidence/phase1a-data-readiness-r07/closeout.json); [manifest.json](evidence/phase1a-data-readiness-r07/manifest.json) hashes the handoff. Specification 0.7 remains byte-identical in [the archive](specifications/archive/phase-definitions-0.7.md) and [execution snapshot](evidence/phase1a-data-readiness-r07/specification-0.7.md). Current revision 0.8 records closure only; no criteria were changed to accommodate these findings.

## One next step: define Route H

Before selecting frontier evaluator/reasoning combinations against these labels, clarify what the reference judgments mean. The smallest useful proposal is **two independent human readers inspecting the same eight frozen pairs: 16 pairwise judgments with brief criterion notes**. No model calls or new data groups are needed. This would test whether a clear, intended task/rubric produces interpretable judgments on the identified cases; eight pairs cannot validate MuCE generally or establish transfer to newly generated outputs.

The next specification must settle rater availability/eligibility, exact original-versus-released task context, comparison instructions, tie/abstention handling, blinding and prior-recognition rules, how disagreements will be interpreted, a descriptive completion decision, human time/cost and authorization. No recruitment or rating has begun. If human review is unavailable, report that limitation and choose one separately defined route with narrower claims; do not launch F and C by default.

Route F remains a future development comparison of frontier models and supported reasoning settings. Route C remains a future measurement reproduction. Neither is discarded, and CrPO's additional dimensions remain relevant. Native benchmark evaluation with declared human checks is still an independent route for the larger project. Phase 2 and the actual upstream Harness² one-step and successive-refinement comparisons remain unstarted; this checkpoint has not changed the central base-model/fixed-strategy/adaptation question.
