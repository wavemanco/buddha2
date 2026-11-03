"""Actual pinned SDK mocks through owned processes; no provider route or real key."""
from __future__ import annotations

import copy
import json
import math
import time
import unittest
import uuid
from typing import TypedDict
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest, write_once
from followups.phase3a_c1_completion_v3 import worker
from followups.phase3a_c1_completion_v3.deadline import KnownDeadlineStop, Policy, budget, eligible
from followups.phase3a_c1_completion_v3.transport import (
    Transport,
    audit_path,
    read_audit,
    validate_audit,
)
from followups.phase3a_v1 import accounting as core
from followups.phase3a_v1.tests.test_accounting import request
from followups.phase3a_v1.transport import Transport as FrozenTransport
from followups.phase3a_v1.transport import TransportFailure


class Credentials(TypedDict):
    anthropic_api_key: str
    openai_api_key: str


KEYS: Credentials = {"anthropic_api_key": "fixture-not-a-secret", "openai_api_key": "fixture-not-a-secret"}
BINDINGS = {"study_sha256": "1" * 64, "source_sha256": "2" * 64,
            "policy_sha256": "3" * 64, "launcher_sha256": "4" * 64}
_WORKER_MAIN = worker.main


def delayed_worker_exit(connection, behavior):
    _WORKER_MAIN(connection, behavior)
    time.sleep(.6)


def blocked_worker_exit(connection, behavior):
    _WORKER_MAIN(connection, behavior)
    time.sleep(10)


def fixture_transport(**kwargs):
    import httpx
    import httpx2
    records = []
    timeouts = []
    def handle(req, module):
        body = json.loads(req.content)
        records.append(copy.deepcopy(body))
        timeouts.append(copy.deepcopy(req.extensions.get("timeout")))
        if body["model"] == "gpt-5.6-luna":
            raw = {"id": "chatcmpl-fixture", "object": "chat.completion", "created": 0,
                "model": body["model"], "choices": [{"index": 0, "message": {"role": "assistant", "content": "Synthetic"},
                    "finish_reason": "stop"}], "service_tier": "default", "usage": {
                    "prompt_tokens": 120, "completion_tokens": 24, "total_tokens": 144,
                    "prompt_tokens_details": {"cached_tokens": 16, "cache_write_tokens": 32},
                    "completion_tokens_details": {"reasoning_tokens": 4}}}
        else:
            raw = {"id": "msg_fixture", "type": "message", "role": "assistant", "model": body["model"],
                "content": [{"type": "text", "text": "Synthetic"}], "stop_reason": "end_turn",
                "usage": {"input_tokens": 80, "output_tokens": 24, "cache_creation_input_tokens": 16,
                    "cache_read_input_tokens": 8, "cache_creation": {"ephemeral_5m_input_tokens": 16,
                    "ephemeral_1h_input_tokens": 0}, "service_tier": "standard", "inference_geo": "global"}}
        return module.Response(200, json=raw, headers={"request-id": "req_fixture"})
    mocks = {"anthropic": httpx2.MockTransport(lambda req: handle(req, httpx2)),
             "openai": httpx.MockTransport(lambda req: handle(req, httpx))}
    value = Transport(**KEYS, http_transports=mocks, **kwargs)
    value.fixture_records = records
    value.fixture_timeout_records = timeouts
    value.fixture_http_transports = mocks
    return value


def bind(transport, role="plan", body=None):
    body = request(role) if body is None else body
    slot = "unit-" + uuid.uuid4().hex
    meta = {"role": role, "pair": "p3a-01", "cell": "p3a-01:adaptive"}
    if role == "editor":
        meta["conversation"] = "p3a-01:adaptive:inv1.a1"
        transport.register_conversation(meta["conversation"], time.monotonic() + 600)
    allocation = transport.prepare(slot, role, meta, BINDINGS)
    intent = {"slot_id": slot, "role": role, "pair": meta["pair"], "cell": meta["cell"],
        "study_sha256": BINDINGS["study_sha256"], "fixture": True,
        "dispatch_id": "unit:0001", "request_sha256": digest(body), "request": copy.deepcopy(body),
        "reservation": core._reservation(role)}
    transport.bind_intent(intent, allocation)
    return intent, allocation, body


def short(**kwargs):
    return Policy(completion=2, cleanup=.6, editor_minimum=.01, editor_margin=.01, **kwargs)


