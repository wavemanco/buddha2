"""Nonauthor replay of the single saved RC1 demonstration; no dispatch path."""
import copy
import hashlib
import json
import sys
from pathlib import Path

from followups.inspect_visibility_i1.importer import block_execution

counts = block_execution()
process_attempts = []


def no_process(event, args):
    if event in {"subprocess.Popen", "os.system"}:
        process_attempts.append(event)
        raise RuntimeError("independent RC1 replay cannot launch a process")


sys.addaudithook(no_process)
from buddha2.artifacts import digest
from followups.phase3a_rank_contract_v1 import adapter
from followups.phase3a_v1.strategy import render_strategy_request

names = ("saved_parent.json", "strategy.json", "demonstration.json")
raw = {name: (Path("/inputs") / name).read_bytes() for name in names}
parent, strategy, demo = (json.loads(raw[name]) for name in names)
context = demo["prepared"]["mapping"]["context"]
prepared = adapter.prepare(parent, parent["task"], strategy, context)
assert prepared == demo["prepared"]
binding = adapter.synthetic_result_binding(prepared, demo["raw_reply"])
assert binding == demo["synthetic_result_binding"]
first = adapter.derive(parent, parent["task"], strategy, context, prepared, demo["raw_reply"], binding)
second = adapter.derive(parent, parent["task"], strategy, context, prepared, demo["raw_reply"], binding)
assert first == second == demo["derivation"]
assert first["status"] == "accepted" and first["eligible_live_result"] is False
assert first["synthetic"] is True and first["unscored"] is True and first["provider_calls"] == 0
indices = [2, 0, 1, 4, 3, 6, 5, 9, 7, 8]
assert first["canonical_output"]["responses"] == [parent["responses"][i] for i in indices]
legacy = render_strategy_request("rank", parent["task"], strategy, responses=parent["responses"])
restored = copy.deepcopy(prepared["request"])
body = json.loads(restored["messages"][0]["content"])
for entry, response in zip(body["responses"], parent["responses"], strict=True):
    assert entry["text"] == response["text"]
    entry["id"] = response["id"]
restored["messages"][0]["content"] = json.dumps(body, ensure_ascii=False)
assert restored == legacy
assert raw == {name: (Path("/inputs") / name).read_bytes() for name in names}
assert not any(counts.values()) and not process_attempts
report = {"kind": "p3a-rc1-independent-saved-replay-v1", "passed": True,
          "input_sha256": {name: hashlib.sha256(value).hexdigest() for name, value in raw.items()},
          "profile_sha256": adapter.PROFILE_SHA256, "map_sha256": prepared["mapping"]["sha256"],
          "request_sha256": digest(prepared["request"]), "derivation_sha256": digest(first),
          "canonical_output_sha256": first["canonical_output_sha256"],
          "renderer_delta_only_id_values": True, "all_response_fields_unchanged": True,
          "exact_saved_derivation_and_repeat": True, "inputs_unchanged": True,
          "model_network_attempts": counts, "subprocess_attempts": process_attempts,
          "provider_calls": 0, "live_execution_ready": False, "phase3a_scientific_complete": False}
with Path("/out/replay.json").open("x", encoding="utf-8") as stream:
    json.dump(report, stream, sort_keys=True, indent=2)
    stream.write("\n")
print(json.dumps({"passed": True, "provider_calls": 0, "derivation_sha256": digest(first)}))
