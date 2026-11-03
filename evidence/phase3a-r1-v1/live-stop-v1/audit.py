"""Offline, standard-library audit of the stopped R1 journal; no provider imports."""
from collections import defaultdict
from decimal import Decimal, ROUND_CEILING
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STUDY = "44d12d6ff196a9481bd6106541ad62d8161fff50fa7a1fd6eef899df4f627012"
RUN = ROOT / "runs/phase3a-r1-v1" / STUDY / "live"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


raw = (RUN / "journal/events.jsonl").read_bytes()
assert raw.endswith(b"\n")
events = [json.loads(line) for line in raw.splitlines()]
previous = None
intents, results = {}, {}
roles = defaultdict(lambda: {"attempts": 0, "known": 0, "unknown": 0,
    "spent_micro_usd": 0, "reserved_micro_usd": 0})
cells = defaultdict(lambda: {"attempts": 0, "known": 0, "unknown": 0,
    "spent_micro_usd": 0, "reserved_micro_usd": 0})
tool_calls = 0
for index, event in enumerate(events, 1):
    assert event["index"] == index and event["previous_event_sha256"] == previous
    assert event["event_sha256"] == digest({k: v for k, v in event.items() if k != "event_sha256"})
    previous = event["event_sha256"]
    record = event["record"]
    assert record["study_sha256"] == STUDY and record["fixture"] is False
    slot = record["slot_id"]
    if event["kind"] == "intent":
        assert slot not in intents and record["request_sha256"] == digest(record["request"])
        intents[slot] = event
        request, role = record["request"], record["role"]
        opus = role in {"editor", "fixed_selector"}
        assert role in {"plan", "answer", "rank", "editor", "fixed_selector"}
        assert request["model"] == ("claude-opus-5" if opus else "claude-sonnet-5-5")
        assert request["thinking"] == {"type": "adaptive"}
        assert request["output_config"]["effort"] == ("high" if opus else "low")
        assert request["max_tokens"] == (16000 if opus else 4096)
        assert request["service_tier"] == "standard_only" and request["inference_geo"] == "global"
        for aggregate in (roles[role], cells[record["cell"]]):
            aggregate["attempts"] += 1
    else:
        assert event["kind"] == "result" and slot not in results and slot in intents
        intent = intents[slot]
        assert record["intent_sha256"] == digest(intent["record"])
        for field in ("request_sha256", "dispatch_id", "cell", "pair", "role"):
            assert record[field] == intent["record"][field]
        results[slot] = record
        if record["status"] == "unknown":
            assert record["response"] is None and record["spent_micro_usd"] is None
            assert record["reserved_micro_usd"] == intent["record"]["reservation"]["micro_usd"] == 11440000
            for aggregate in (roles[record["role"]], cells[record["cell"]]):
                aggregate["unknown"] += 1
                aggregate["reserved_micro_usd"] += record["reserved_micro_usd"]
            continue
        assert record["status"] == "response" and record["reserved_micro_usd"] == 0
        response, role = record["response"], record["role"]
        assert response["model"] == intent["record"]["request"]["model"]
        usage = response["usage"]
        assert usage["service_tier"] == "standard" and usage.get("inference_geo") in (None, "global")
        assert usage.get("speed") in (None, "standard") and not usage.get("server_tool_use")
        base, output, writes, reads = [usage[k] for k in ("input_tokens", "output_tokens",
            "cache_creation_input_tokens", "cache_read_input_tokens")]
        assert all(type(v) is int and v >= 0 for v in (base, output, writes, reads))
        cache = usage.get("cache_creation") or {}
        five, hour = cache.get("ephemeral_5m_input_tokens", 0), cache.get("ephemeral_1h_input_tokens", 0)
        assert five + hour == writes
        if role in {"editor", "fixed_selector"}:
            amount = (Decimal(base) * Decimal("5.5") + Decimal(five) * Decimal("6.875")
                + Decimal(hour) * 11 + Decimal(reads) * Decimal("0.55") + Decimal(output) * Decimal("27.5"))
        else:
            assert hour == 0
            amount = Decimal(base) * 2 + Decimal(five) * Decimal("2.5") + Decimal(reads) * Decimal("0.1") + Decimal(output) * 10
        cost = int(amount.to_integral_value(rounding=ROUND_CEILING))
        assert record["spent_micro_usd"] == cost
        assert record["input_tokens"] == base + writes + reads and record["output_tokens"] == output
        for aggregate in (roles[role], cells[record["cell"]]):
            aggregate["known"] += 1
            aggregate["spent_micro_usd"] += cost
        if role == "editor":
            for block in response["provider_response"]["content"]:
                if block["type"] == "tool_use":
                    assert block.get("caller") == {"type": "direct"}
                    tool_calls += 1

