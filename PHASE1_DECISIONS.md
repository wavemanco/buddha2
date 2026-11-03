# Phase 1 decisions and preparation record

2026-10-25, America/Los_Angeles. Applies only to `C:\Users\arvik\code\research\Buddha2`.

The user requested completion of Phase 1. Its reviewed definition has two checkpoints: an offline usable kit, then a separately authorized live evaluator audit. This record implements the first. No model/provider requests or spending have occurred. It does not amend historical Phase 0 decisions or evidence.

## Population revision before evaluator observation

The original specification 0.4 proposed four task families, all under overall creativity. The pinned source cannot supply that population: remaining eligible groups are 0 Alternate Uses, 0 Design Solutions, 1 Real-Life Creative Problem Solving and 46 Metaphors. Originality could support broader coverage but would change the construct.

Before pair allocation, the user chose: “Metaphors only: preserve overall creativity; select 24 prompts from 46 eligible groups.” The approved policy is `configs/phase1/selection.json`; specification 0.4 is preserved byte for byte in `specifications/archive/phase-definitions-0.4.md`. Revision 0.5 narrows applicability while retaining 24 groups, a 12/12 split, both orders, the audit floors and proposed budget.

The seed remains 20261024. Normalize Unicode NFKC, case and whitespace only for grouping; retain original text. Cluster normalized source/effective prompt aliases before allocation. Select groups, pairs, split and presentation order by distinct stable seeded hashes. Choose a pair independently of its score-gap magnitude, subject to a minimum five-point gap. Pair members share their full source/task/rating context. Balance the human-preferred identity's first presentation position within each stage.

Exclude published Metaphors examples using the frozen patterns `the hot tea is` and `stomata are tiny`. One otherwise eligible prompt group is excluded. Neither other public splits nor final method-confirmation material was opened. Reserve all selected groups from later confirmation.

## Source and preparation