class DeadlineTests(unittest.TestCase):
    def test_absolute_budget_clamps_after_queue_and_exact_capture_boundary(self):
        b = budget(400, now=100)
        self.assertEqual(b.effective_seconds, 240)
        b = budget(400, now=340)
        self.assertEqual(b.effective_seconds, 30)
        self.assertTrue(eligible(370, b))
        self.assertFalse(eligible(math.nextafter(370, math.inf), b))
        with self.assertRaises(KnownDeadlineStop):
            budget(400, now=340.001)
        with self.assertRaises(ContractError):
            budget(float("nan"), now=100)

    def test_fixture_overrides_cannot_enter_live_constructor(self):
        with self.assertRaises(ContractError):
            Transport(**KEYS, fixture_policy=short())
        with self.assertRaises(ContractError):
            fixture_transport(fixture_behavior={"unexpected": True})

    def test_closed_transport_rejects_before_any_intent_or_sdk(self):
        t = fixture_transport()
        t.close()
        with self.assertRaises(ContractError):
            bind(t)
        self.assertEqual(t.fixture_records, [])

    def test_async_actual_sdk_normalization_matches_frozen_sync_all_roles(self):
        for role in ("plan", "answer", "rank", "editor", "fixed_selector", "group", "quality"):
            with self.subTest(role=role):
                t = fixture_transport()
                self.addCleanup(t.close)
                intent, _, body = bind(t, role)
                response = t.create(role, body)
                old = FrozenTransport(**KEYS, http_transports=t.fixture_http_transports)
                try:
                    expected = old.create(role, body)
                finally:
                    old._anthropic.close()
                    old._openai.close()
                self.assertEqual({k: v for k, v in response.items() if k != "latency_seconds"},
                                 {k: v for k, v in expected.items() if k != "latency_seconds"})
                self.assertEqual(t.fixture_records[0], body)
                self.assertEqual(t.fixture_timeout_records[0], {"connect": 10, "pool": 10, "write": 30, "read": 240})
                result = core._result(intent, response)
                self.assertEqual(result["status"], "response")
                audit = t.commit(intent["slot_id"], result)
                self.assertFalse(audit["late_known"])
                self.assertFalse(audit["owner_stop_required"])
                validate_audit(audit, intent=intent, result=result, bindings=BINDINGS)

    def test_safe_conversion_failure_retains_same_bounded_response_as_frozen(self):
        import httpx
        import httpx2
        raw = {"id": "chatcmpl-fixture", "object": "chat.completion", "created": 0,
               "model": "gpt-5.6-luna", "choices": [], "usage": {"prompt_tokens": 1,
               "completion_tokens": 1, "total_tokens": 2}}
        mocks = {"anthropic": httpx2.MockTransport(lambda r: httpx2.Response(200, json={})),
                 "openai": httpx.MockTransport(lambda r: httpx.Response(200, json=raw,
                       headers={"request-id": "req_fixture"}))}
        t = Transport(**KEYS, http_transports=mocks)
        self.addCleanup(t.close)
        intent, _, body = bind(t, "group")
        with self.assertRaises(TransportFailure) as fresh:
            t.create("group", body)
        old = FrozenTransport(**KEYS, http_transports=mocks)
        try:
            with self.assertRaises(TransportFailure) as frozen:
                old.create("group", body)
        finally:
            old._anthropic.close()
            old._openai.close()
        self.assertEqual(fresh.exception.failure, frozen.exception.failure)
        self.assertEqual(fresh.exception.response, frozen.exception.response)
        result = core._result(intent, fresh.exception.response, failure=fresh.exception.failure)
        self.assertEqual(result["status"], "unknown")
        validate_audit(t.commit(intent["slot_id"], result), intent=intent, result=result, bindings=BINDINGS)

    def test_actual_sdk_timeout_subtypes_are_bounded_safe_unknowns(self):
        for subtype in ("connect", "read", "write", "pool"):
            with self.subTest(subtype=subtype):
                t = fixture_transport(fixture_behavior={"failure": subtype})
                self.addCleanup(t.close)
                intent, _, body = bind(t)
                with self.assertRaises(TransportFailure) as caught:
                    t.create("plan", body)
                self.assertEqual(caught.exception.failure["category"], "timeout")
                result = core._result(intent, None, failure=caught.exception.failure)
                self.assertEqual(result["reserved_micro_usd"], intent["reservation"]["micro_usd"])
                audit = t.commit(intent["slot_id"], result)
                self.assertEqual(audit["timeout_subtype"], subtype.title() + "Timeout")
                validate_audit(audit, intent=intent, result=result, bindings=BINDINGS)

    def test_cancellation_suppressed_late_complete_is_known_accounting_only(self):
        t = fixture_transport(fixture_policy=short(), fixture_behavior={
            "response_delay": 10, "ignore_cancel": True, "cancel_delay": .02})
        self.addCleanup(t.close)
        intent, allocation, body = bind(t)
        response = t.create("plan", body)
        result = core._result(intent, response)
        self.assertEqual(result["status"], "response")
        audit = t.commit(intent["slot_id"], result)
        self.assertTrue(audit["late_known"])
        self.assertGreater(audit["parent_capture_monotonic"], allocation.deadline_monotonic)
        self.assertFalse(audit["owner_stop_required"])
        with self.assertRaises(KnownDeadlineStop):
            bind(t)
        validate_audit(audit, intent=intent, result=result, bindings=BINDINGS)

    def test_uncooperative_sdk_loop_is_killed_and_reaped_without_resend(self):
        t = fixture_transport(fixture_policy=short(), fixture_behavior={"block_loop": True})
        self.addCleanup(t.close)
        intent, _, body = bind(t)
        started = time.monotonic()
        with self.assertRaises(TransportFailure) as caught:
            t.create("plan", body)
        self.assertLess(time.monotonic() - started, 4)
        self.assertEqual(caught.exception.failure["category"], "timeout")
        result = core._result(intent, None, failure=caught.exception.failure)
        audit = t.commit(intent["slot_id"], result)
        self.assertTrue(audit["worker_stopped"])
        self.assertFalse(audit["owner_stop_required"])
        self.assertEqual(t.fixture_records, [])
        with self.assertRaises(KnownDeadlineStop):
            bind(t)

    def test_partial_frame_and_blocked_initial_send_do_not_block_coordinator(self):
        for mode in ("partial_frame", "never_read"):
            with self.subTest(mode=mode):
                policy = Policy(completion=.3, cleanup=.6, editor_minimum=.01, editor_margin=.01)
                t = fixture_transport(fixture_policy=policy, fixture_behavior={"ipc": mode})
                self.addCleanup(t.close)
                body = request("editor")
                body["messages"][0]["content"] = "x" * 1_000_000
                intent, _, body = bind(t, "editor", body)
                start = time.monotonic()
                with self.assertRaises(TransportFailure) as caught:
                    t.create("editor", body)
                self.assertLess(time.monotonic() - start, 2)
                audit = t.commit(intent["slot_id"], core._result(intent, None, failure=caught.exception.failure))
                self.assertIs(audit["sdk_invoked"], False)
                self.assertEqual(audit["wire_egress"], "not-started")
                self.assertTrue(audit["worker_stopped"])
                self.assertEqual(t.fixture_records, [])
                close_start = time.monotonic()
                t.close()
                self.assertLess(time.monotonic() - close_start, .2)

    def test_after_intent_deadline_expiry_has_no_sdk_invocation_but_holds(self):
        policy = Policy(completion=.01, cleanup=.6, editor_minimum=.001, editor_margin=.001)
        t = fixture_transport(fixture_policy=policy)
        self.addCleanup(t.close)
        intent, _, body = bind(t)
        time.sleep(.03)
        with self.assertRaises(TransportFailure) as caught:
            t.create("plan", body)
        result = core._result(intent, None, failure=caught.exception.failure)
        audit = t.commit(intent["slot_id"], result)
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["reserved_micro_usd"], intent["reservation"]["micro_usd"])
        self.assertIs(audit["sdk_invoked"], False)
        self.assertEqual(t.fixture_records, [])

    def test_delayed_body_is_inside_completion_not_merely_header_arrival(self):
        t = fixture_transport(fixture_policy=short(), fixture_behavior={"body_delay": 10})
        self.addCleanup(t.close)
        intent, _, body = bind(t)
        with self.assertRaises(TransportFailure) as caught:
            t.create("plan", body)
        audit = t.commit(intent["slot_id"], core._result(intent, None, failure=caught.exception.failure))
        self.assertEqual(len(t.fixture_records), 1)
        self.assertIsNone(audit["parent_capture_monotonic"])
        self.assertEqual(audit["terminal_status"], "unknown")
        self.assertTrue(audit["worker_stopped"])

    def test_known_response_with_unfinished_cleanup_requires_known_stop(self):
        t = fixture_transport(fixture_policy=short(), fixture_behavior={"cleanup_delay": 10})
        self.addCleanup(t.close)
        intent, _, body = bind(t)
        response = t.create("plan", body)
        result = core._result(intent, response)
        audit = t.commit(intent["slot_id"], result)
        self.assertEqual(result["status"], "response")
        self.assertFalse(audit["late_known"])
        self.assertTrue(audit["cleanup_failed"])
        self.assertTrue(audit["worker_stopped"])
        with self.assertRaises(KnownDeadlineStop):
            bind(t)
        validate_audit(audit, intent=intent, result=result, bindings=BINDINGS)

    def test_completed_worker_natural_exit_uses_existing_cleanup_allowance(self):
        t = fixture_transport()
        self.addCleanup(t.close)
        with patch.object(worker, "main", delayed_worker_exit):
            for _ in range(2):
                intent, allocation, body = bind(t)
                result = core._result(intent, t.create("plan", body))
                audit = t.commit(intent["slot_id"], result)
                self.assertEqual(result["status"], "response")
                self.assertLessEqual(audit["parent_capture_monotonic"], allocation.deadline_monotonic)
                self.assertEqual(audit["budget"]["policy"]["cleanup"], 60)
                self.assertLess(audit["cleanup_elapsed_seconds"], 60)
                self.assertFalse(audit["cleanup_failed"])
                self.assertTrue(audit["worker_stopped"])
                self.assertFalse(audit["owner_stop_required"])
                self.assertFalse(audit["late_known"])
                validate_audit(audit, intent=intent, result=result, bindings=BINDINGS)
        self.assertEqual(len(t.fixture_records), 2)

    def test_completed_worker_exit_beyond_cleanup_allowance_is_still_terminal(self):
        policy = Policy(completion=10, cleanup=.6, editor_minimum=.01, editor_margin=.01)
        t = fixture_transport(fixture_policy=policy)
        self.addCleanup(t.close)
        with patch.object(worker, "main", blocked_worker_exit):
            intent, _, body = bind(t)
            result = core._result(intent, t.create("plan", body))
        audit = t.commit(intent["slot_id"], result)
        self.assertEqual(result["status"], "response")
        self.assertLess(audit["cleanup_elapsed_seconds"], 1.2)
        self.assertFalse(audit["late_known"])
        self.assertTrue(audit["cleanup_failed"])
        self.assertTrue(audit["worker_stopped"])
        self.assertFalse(audit["owner_stop_required"])
        with self.assertRaises(KnownDeadlineStop):
            bind(t)
        self.assertEqual(len(t.fixture_records), 1)
        validate_audit(audit, intent=intent, result=result, bindings=BINDINGS)

    def test_unproven_cleanup_flag_does_not_claim_owner_stopped(self):
        t = fixture_transport()
        self.addCleanup(t.close)
        intent, _, body = bind(t)
        original = Transport._stop
        def unproven(state, limit):
            original(state, limit)
            return False
        with patch.object(Transport, "_stop", side_effect=unproven):
            response = t.create("plan", body)
        audit = t.commit(intent["slot_id"], core._result(intent, response))
        self.assertFalse(audit["worker_stopped"])
        self.assertTrue(audit["owner_stop_required"])
        with self.assertRaises(KnownDeadlineStop):
            bind(t)

    def test_audit_replay_is_exact_immutable_and_client_free(self):
        t = fixture_transport()
        self.addCleanup(t.close)
        intent, _, body = bind(t)
        result = core._result(intent, t.create("plan", body))
        audit = t.commit(intent["slot_id"], result)
        self.assertEqual(t.commit(intent["slot_id"], result), audit)
        with self.assertRaises(ContractError):
            t.commit(intent["slot_id"], result | {"spent_micro_usd": 99})
        changed = copy.deepcopy(audit)
        changed["late_known"] = True
        changed["sha256"] = digest({k: v for k, v in changed.items() if k != "sha256"})
        with self.assertRaises(ContractError):
            validate_audit(changed, intent=intent, result=result, bindings=BINDINGS)
        root = audit_path(intent["study_sha256"], True, intent["slot_id"])
        write_once(root, audit)
        self.addCleanup(lambda: root.unlink(missing_ok=True))
        with patch.object(Transport, "__init__", side_effect=AssertionError("client construction")):
            self.assertEqual(read_audit(intent["study_sha256"], True, intent["slot_id"],
                intent=intent, result=result, bindings=BINDINGS), audit)


if __name__ == "__main__":
    unittest.main()
