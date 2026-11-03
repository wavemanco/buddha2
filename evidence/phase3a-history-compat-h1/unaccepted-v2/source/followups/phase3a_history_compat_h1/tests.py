"""Adverse history checks must stop before another mocked admission."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
import urllib.request
from pathlib import Path

from buddha2.artifacts import ContractError
from followups.phase3a_c1_completion_v4.editor import _FALSE, relay

from .guard import HistoryGuard


class HistoryTests(unittest.TestCase):
    def start(self):
        content = [
            {"type": "thinking", "thinking": "", "signature": "SYNTHETIC"},
            {
                "type": "thinking",
                "thinking": "SYNTHETIC ONLY",
                "signature": "SYNTHETIC-2",
            },
            {"type": "redacted_thinking", "data": "SYNTHETIC-3"},
            {
                "type": "tool_use",
                "id": "read01",
                "name": "read",
                "input": {"filePath": "/tmp/fixture"},
                "caller": {"type": "direct"},
            },
        ]
        calls = []

        def delegate(slot, role, request):
            calls.append(slot)
            return {
                "status": "response",
                "response": {
                    "provider_response": {
                        "content": copy.deepcopy(content),
                        "stop_reason": "tool_use",
                    }
                },
            }

        guard = HistoryGuard(delegate, "fixture")
        initial: dict = {
            "model": "claude-opus-5",
            "messages": [{"role": "user", "content": "SYNTHETIC"}],
        }
        guard("fixture.t01", "editor", initial)
        next_request = copy.deepcopy(initial)
        next_request["messages"] += [
            {"role": "assistant", "content": copy.deepcopy(content)},
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "read01",
                        "content": "SYNTHETIC RESULT",
                    }
                ],
            },
        ]
        return guard, calls, next_request

    def test_empty_visible_redacted_and_direct_caller_preserved(self):
        guard, calls, request = self.start()
        del request["messages"][1]["content"][-1]["caller"]
        guard("fixture.t02", "editor", request)
        self.assertEqual(len(calls), 2)
        self.assertFalse(any(a["history_restored"] for a in guard.audits))

    def test_all_history_tampering_stops_before_second_admission(self):
        for kind in (
            "drop",
            "change-signature",
            "change-visible",
            "duplicate",
            "reorder",
            "tool-input",
            "missing-tool",
            "prior-user",
            "tool-result-id",
            "tool-result-duplicate",
            "model",
            "cross-conversation",
            "incomplete-stream-history",
        ):
            with self.subTest(kind=kind):
                guard, calls, request = self.start()
                blocks = request["messages"][1]["content"]
                slot = "fixture.t02"
                if kind in {"drop", "incomplete-stream-history"}:
                    blocks.pop(0)
                elif kind == "change-signature":
                    blocks[0]["signature"] += "CHANGED"
                elif kind == "change-visible":
                    blocks[1]["thinking"] += "CHANGED"
                elif kind == "duplicate":
                    blocks.insert(0, copy.deepcopy(blocks[0]))
                elif kind == "reorder":
                    blocks[0], blocks[2] = blocks[2], blocks[0]
                elif kind == "tool-input":
                    blocks[-1]["input"]["filePath"] = "/tmp/other"
                elif kind == "missing-tool":
                    blocks.pop()
                elif kind == "prior-user":
                    request["messages"][0]["content"] = "CHANGED"
                elif kind == "tool-result-id":
                    request["messages"][-1]["content"][0]["tool_use_id"] = "other"
                elif kind == "tool-result-duplicate":
                    request["messages"][-1]["content"] *= 2
                elif kind == "model":
                    request["model"] = "other"
                elif kind == "cross-conversation":
                    slot = "foreign.t02"
                with self.assertRaises(ContractError):
                    guard(slot, "editor", request)
                self.assertEqual(len(calls), 1)

    def test_incomplete_provider_result_cannot_advance(self):
        calls = []

        def incomplete(*args):
            calls.append(True)
            return {
                "status": "response",
                "response": {"provider_response": {"content": []}},
            }

        guard = HistoryGuard(incomplete, "fixture")
        for _ in range(2):
            with self.assertRaises(ContractError):
                guard(
                    "fixture.t01",
                    "editor",
                    {"messages": [{"role": "user", "content": "SYNTHETIC"}]},
                )
        self.assertEqual(guard.responses, [])
        self.assertTrue(guard.stopped)
        self.assertEqual(len(calls), 1)

    def test_terminal_sixteen_is_outside_ordinary_guard(self):
        guard = HistoryGuard(lambda *args: self.fail("terminal dispatch forbidden"), "fixture")
        guard.responses = [[] for _ in range(15)]
        with self.assertRaises(ContractError):
            guard("fixture.t16", "editor", {"messages": [{"role": "user", "content": "SYNTHETIC"}]})

    def test_identical_local_request_replays_without_admission(self):
        calls = []

        def dispatch(*args):
            calls.append(True)
            return {
                "status": "response",
                "response": {
                    "provider_response": {
                        "id": "fixture",
                        "type": "message",
                        "role": "assistant",
                        "model": "claude-opus-5",
                        "content": [{"type": "text", "text": "SYNTHETIC"}],
                        "stop_reason": "end_turn",
                        "usage": {"input_tokens": 1, "output_tokens": 1},
                    }
                },
            }

        raw = {
            "model": "claude-opus-5",
            "max_tokens": 16000,
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": "high"},
            "stream": True,
            "messages": [{"role": "user", "content": "SYNTHETIC"}],
        }
        record = {"fixture": True, "requests": []}
        with (
            tempfile.TemporaryDirectory() as directory,
            relay(
                Path(directory),
                HistoryGuard(dispatch, "fixture"),
                "fixture",
                record,
                lambda *a, **k: self.fail("unexpected relay halt"),
            ) as url,
        ):
            responses = []
            for _ in range(2):
                request = urllib.request.Request(
                    url + "/messages",
                    data=json.dumps(raw).encode(),
                    headers={"x-api-key": _FALSE},
                )
                with urllib.request.urlopen(request, timeout=10) as response:
                    responses.append(response.read())
        self.assertEqual(responses[0], responses[1])
        self.assertEqual(len(calls), 1)
        self.assertEqual(record["local_response_replays"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
