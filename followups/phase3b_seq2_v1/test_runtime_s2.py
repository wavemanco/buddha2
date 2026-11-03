"""S2 hermetic startup cases; actual agent/Windows rehearsal remains separate evidence."""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest

from . import supervision
from .support import ROOT


class SupervisionTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / "runs/phase3b-seq2-v1/unit-supervision" if os.name == "nt" else supervision.BASE
        parent.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="startup-", dir=parent)
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.scope = patch.object(supervision, "BASE", self.base)
        self.scope.start()
        self.addCleanup(self.scope.stop)
        self.sequence = 0

    def new(self, *, fixture=True):
        self.sequence += 1
        checked = {key: digest([key, self.sequence]) for key in supervision.BINDINGS}
        checked.update(fixture=fixture, supervisor_agent="/root/s2_supervisor", mode="mock" if fixture else "provider")
        checked["run"] = str(self.base / "native" / checked["study_sha256"] / ("mock" if fixture else "live"))
        inspection = {"container": {"container_id": "2" * 64}, "preflight": checked}
        inspection["inspection_sha256"] = digest(inspection)
        return checked, inspection

    def observation(self, request, *, status="running"):
        return {"kind": "phase3b-s2-supervisor-observation-v1", "tool": "collaboration.list_agents",
            "request_sha256": request["sha256"], "observed_at_utc": supervision._utc(),
            "agent": {"agent_name": request["supervisor_agent"], "agent_status": status}}

    def owner(self, identity):
        return {"container_id": identity, "running": True, "observed_at_utc": supervision._utc()}

    def publish(self, checked, mutate=None):
        target = supervision._directory(checked) / "request.json"
        request = supervision.read(target)
        ack = supervision.publish_ack(target, self.observation(request), observe_owner=self.owner)
        if mutate:
            altered = copy.deepcopy(ack)
            mutate(altered)
            altered["sha256"] = digest({k: v for k, v in altered.items() if k != "sha256"})
            (target.parent / "ack.json").write_text(json.dumps(altered), encoding="utf-8")

    def wait(self, checked, inspection, mutate=None):
        with patch.object(supervision.time, "sleep", side_effect=lambda _: self.publish(checked, mutate)):
            return supervision.wait_for_attachment(checked, inspection)

    def rejected_ack(self, mutate):
        checked, inspection = self.new()
        with self.assertRaises(ContractError):
            self.wait(checked, inspection, mutate)
        failure = supervision.read(supervision._directory(checked) / "failure.json")
        self.assertEqual((failure["provider_calls"], failure["durable_intents"]), (0, 0))
        self.assertFalse((supervision._directory(checked) / "receipt.json").exists())

    def test_s01_fresh_bound_ack_is_consumed_once_before_any_call(self):
        checked, inspection = self.new()
        receipt = self.wait(checked, inspection)
        self.assertEqual((receipt["provider_calls"], receipt["durable_intents"]), (0, 0))
        self.assertEqual(supervision.require_attached(checked, checked, True), receipt)
        self.assertTrue(receipt["point_in_time_presence_only"])
        self.assertFalse(receipt["scientific_complete"])

    def test_s02_missing_ack_expires_with_zero_intents(self):
        checked, inspection = self.new()
        clock = [100.0]
        def expire(_):
            clock[0] += supervision.SECONDS + 1
        with patch.object(supervision.time, "monotonic", side_effect=lambda: clock[0]), patch.object(supervision.time, "sleep", side_effect=expire):
            with self.assertRaisesRegex(ContractError, "timed out"):
                supervision.wait_for_attachment(checked, inspection)
        self.assertEqual(supervision.read(supervision._directory(checked) / "failure.json")["durable_intents"], 0)

    def test_s03_wrong_nonce_rejected(self):
        self.rejected_ack(lambda ack: ack["request"].update(launch_nonce="0" * 32))

    def test_s04_wrong_controller_owner_rejected(self):
        self.rejected_ack(lambda ack: ack["controller_observation"].update(container_id="0" * 64))

    def test_s05_every_release_and_inspection_binding_is_exact(self):
        for field in (*supervision.BINDINGS, "inspection_sha256"):
            with self.subTest(field=field):
                self.rejected_ack(lambda ack: ack["request"].update({field: "0" * 64}))

    def test_s06_stale_request_or_old_observation_rejected(self):
        checked, inspection = self.new()
        request = supervision.request(checked, inspection)
        target = supervision._directory(checked) / "request.json"
        future = (supervision._timestamp(request["expires_at_utc"]) + dt.timedelta(seconds=1)).isoformat()
        with patch.object(supervision, "_utc", return_value=future), self.assertRaisesRegex(ContractError, "stale"):
            supervision.publish_ack(target, self.observation(request), observe_owner=self.owner)
        observation = self.observation(request)
        observation["observed_at_utc"] = (supervision._timestamp(request["created_at_utc"]) - dt.timedelta(seconds=1)).isoformat()
        with self.assertRaisesRegex(ContractError, "stale"):
            supervision.publish_ack(target, observation, observe_owner=self.owner)

    def test_s07_late_ack_rejected(self):
        self.rejected_ack(lambda ack: ack.update(published_at_utc=ack["request"]["expires_at_utc"]))

    def test_s08_old_ack_and_republication_rejected(self):
        self.rejected_ack(lambda ack: ack.update(request_sha256="0" * 64))
        checked, inspection = self.new()
        request = supervision.request(checked, inspection)
        target = supervision._directory(checked) / "request.json"
        supervision.publish_ack(target, self.observation(request), observe_owner=self.owner)
        with self.assertRaisesRegex(ContractError, "already been published"):
            supervision.publish_ack(target, self.observation(request), observe_owner=self.owner)
        with self.assertRaisesRegex(ContractError, "one-shot"):
            supervision.request(checked, inspection)

    def test_s09_wrong_fixture_rejected(self):
        self.rejected_ack(lambda ack: ack["request"].update(fixture=False))

    def test_s10a_absent_supervisor_cannot_publish(self):
        checked, inspection = self.new()
        request = supervision.request(checked, inspection)
        with self.assertRaisesRegex(ContractError, "running-agent"):
            supervision.publish_ack(supervision._directory(checked) / "request.json",
                                    self.observation(request, status="idle"), observe_owner=self.owner)

    def test_s10b_actual_post_request_completed_observation_cannot_publish(self):
        checked, inspection = self.new()
        request = supervision.request(checked, inspection)
        # The trusted caller must use this new tool observation, not the prior running record.
        actual_fresh_observation = self.observation(request, status={"completed": "fixture exited"})
        with self.assertRaisesRegex(ContractError, "running-agent"):
            supervision.publish_ack(supervision._directory(checked) / "request.json", actual_fresh_observation, observe_owner=self.owner)

    def test_s12_deadline_cannot_be_reset_even_with_resealed_request(self):
        checked, inspection = self.new()
        def reset(_):
            target = supervision._directory(checked) / "request.json"
            value = supervision.read(target)
            value["deadline_monotonic"] += 60
            value["sha256"] = digest({k: v for k, v in value.items() if k != "sha256"})
            target.write_text(json.dumps(value), encoding="utf-8")
        with patch.object(supervision.time, "sleep", side_effect=reset), self.assertRaisesRegex(ContractError, "changed"):
            supervision.wait_for_attachment(checked, inspection)

    def test_s14_real_transport_requires_this_controllers_consumed_receipt(self):
        with self.assertRaises(ContractError):
            supervision.require_transport_attachment(None)
        checked, inspection = self.new(fixture=False)
        receipt = self.wait(checked, inspection)
        self.assertEqual(supervision.require_transport_attachment(receipt), receipt)
        altered = copy.deepcopy(receipt)
        altered["request"]["controller_owner"]["pid"] += 1
        altered["request"]["sha256"] = digest({k: v for k, v in altered["request"].items() if k != "sha256"})
        altered["sha256"] = digest({k: v for k, v in altered.items() if k != "sha256"})
        with self.assertRaises(ContractError):
            supervision.require_transport_attachment(altered)

    def test_s15_owned_startup_cancellation_is_terminal_zero_call(self):
        checked, inspection = self.new()
        with patch.object(supervision.time, "sleep", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            supervision.wait_for_attachment(checked, inspection)
        failure = supervision.read(supervision._directory(checked) / "failure.json")
        self.assertFalse(failure["resume_allowed"])
        self.assertEqual((failure["provider_calls"], failure["durable_intents"]), (0, 0))
        with self.assertRaises(ContractError):
            supervision.request(checked, inspection)

    def test_host_owner_observation_cannot_bind_foreign_or_stopped_container(self):
        for observed in ({"container_id": "0" * 64, "running": True}, {"container_id": "2" * 64, "running": False}):
            checked, inspection = self.new()
            request = supervision.request(checked, inspection)
            with self.subTest(owner=observed), self.assertRaises(ContractError):
                supervision.publish_ack(supervision._directory(checked) / "request.json", self.observation(request),
                                        observe_owner=lambda _: observed)


class SelectorRuntimeTests(unittest.TestCase):
    def transport_shell(self):
        from .transport import Transport
        value = Transport.__new__(Transport)
        value._closed = value._terminal = False
        value._local = threading.local()
        value._conversations = {}
        from .deadline import POLICY
        value._policy = POLICY
        return value

    def test_native_selector_requires_its_registered_absolute_deadline(self):
        value = self.transport_shell()
        bindings = {key: "1" * 64 for key in ("source_sha256", "policy_sha256", "launcher_sha256")}
        meta = {"role": "native_selector", "conversation": "p3b-01:adaptive:select.seq2"}
        with self.assertRaisesRegex(ContractError, "absolute native conversation"):
            value.prepare("p3b-01.adaptive.editor.select.seq2.t01", "native_selector", meta, bindings)
        absolute = time.monotonic() + 100
        value.register_conversation(meta["conversation"], absolute)
        allocation = value.prepare("p3b-01.adaptive.editor.select.seq2.t01", "native_selector", meta, bindings)
        self.assertEqual(allocation.conversation_deadline, absolute)
        self.assertAlmostEqual(allocation.effective_seconds,
            absolute - allocation.started_monotonic - 30, places=5)
        self.assertEqual(allocation.policy.cleanup, 60)
        with self.assertRaisesRegex(ContractError, "cannot be renewed"):
            value.register_conversation(meta["conversation"], absolute + 1)

    def test_fixed_selector_has_no_native_conversation_clamp(self):
        value = self.transport_shell()
        bindings = {key: "1" * 64 for key in ("source_sha256", "policy_sha256", "launcher_sha256")}
        allocation = value.prepare("p3b-01.fixed.select", "fixed_selector", {"role": "fixed_selector"}, bindings)
        self.assertIsNone(allocation.conversation_deadline)
        self.assertEqual((allocation.effective_seconds, allocation.policy.cleanup), (240, 60))

    def test_native_selector_signed_blocks_are_retained_losslessly(self):
        from .transport import normalize
        signed = {"type": "thinking", "thinking": "", "signature": "SYNTHETIC-SIGNATURE"}
        raw = {"id": "fixture-message", "model": "claude-opus-5", "stop_reason": "tool_use",
               "usage": {"input_tokens": 1, "output_tokens": 2},
               "content": [signed, {"type": "tool_use", "id": "fixture-read", "name": "read",
                   "input": {"filePath": "/fixture/context/candidates/A.md"}}]}
        value = normalize("native_selector", raw, None, 0.5)
        self.assertEqual(value["provider_response"], raw)
        self.assertEqual(value["provider_response"]["content"][0], signed)

    def test_absent_startup_attachment_blocks_before_sdk_import_or_constructor(self):
        from .transport import Transport
        with patch.object(supervision, "require_transport_attachment", side_effect=ContractError("absent attachment")):
            with self.assertRaisesRegex(ContractError, "absent attachment"):
                Transport(anthropic_api_key="fixture-not-a-secret", openai_api_key="fixture-not-a-secret")


class SelectorOwnedWorkerTests(unittest.TestCase):
    def fixture_transport(self, behavior=None):
        import httpx
        import httpx2

        from .deadline import Policy
        from .transport import Transport

        self.http_calls: list[dict] = []

        def response(request):
            self.http_calls.append(json.loads(request.content))
            return httpx2.Response(200, json={"id": "fixture-s2-selector", "type": "message",
                "role": "assistant", "model": "claude-opus-5", "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "SYNTHETIC selector response"}],
                "usage": {"input_tokens": 80, "output_tokens": 24, "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0, "cache_creation": {"ephemeral_5m_input_tokens": 0,
                        "ephemeral_1h_input_tokens": 0}, "service_tier": "standard", "inference_geo": "global"}})

        value = Transport(anthropic_api_key="fixture-not-a-secret", openai_api_key="fixture-not-a-secret",
            http_transports={"anthropic": httpx2.MockTransport(response),
                "openai": httpx.MockTransport(lambda _: (_ for _ in ()).throw(AssertionError("wrong provider")))},
            fixture_policy=Policy(completion=10, cleanup=2, editor_margin=.01, editor_minimum=.01),
            fixture_behavior=behavior)
        self.addCleanup(value.close)
        return value

    def bind(self, value):
        from . import ledger_core
        bindings = {key: "1" * 64 for key in ("study_sha256", "source_sha256", "policy_sha256", "launcher_sha256")}
        body = {"model": "claude-opus-5", "max_tokens": 16000, "thinking": {"type": "adaptive"},
                "output_config": {"effort": "high"}, "inference_geo": "global", "service_tier": "standard_only",
                "messages": [{"role": "user", "content": "SYNTHETIC selector fixture"}]}
        slot = "p3b-01.adaptive.editor.select.seq2.t01"
        meta = {"role": "native_selector", "pair": "p3b-01", "cell": "p3b-01:adaptive",
                "conversation": "p3b-01:adaptive:select.seq2"}
        value.register_conversation(meta["conversation"], time.monotonic() + 600)
        allocation = value.prepare(slot, "native_selector", meta, bindings)
        intent = {"slot_id": slot, "role": "native_selector", "pair": "p3b-01", "cell": meta["cell"],
            "study_sha256": bindings["study_sha256"], "fixture": True, "dispatch_id": "fixture:0001",
            "request_sha256": digest(body), "request": body, "reservation": ledger_core._reservation("native_selector")}
        value.bind_intent(intent, allocation)
        return bindings, body, intent

    def test_actual_pinned_selector_sdk_response_has_bound_native_role_audit(self):
        from . import ledger_core
        from .transport import validate_audit
        value = self.fixture_transport()
        bindings, body, intent = self.bind(value)
        response = value.create("native_selector", body)
        result = ledger_core._result(intent, response)
        audit = value.commit(intent["slot_id"], result)
        validate_audit(audit, intent=intent, result=result, bindings=bindings)
        self.assertEqual((result["status"], result["reserved_micro_usd"]), ("response", 0))
        self.assertEqual(audit["role"], "native_selector")
        self.assertTrue(audit["worker_stopped"] and audit["sdk_invoked"])
        self.assertEqual(len(self.http_calls), 1)

    def test_uncooperative_selector_worker_holds_full_liability_and_cannot_resend(self):
        from . import ledger_core
        from .deadline import KnownDeadlineStop
        from .transport import TransportFailure, validate_audit
        value = self.fixture_transport({"block_loop": True})
        bindings, body, intent = self.bind(value)
        with self.assertRaises(TransportFailure) as caught:
            value.create("native_selector", body)
        result = ledger_core._result(intent, None, failure=caught.exception.failure)
        audit = value.commit(intent["slot_id"], result)
        validate_audit(audit, intent=intent, result=result, bindings=bindings)
        self.assertEqual((result["status"], result["reserved_micro_usd"]), ("unknown", 11440000))
        self.assertTrue(audit["worker_stopped"])
        with self.assertRaises(KnownDeadlineStop):
            value.prepare("p3b-01.adaptive.editor.select.seq2.t02", "native_selector",
                {"role": "native_selector"}, bindings)
        self.assertEqual(self.http_calls, [])


