"""Frozen, content-hidden confirmation intake; no generation or provider imports."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, cast

from buddha2.artifacts import ContractError, digest

SOURCE_PATH = Path(__file__).resolve().parents[2] / ".upstream/novelty-bench/data/wildchat-1k.jsonl"
SOURCE_SHA256 = "8534288089508df3f413c1151a58d5fa5bda9d8f8385ae2815384d4e310a54ca"
SOURCE_ROWS = 1000
SAMPLE_SIZE = 24


def _require(value: Any, message: str) -> None:
    if not value:
        raise ContractError(message)


def _hash(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _strings(values: Any, *, hashes: bool = False) -> set[str]:
    _require(isinstance(values, (list, tuple, set, frozenset)), "exclusions must be explicit collections")
    _require(all(_hash(v) if hashes else isinstance(v, str) and bool(v.strip()) and "\x00" not in v
                 for v in values), "invalid exclusion identity")
    return set(values)


def build_manifest(rows: list[dict], *, source_sha256: str, frozen_method_sha256: str,
                   exposure_inventory_sha256: str, excluded_source_ids: Any,
                   excluded_prompt_hashes: Any, exposure_coverage_complete: bool) -> dict:
    """Consume rows only after freeze; return identifiers/hashes, never task text."""
    _require(exposure_coverage_complete is True, "exposure coverage is not independently established")
    _require(source_sha256 == SOURCE_SHA256 and _hash(frozen_method_sha256)
             and _hash(exposure_inventory_sha256), "missing or foreign frozen intake identity")
    ids = _strings(excluded_source_ids)
    aliases = _strings(excluded_prompt_hashes, hashes=True)
    _require(isinstance(rows, list) and bool(rows), "frame must be a nonempty row list")
    seen: set[str] = set()
    groups: dict[str, list[dict]] = {}
    for row in rows:
        _require(isinstance(row, dict), "invalid frame row")
        task_id, prompt = row.get("id"), row.get("prompt")
        _require(isinstance(task_id, str) and bool(task_id.strip()) and len(task_id) <= 256
                 and "\x00" not in task_id and task_id not in seen, "invalid or duplicate source ID")
        _require(isinstance(prompt, str) and bool(prompt.strip()) and "\x00" not in prompt,
                 "invalid prompt input")
        task_id, prompt = cast(str, task_id), cast(str, prompt)
        seen.add(task_id)
        alias = digest(normalize(prompt))
        groups.setdefault(alias, []).append({"source_task_id": task_id,
            "prompt_sha256": digest(prompt), "normalized_prompt_sha256": alias})
    inventory, eligible = [], []
    for alias, members in groups.items():
        ordered = sorted(members, key=lambda r: r["source_task_id"])
        exposed_members = sorted(r["source_task_id"] for r in ordered if r["source_task_id"] in ids)
        reasons = (["known_source_id"] if exposed_members else []) + (["known_prompt_alias"] if alias in aliases else [])
        unit = ordered[0] | {"duplicate_source_ids": [r["source_task_id"] for r in ordered[1:]],
            "known_exposed_source_ids": exposed_members, "exclusion_reasons": reasons}
        # A duplicate cannot evade a known-ID exclusion by using another ID.
        if not reasons:
            unit["selection_rank_sha256"] = hashlib.sha256(
                ("P4-CM1-v1|" + unit["source_task_id"]).encode("utf-8")).hexdigest()
            eligible.append(unit)
        inventory.append(unit)
    passed = len(eligible) >= SAMPLE_SIZE
    selected = sorted(eligible, key=lambda r: (r["selection_rank_sha256"], r["source_task_id"]))[:SAMPLE_SIZE] if passed else []
    result = {"kind": "phase4-cm1-eligibility-manifest-v1", "source_sha256": source_sha256,
        "frozen_method_sha256": frozen_method_sha256, "exposure_inventory_sha256": exposure_inventory_sha256,
        "exposure_coverage_complete": True, "source_rows": len(rows), "unique_prompt_units": len(groups),
        "duplicate_rows_collapsed": len(rows) - len(groups), "excluded_prompt_units": len(groups) - len(eligible),
        "eligible_prompt_units": len(eligible), "eligibility_passed": passed,
        "status": "eligible" if passed else "insufficient_eligible_units", "selected_count": len(selected),
        "selected": selected, "inventory": sorted(inventory, key=lambda r: r["source_task_id"]),
        "selection_rule": "SHA256(UTF8(P4-CM1-v1| + exact source ID)), lexical-ID tie-break; first24",
        "limitations": "Exact normalized matching does not establish semantic independence or pretraining freshness."}
    return result | {"manifest_sha256": digest(result)}


def intake(source: Path, *, freeze: dict, exposure_audit_path: Path, eligibility_proof: dict) -> dict:
    """Verify accepted freeze and scope proof before opening the pinned corpus."""
    _require(isinstance(freeze, dict) and freeze.get("accepted") is True
             and _hash(freeze.get("method_sha256")) and freeze.get("source_sha256") == SOURCE_SHA256,
             "accepted method/source freeze required before corpus access")
    _require(isinstance(eligibility_proof, dict) and eligibility_proof.get("passed") is True
             and freeze.get("eligibility_proof_sha256") == digest(eligibility_proof),
             "independent eligibility proof does not match the freeze")
    audit_bytes = Path(exposure_audit_path).read_bytes()
    audit_hash = hashlib.sha256(audit_bytes).hexdigest()
    _require(audit_hash == freeze.get("exposure_inventory_sha256")
             == eligibility_proof.get("exposure_inventory_sha256"), "exposure inventory binding differs")
    try:
        audit = json.loads(audit_bytes.decode("utf-8"))
        exclusions = audit["known_exclusions"]
        historical = exclusions["historical_wildchat"]["aliases"]
        curated = exclusions["curated"]["aliases"]
        prior = exclusions["prior_synthetic_and_muce"]["aliases"]
        _require(audit.get("kind") == "phase4-cm1-exposure-audit-v1"
                 and len(historical) == 263 and len(curated) == 100 and len(prior) == 50,
                 "required exposure coverage is incomplete")
        excluded_ids = [r["source_task_id"] for r in historical] + [r["source_task_id"] for r in curated]
        excluded_hashes = [r["normalized_prompt_sha256"] for r in historical + curated] + prior
        _require(len({r["source_task_id"] for r in historical}) == 263
                 and len({r["source_task_id"] for r in curated}) == 100,
                 "duplicate source IDs cannot supply exposure coverage")
        _strings(excluded_ids)
        _strings(excluded_hashes, hashes=True)
    except (UnicodeError, ValueError, TypeError, KeyError):
        raise ContractError("exposure metadata is invalid") from None
    source = Path(source)
    _require(source.absolute() == SOURCE_PATH.absolute() and not any(p.is_symlink() for p in (source, *source.parents)),
             "intake source must be the exact pinned ordinary corpus path")
    raw = source.read_bytes()
    _require(hashlib.sha256(raw).hexdigest() == SOURCE_SHA256, "pinned corpus bytes differ")
    try:
        rows = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    except (UnicodeError, ValueError):
        raise ContractError("pinned corpus is not valid UTF-8 JSONL") from None
    _require(len(rows) == SOURCE_ROWS, "pinned frame row count differs")
    return build_manifest(rows, source_sha256=SOURCE_SHA256,
        frozen_method_sha256=freeze["method_sha256"], exposure_inventory_sha256=audit_hash,
        excluded_source_ids=excluded_ids, excluded_prompt_hashes=excluded_hashes,
        exposure_coverage_complete=True)
