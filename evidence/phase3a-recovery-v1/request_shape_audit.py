"""Read-only extraction of the stopped request; no inference or credential access."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDY = "44d12d6ff196a9481bd6106541ad62d8161fff50fa7a1fd6eef899df4f627012"
JOURNAL = ROOT / "runs/phase3a-r1-v1" / STUDY / "live/journal/events.jsonl"
SLOT = "p3a-01.adaptive.editor.dom1.a1.t06"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        allow_nan=False, separators=(",", ":")).encode()).hexdigest()


raw = JOURNAL.read_bytes()
assert hashlib.sha256(raw).hexdigest() == "86f4af3164aed3c09e20c0f21695f9515318d1d24eb2cc6f284b27e29251c6e5"
assert raw.endswith(b"\n")
events = [json.loads(line) for line in raw.splitlines()]
parent = None
for index, event in enumerate(events, 1):
    assert event["index"] == index and event["previous_event_sha256"] == parent
    assert event["event_sha256"] == digest({k: v for k, v in event.items() if k != "event_sha256"})
    parent = event["event_sha256"]
intent = next(e for e in events if e["kind"] == "intent" and e["record"]["slot_id"] == SLOT)
result = next(e for e in events if e["kind"] == "result" and e["record"]["slot_id"] == SLOT)
request = intent["record"]["request"]
assert digest(request) == intent["record"]["request_sha256"] == "0e136a2a2a92b9d6be91b41eef2288352b3d53ba038b86b9cf46eca63f29815e"
assert result["record"]["intent_sha256"] == digest(intent["record"])
assert result["record"]["status"] == "unknown" and result["record"]["response"] is None
last = request["messages"][-1]
assert last["role"] == "assistant" and len(last["content"]) == 1
assert last["content"][0]["type"] == "text"
note = last["content"][0]["text"]
assert note.startswith("CRITICAL - MAXIMUM STEPS REACHED") and len(note) == 765
assert hashlib.sha256(note.encode()).hexdigest() == "dd27eb87f2347972e29af2187fea9fa8498fdd012044a60c23179083806b685f"
assert request["model"] == "claude-opus-5" and request["thinking"] == {"type": "adaptive"}
known = [e["record"] for e in events if e["kind"] == "result"
    and e["record"]["slot_id"].startswith("p3a-01.adaptive.editor.dom1.a1.t")
    and e["record"]["status"] == "response"]
assert len(known) == 5
tools = [b for r in known for b in r["response"]["provider_response"]["content"] if b["type"] == "tool_use"]
assert len(tools) == 13 and all(b["name"] == "read" and b["caller"] == {"type": "direct"} for b in tools)
study = json.loads((ROOT / "runs/phase3a-r1-v1/release-v1/study.json").read_text(encoding="utf-8"))
for name, expected in study["source"]["files"].items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
audit = {
    "kind": "phase3a-r1-terminal-request-shape-audit-v1", "passed": True,
    "study_sha256": STUDY, "journal_sha256": hashlib.sha256(raw).hexdigest(),
    "event_count": len(events), "slot_id": SLOT,
    "intent_event_sha256": intent["event_sha256"], "request_sha256": digest(request),
    "model": request["model"], "thinking": request["thinking"],
    "message_count": len(request["messages"]), "last_role": last["role"],
    "last_content_types": [b["type"] for b in last["content"]],
    "terminal_note_characters": len(note), "terminal_note_utf8_sha256": hashlib.sha256(note.encode()).hexdigest(),
    "terminal_note_prefix": "CRITICAL - MAXIMUM STEPS REACHED",
    "preceding_known_editor_responses": len(known), "preceding_direct_read_tool_blocks": len(tools),
    "preceding_known_latency_seconds": [r["response"]["latency_seconds"] for r in known],
    "response_retained": False, "unknown_reserved_micro_usd": result["record"]["reserved_micro_usd"],
    "documented_prefill_incompatibility": True,
    "docs_checked_utc_date": "2026-10-29",
    "primary_source": "https://platform.claude.com/docs/en/api/errors#prefill-not-supported",
    "source_files_verified_unchanged": len(study["source"]["files"]),
    "actual_exception_or_charge_established": False,
    "limitation": "Observed request shape plus documented API rule; no real replay or recovered failure. Does not settle or release the unknown.",
    "provider_calls": 0, "SDK_constructions": 0, "credential_or_lock_contents_read": False,
    "original_folder_accessed": False,
}
target = Path(__file__).with_name("request-shape-audit.json")
encoded = (json.dumps(audit, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode()
if target.exists():
    assert target.read_bytes() == encoded
else:
    with target.open("xb") as stream:
        stream.write(encoded)
print(json.dumps({k: audit[k] for k in ("passed", "last_role", "terminal_note_characters",
    "documented_prefill_incompatibility", "actual_exception_or_charge_established", "provider_calls")}))
