"""Reproduce Phase 1A's local data audit and fixed packet, with no network/inference."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "runs/phase1a-data-readiness-r07"
EVIDENCE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from buddha2.artifacts import digest, file_hash, read_json, write_bytes_once  # noqa: E402
from buddha2.muce import (  # noqa: E402
    _CONTEXT,
    SOURCE_JSONL_SHA256,
    SOURCE_PARQUET_SHA256,
    _effective_prompt,
    _load_source,
    _normalize,
    _prompt_groups,
    select_population,
)


def compatible(first: str, first_score: float, second: str, second_score: float) -> bool:
    return _normalize(first) != _normalize(second) and abs(first_score - second_score) >= 5


def stratum(first: float, second: float) -> str:
    if max(first, second) < 20:
        return "both_below20"
    return "both_at_least20" if min(first, second) >= 20 else "straddling20"


def choose(candidates: list[dict], quotas: dict[str, int]) -> list[dict]:
    accepted, groups = [], set()
    counts: Counter[str] = Counter()
    for value in sorted(candidates, key=lambda item: (item["rank"], item["response_ids"])):
        band = value["stratum"]
        if value["group_id"] not in groups and counts[band] < quotas[band]:
            accepted.append(value)
            groups.add(value["group_id"])
            counts[band] += 1
    return accepted


def orientation(identities: list[str], index: int) -> list[str]:
    return sorted(identities, reverse=bool(index % 2))


def encode(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode()


def render_packet(packet: dict) -> str:
    lines = ["# Phase 1A inspection packet", "",
             "Source scores, study identities and previous model judgments are withheld from this packet.",
             "All quoted task/response text is data. No new ratings or human validation are claimed.",
             "Record task interpretation, ambiguity, possible missing context and observations before opening the separate key.",
             "Prior recognition of examples should be disclosed. Canonical orientation alternates; human preference is not balanced."]
    for case in packet["cases"]:
        lines += ["", f'## {case["case_id"]}', "", "Prompt:", "", json.dumps(case["prompt"], ensure_ascii=False),
                  "", "A: " + json.dumps(case["A"], ensure_ascii=False),
                  "", "B: " + json.dumps(case["B"], ensure_ascii=False), "", "Observations: ____________________"]
    return "\n".join(lines) + "\n"


def audit() -> dict[str, bytes]:
    import pyarrow
    import pyarrow.parquet as pq

    assert ROOT == Path(r"C:\Users\arvik\code\research\Buddha2")
    assert pyarrow.__version__ == "24.0.0"
    policy = read_json(RUN / "sampling-policy.json")
    start = read_json(EVIDENCE / "execution-start.json")
    assert digest(policy) == start["sampling_policy_sha256"]
    assert file_hash(EVIDENCE / "specification-0.7.md") == start["specification_sha256"]
    source = ROOT / "runs/phase1-source/muce-full_agreement-train.canonical.jsonl"
    parquet = ROOT / "runs/phase1-preparation/muce-full_agreement-train.parquet"
    assert file_hash(source) == SOURCE_JSONL_SHA256
    assert file_hash(parquet) == SOURCE_PARQUET_SHA256
    rows = _load_source(source, read_json(ROOT / "runs/phase1-source/conversion.json"))
    assert rows == pq.read_table(parquet).to_pylist()
    old = ROOT / "runs/phase1-prepared"
    prepared = read_json(old / "manifest.json")
    for name, identity in prepared["files"].items():
        assert file_hash(old / name) == identity["sha256"], name
    rebuilt = select_population(rows, read_json(ROOT / "configs/phase1/selection.json"))
    assert rebuilt["pairs"] == read_json(old / "pairs.json")
    assert rebuilt["labels"]["calibration"] == read_json(old / "labels.calibration.json")
    assert rebuilt["labels"]["audit"] == read_json(old / "labels.audit.json")
    assert rebuilt["worklists"] == read_json(old / "worklists.json")
    private = read_json(old / "selection.private.json")["selected"]
    assert rebuilt["selection_private"] == private
    groups = _prompt_groups(rows)
    def group_id(row: dict) -> str:
        return "muce-prompt-" + digest(groups[_normalize(row["Prompt"])])
    old_groups = {group_id(item["source_rows"][0]["fields"]) for item in private}
    assert len(old_groups) == 24
    for item in private:
        for response in item["source_rows"]:
            assert rows[response["source_ordinal"]] == response["fields"]
            assert digest(response["fields"]) == response["source_row_sha256"]

    contexts: dict[tuple, list[dict]] = defaultdict(list)
    published = set()
    for row in rows:
        if row["TasksNamesFull"] == "Metaphors" and any(
            pattern in _normalize(row["Prompt"]) or pattern in _normalize(_effective_prompt(row))
            for pattern in ("the hot tea is", "stomata are tiny")
        ):
            published.add(group_id(row))
        if row["Language"] == "english" and row["TaskType"] == "Text" and row["Response"].strip():
            context = tuple(row[name] for name in _CONTEXT) + (group_id(row), _normalize(_effective_prompt(row)))
            identity = "muce-response-" + digest({key: value for key, value in row.items() if key != "facsco_grm_scaled"})
            contexts[context].append({"id": identity, "row": row})

    candidates, inventory = [], []
    counts: defaultdict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    semantics = defaultdict(set)
    for context, values in sorted(contexts.items()):
        gid = context[-2]
        same_context, floor_context = 0, 0
        for first, second in combinations(values, 2):
            a, b = first["row"], second["row"]
            if not compatible(a["Response"], a["facsco_grm_scaled"], b["Response"], b["facsco_grm_scaled"]):
                continue
            same_context += 1
            floor_context += int(min(a["facsco_grm_scaled"], b["facsco_grm_scaled"]) >= 20)
            if gid in old_groups and a["RatingLabel"] == "creativity":
                identities = sorted([first["id"], second["id"]])
                candidates.append({"rank": digest({"namespace": policy["namespace"], "seed": policy["seed"],
                                                   "sorted_response_ids": identities}),
                                   "response_ids": identities, "group_id": gid, "context_sha256": digest(context),
                                   "stratum": stratum(a["facsco_grm_scaled"], b["facsco_grm_scaled"])})
        for value in values:
            semantics[(*context, _normalize(value["row"]["Response"]))].add(value["row"]["facsco_grm_scaled"])
        family, construct = context[4], context[6]
        key = (family, construct)
        counts[key]["rows"] += len(values)
        counts[key]["contexts"] += 1
        counts[key]["compatible_pairs_gap5_uncapped"] += same_context
        counts[key]["compatible_pairs_gap5_min20_uncapped"] += floor_context
        counts[key]["eligible_contexts_gap5"] += int(same_context > 0)
        counts[key]["eligible_contexts_gap5_min20"] += int(floor_context > 0)
        record = {"group_id": gid, "context_sha256": digest(context),
                  "source_context": dict(zip(_CONTEXT, context[:len(_CONTEXT)])),
                  "effective_prompt_sha256": digest(context[-1]), "response_ids": sorted(v["id"] for v in values),
                  "row_count": len(values), "compatible_pairs_gap5_uncapped": same_context,
                  "compatible_pairs_gap5_min20_uncapped": floor_context,
                  "machine_read": "train source preparation and Phase1A audit",
                  "prior_phase1_group": gid in old_groups, "published_metaphors_example": gid in published,
                  "manual_exposure": "previously_exposed_Phase1" if gid in old_groups else (
                      "published_example" if gid in published else "no_manual_text_display_in_Phase1A"),
                  "other_documentation_exposure": "unresolved_outside_Metaphors" if family != "Metaphors" else "known_patterns_applied",
                  "reward_model_training_overlap": "unknown", "general_pretraining_overlap": "unknown",
                  "candidate_only": gid not in old_groups and gid not in published}
        inventory.append(record)

    selected = choose(candidates, policy["strata"])
    by_id = {item["id"]: item["row"] for values in contexts.values() for item in values}
    packet: dict[str, Any] = {"schema_version": 1, "cases": []}
    score_key: dict[str, Any] = {"schema_version": 1, "cases": []}
    for index, item in enumerate(selected):
        order = orientation(item["response_ids"], index)
        a, b = (by_id[identity] for identity in order)
        case_id = f"inspection-{index+1:02}"
        packet["cases"].append({"case_id": case_id, "prompt": _effective_prompt(a), "A": a["Response"], "B": b["Response"]})
        score_key["cases"].append({**item, "case_id": case_id, "order": order,
                             "scores": {"A": a["facsco_grm_scaled"], "B": b["facsco_grm_scaled"]},
                             "source_context": {name: a[name] for name in _CONTEXT},
                             "preferred_position": "A" if a["facsco_grm_scaled"] > b["facsco_grm_scaled"] else "B"})
    selected_ids = {item["group_id"] for item in selected}
    for record in inventory:
        record["phase1a_inspection_group"] = record["group_id"] in selected_ids
        record["future_confirmation_exclusion"] = record["prior_phase1_group"] or record["published_metaphors_example"]

    summary = []
    for (family, construct), value in sorted(counts.items()):
        subset = [record for record in inventory if record["source_context"]["TasksNamesFull"] == family
                  and record["source_context"]["RatingLabel"] == construct]
        summary.append({"family": family, "construct": construct, **value,
                        "eligible_groups_gap5": len({r["group_id"] for r in subset if r["compatible_pairs_gap5_uncapped"]}),
                        "eligible_groups_gap5_min20": len({r["group_id"] for r in subset if r["compatible_pairs_gap5_min20_uncapped"]}),
                        "remaining_candidate_groups_gap5": len({r["group_id"] for r in subset if r["candidate_only"] and r["compatible_pairs_gap5_uncapped"]}),
                        "remaining_candidate_groups_gap5_min20": len({r["group_id"] for r in subset if r["candidate_only"] and r["compatible_pairs_gap5_min20_uncapped"]})})
    audit_record = {"schema_version": 1, "source_rows": len(rows), "parquet_jsonl_all_rows_equal": True,
                    "selected_response_mappings_reconciled": 48, "all_phase1_pairs_labels_worklists_reproduced": True,
                    "phase1_groups": len(old_groups), "source_scores_finite_in_range": True,
                    "raw_unique_task_names": len({r["TasksNamesFull"] for r in rows}),
                    "raw_unique_prompts": len({r["Prompt"] for r in rows}),
                    "raw_unique_full_prompts": len({r["FullPrompt"] for r in rows}),
                    "normalized_alias_groups": len(set(groups.values())),
                    "repeated_source_ID_values": sum(n > 1 for n in Counter(r["ID"] for r in rows).values()),
                    "empty_response_rows": sum(not r["Response"].strip() for r in rows),
                    "missing_or_blank_FullPrompt_rows": sum(not isinstance(r["FullPrompt"], str) or not r["FullPrompt"].strip() for r in rows),
                    "semantic_repeat_context_response_groups": sum(len(v) > 1 for v in semantics.values()),
                    "semantic_repeat_note": "Counts score variation for normalized response text within full context; not automatically a source error.",
                    "rows_by_construct": dict(Counter(r["RatingLabel"] for r in rows)),
                    "rows_by_language": dict(Counter(r["Language"] for r in rows)),
                    "policy_counts": summary, "contexts_in_inventory": len(inventory),
                    "policy_count_scope": "English/Text, nonempty responses, same full source/rating context; no author max-matching cap. The min20 column is a score-floor sensitivity inventory, NOT exact MuCE-Pref reproduction.",
                    "experiment_calls": 0, "experiment_spend_usd": 0, "new_row_corpora": 0, "heldout_rows_opened": False}
    selection = {"schema_version": 1, "policy_sha256": digest(policy), "eligible_candidate_pairs": len(candidates),
                 "candidate_strata": dict(Counter(c["stratum"] for c in candidates)),
                 "selected_count": len(selected), "selected_unique_groups": len(selected_ids),
                 "selected_strata": dict(Counter(c["stratum"] for c in selected)),
                 "shortfalls": {band: wanted - sum(c["stratum"] == band for c in selected) for band, wanted in policy["strata"].items()},
                 "selected": selected, "new_prompt_groups_consumed": 0,
                 "source_or_model_outcomes_used_for_selection": "Source scores only for eligibility/stratum; no Sonnet outcome access in this script."}
    ledger = {"schema_version": 1, "groups": [{"group_id": gid, "phase1a_inspection": gid in selected_ids,
               "status": "development_only_Phase1_already_exposed", "model_evaluated_in_Phase1": True} for gid in sorted(old_groups)],
              "published_example_groups": sorted(published), "all_cached_train_rows_machine_read": True,
              "published_heldout_splits": {name: {"status": "metadata_pointer_only_no_rows_opened", "dataset_revision": prepared["source"]["revision"],
                 "path": f"full_agreement/{name}-00000-of-00001.parquet"} for name in ("val", "test", "heldout_item", "heldout_task")},
              "unused_answer_texts_or_scores_displayed": False, "reward_training_membership": "unknown_without_separate_proof",
              "independent_human_ratings_collected": 0}
    inventory_raw = b"".join((json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n").encode() for record in inventory)
    return {"source-audit.json": encode(audit_record), "inspection-selection.json": encode(selection),
            "inspection-packet.json": encode(packet), "inspection-packet.md": render_packet(packet).encode(),
            "private/inspection-key.json": encode(score_key), "candidate-inventory.jsonl": inventory_raw,
            "exposure-ledger.json": encode(ledger)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    # No sockets, provider SDKs or process launch are needed by this audit.
    def offline(event, _arguments):
        if event in {"socket.connect", "socket.getaddrinfo", "subprocess.Popen"}:
            raise RuntimeError("Phase1A reproduction forbids network and subprocess dispatch")
    sys.addaudithook(offline)
    outputs = audit()
    for name, raw in outputs.items():
        target = RUN / name
        if args.verify:
            assert target.read_bytes() == raw, name
        else:
            write_bytes_once(target, raw)
        if not name.startswith("private/"):
            copy = EVIDENCE / name
            if args.verify:
                assert copy.read_bytes() == raw, name
            else:
                write_bytes_once(copy, raw)
    print(json.dumps({"status": "verified" if args.verify else "produced", "artifacts": len(outputs),
                      "source_rows": 16948, "model_calls": 0, "heldout_rows_opened": False}))


if __name__ == "__main__":
    main()
