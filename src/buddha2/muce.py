"""Prepare a pinned MuCE development population without evaluator calls or label leakage."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .artifacts import ContractError, digest, file_hash, read_json, write_once
from .pairs import make_label, make_pair, make_presentation

SOURCE = {
    "dataset": "CNCL-Penn-State/MuCE",
    "revision": "a02181e394c41602a95d0678b0ce9d880e994289",
    "configuration": "full_agreement", "split": "train",
}
SOURCE_PARQUET_SHA256 = "701ea8d6c0eeb20625d2809a96b5b377e2be22f28f0a22d1dfcafa820aa173ec"
SOURCE_JSONL_SHA256 = "45c90e6a49b59b2cb6d5a48fb7818dac5cbfea2f6cb9c81b3dad9a85f91b0bde"
SOURCE_ROWS = 16948
SOURCE_SCHEMA = {
    "ID": "string", "Dataset": "string", "Set": "string", "DatasetsSplit": "string",
    "Language": "string", "Prompt": "string", "RatingLabel": "string", "Response": "string",
    "TasksNamesFull": "string", "TaskType": "string", "facsco_grm_scaled": "double",
    "FullPrompt": "string",
}
_POLICY_KEYS = {
    "schema_version", "selection_revision", *SOURCE, "construct", "seed", "min_margin",
    "families", "exposure_patterns", "aliases", "effective_prompt", "population_authorization",
}
_CONTEXT = ("Dataset", "Set", "DatasetsSplit", "Language", "TasksNamesFull", "TaskType", "RatingLabel")


def _normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _effective_prompt(row: dict) -> str:
    value = row["FullPrompt"]
    return value if isinstance(value, str) and value.strip() else row["Prompt"]


def _safe_path(path: Path) -> None:
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink() or (hasattr(ancestor, "is_junction") and ancestor.is_junction()):
            raise ContractError("linked preparation paths are not supported")


def validate_policy(policy: Any) -> None:
    if (
        not isinstance(policy, dict) or set(policy) != _POLICY_KEYS
        or type(policy.get("schema_version")) is not int or policy["schema_version"] != 1
        or policy.get("selection_revision") != "phase1-muce-v1"
        or any(policy.get(key) != value for key, value in SOURCE.items())
        or policy.get("construct") not in ("creativity", "originality")
        or type(policy.get("seed")) is not int or policy["seed"] != 20261024
        or type(policy.get("min_margin")) not in (int, float) or policy["min_margin"] != 5
        or policy.get("aliases") != {} or policy.get("effective_prompt") != "FullPrompt-or-Prompt"
        or not isinstance(policy.get("population_authorization"), str)
        or not policy["population_authorization"].strip() or len(policy["population_authorization"]) > 4000
    ):
        raise ContractError("unsupported or incomplete frozen MuCE selection policy")
    families, patterns = policy["families"], policy["exposure_patterns"]
    if (
        not isinstance(families, dict) or not families or not isinstance(patterns, dict)
        or set(patterns) != set(families)
    ):
        raise ContractError("family quotas and exposure rules must be explicit")
    total = 0
    for family, quotas in families.items():
        if (
            not isinstance(family, str) or not family.strip() or len(family) > 256
            or not isinstance(quotas, dict) or set(quotas) != {"calibration", "audit"}
            or any(type(count) is not int or count < 1 for count in quotas.values())
            or not isinstance(patterns[family], list)
            or any(not isinstance(value, str) or not value.strip() for value in patterns[family])
        ):
            raise ContractError("invalid family quota or exposure pattern")
        total += sum(quotas.values())
    if total > 24:
        raise ContractError("selection exceeds the Phase 1 prompt ceiling")


def _validate_rows(rows: Any) -> list[dict]:
    if not isinstance(rows, list) or not rows:
        raise ContractError("source requires nonempty original row records")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(SOURCE_SCHEMA):
            raise ContractError("source columns differ from the pinned MuCE schema")
        for name in SOURCE_SCHEMA:
            value = row[name]
            if name == "facsco_grm_scaled":
                if type(value) not in (int, float) or not math.isfinite(value) or not 10 <= value <= 50:
                    raise ContractError("source score must be finite in its documented 10-50 scale")
            elif name == "FullPrompt" and value is None:
                continue
            elif not isinstance(value, str) or "\x00" in value or len(value) > 100_000:
                raise ContractError("source contains an invalid text field")
        if any(not row[name].strip() for name in (*_CONTEXT, "ID", "Prompt")):
            raise ContractError("source identity or rating context is missing")
        if row["RatingLabel"] not in ("creativity", "originality"):
            raise ContractError("unknown source rating construct")
        identity = digest({name: value for name, value in row.items() if name != "facsco_grm_scaled"})
        if identity in seen:
            raise ContractError("duplicate or conflicting complete source response identity")
        seen.add(identity)
    return rows


def _load_source(source_jsonl: Path, metadata: Any) -> list[dict]:
    _safe_path(source_jsonl)
    try:
        if source_jsonl.stat().st_size > 30_000_000 or file_hash(source_jsonl) != SOURCE_JSONL_SHA256:
            raise ContractError("canonical MuCE train source hash mismatch")
    except OSError as exc:
        raise ContractError("unreadable canonical MuCE train source") from exc
    if (
        not isinstance(metadata, dict) or type(metadata.get("schema_version")) is not int
        or metadata["schema_version"] != 1
        or any(metadata.get(key) != value for key, value in SOURCE.items())
        or metadata.get("source_sha256") != SOURCE_PARQUET_SHA256
        or metadata.get("converted_sha256") != SOURCE_JSONL_SHA256
        or metadata.get("source_rows") != SOURCE_ROWS or metadata.get("converted_rows") != SOURCE_ROWS
        or metadata.get("source_schema") != SOURCE_SCHEMA
        or metadata.get("roundtrip_all_original_records_equal") is not True
        or metadata.get("opened_data_splits") != ["train"]
    ):
        raise ContractError("source conversion metadata is incompatible with the frozen train pin")
    try:
        with source_jsonl.open(encoding="utf-8") as stream:
            rows = [json.loads(line) for line in stream]
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError("invalid canonical MuCE source JSONL") from exc
    if len(rows) != SOURCE_ROWS:
        raise ContractError("pinned source row count mismatch")
    return _validate_rows(rows)


def _rank(policy: dict, purpose: str, value: Any) -> str:
    return digest({"selection_revision": policy["selection_revision"], "seed": policy["seed"], "purpose": purpose, "value": value})


def _pairs(rows: list[dict], margin: float):
    for first, second in itertools.combinations(rows, 2):
        if (
            _normalize(first["row"]["Response"]) != _normalize(second["row"]["Response"])
            and abs(first["row"]["facsco_grm_scaled"] - second["row"]["facsco_grm_scaled"]) >= margin
        ):
            yield first, second


def _prompt_groups(rows: list[dict]) -> dict[str, str]:
    """Cluster exact normalized raw or effective prompt identities before allocation."""
    parents: dict[str, str] = {}
    effective_to_raw: dict[str, str] = {}

    def find(value: str) -> str:
        while parents[value] != value:
            parents[value] = parents[parents[value]]
            value = parents[value]
        return value

    for row in rows:
        raw = _normalize(row["Prompt"])
        effective = _normalize(_effective_prompt(row))
        parents.setdefault(raw, raw)
        if effective in effective_to_raw:
            first, second = find(raw), find(effective_to_raw[effective])
            parents[max(first, second)] = min(first, second)
        else:
            effective_to_raw[effective] = raw
    return {value: find(value) for value in parents}


def select_population(rows: list[dict], policy: dict) -> dict:
    """Pure selector: no allocations or response labels are emitted on any quota shortfall."""
    validate_policy(policy)
    _validate_rows(rows)
    families = policy["families"]
    prompt_groups = _prompt_groups(rows)
    contexts: dict[tuple, list[dict]] = defaultdict(list)
    exposed: dict[str, set[str]] = {family: set() for family in families}
    source_counts: Counter[str] = Counter()
    for ordinal, row in enumerate(rows):
        family = row["TasksNamesFull"]
        if family not in families:
            continue
        group = prompt_groups[_normalize(row["Prompt"])]
        effective = _effective_prompt(row)
        if any(
            _normalize(pattern) in _normalize(row["Prompt"]) or _normalize(pattern) in _normalize(effective)
            for pattern in policy["exposure_patterns"][family]
        ):
            exposed[family].add(group)
        if row["RatingLabel"] != policy["construct"] or row["Language"] != "english" or row["TaskType"] != "Text":
            continue
        source_counts[family] += 1
        if not row["Response"].strip():
            continue
        identity = digest({name: value for name, value in row.items() if name != "facsco_grm_scaled"})
        context = tuple(row[name] for name in _CONTEXT) + (group, _normalize(effective))
        contexts[context].append({"ordinal": ordinal, "row": row, "identity": identity, "effective": effective})
    eligible: dict[str, dict[str, list[list[dict]]]] = {family: defaultdict(list) for family in families}
    context_counts: Counter[str] = Counter()
    for context, values in contexts.items():
        family, group = context[4], context[-2]
        if group not in exposed[family] and next(_pairs(values, policy["min_margin"]), None) is not None:
            eligible[family][group].append(values)
            context_counts[family] += 1
    groups_to_families: dict[str, set[str]] = defaultdict(set)
    for family, groups in eligible.items():
        for group in groups:
            groups_to_families[group].add(family)
    if any(len(values) > 1 for values in groups_to_families.values()):
        raise ContractError("cross-family prompt aliases require explicit resolution before selection")
    counts = {
        family: {
            "construct_rows": source_counts[family], "eligible_prompt_groups": len(eligible[family]),
            "eligible_context_groups": context_counts[family], "exposed_prompt_groups": len(exposed[family]),
            "required_prompt_groups": sum(quotas.values()),
            "shortfall": max(0, sum(quotas.values()) - len(eligible[family])),
        } for family, quotas in families.items()
    }
    worklists: dict[str, Any] = {
        "schema_version": 1, "kind": "pair-worklists",
        "calibration": {"pair_ids": [], "presentations": []},
        "audit": {"pair_ids": [], "presentations": []},
    }
    result: dict[str, Any] = {
        "status": "population_shortfall" if any(value["shortfall"] for value in counts.values()) else "prepared",
        "counts": counts, "pairs": [], "labels": {"calibration": [], "audit": []},
        "worklists": worklists, "selection_private": [],
    }
    if result["status"] != "prepared":
        return result
    chosen: dict[str, list[dict]] = {"calibration": [], "audit": []}
    for family, quotas in sorted(families.items()):
        ordered_groups = sorted(eligible[family], key=lambda group: _rank(policy, "group", group))
        offset = 0
        for stage in ("calibration", "audit"):
            for group in ordered_groups[offset:offset + quotas[stage]]:
                candidates = (pair for values in eligible[family][group] for pair in _pairs(values, policy["min_margin"]))
                first, second = min(candidates, key=lambda pair: _rank(policy, "pair", sorted(value["identity"] for value in pair)))
                ordered_rows = sorted((first, second), key=lambda value: value["identity"])
                pair = make_pair(
                    "muce-prompt-" + digest(group), ordered_rows[0]["effective"], family,
                    [{"id": "muce-response-" + value["identity"], "text": value["row"]["Response"]} for value in ordered_rows],
                )
                preferred = max(ordered_rows, key=lambda value: value["row"]["facsco_grm_scaled"])
                chosen[stage].append({"pair": pair, "preferred": "muce-response-" + preferred["identity"], "rows": ordered_rows})
            offset += quotas[stage]
    for stage, selected in chosen.items():
        selected.sort(key=lambda value: _rank(policy, "stage-order", value["pair"]["pair_id"]))
        preferred_first = {
            value["pair"]["pair_id"] for value in sorted(selected, key=lambda value: _rank(policy, "preferred-position", value["pair"]["pair_id"]))[:len(selected) // 2]
        }
        for value in selected:
            pair, preferred = value["pair"], value["preferred"]
            result["pairs"].append(pair)
            worklists[stage]["pair_ids"].append(pair["pair_id"])
            other = next(row["id"] for row in pair["responses"] if row["id"] != preferred)
            order = [preferred, other] if pair["pair_id"] in preferred_first else [other, preferred]
            worklists[stage]["presentations"].extend((make_presentation(pair, order), make_presentation(pair, list(reversed(order)))))
            source_rows = value["rows"]
            label_context = {name: source_rows[0]["row"][name] for name in _CONTEXT}
            label_context.update({
                **SOURCE, "construct": policy["construct"], "score_field": "facsco_grm_scaled",
                "scale": [10, 50], "minimum_margin": policy["min_margin"],
                "scores": {"muce-response-" + row["identity"]: row["row"]["facsco_grm_scaled"] for row in source_rows},
            })
            result["labels"][stage].append(make_label(pair, preferred, label_context))
            result["selection_private"].append({
                "pair_id": pair["pair_id"], "stage": stage, "source_prompt_group_sha256": digest(_normalize(source_rows[0]["row"]["Prompt"])),
                "source_rows": [{"source_ordinal": row["ordinal"], "source_row_sha256": digest(row["row"]), "response_id": "muce-response-" + row["identity"], "fields": row["row"]} for row in source_rows],
            })
    return result


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8")


def prepare_muce(source_jsonl: Path, metadata: dict, policy: dict, output_dir: Path) -> dict:
    """Validate the frozen source, prepare one population, and publish immutable sidecars."""
    validate_policy(policy)
    _safe_path(output_dir)
    rows = _load_source(source_jsonl, metadata)
    selected = select_population(rows, policy)
    records = {}
    if selected["status"] == "prepared":
        records = {
            "pairs.json": selected["pairs"], "worklists.json": selected["worklists"],
            "labels.calibration.json": selected["labels"]["calibration"],
            "labels.audit.json": selected["labels"]["audit"],
            "selection.private.json": {"schema_version": 1, "kind": "muce-selection-private", "source": SOURCE, "selected": selected["selection_private"]},
        }
    manifest = {
        "schema_version": 1, "kind": "muce-preparation", "status": selected["status"],
        "source": {**SOURCE, "jsonl_sha256": SOURCE_JSONL_SHA256, "parquet_sha256": SOURCE_PARQUET_SHA256, "rows": len(rows)},
        "policy_sha256": digest(policy), "policy": policy, "counts": selected["counts"],
        "selected_pairs": len(selected["pairs"]), "model_requests": 0,
        "files": {name: {"sha256": hashlib.sha256(_json_bytes(record)).hexdigest(), "access": "critic-input" if name in ("pairs.json", "worklists.json") else "separate-human-labels" if name.startswith("labels.") else "private-preparation"} for name, record in records.items()},
        "label_access": "Preparation read source ratings to construct eligible pairs; audit labels are separate and must not be mounted into critic execution.",
        "limitations": ["Public data; model-pretraining contamination cannot be excluded.", "Scale semantics follow the paper; individual rater scores are unavailable.", "Source IDs repeat; complete source context and content are retained privately."],
    }
    manifest_path = output_dir / "manifest.json"
    if manifest_path.exists():
        if read_json(manifest_path) != manifest:
            raise ContractError("prepared population identity differs; use a fresh output directory")
        for name, identity in manifest["files"].items():
            artifact = output_dir / name
            _safe_path(artifact)
            if not artifact.is_file() or file_hash(artifact) != identity["sha256"]:
                raise ContractError("completed preparation artifact is missing or corrupted")
        return manifest
    if output_dir.exists() and any(path.name not in records for path in output_dir.iterdir()):
        raise ContractError("preparation directory contains undeclared artifacts")
    for name, record in records.items():
        write_once(output_dir / name, record)
    write_once(manifest_path, manifest)
    return manifest