class OperatorRetentionTests(unittest.TestCase):
    def test_explicit_public_operator_bytes_are_retained_losslessly(self):
        import base64
        import hashlib

        from .delivery import retain_operator_records
        directory = supervision.BASE / "operator"
        directory.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="public-fixture-", dir=directory)
        self.addCleanup(temporary.cleanup)
        source = Path(temporary.name) / "record.json"
        raw = b'{"fixture":true,"opaque":"synthetic"}\r\n'
        source.write_bytes(raw)
        name = source.relative_to(directory).as_posix()
        records = retain_operator_records(directory, [name])
        self.assertEqual(len(records), 1)
        self.assertEqual(base64.b64decode(records[0]["base64"], validate=True), raw)
        self.assertEqual(records[0]["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(source.read_bytes(), raw)

    def test_excluded_operator_names_reject_before_metadata(self):
        from .delivery import retain_operator_records
        for name in ("CREDENTIALS.JSON", "nested/synthetic.stdout.log", ".cache/record.json"):
            with self.subTest(name=name), patch.object(Path, "lstat", side_effect=AssertionError("metadata forbidden")):
                with self.assertRaises(ValueError):
                    retain_operator_records(supervision.BASE / "operator", [name])


if __name__ == "__main__":
    unittest.main(verbosity=2)
