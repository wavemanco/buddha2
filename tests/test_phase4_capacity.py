"""Actual producer-to-journal/worker boundaries, using synthetic data and no SDK calls."""
from __future__ import annotations

import asyncio
import base64
import json
import queue
import threading
import unittest
import uuid
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from buddha2.artifacts import ContractError, digest
from buddha2.phase2_contracts import MAX_PROMPT_CHARS, MAX_RESPONSE_CHARS, make_portfolio
from followups.phase3a_c1_completion_v3 import worker
from followups.phase3b_seq2_v1 import accounting, deadline, native, strategy, transport
from followups.phase3b_seq2_v1 import ledger_core as core
from tests.test_phase4_assessment import portfolio
from tests.test_phase4_policy import authority_for, profile_for


class Phase4CapacityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        task = portfolio()["task"]
        task["prompt"] = "\x01" * MAX_PROMPT_CHARS
        responses = [{"id": f"synthetic-{i}", "text": "\x01" * MAX_RESPONSE_CHARS,
            "status": "ok", "request_id": f"synthetic.request.{i}"} for i in range(10)]
        maximum = make_portfolio(task, responses, method="A", repeat=1,
            model={"requested": "fixture-no-model", "returned": "fixture-no-model"},
            settings_sha256="0" * 64, procedure_sha256="1" * 64, study_sha256="2" * 64,
            request_ids=[row["request_id"] for row in responses], fixture=True)
        mapping = {f"candidate-{i:02d}": {"portfolio": maximum} for i in range(1, 13)}
        cls.maximum_request = strategy.fixed_selection_request(task, mapping)

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        names = ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex")
        if self._testMethodName != "test_actual_sdk_fixture_request_crosses_worker_base64_rpc_frame":
            names += ("anthropic.Anthropic", "anthropic.AsyncAnthropic", "openai.OpenAI",
                      "openai.AsyncOpenAI", "subprocess.Popen", "subprocess.run")
        self.blocked = [self.stack.enter_context(patch(name, side_effect=AssertionError("external activity")))
                        for name in names]

    def tearDown(self):
        self.assertTrue(all(mock.call_count == 0 for mock in self.blocked))

    def test_producer_maximum_appends_and_replays_a_real_large_intent(self):
        profile, slots = profile_for("dev", "dev02")
        request = self.maximum_request
        core.validate_request("fixed_selector", request, policy=profile)
        self.assertGreater(len(core._wire(request)), worker.MAX_FRAME)
        self.assertLessEqual(len(core._wire(request)), profile["role_payload_bytes"]["fixed_selector"])
        with self.assertRaises(ContractError):
            core.validate_request("fixed_selector", request)
        study = digest(["synthetic-p4-capacity", uuid.uuid4().hex])
        authority, bindings = authority_for(profile, study)
        inputs = {"study_sha256": study, "slots": slots, "authority": authority, "fixture": True,
                  "bindings": bindings, "policy": profile, "editor_tools": {}}
        manifest = {"kind": "phase3b-seq2-ledger-v1", "inputs": inputs,
            "run_id": accounting.journal_identity(study_sha256=study, slots=slots, authority=authority,
                fixture=True, bindings=bindings, profile=profile)}
        journal = accounting.canonical_journal(study, True)
        core._publish(journal / "manifest.json", manifest)
        slot = next(name for name, row in slots.items() if row["role"] == "fixed_selector")
        intent = core._intent(manifest, slot, request, 1)
        accounting._intent_capacity(journal, intent, profile)
        events = []
        core._append_event(journal, "intent", intent, events,
            max_bytes=profile["role_payload_bytes"]["fixed_selector"] + 65_536)
        first, replayed, _ = accounting._replay(journal)
        self.assertEqual(replayed, events)
        self.assertEqual(first["attempts"], 1)
        self.assertEqual(first["status"], "blocked-unknown")
        self.assertEqual(first["reserved_micro_usd"], core._reservation("fixed_selector")["micro_usd"])
        self.assertEqual(first["intents"][slot]["request_sha256"], digest(request))
        self.assertEqual(first["provider_calls"], 0)

    def test_real_worker_initial_frame_accepts_producer_maximum_and_legacy_bound_stays(self):
        init = {"fixture": True, "keys": {"anthropic": "fixture-not-a-secret"},
                "request": self.maximum_request}
        raw = json.dumps(init, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
        accepted = []

        class Connection:
            def __init__(self):
                self.limit, self.closed = None, False

            def recv_bytes(self, limit):
                self.limit = limit
                if len(raw) > limit:
                    raise OSError("synthetic oversized IPC frame")
                return raw

            def close(self):
                self.closed = True

        async def operation(connection, value, behavior):
            accepted.append(digest(value["request"]))

        with patch.object(worker, "_operation", side_effect=operation):
            old = Connection()
            worker.main(old)
            self.assertEqual(accepted, [])
            expanded = Connection()
            worker.main(expanded, request_frame_limit=len(raw) + 1_048_576)
        self.assertEqual(accepted, [digest(self.maximum_request)])
        self.assertTrue(old.closed and expanded.closed)
        self.assertEqual(old.limit, worker.MAX_FRAME)

    def test_transport_derives_worker_limit_from_actual_wire_before_start(self):
        class BeforeStart(Exception):
            pass

        context = Mock()
        context.Pipe.return_value = (object(), object())
        context.Process.side_effect = BeforeStart
        adapter = object.__new__(transport.Transport)
        adapter.fixture, adapter._behavior = True, {}
        allocation = SimpleNamespace(started_monotonic=0, cleanup_deadline=1)
        with patch.object(transport.multiprocessing, "get_context", return_value=context), \
                self.assertRaises(BeforeStart):
            adapter._coordinate({"budget": allocation}, self.maximum_request)
        args = context.Process.call_args.kwargs["args"]
        actual = len(json.dumps(self.maximum_request, ensure_ascii=False, allow_nan=False,
                                separators=(",", ":")).encode())
        self.assertEqual(context.Process.call_args.kwargs["target"], worker.main)
        self.assertEqual(args[2], actual + 1_048_576)
        self.assertGreater(args[2], worker.MAX_FRAME)
        self.assertLessEqual(args[2], 130_000_000)

    def test_native_saved_resume_forwards_the_same_request_policy(self):
        adapter = object.__new__(native.PortfolioAdapter)
        adapter.task, adapter.harness_dir = {"id": "synthetic"}, Path("/unused-seed")
        adapter.study_sha256, adapter.run_root, adapter.tag = "a" * 64, Path("/unused-root"), "p4-24"
        adapter.fixture, adapter.known_results = True, {}
        adapter.request_policy = {"synthetic": "policy"}
        adapter.recovery_policy = None
        checked = {label: {"status": "not_started"} for label in native.LABELS}
        with patch.object(native, "validate_adaptive_partial", return_value=checked) as validate:
            adapter._validate_existing({})
        self.assertIs(validate.call_args.kwargs["request_policy"], adapter.request_policy)

    def test_actual_sdk_fixture_request_crosses_worker_base64_rpc_frame(self):
        """Actual worker/SDK MockTransport; in-memory owned IPC, never a socket/provider."""
        messages = queue.Queue()
        frames, receipts = [], []
        reader_closed = threading.Event()
        expected = digest(self.maximum_request)

        class Connection:
            def recv_bytes(inner, limit):
                item = messages.get(timeout=30)
                if item is None:
                    reader_closed.set()
                    raise EOFError
                if len(item) > limit:
                    raise OSError("synthetic incoming frame exceeds the unchanged response bound")
                return item

            def send_bytes(inner, raw):
                value = json.loads(raw)
                kind = value["type"]
                frames.append((kind, len(raw)))
                if kind == "ready":
                    messages.put(b'{"type":"go"}')
                elif kind == "http":
                    body = base64.b64decode(value["body"], validate=True)
                    self.assertEqual(digest(json.loads(body)), expected)
                    self.assertGreater(len(raw), worker.MAX_FRAME)
                    self.assertLessEqual(len(raw), worker.fixture_http_frame_limit(self.maximum_request))
                    response = {"id": "msg_synthetic_capacity", "type": "message", "role": "assistant",
                        "model": "claude-opus-5", "content": [{"type": "text", "text": '{"candidate_id":"candidate-01"}'}],
                        "stop_reason": "end_turn", "stop_sequence": None,
                        "usage": {"input_tokens": 100, "output_tokens": 10}}
                    messages.put(json.dumps({"type": "http_result", "id": value["id"], "status": 200,
                        "headers": {"request-id": "req_synthetic_capacity", "content-type": "application/json"},
                        "body": base64.b64encode(json.dumps(response).encode()).decode()}).encode())
                elif kind == "receipt":
                    receipts.append(value)
                elif kind == "done":
                    messages.put(None)

        init = {"fixture": True, "keys": {"anthropic_api_key": "fixture-not-a-secret"},
                "role": "fixed_selector", "request": self.maximum_request,
                "io": {"connect": 5, "pool": 5, "write": 5, "read": 5}}
        # The only clients constructed use the worker's injected SDK MockTransport.
        # This method is separate from the constructor-blocked pure component group.
        with ExitStack() as blocked:
            sockets = [blocked.enter_context(patch(name, side_effect=AssertionError("network forbidden")))
                for name in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex")]
            asyncio.run(worker._operation(Connection(), init, {}))
        self.assertTrue(reader_closed.wait(2))
        self.assertTrue(all(mock.call_count == 0 for mock in sockets))
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]["raw"]["content"][0]["text"], '{"candidate_id":"candidate-01"}')
        self.assertFalse(any(kind == "failure" for kind, _ in frames))
        self.assertTrue(all(size <= worker.MAX_FRAME for kind, size in frames if kind != "http"))

    def test_strategy_saved_full_and_partial_replay_forward_request_policy(self):
        policy = {"synthetic": "policy"}
        record = {"requests": [], "run_id": "synthetic", "arm": "adaptive"}
        with patch.object(strategy, "execute_cn", return_value=record) as execute:
            strategy.validate_rollout(record, {}, Path("/unused-seed"), study_sha256="a" * 64,
                                      fixture=True, request_policy=policy)
            self.assertIs(execute.call_args.kwargs["request_policy"], policy)
            strategy.validate_partial({}, Path("/unused-seed"), study_sha256="a" * 64,
                run_id="synthetic", fixture=True, arm="adaptive", results={}, request_policy=policy)
            self.assertIs(execute.call_args.kwargs["request_policy"], policy)
        with patch.object(strategy, "_fixed_best12", return_value={}) as fixed:
            strategy.fixed_best12({}, Path("/unused-seed"), study_sha256="a" * 64,
                run_id="synthetic", dispatch=Mock(), fixture=True, request_policy=policy)
        self.assertIs(fixed.call_args.kwargs["request_policy"], policy)

    def test_timing_accepts_p4_endpoints_without_broadening_outside_the_worklist(self):
        for pair in ("p4-01", "p4-24", "p3b-01", "p3b-04"):
            for label in ("inv1.a1", "dom2.a2", "c2.a1", "select.seq2"):
                value = deadline.clock_record(study_sha256="a" * 64, source_sha256="b" * 64,
                    pilot=pair, label=label, fixture=True, editor_profile_sha256="c" * 64, started=100)
                self.assertEqual(deadline.validate_clock(value), value)
        for pair in ("p4-00", "p4-25", "p4-1", "dev02", "p3b-05"):
            with self.subTest(pair=pair), self.assertRaises(ContractError):
                deadline.clock_record(study_sha256="a" * 64, source_sha256="b" * 64,
                    pilot=pair, label="inv1.a1", fixture=True, editor_profile_sha256="c" * 64, started=100)