Use only [MuCE full_agreement/train at the pinned revision](https://huggingface.co/datasets/CNCL-Penn-State/MuCE/tree/a02181e394c41602a95d0678b0ce9d880e994289). The Parquet SHA-256 is `701ea8d6c0eeb20625d2809a96b5b377e2be22f28f0a22d1dfcafa820aa173ec`. Its 16,948 rows are converted without filtering, rewriting fields or rescaling scores to canonical JSONL SHA-256 `45c90e6a49b59b2cb6d5a48fb7818dac5cbfea2f6cb9c81b3dad9a85f91b0bde`.

The already-installed host Python 3.13.12/PyArrow 24.0.0 reads the source Parquet as a preparation utility. The standard-library selector, evaluator and tests use the existing supported Linux/amd64 Python 3.12.15 image. No dependency installation, new image, Windows runtime port or model download was added. Reader versions, schemas, hashes and round-trip verification are retained in `runs/phase1-source/conversion.json`. `tools/muce_source.py` reproduces the conversion from the pinned cached source.

The [paper](https://arxiv.org/html/2505.14442v2) documents independently factor-scored source populations, min-max rescaling to 10–50 and a five-point preference margin. Pair only within one compatible source context; do not compare absolute source ratings across subdatasets. The observed `creativity` and `originality` labels remain separate. Public records do not expose individual raters or allow reconstruction of human interrater reliability.

Original source `ID` repeats even within task/prompt contexts. Preserve it and the original fields privately, and derive response identity from full score-free source/context/prompt/response content. Only a genuinely conflicting full-content rating identity is rejected. The frozen preparation contains 24 unique source and effective prompt groups.

The card declares MIT and supplies attribution. Original-source licensing/participant permissions were not independently re-audited; the card does not map `MersealDissertation` to its original publication/license. Source data remain a local cache. This checkpoint makes no public redistribution claim. Retain Ismayilzada et al. (2025), *Creative Preference Optimization*, arXiv:2505.14442, and the pinned card.

## Evaluator and execution

`pairs.py` defines a two-response contract separate from Phase 0 portfolios. A presentation binds pair content and response order. A judgment binds presentation, requested/returned model, exact rubric/settings, status, choice, reason, usage and known/unknown cost. Analysis preserves the fixed prompt denominator, reports coverage and Wilson intervals, and treats nondecisive outcomes as zero for acceptance floors.

`phase1_runner.py` uses installed Anthropic SDK 1.4.0 directly. `configs/phase1/profile.json` matches its fixed profile: exact `claude-sonnet-5-5`, medium effort, adaptive thinking, 2,048 output tokens including thinking, standard tier, explicit global inference geography, 8,000 counted input tokens and $2/$10 per million input/output tokens. Default API version is 2023-06-01; actual live compatibility is unverified. Official documentation and SDK source were checked; no model request was used for that verification.

One process executes sequentially under an OS-owned lock. Shared calibration/audit journals enforce 48 presentations, at most 52 attempts, at most four declared retries and two attempts per presentation. Each generation intent reserves 36,480 micro-USD before dispatch. Free count requests have separate intent/results. SDK retries are zero; proxies, redirects and ambient provider configuration are refused. The explicitly supplied key is used only in the live transport; no discovery from files or home directories occurs.

HTTP errors, including 429/529, currently stop with unresolved reservation: official error semantics do not prove zero charge. Automatic retry is exercised only by the explicitly unaccepted synthetic transport. Unknown delivery, usage, geography, speed, tier or cache billing stops expansion. Missing intent completion is not automatically redispatched. No billing reconciliation platform or arbitrary-crash exactly-once guarantee is introduced.

The $1.89696 maximum token-price calculation is conditional on counted/server token agreement and the declared tariff. The count endpoint is a pre-dispatch gate; unexpected actual usage can only be detected on return. The separate proposed $5 cap includes recorded liabilities and is not a spending target. Tax, account funding minima and operator time are excluded. Live verification remains necessary.

## Label and authority boundaries

Preparation reads source scores to construct eligible pairs and writes labels separately. `stage` copies only pair inputs, worklists, aggregate preparation identity and rubric into an immutable evaluator bundle. It does not copy labels, source rows or private selections.

`phase1.ps1` leaves Phase 0's launcher intact. Offline execution is network-disabled and credential-free. A future live invocation requires `live -Live -LiveRun NAME`, and mounts only `src` read-only plus the staged run writable. Thus raw data and both label files are absent from the critic container. No home, original-folder or credential-directory mount exists. First-party endpoint selection is enforced by the SDK client; OS-level domain-specific egress restriction is not claimed.

The first two calibration presentations form the readiness checkpoint. Repeating the command before a recorded readiness review does not expand it. A review binds those saved predictions and the run. Calibration then finishes to 24 presentations; analysis may open calibration labels. At most one rubric wording revision is frozen with calibration evidence. Audit inference requires that freeze, and later calls cannot change it. Audit analysis commits all 24 saved predictions before reading the separately held label file. Source hashes/code/image changes refuse reuse.

These are experimenter-held-out procedural controls, not protection against an adversarial operator modifying the application, cryptographic proof of human blinding, or evidence against public-data pretraining contamination.

## Scope and next checkpoint

No generator, reranker, native live Harness², recursive adaptation, second critic, training, new benchmark or supplementary CrPO/Bayesian-surprise scorer is added. Existing native Harness² and NoveltyBench sources remain unchanged. Later research phases keep their prior scope; a Metaphors screen does not validate a general creativity critic or a portfolio scorer. Phase 2 may use native protocol evaluation and declared human checks even if the MuCE critic fails.

Review the preparation report and exact rubric/profile, then obtain an applicable ceiling before any paid launch. After the first two live presentations, inspect the actual model, controls, parsing and usage before expansion. A failed audit may yield diagnostic-only scientific completion; broken accounting/transport remains incomplete. The offline checkpoint alone does not complete Phase 1.
