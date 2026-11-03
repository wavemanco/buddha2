"""Real pinned SDK serialization/parsing against in-memory, socket-blocked HTTP."""

import copy
import json
import socket
import unittest

from buddha2.artifacts import ContractError
from buddha2.phase2 import parse_angles, parse_order, render_request
from buddha2.phase2_am1_controls import account
from buddha2.phase2_am1_mock import SDKMock
from buddha2.phase2_dispatch import build_request


def requests():
    task = {"prompt": "Suggest a useful reading room. Unicode: café, 雨, 🪴."}
    rows = [{"id": f"r{i}", "text": f"Saved answer {i}"} for i in range(10)]
    group_schema = {"type": "json_schema", "json_schema": {
        "name": "Partition", "strict": True, "schema": {
            "type": "object", "properties": {"groups": {"type": "array", "items": {
                "type": "array", "items": {"type": "integer"}}}},
            "required": ["groups"], "additionalProperties": False}}}
    quality = build_request("quality", messages=[{"role": "user", "content": task["prompt"]}],
                            system="Score the saved response.")
    quality["output_config"]["format"] = {"type": "json_schema", "schema": {
        "type": "object", "properties": {"score": {"type": "integer"}},
        "required": ["score"], "additionalProperties": False}}
    return {"answer": render_request("answer", task), "plan": render_request("plan", task),
            "rank": render_request("rank", task, responses=rows),
            "group": build_request("group", messages=[{"role": "system", "content": "Group answers."},
                         {"role": "user", "content": json.dumps(rows)}], response_format=group_schema),
            "quality": quality}


class SDKHTTPTests(unittest.TestCase):
    def test_actual_sdks_preserve_all_five_role_bodies_and_usage_categories(self):
        import anthropic
        import openai

        bodies = requests()
        saved = copy.deepcopy(bodies)
        with SDKMock() as mock:
            self.assertTrue(mock.transport.fixture)
            self.assertIs(type(mock.transport._anthropic), anthropic.Anthropic)
            self.assertIs(type(mock.transport._openai), openai.OpenAI)
            self.assertEqual(mock.transport._anthropic.max_retries, 0)
            self.assertEqual(mock.transport._openai.max_retries, 0)
            replies = {}
            for role, body in bodies.items():
                mock.select(role, "sdk." + role)
                replies[role] = mock.transport.create(role, body)
                self.assertEqual(mock.records[-1]["request"], body)
                self.assertEqual(replies[role]["request_id"], mock.records[-1]["request_id"])
                self.assertGreaterEqual(replies[role]["latency_seconds"], 0)
                self.assertEqual(account(role, replies[role]),
                                 (57 if role == "group" else 1100 if role == "quality" else 441, True))
            self.assertEqual(mock.http_calls, 5)
            self.assertEqual(bodies, saved)
            group = replies["group"]
            self.assertEqual(group["provider_usage"]["prompt_tokens_details"]["cache_write_tokens"], 32)
            self.assertEqual(group["usage"]["input_tokens"], 72)
            self.assertEqual(group["usage"]["cache_creation_input_tokens"], 32)
            self.assertEqual(group["usage"]["cache_read_input_tokens"], 16)
            self.assertEqual(group["usage"]["output_tokens"], 24)
            self.assertEqual(group["usage"]["output_tokens_details"], {"reasoning_tokens": 4})
            self.assertEqual(len(parse_angles(json.loads(replies["plan"]["text"]))), 10)
            self.assertEqual(parse_order(json.loads(replies["rank"]["text"]), [f"r{i}" for i in range(10)]),
                             [f"r{i}" for i in reversed(range(10))])
            self.assertEqual(json.loads(group["text"]), {"groups": [[i] for i in range(10)]})
            self.assertEqual(json.loads(replies["quality"]["text"]), {"score": 5})
            self.assertNotIn("max_tokens", mock.records[3]["request"])
            self.assertNotIn("reasoning_effort", mock.records[3]["request"])
            self.assertNotIn("service_tier", mock.records[3]["request"])
            self.assertNotIn("fixture-not-a-secret", json.dumps(mock.records))

    def test_socket_construction_dns_and_connections_blocked_and_restored(self):
        original_socket, original_lookup = socket.socket, socket.getaddrinfo
        with SDKMock() as mock:
            for action in (lambda: socket.socket(), lambda: socket.getaddrinfo("example.invalid", 443),
                           lambda: socket.create_connection(("example.invalid", 443))):
                with self.assertRaisesRegex(ContractError, "external sockets are disabled"):
                    action()
            self.assertEqual(mock.http_calls, 0)
        self.assertIs(socket.socket, original_socket)
        self.assertIs(socket.getaddrinfo, original_lookup)

    def test_changed_profile_is_rejected_before_http(self):
        body = requests()["answer"]
        body["output_config"]["effort"] = "high"
        with SDKMock() as mock:
            mock.select("answer", "sdk.changed-profile")
            with self.assertRaisesRegex(ContractError, "frozen profile"):
                mock.transport.create("answer", body)
            self.assertEqual(mock.http_calls, 0)

    def test_unknown_usage_and_missing_write_are_not_zero_cost_or_silently_lost(self):
        for fault in ("unknown-usage", "missing-write", "unknown-tier", "over-input", "wrong-model"):
            with self.subTest(fault=fault), SDKMock(fault=fault) as mock:
                mock.select("group", "sdk.group-fault")
                response = mock.transport.create("group", requests()["group"])
                self.assertEqual(account("group", response), (None, False))
                self.assertEqual(mock.http_calls, 1)
                self.assertTrue(mock.fault_triggered)
                if fault == "unknown-usage":
                    self.assertEqual(response["provider_usage"]["unpriced_tokens"], 7)
                if fault == "missing-write":
                    self.assertNotIn("cache_write_tokens", response["provider_usage"]["prompt_tokens_details"])

    def test_malformed_plan_is_a_paid_known_outcome_without_replacement(self):
        with SDKMock(fault="malformed-plan") as mock:
            mock.select("plan", "sdk.bad-plan")
            response = mock.transport.create("plan", requests()["plan"])
            self.assertEqual(account("plan", response), (441, True))
            with self.assertRaisesRegex(ContractError, "exactly ten"):
                parse_angles(json.loads(response["text"]))
            self.assertEqual(mock.http_calls, 1)

    def test_timeout_uses_exactly_one_sdk_attempt(self):
        import anthropic

        with SDKMock(fault="timeout") as mock:
            mock.select("answer", "sdk.timeout")
            with self.assertRaises(anthropic.APITimeoutError):
                mock.transport.create("answer", requests()["answer"])
            self.assertEqual(mock.http_calls, 1)
            self.assertIsNone(mock.records[0]["response"])

    def test_pairs_script_preserves_all_positions_without_claiming_semantic_truth(self):
        with SDKMock(partition="pairs") as mock:
            mock.select("group", "sdk.pairs")
            response = mock.transport.create("group", requests()["group"])
            self.assertEqual(json.loads(response["text"]),
                             {"groups": [[i, i + 1] for i in range(0, 10, 2)]})
            self.assertEqual(mock.http_calls, 1)


if __name__ == "__main__":
    unittest.main()
