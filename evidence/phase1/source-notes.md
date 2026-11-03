# MuCE train preparation: source and feasibility notes

No evaluator requests, pair selection, audit allocation or held-out file reads occurred in this preparation. Only the pinned `full_agreement/train` Parquet, dataset card and repository metadata were downloaded. Repository metadata lists the other split filenames; their data were not opened.

## Provenance

- Dataset: [CNCL-Penn-State/MuCE](https://huggingface.co/datasets/CNCL-Penn-State/MuCE/tree/a02181e394c41602a95d0678b0ce9d880e994289).
- [Exact train source](https://huggingface.co/datasets/CNCL-Penn-State/MuCE/resolve/a02181e394c41602a95d0678b0ce9d880e994289/full_agreement/train-00000-of-00001.parquet): 935,313 bytes; SHA-256 `701ea8d6c0eeb20625d2809a96b5b377e2be22f28f0a22d1dfcafa820aa173ec`.
- [Exact dataset card](https://huggingface.co/datasets/CNCL-Penn-State/MuCE/raw/a02181e394c41602a95d0678b0ce9d880e994289/README.md): SHA-256 `6df633265496dcc64622efac6150973914fde8e7c11bcd340a316988bb80e0f0`.
- [Revision metadata](https://huggingface.co/api/datasets/CNCL-Penn-State/MuCE/revision/a02181e394c41602a95d0678b0ce9d880e994289): downloaded before conversion; the mutable metadata response is retained locally and hashed, rather than treated as immutable content just because the revision is pinned.
- [CrPO paper, version 2](https://arxiv.org/html/2505.14442v2), particularly Section 4 and Appendices A/B, documents factor scoring, within-subdataset scaling and the five-point preference margin.

The canonical JSONL conversion retains all 16,948 source rows, original row order and original typed fields. No normalization, filtering, re-rating or added fields occurs. It has SHA-256 `45c90e6a49b59b2cb6d5a48fb7818dac5cbfea2f6cb9c81b3dad9a85f91b0bde`. The exact conversion code and environment are retained in `convert_muce_train.py` and `conversion.json`. Conversion round-trips every original row without differences. Host PyArrow 24.0.0 was already installed; no dependencies were installed.

## Eligibility result

Overall creativity and originality must remain separate constructs. At this pin, `RatingLabel` has only these two literal values. Scores are finite integer-valued doubles in the observed 10–50 range. The paper documents independently computed subdataset GRM factor scores, followed by min-max scaling; absolute values from different source contexts should not be compared. Public records do not include individual rater scores or counts, so agreement cannot be reconstructed independently.

| Family | Remaining eligible prompt groups, creativity | Remaining eligible prompt groups, originality |
|---|---:|---:|
| Alternate Uses of Objects Task | 0 | 10 |
| Design Solutions | 0 | 15 |
| Real-Life Creative Problem Solving | 1 | 8 |
| Metaphors | 46 | 10 |

Each candidate pair is within the same source dataset, source split, task, language, rating label and normalized effective prompt, with nonempty different responses and a score gap of at least five. Normalize NFKC, case and whitespace for grouping; retain original text. These are aggregate feasibility counts, not selected pairs or a frozen execution manifest. The originality counts, especially cross-source real-life scenarios, remain candidate counts pending explicit alias review if that alternative is chosen.

Metaphors has 54 creativity prompt/context groups before eligibility, 47 with an eligible pair, and 46 after excluding the published hot-tea example. All 46 remaining effective prompts are unique after the specified normalization. An additional punctuation-stripped collision check found no collisions among the original 54 prompt strings. Six eligible groups are from `DiStefano2024crj_Meta`, and 40 from `MersealDissertation` with `DatasetsSplit=MersealDissertationMetaphors_english`. No allocation has been made. FullPrompt is nonempty for all creativity-labeled rows in the source; the 647 missing FullPrompt values are all originality-labeled real-life problem-solving rows.

The original four-family overall-creativity plan is unassemblable. A 24-prompt metaphors-only creativity population is feasible as an explicitly revised, narrower population. An originality-only population could retain the four task families but changes the construct; it cannot silently replace overall creativity.

Public example exclusions use conservative normalized substring matching within the family: knife/rope for alternative uses; air-pollution/litter phrases for design; Becky/Clara scenario prefixes for real-life problems; hot-tea/stomata phrases for metaphors. The exact patterns are in `feasibility.json`. They cover paper Tables 10–14, with conservative exclusions for the additional Table 5 examples where present. Sentence Completion is outside the declared families. No individual response or human rating is reproduced in these notes.

## Identity constraint

Original `ID` is not a unique response identifier. There are 3,625 conflicting duplicate groups under Dataset/Set/DatasetsSplit/ID, and still 2,975 after adding task, language, rating label and Prompt. Both complete canonical source rows and complete textual source identities excluding score are unique across all 16,948 rows. Preserve original ID and every source context field; derive a response identity from the frozen source and full row digest, retaining the zero-based source ordinal. Expected ID reuse must not be mistaken for conflicting full-row identity.

## Attribution and license limits

The pinned dataset card declares MIT. No separate LICENSE file is listed in its revision metadata. Retain the card and citation: Ismayilzada, Laverghetta Jr., Luchini, Patel, Bosselut, van der Plas and Beaty (2025), *Creative Preference Optimization*, arXiv:2505.14442.

Appendix A states that crowdsourced contributors were asked whether they agreed to open-source release, and that OSF data came from associated peer-reviewed studies. The card does not give a row-to-original-license mapping. Individual original-source licenses and participant permissions were not independently re-audited; do not claim that the card proves every original source's redistribution terms. This is a local research cache, with no public redistribution decision.

For metaphors, the paper's task-level source list names DiStefano, Patterson and Beaty (2024), *Automatic Scoring of Metaphor Creativity with Large Language Models*, and Yu et al. (2024), *Exploring How Generating Metaphor via Insight Versus Analysis Affects Metaphor Quality and Learning Outcomes*. The latter corresponds to originality-labeled public rows. The card does not map `MersealDissertation` to a specific original publication or license; that provenance detail remains unresolved rather than being inferred from the filename. The metadata and aggregate report preserve the source identifier explicitly.
