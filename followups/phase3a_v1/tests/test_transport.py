"""Real pinned SDK serialization and bounded failure evidence, without provider access."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
import httpx2

from buddha2.artifacts import ContractError, digest
from buddha2.phase2_dispatch import DirectSDKTransport
from followups.phase3a_v1 import accounting as a
from followups.phase3a_v1.tests.test_accounting import AUTHORITY, BINDINGS, STUDY, request, slots
from followups.phase3a_v1.transport import Transport, validate_failure

SECRET = "fixture-error-must-not-be-retained"


def message(body):
    return {"id": "msg_fixture", "type": "message", "role": "assistant", "model": body["model"],
        "content": [{"type": "text", "text": "Fixture response"}], "stop_reason": "end_turn",
        "usage": {"input_tokens": 80, "output_tokens": 24, "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0, "cache_creation": {"ephemeral_5m_input_tokens": 0,
                "ephemeral_1h_input_tokens": 0}, "service_tier": "standard", "inference_geo": "global"}}


def completion(body):
    return {"id": "chatcmpl_fixture", "object": "chat.completion", "created": 1, "model": body["model"],
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "Fixture grouping", "refusal": None},
                     "finish_reason": "stop"}], "service_tier": "default",
        "usage": {"prompt_tokens": 80, "completion_tokens": 24, "total_tokens": 104,
            "prompt_tokens_details": {"cached_tokens": 0}, "completion_tokens_details": {"reasoning_tokens": 3}}}


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="phase3a-r2-transport-")
        self.addCleanup(self.temporary.cleanup)
        self.journal = Path(self.temporary.name) / "journal"
        self.wire: list[dict] = []

    def transport(self, callback=None):
        def handle(req, module):
            body = json.loads(req.content)
            self.wire.append(copy.deepcopy(body))
            if callback is not None:
                return callback(req, body, module)
            payload = completion(body) if module is httpx else message(body)
            return module.Response(200, json=payload, headers={"x-request-id": "req_fixture", "request-id": "req_fixture"})
        value = Transport(anthropic_api_key="fixture-not-a-secret", openai_api_key="fixture-not-a-secret",
            http_transports={"anthropic": httpx2.MockTransport(lambda req: handle(req, httpx2)),
                             "openai": httpx.MockTransport(lambda req: handle(req, httpx))})
        self.addCleanup(value._anthropic.close)
        self.addCleanup(value._openai.close)
        return value

    def ledger(self, transport):
        return a.Ledger(self.journal, study_sha256=STUDY, slots=slots(), authority=AUTHORITY,
                        transport=transport, bindings=BINDINGS)

    def test_noneditor_wire_profile_and_normalization_equal_frozen_parent(self):
        transport = self.transport()
        for role in ("plan", "answer", "rank", "quality", "group"):
            with self.subTest(role=role):
                body = request(role)
                before = copy.deepcopy(body)
                first = transport.create(role, body)
                parent = DirectSDKTransport.create(transport, role, body)
                self.assertEqual({k: v for k, v in first.items() if k != "latency_seconds"},
                                 {k: v for k, v in parent.items() if k != "latency_seconds"})
                self.assertEqual(self.wire[-2:], [before, before])
                self.assertEqual(body, before)
                if role in {"quality", "group"}:
                    self.assertNotIn("service_tier", body)
                    self.assertNotIn("inference_geo", body)
                if role == "group":
                    for omitted in ("reasoning_effort", "max_tokens", "max_completion_tokens", "temperature", "seed"):
                        self.assertNotIn(omitted, body)
        self.assertEqual(transport._anthropic.max_retries, 0)
        self.assertEqual(transport._openai.max_retries, 0)
        self.assertEqual(transport._anthropic.timeout, 90.0)
        self.assertEqual(transport._openai.timeout, 90.0)

    def test_actual_sdk_typed_timeout_connection_and_status_hold_without_resend(self):
        for role in ("editor", "group"):
            for category in ("timeout", "connection", "provider_status"):
                with self.subTest(role=role, category=category):
                    self.journal = Path(self.temporary.name) / (role + category)
                    self.wire = []
                    def failed(req, body, module):
                        if category == "timeout":
                            raise module.ReadTimeout(SECRET, request=req)
                        if category == "connection":
                            raise module.ConnectError(SECRET, request=req)
                        return module.Response(429, json={"error": {"type": "rate_limit_error", "message": SECRET}},
                            headers={"request-id": "req_fixture_429", "x-request-id": "req_fixture_429", "unfiltered": SECRET})
                    transport = self.transport(failed)
                    ledger = self.ledger(transport)
                    slot = "p3a-01.adaptive.editor.inv1.a1.t01" if role == "editor" else "p3a-01.assessment.00.group"
                    result = ledger.dispatch(slot, role, request(role))
                    self.assertEqual(result["status"], "unknown")
                    self.assertEqual(result["failure"], {"category": category, "stage": "provider_call",
                        "status_code": 429 if category == "provider_status" else None,
                        "provider_request_id": "req_fixture_429" if category == "provider_status" else None})
                    self.assertIsNone(result["response"])
                    self.assertEqual(result["reserved_micro_usd"], a._reservation(role)["micro_usd"])
                    with self.assertRaises(a.LiabilityStop):
                        self.ledger(transport).dispatch(slot, role, request(role))
                    self.assertEqual(len(self.wire), 1)
                    self.assertNotIn(SECRET.encode(), (self.journal / "events.jsonl").read_bytes())
                    self.assertEqual(a.replay(self.journal)["results"][slot], result)

    def test_invalid_provider_request_id_and_error_body_are_not_retained(self):
        def failed(req, body, module):
            return module.Response(400, json={"error": {"message": SECRET}},
                headers={"request-id": "Bearer " + SECRET, "authorization": SECRET})
        result = self.ledger(self.transport(failed)).dispatch("p3a-01.adaptive.editor.inv1.a1.t01", "editor", request("editor"))
        self.assertEqual(result["failure"]["status_code"], 400)
        self.assertIsNone(result["failure"]["provider_request_id"])
        self.assertIsNone(result["response"])
        self.assertNotIn(SECRET.encode(), (self.journal / "events.jsonl").read_bytes())

    def test_sdk_success_conversion_failure_retains_safe_response_not_extra_error_body(self):
        def invalid(req, body, module):
            payload = message(body)
            payload.pop("stop_reason")
            payload["error"] = {"message": SECRET, "authorization": SECRET}
            return module.Response(200, json=payload, headers={"request-id": "req_fixture_conversion"})
        result = self.ledger(self.transport(invalid)).dispatch("p3a-01.adaptive.editor.inv1.a1.t01", "editor", request("editor"))
        self.assertEqual(result["failure"], {"category": "processing_error", "stage": "response_conversion",
            "status_code": None, "provider_request_id": "req_fixture_conversion"})
        self.assertEqual(result["response"]["provider_response"]["model"], "claude-opus-5")
        self.assertEqual(result["response"]["provider_response"]["usage"]["output_tokens"], 24)
        self.assertNotIn("error", result["response"]["provider_response"])
        self.assertEqual((result["status"], result["reserved_micro_usd"]), ("unknown", 11440000))
        self.assertNotIn(SECRET.encode(), (self.journal / "events.jsonl").read_bytes())

    def test_post_response_accounting_and_serialization_failures_keep_returned_response(self):
        for stage in ("accounting", "serialization"):
            with self.subTest(stage=stage):
                self.journal = Path(self.temporary.name) / stage
                transport = self.transport()
                ledger = self.ledger(transport)
                if stage == "accounting":
                    guarded = patch.object(a.am1, "account", side_effect=ValueError(SECRET))
                else:
                    original = a._wire
                    def fail_result(value):
                        if isinstance(value, dict) and "intent_sha256" in value and value.get("status") == "response":
                            raise ValueError(SECRET)
                        return original(value)
                    guarded = patch.object(a, "_wire", side_effect=fail_result)
                with guarded:
                    result = ledger.dispatch("p3a-01.adaptive.editor.inv1.a1.t01", "editor", request("editor"))
                self.assertEqual(result["failure"], {"category": "processing_error", "stage": stage,
                    "status_code": None, "provider_request_id": "req_fixture"})
                self.assertEqual(result["response"]["usage"]["output_tokens"], 24)
                self.assertEqual(result["response"]["provider_response"]["content"][0]["text"], "Fixture response")
                self.assertEqual((result["status"], result["reserved_micro_usd"]), ("unknown", 11440000))
                self.assertEqual(a.replay(self.journal)["status"], "blocked-unknown")
                self.assertNotIn(SECRET.encode(), (self.journal / "events.jsonl").read_bytes())

    def test_nonfinite_return_is_unknown_with_copy_stage_and_no_unsafe_response(self):
        transport = self.transport()
        original = transport.create
        def nonfinite(role, body):
            return original(role, body) | {"latency_seconds": float("nan")}
        with patch.object(transport, "create", side_effect=nonfinite):
            result = self.ledger(transport).dispatch("p3a-01.adaptive.editor.inv1.a1.t01", "editor", request("editor"))
        self.assertEqual(result["failure"]["stage"], "response_copy")
        self.assertEqual(result["failure"]["provider_request_id"], "req_fixture")
        self.assertIsNone(result["response"])
        self.assertEqual(result["reserved_micro_usd"], 11440000)
        self.assertEqual(len(self.wire), 1)

    def test_result_event_projection_matches_parent_encoding_and_exact_limit(self):
        directory = Path(self.temporary.name) / "encoder"
        directory.mkdir()
        events: list[dict] = []
        a._append_event(directory, "intent", {"fixture": True}, events)
        record = {"text": "Unicode é and newline\n"}
        projected = a._result_event_bytes(record, events)
        a._append_event(directory, "result", record, events)
        self.assertEqual((directory / "events.jsonl").read_bytes().splitlines(keepends=True)[-1], projected)
        record = {"text": ""}
        record["text"] = "x" * (2_000_000 - len(a._result_event_bytes(record, events)))
        self.assertEqual(len(a._result_event_bytes(record, events)), 2_000_000)
        a._append_event(directory, "result", record, events)
        record["text"] += "x"
        self.assertEqual(len(a._result_event_bytes(record, events)), 2_000_001)
        with self.assertRaises(ContractError):
            a._append_event(directory, "result", record, events)

    def test_oversized_sdk_success_or_postprocess_failure_persists_small_unknown_with_id(self):
        for postprocess_failure in (False, True):
            with self.subTest(postprocess_failure=postprocess_failure):
                self.journal = Path(self.temporary.name) / str(postprocess_failure)
                self.wire = []
                def oversized(req, body, module):
                    payload = message(body)
                    payload["content"][0]["text"] = "x" * (3 * 1024 * 1024)
                    return module.Response(200, json=payload, headers={"request-id": "req_fixture_oversized"})
                transport = self.transport(oversized)
                ledger = self.ledger(transport)
                slot = "p3a-01.adaptive.editor.inv1.a1.t01"
                if postprocess_failure:
                    with patch.object(a.am1, "account", side_effect=ValueError(SECRET)):
                        result = ledger.dispatch(slot, "editor", request("editor"))
                else:
                    result = ledger.dispatch(slot, "editor", request("editor"))
                self.assertEqual(result["failure"], {"category": "processing_error", "stage": "serialization",
                    "status_code": None, "provider_request_id": "req_fixture_oversized"})
                self.assertEqual((result["status"], result["reserved_micro_usd"]), ("unknown", 11440000))
                self.assertIsNone(result["response"])
                raw = (self.journal / "events.jsonl").read_bytes()
                lines = raw.splitlines(keepends=True)
                self.assertEqual(len(lines), 2)
                self.assertLessEqual(len(lines[-1]), 2_000_000)
                prefix = [json.loads(lines[0])]
                self.assertEqual(lines[-1], a._result_event_bytes(result, prefix))
                self.assertEqual(a.replay(self.journal)["results"][slot], result)
                self.assertEqual(a.replay(self.journal)["status"], "blocked-unknown")
                with self.assertRaises(a.LiabilityStop):
                    self.ledger(transport).dispatch(slot, "editor", request("editor"))
                self.assertEqual(len(self.wire), 1)
                self.assertNotIn(SECRET.encode(), raw)

    def test_metadata_schema_and_retained_request_identity_reject_coherent_tamper(self):
        transport = self.transport()
        ledger = self.ledger(transport)
        with patch.object(a.am1, "account", side_effect=ValueError(SECRET)):
            result = ledger.dispatch("p3a-01.adaptive.editor.inv1.a1.t01", "editor", request("editor"))
        for changed in (result["failure"] | {"exception": SECRET}, result["failure"] | {"category": []},
                        result["failure"] | {"status_code": True}, result["failure"] | {"provider_request_id": "unsafe\n"}):
            with self.assertRaises(ContractError):
                validate_failure(changed)
        path = self.journal / "events.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        rows[-1]["record"]["failure"]["provider_request_id"] = "req_other"
        rows[-1]["event_sha256"] = digest({k: v for k, v in rows[-1].items() if k != "event_sha256"})
        path.write_text("".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        with self.assertRaises(ContractError):
            a.replay(self.journal)

    def test_every_anthropic_role_rejects_final_assistant_before_intent_or_http(self):
        for role, slot in {"plan": "p3a-01.fixed.plan.00", "answer": "p3a-01.fixed.answer.00",
            "rank": "p3a-01.fixed.rank.00", "quality": "p3a-01.assessment.00.quality.00",
            "editor": "p3a-01.adaptive.editor.inv1.a1.t01", "fixed_selector": "p3a-01.fixed.fixed_selector.00"}.items():
            with self.subTest(role=role):
                self.journal = Path(self.temporary.name) / role
                self.wire = []
                body = request(role)
                body["messages"].append({"role": "assistant", "content": "Unsupported prefill"})
                before = copy.deepcopy(body)
                transport = self.transport()
                ledger = self.ledger(transport)
                with self.assertRaises(a.IntegrityStop):
                    ledger.dispatch(slot, role, body)
                self.assertEqual(a.replay(self.journal)["attempts"], 0)
                self.assertEqual(self.wire, [])
                self.assertEqual(body, before)


if __name__ == "__main__":
    unittest.main()
