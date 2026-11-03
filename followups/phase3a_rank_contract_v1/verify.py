"""Bounded RC1 offline demonstration and frozen acceptance inventory; no live route."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from followups.inspect_visibility_i1.importer import block_execution, decode
from followups.inspect_visibility_i1.paths import checked_path, lexical

INPUTS = ("saved_parent.json", "strategy.json", "historical_failure.json", "lineage.json",
          "fixture-inventory.json")
INVENTORY_SHA = "c4ccc6f2830f7122f604febfdf33028a0902e307e371aa9ad1bf75ad976dc878"


def main() -> None:
    import hashlib

    counts = block_execution()
    process_attempts: list[str] = []

    def no_process(event: str, args: tuple) -> None:
        if event in {"subprocess.Popen", "os.system"}:
            process_attempts.append(event)
            raise RuntimeError("RC1 fixtures cannot launch a subprocess")

    sys.addaudithook(no_process)
    # Only pure source contracts are imported after the execution guards.
    from buddha2.artifacts import ContractError, digest, write_once
    from followups.rank_format_v1.normalizer import normalize_rank

    from . import adapter, test_adapter

    source = Path("/inputs")
    output = checked_path(Path("/out"), Path("/out"))

    def data(name: str) -> dict:
        if name not in (*INPUTS, "manifest.json"):
            raise ContractError("undeclared RC1 input")
        path = checked_path(source / name, source)
        value = decode(path.read_bytes())
        if not isinstance(value, dict):
            raise ContractError("RC1 input must be a JSON object")
        return value

    manifest = data("manifest.json")
    before = {}
    for name in INPUTS:
        lexical(name)
        raw = checked_path(source / name, source).read_bytes()
        before[name] = hashlib.sha256(raw).hexdigest()
        if before[name] != manifest["inputs"][name]["file_sha256"]:
            raise ContractError("RC1 input bytes differ from the frozen manifest")
    if before["fixture-inventory.json"] != INVENTORY_SHA:
        raise ContractError("RC1 acceptance inventory changed")

    historical = data("historical_failure.json")
    old_result = normalize_rank(historical["raw_reply"], historical["original_ids"])
    if old_result != historical["expected"] or old_result["status"] != "rejected":
        raise ContractError("the saved failed rank did not retain its exact original rejection")
    historical_proof = {"case_id": "H01", "passed": True, "normalization": old_result,
                        "original_failed_result_changed": False, "provider_calls": 0,
                        "source_input_sha256": before["historical_failure.json"]}
    write_once(output / "historical-replay.json", historical_proof)

    summary = test_adapter.run_inventory(source, output)
    cases = decode((output / "cases.json").read_bytes())
    if not isinstance(cases, list):
        raise ContractError("RC1 case evidence must be a list")
    inventory = data("fixture-inventory.json")
    expected_ids = {row["id"] for row in inventory["new_cases"]}
    if (len(cases) != 76 or {row["id"] for row in cases} != expected_ids
            or not all(row["passed"] for row in cases)):
        raise ContractError("not every frozen RC1 case passed")

    parent, strategy = data("saved_parent.json"), data("strategy.json")
    if digest(parent) != manifest["parent_B_sha256"]:
        raise ContractError("saved B parent identity differs")
    context = {"study_sha256": parent["provenance"]["study_sha256"],
               "run_id": "rc1-synthetic-demonstration", "slot_id": "rc1-synthetic-rank-demonstration",
               "caller": "fixed-candidate", "synthetic": True}
    prepared = adapter.prepare(parent, parent["task"], strategy, context)
    raw_reply = json.dumps({"order": [adapter.LABELS[i] for i in [2, 0, 1, 4, 3, 6, 5, 9, 7, 8]]})
    binding = adapter.synthetic_result_binding(prepared, raw_reply)
    first = adapter.derive(parent, parent["task"], strategy, context, prepared, raw_reply, binding)
    replay = adapter.derive(parent, parent["task"], strategy, context, prepared, raw_reply, binding)
    if first != replay or first["eligible_live_result"] or first["status"] != "accepted":
        raise ContractError("synthetic demonstration/replay did not preserve its contract")
    write_once(output / "demonstration.json", {"prepared": prepared, "raw_reply": raw_reply,
               "synthetic_result_binding": binding, "derivation": first})
    write_once(output / "replay.json", {"byte_semantics_equal": True,
               "first_sha256": digest(first), "replay_sha256": digest(replay), "provider_calls": 0})

    after = {name: hashlib.sha256(checked_path(source / name, source).read_bytes()).hexdigest()
             for name in INPUTS}
    if before != after or any(counts.values()) or process_attempts:
        raise ContractError("input mutation or execution attempt during offline acceptance")
    proof = {"kind": "phase3a-rc1-offline-verification-v1", "passed": True,
             "profile": adapter.profile(), "profile_sha256": adapter.PROFILE_SHA256,
             "frozen_cases": 76, "historical_controls": 1, "inventory_sha256": INVENTORY_SHA,
             "case_result_sha256": hashlib.sha256((output / "cases.json").read_bytes()).hexdigest(),
             "summary": summary, "input_sha256": before, "inputs_unchanged": True,
             "model_network_attempts": counts, "subprocess_attempts": process_attempts,
             "provider_calls": 0, "api_spend": 0, "live_execution_ready": False,
             "phase3a_scientific_complete": False}
    write_once(output / "verification.json", proof)
    print(json.dumps({"passed": True, "cases": 77, "provider_calls": 0,
                      "profile_sha256": adapter.PROFILE_SHA256}, sort_keys=True))


if __name__ == "__main__":
    main()
