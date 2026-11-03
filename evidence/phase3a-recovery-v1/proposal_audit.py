"""Offline arithmetic for an unaccepted recovery proposal; no execution grant."""
from decimal import Decimal
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
definition = ROOT / "PHASE3A_RECOVERY_DEFINITION.md"
spec_path = ROOT / "specifications/phase3a-r1-v1.json"
spec = json.loads(spec_path.read_text(encoding="utf-8"))
prior = json.loads((ROOT / "evidence/phase3a-r1-v1/live-stop-v1/cost-audit.json").read_text(encoding="utf-8"))
assert prior["cumulative_known_micro_usd"] == 2695297 and prior["reserved_micro_usd"] == 11440000
carry = prior["cumulative_known_micro_usd"] + prior["reserved_micro_usd"]
new_total, new_first = 205860000, 50860000
assert carry + new_total == 219995297 <= 220000000
assert carry + new_first == 64995297 <= 65000000
assert new_total - 8 * 20000000 == 45860000
assert 23700000 <= new_first and 23700000 <= 45860000
assert 2 * 20000000 + 23700000 > new_first
adaptive = 48 + 3 * 2 * 8
fixed = 6 * 12 + 1
new_attempts = 4 * (adaptive + fixed) + 9 * 11
assert adaptive == 96 and fixed == 73 and new_attempts == 775
assert new_attempts + prior["cumulative_attempts"] == 952
assert adaptive + fixed + 3 * 11 == 202
scenarios = {}
for name in ("working", "heavier"):
    scenario = next(s for s in spec["scenarios"] if s["name"] == name)
    old = scenario["accounted_usd"]
    input_tokens, output_tokens = scenario["input_output_tokens_per_editor_turn"]
    per_call = (Decimal(input_tokens) * 5 + Decimal(output_tokens) * 25) * Decimal("1.1") / 1000000
    assert per_call * scenario["editor_http_calls_clean"] == Decimal(old["editor"])
    unchanged = sum(Decimal(old[k]) for k in ("strategy", "fixed_selector", "assessment"))
    editor = 12 * 8 * per_call
    first_other = Decimal(old["first_pair_including_anchor"]) - Decimal(old["editor"]) / 4
    values = {
        "editor_per_call": per_call, "editor_clean": editor,
        "unchanged_other_components": unchanged,
        "new_total_clean": unchanged + editor,
        "new_total_all_second_shapes": unchanged + 2 * editor,
        "new_first_including_duplicate": first_other + editor / 4,
        "new_first_all_second_shapes": first_other + editor / 2,
    }
    expected = ("18.13789", "27.11389", "4.69213") if name == "working" else ("54.61828", "82.07428", "14.69176")
    assert tuple(values[k] for k in ("new_total_clean", "new_total_all_second_shapes", "new_first_including_duplicate")) == tuple(map(Decimal, expected))
    scenarios[name] = {
        "editor_mean_input_output": [input_tokens, output_tokens],
        "turns_per_conversation": 8, "clean_conversations": 12,
        "quality_heads_per_assessment": scenario["heads_per_assessment"],
        "usd": {k: format(v, ".6f") for k, v in values.items()},
    }
record = {
    "kind": "phase3a-r2-proposal-arithmetic-audit-v1", "passed": True,
    "authorized": False, "implementation_started": False,
    "definition_sha256": hashlib.sha256(definition.read_bytes()).hexdigest(),
    "parent_specification_sha256": hashlib.sha256(spec_path.read_bytes()).hexdigest(),
    "historical_known_micro_usd": prior["cumulative_known_micro_usd"],
    "unresolved_historical_micro_usd": prior["reserved_micro_usd"],
    "carry_micro_usd": carry, "new_cap_micro_usd": new_total,
    "new_first_cap_micro_usd": new_first, "new_assessment_micro_usd": 45860000,
    "overlapping_first_assessment_micro_usd": 23700000,
    "combined_total_exposure_micro_usd": carry + new_total,
    "combined_checkpoint_exposure_micro_usd": carry + new_first,
    "new_attempt_ceiling": new_attempts, "prior_attempts": prior["cumulative_attempts"],
    "cumulative_attempt_ceiling": 952, "new_first_attempt_ceiling": 202,
    "equal_allowed_inference_vector": {"usd": 20, "http": 96, "input": 4000000, "output": 786432},
    "configured_adaptive_maximum_output": 48 * 4096 + 48 * 16000,
    "joint_output_limit_can_stop_earlier": True,
    "conditional_demand_not_forecast": scenarios,
    "assumptions": spec["scenario_assumptions"],
    "unknown_reconciled_or_released": False,
    "provider_calls": 0, "SDK_constructions": 0, "credential_contents_read": False,
    "original_folder_accessed": False,
}
target = Path(__file__).with_name("proposal-audit.json")
encoded = (json.dumps(record, indent=2, sort_keys=True) + "\n").encode()
if target.exists():
    assert target.read_bytes() == encoded
else:
    with target.open("xb") as stream:
        stream.write(encoded)
print(json.dumps({k: record[k] for k in ("passed", "authorized", "combined_total_exposure_micro_usd",
    "combined_checkpoint_exposure_micro_usd", "new_attempt_ceiling", "cumulative_attempt_ceiling")}))