study = read(ROOT / "runs/phase3a-r1-v1/release-v1/study.json")
assert study["study_sha256"] == STUDY
source = study["source"]
assert len(source["files"]) == 149 and digest(source["files"]) == source["sha256"] == study["source_sha256"]
for name, expected in source["files"].items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
assert set(intents) == set(results) and len(events) == 182 and len(intents) == 91
known = sum(r["known"] for r in roles.values())
unknown = sum(r["unknown"] for r in roles.values())
spent = sum(r["spent_micro_usd"] for r in roles.values())
reserved = sum(r["reserved_micro_usd"] for r in roles.values())
assert (known, unknown, spent, reserved, tool_calls) == (90, 1, 1401860, 11440000, 13)
prior_path = ROOT / "evidence/phase3a-v1/live-stop-v1/cost-audit.json"
prior = read(prior_path)
assert prior["spent_micro_usd"] == 1293437 and prior["unknown"] == prior["reserved_micro_usd"] == 0
authority = read(ROOT / "evidence/phase3a-r1-v1/authorization.json")
assert hashlib.sha256(prior_path.read_bytes()).hexdigest() == authority["prior_cost_audit_sha256"]
assert not (RUN / "seals").exists() and not (RUN / "assessments").exists()
result = {
    "kind": "phase3a-r1-live-stop-cost-audit-v1", "passed": True, "fixture": False,
    "study_sha256": STUDY, "source_sha256": source["sha256"], "source_files_verified": 149,
    "journal_sha256": hashlib.sha256(raw).hexdigest(), "last_event_sha256": previous,
    "event_count": len(events), "attempts": len(intents), "known_requests": known,
    "unknown": unknown, "pending": 0, "spent_micro_usd": spent, "reserved_micro_usd": reserved,
    "role_accounting": dict(sorted(roles.items())), "cell_accounting": dict(sorted(cells.items())),
    "returned_editor_direct_tool_blocks": tool_calls,
    "unknown_slot": next(slot for slot, row in results.items() if row["status"] == "unknown"),
    "unknown_cause": "No retained response or typed exception; cause and actual charge unestablished.",
    "cost_basis": "usage-based-public-price-upper-bound-not-invoice",
    "cost_method": "Independent Decimal per-request recomputation using frozen category rates, rounded upward to micro-USD. Opus rates include the 1.1 geography envelope; output charged once.",
    "prior_known_requests": prior["known_requests"], "prior_spent_micro_usd": prior["spent_micro_usd"],
    "cumulative_attempts": prior["known_requests"] + len(intents),
    "cumulative_known_micro_usd": prior["spent_micro_usd"] + spent,
    "cumulative_known_plus_liability_micro_usd": prior["spent_micro_usd"] + spent + reserved,
    "unknown_reservation_is_confirmed_spend": False,
    "scientific_complete": False, "primary_scores": 0, "native_assessments": 0,
    "new_provider_calls": 0, "SDK_constructions": 0,
    "credential_binding_or_lock_contents_read": False, "original_folder_accessed": False,
}
target = Path(__file__).with_name("cost-audit.json")
encoded = (json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode()
if target.exists():
    assert target.read_bytes() == encoded
else:
    with target.open("xb") as stream:
        stream.write(encoded)
print(json.dumps({k: result[k] for k in ("passed", "attempts", "known_requests", "unknown",
    "spent_micro_usd", "reserved_micro_usd", "cumulative_known_micro_usd")}, sort_keys=True))
