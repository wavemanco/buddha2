from __future__ import annotations

import json
import tempfile
import unittest
import urllib.request
from pathlib import Path

from buddha2.artifacts import ContractError
from followups.phase3a_v1 import editor, strategy
from followups.phase3a_v1.support import RESULTS
from followups.phase3a_v1.transport import Transport


def message(content, stop="end_turn"):
    return {"id": "msg_offline_editor", "type": "message", "role": "assistant",
            "model": "claude-opus-5", "content": content, "stop_reason": stop, "stop_sequence": None,
            "usage": {"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 0,
                      "cache_creation_input_tokens": 0,
                      "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 0},
                      "service_tier": "standard", "inference_geo": "global"}}


class EditorTests(unittest.TestCase):
    def test_identical_local_http_retry_replays_one_settled_sdk_request(self):
        import httpx
        import httpx2
        calls, holds = [], []

        def handle(request):
            calls.append(json.loads(request.content))
            return httpx2.Response(200, json=message([{"type": "text", "text": "known settled reply"}]))

        transport = Transport(anthropic_api_key="fixture-not-a-secret", openai_api_key="fixture-not-a-secret",
            http_transports={"anthropic": httpx2.MockTransport(handle),
                             "openai": httpx.MockTransport(lambda _: self.fail("unexpected OpenAI request"))})
        def dispatch(slot, role, request):
            return {"status": "response", "response": transport.create(role, request)}

        raw = {"model": "claude-opus-5", "max_tokens": 16000, "thinking": {"type": "adaptive"},
               "output_config": {"effort": "high"}, "stream": True,
               "messages": [{"role": "user", "content": "fixture"}]}
        record: dict = {"fixture": True, "requests": []}
        with tempfile.TemporaryDirectory() as tmp, editor.relay(Path(tmp), dispatch, "fixture", record,
                lambda *args, **kwargs: holds.append((args, kwargs))) as url:
            payloads = []
            for _ in range(2):
                request = urllib.request.Request(url + "/messages", data=json.dumps(raw).encode(),
                    headers={"x-api-key": "fixture-not-a-secret", "Content-Type": "application/json"})
                with urllib.request.urlopen(request, timeout=5) as response:  # nosec B310: fixed loopback fixture relay
                    payloads.append(response.read())
        self.assertEqual(payloads[0], payloads[1])
        self.assertEqual(1, len(calls))
        self.assertEqual(1, len(record["requests"]))
        self.assertEqual(1, record["local_response_replays"])
        self.assertEqual([], holds)
        transport._anthropic.close()
        transport._openai.close()

    def test_tools_are_confined_before_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "context/harness").mkdir(parents=True)
            (root / "output").mkdir()
            allowed = root / "context/harness/systemprompt.md"
            editor.tool_boundary([{"type": "tool_use", "name": "write", "input": {
                "filePath": str(allowed), "content": "{}"}}], root)
            for name, path in (("read", "/proc/self/environ"), ("write", str(root / "opencode.json")),
                               ("edit", str(root / "context/harness/plugin.py")), ("bash", str(allowed))):
                with self.assertRaises(ContractError):
                    editor.tool_boundary([{"type": "tool_use", "name": name,
                        "input": {"filePath": path}}], root)
            (root / "link").symlink_to(Path("/proc"), target_is_directory=True)
            with self.assertRaises(ContractError):
                editor.tool_boundary([{"type": "tool_use", "name": "read", "input": {
                    "filePath": str(root / "link/self/environ")}}], root)

    def test_sse_preserves_thinking_and_tool_arguments(self):
        content = [{"type": "thinking", "thinking": "fixture thought", "signature": "fixture signature"},
                   {"type": "tool_use", "id": "tool_1", "name": "read", "input": {"filePath": "/tmp/data"},
                    "caller": {"type": "direct"}}]
        wire = editor.sse(message(content, "tool_use")).decode()
        self.assertIn("signature_delta", wire)
        self.assertIn("fixture signature", wire)
        self.assertIn("input_json_delta", wire)
        self.assertIn("message_stop", wire)
        starts = [json.loads(line.removeprefix("data: ")) for line in wire.splitlines()
                  if line.startswith("data: ") and json.loads(line.removeprefix("data: ")).get("type") == "content_block_start"]
        self.assertEqual(starts[1]["content_block"]["caller"], {"type": "direct"})

    @unittest.skipUnless(Path("/opt/phase3a-opencode").is_dir(), "requires the actual pinned OpenCode runtime")
    def test_actual_opencode_reads_and_writes_through_settled_tools(self):
        from followups.phase3a_v1.accounting import validate_request
        from followups.phase3a_v1.mocks import SDKMock
        with SDKMock() as mock, tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            strategy.materialize_seed(root / "input/harness")
            holds = []

            def dispatch(slot, role, request):
                frozen_tools = json.loads((strategy.ROOT / "followups/phase3a_v1/editor-tools.json").read_text())
                validate_request(role, request, editor_tools=frozen_tools)
                mock.transport.select(role, slot)
                response = mock.transport.create(role, request)
                return {"status": "response", "response": response, "slot_id": slot}

            prop = editor.AccountedProposer(pilot="p3a-01", study_sha256="b" * 64,
                dispatch=dispatch, audit_dir=root / "audit", fixture=True,
                halt=lambda *args, **kwargs: holds.append((args, kwargs)))
            try:
                reply = prop.call("Edit the declared strategy and report completion.", root / "input",
                                  "inv1.a1", harvest="context/harness", max_attempts=1)
            except Exception:
                self.fail(json.dumps(prop.phase3a_evidence(), ensure_ascii=False))
            self.assertEqual([], holds)
            self.assertEqual(3, mock.http_calls)
            returned_calls = [block for block in mock.records[0]["response"]["content"] if block["type"] == "tool_use"]
            echoed_calls = [block for message in mock.records[1]["request"]["messages"]
                            if message["role"] == "assistant" and isinstance(message["content"], list)
                            for block in message["content"] if block["type"] == "tool_use"]
            self.assertTrue(returned_calls)
            self.assertEqual({block["id"] for block in returned_calls}, {block["id"] for block in echoed_calls})
            for returned in returned_calls:
                echoed = next(block for block in echoed_calls if block["id"] == returned["id"])
                self.assertEqual(returned["caller"], {"type": "direct"})
                self.assertEqual({key: echoed[key] for key in returned}, returned)
            self.assertNotEqual(strategy.validate_harness(root / "input/harness")["effective_strategy_sha256"],
                                strategy.validate_harness(reply.workspace)["effective_strategy_sha256"])
            self.assertEqual("valid", prop.phase3a_evidence()["sessions"]["inv1.a1"]["status"])

    @unittest.skipUnless(Path("/opt/phase3a-opencode").is_dir(), "requires the actual pinned OpenCode runtime")
    def test_actual_native_proposer_opencode_sdk_mock_and_resume(self):
        import httpx
        import httpx2
        records = []

        def handle(request):
            body = json.loads(request.content)
            records.append(body)
            return httpx2.Response(200, json=message([{"type": "text", "text": "The supplied harness is retained unchanged."}]))

        transport = Transport(anthropic_api_key="fixture-not-a-secret", openai_api_key="fixture-not-a-secret",
                              http_transports={"anthropic": httpx2.MockTransport(handle),
                                               "openai": httpx.MockTransport(lambda _: self.fail("unexpected OpenAI request"))})
        def dispatch(slot, role, request):
            response = transport.create(role, request)
            return {"status": "response", "response": response, "slot_id": slot}

        holds = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = root / "input"
            strategy.materialize_seed(context / "harness")
            prop = editor.AccountedProposer(pilot="p3a-01", study_sha256="a" * 64, dispatch=dispatch,
                                            audit_dir=root / "audit", fixture=True,
                                            halt=lambda *args, **kwargs: holds.append((args, kwargs)))
            try:
                reply = prop.call("Retain the supplied context/harness unchanged and report completion.",
                                  context, "inv1.a1", harvest="context/harness", max_attempts=1)
            except Exception:
                self.fail(json.dumps(prop.phase3a_evidence(), ensure_ascii=False))
            self.assertTrue(reply.text)
            proof = prop.phase3a_evidence()
            self.assertEqual([], holds)
            self.assertGreater(len(records), 0)
            self.assertLessEqual(len(records), 6)
            self.assertEqual("valid", proof["sessions"]["inv1.a1"]["status"])
            fresh = editor.AccountedProposer(pilot="p3a-01", study_sha256="a" * 64, dispatch=dispatch,
                                            audit_dir=root / "audit", fixture=True,
                                            halt=lambda *args, **kwargs: self.fail("unexpected hold"))
            self.assertEqual(proof, fresh.phase3a_evidence())
            capture = RESULTS / "editor-capture.json"
            capture.parent.mkdir(parents=True, exist_ok=True)
            capture.write_text(json.dumps({"fixture": True, "provider_calls": 0,
                "SDK_mock_calls": len(records), "requests": records,
                "proof": proof, "tool_definitions": {t["name"]: t for t in records[0].get("tools", [])}},
                sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        transport._anthropic.close()
        transport._openai.close()


if __name__ == "__main__":
    unittest.main()
