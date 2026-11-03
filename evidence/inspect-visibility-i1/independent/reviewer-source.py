"""Independent I1 saved-log comparison; canonical fixture files are authoritative."""

import hashlib
import json
import sys
from pathlib import Path


attempts = []


def audit(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "urllib.Request"}:
        attempts.append(event)
        raise AssertionError("independent review forbids network")


sys.addaudithook(audit)
from inspect_ai.log import read_eval_log
from inspect_ai.model import Model, ModelAPI


def forbidden(*args, **kwargs):
    attempts.append("model-constructor")
    raise AssertionError("independent review forbids model construction")


Model.__init__ = forbidden
ModelAPI.__init__ = forbidden

pins = {
    "fixed-changed": {
        "result.json": "e8fe7baeea34943fccd1e45c3a57b13f527f128c0cda705ef4250453f6401b6f",
        "synthetic-wire.json": "b296dd8a889c8560ea215d0b36192e39adc3dd3028455625cdf1e7659125e91f",
    },
    "baseline-loss": {
        "result.json": "5f8386074c8841179a9c56282cf7ff1e1eb15920b369885e55b6ab9ec6ab47d7",
        "synthetic-wire.json": "de748c8de154f463bbd3e866e619617daef033f4edb85c85b78896ccb75ef342",
    },
}
checks = []
for case, files in pins.items():
    raw = {name: (Path("/inputs") / case / name).read_bytes() for name in files}
    for name, value in raw.items():
        assert hashlib.sha256(value).hexdigest() == files[name]
    result = json.loads(raw["result.json"])
    wire = json.loads(raw["synthetic-wire.json"])
    ok = case == "fixed-changed"
    assert result["passed"] is True
    assert result["native_reply_ok"] is ok
    previous = None
    for run in ("author-1", "author-2", "review-1", "review-2"):
        filename = Path("/logs") / run / f"{case}.eval"
        raw_log = read_eval_log(filename, resolve_attachments=False)
        log = read_eval_log(filename, resolve_attachments=True)
        assert log.eval.model == "none" and log.results is None
        assert log.status == ("success" if ok else "error")
        assert len(log.samples) == 1
        sample = log.samples[0]
        meta = sample.metadata
        assert sample.id == f"{case}/inv1.a1"
        assert sample.scores is None
        assert not sample.model_usage and not sample.role_usage
        assert meta["fixture_expectation_passed"] is True
        assert meta["native_reply_ok"] is ok
        assert meta["native_result"] == result
        assert meta["native_wire"] == wire
        assert meta["scientific_eligibility"] is False
        assert meta["assessment_presence"] == "absent"
        assert meta["origin_model"] == "claude-opus-5"
        assert meta["origin_role"] == "editor"
        assert meta["accounting"]["real_provider_calls"] == 0
        assert meta["accounting"]["real_api_spend"] == 0
        assert meta["accounting"]["synthetic_mock_calls"] == (11 if ok else 1)
        assert meta["accounting"]["recorded_synthetic_usage"] == [
            record["response"]["usage"] for record in wire["records"]
        ]
        for name, value in raw.items():
            assert raw_log.samples[0].attachments[f"{case}/{name}"].encode("utf-8") == value
        assert len(sample.events) == len(wire["records"])
        for event, record in zip(sample.events, wire["records"], strict=True):
            assert event.event == "info"
            assert event.data["imported_synthetic_native_call"] == record
            assert event.data["qualified_slot_id"] == f"{case}/{record['slot_id']}"
        if ok:
            final = "".join(block["text"] for block in wire["records"][-1]["response"]["content"]
                            if block["type"] == "text")
            assert meta["native_final_text"] == final
            assert sample.output.completion == final
            assert sample.error is None and log.error is None
            assert result["native_proof"]["effective_changed"] is True
            assert result["native_proof"]["normal_final"] is True
        else:
            assert meta["native_final_text"] is None
            assert not sample.output.choices
            assert sample.error.message == result["failure"]
            assert log.error.message == result["failure"]
            assert "not a recorded Python stack trace" in sample.error.traceback
            assert wire["native_relay"]["offline_error_detail"] in sample.error.traceback
            assert wire["native_relay"]["halted"] is True
            assert result["native_proof"]["decision_after_complete_evidence"] is False
            assert result["native_proof"]["verification_after_write"] is False
            assert len(wire["native_relay"]["offline_wire"]) == 2
        # Compare independent public-reader payloads, not the author's semantic proof.
        semantic = {
            "status": log.status,
            "eval": log.eval.model_dump(),
            "error": log.error.model_dump() if log.error else None,
            "metadata": meta,
            "output": sample.output.model_dump(),
            "attachments": {f"{case}/{name}": raw_log.samples[0].attachments[f"{case}/{name}"]
                            for name in raw},
            "events": [{"event": event.event, "data": event.data} for event in sample.events],
        }
        if previous is not None:
            assert previous == semantic
        previous = semantic
        checks.append({"case": case, "run": run, "exact_native_payload": True,
                       "exact_source_attachments": True, "native_status_and_missingness": True,
                       "no_invented_model_events_or_scores": True})

assert not attempts
proof = {"passed": True, "comparisons": checks, "source_sha256": pins,
         "zero_model_or_network_attempts": True, "api_spend": 0,
         "scope": "independent saved-log semantic/byte comparison only; not live or scientific evidence"}
Path("/out/saved-log-comparison.json").write_text(json.dumps(proof, sort_keys=True, indent=2) + "\n")
print(json.dumps({"passed": True, "saved_logs_compared": len(checks), "model_calls": 0}))
