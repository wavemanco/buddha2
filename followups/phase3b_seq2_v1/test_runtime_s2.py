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
from unittest.mock import Mock, patch

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
    @staticmethod
    def transport_shell():
        from .transport import Transport
        value = Transport.__new__(Transport)
        value._closed = value._terminal = False
        value._local = threading.local()
        value._conversations = {}
        value._soft_clocks = {}
        value.fixture, value.startup_attachment = True, None
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


class SoftConversationTimingTests(unittest.TestCase):
    def setUp(self):
        from . import deadline

        self.timing = deadline
        parent = ROOT / "runs/phase3b-seq2-v1/unit-timing" if os.name == "nt" else supervision.BASE
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="soft-time-", dir=parent)
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.now, self.sequence = 0.0, 0
        clock = patch.object(deadline.time, "monotonic", side_effect=lambda: self.now)
        clock.start()
        self.addCleanup(clock.stop)
        self.bindings = {"study_sha256": "1" * 64, "source_sha256": "2" * 64,
                         "policy_sha256": "3" * 64, "launcher_sha256": "4" * 64}
        self.slot = "p3b-01.adaptive.editor.select.seq2.t11"
        self.financial = {"spent_micro_usd": 7, "reserved_micro_usd": 0, "attempts": 10}

    def new_clock(self):
        self.sequence += 1
        record = self.timing.clock_record(study_sha256=self.bindings["study_sha256"],
            source_sha256=self.bindings["source_sha256"], pilot="p3b-01", label="select.seq2",
            fixture=True, editor_profile_sha256="5" * 64, started=0.0)
        directory = self.base / str(self.sequence) / "timing-controls" / digest(
            {"conversation_id": record["conversation_id"]})
        return self.timing.Clock(record, directory)

    def gate(self, clock):
        return clock.before_request(self.slot, self.bindings, self.financial)

    @staticmethod
    def read(path):
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def sealed(value):
        return {**value, "sha256": digest(value)}

    def answer(self, clock, decision="continue", wait=0.0):
        def publish(_):
            self.now += wait
            request = clock.directory / f"review-{len(clock.reviews) + 1:02}.request.json"
            self.last_decision = self.timing.decide(request, decision)
        return patch.object(self.timing.time, "sleep", side_effect=publish)

    def test_saved_543_second_shortfall_keeps_full_request_budget_in_new_mode(self):
        from . import transport

        clock = self.new_clock()
        self.now = 543.052
        with self.assertRaises(self.timing.KnownDeadlineStop):
            self.timing.budget(600, now=self.now)
        value = SelectorRuntimeTests.transport_shell()
        with patch.object(transport, "Clock", return_value=clock):
            value.register_conversation(clock.record["conversation_id"],
                                        clock.record["deadline_monotonic"], clock=clock.record)
        meta = {"role": "native_selector", "conversation": clock.record["conversation_id"]}
        with self.assertRaisesRegex(ContractError, "pre-intent review gate"):
            value.prepare(self.slot, "native_selector", meta, self.bindings)
        value.review_before_intent(self.slot, "native_selector", meta, self.bindings, self.financial)
        allocation = value.prepare(self.slot, "native_selector", meta, self.bindings)
        self.assertEqual((allocation.effective_seconds, allocation.conversation_deadline,
                          allocation.policy.cleanup), (240, None, 60))
        self.assertFalse((clock.directory / "review-01.request.json").exists())

    def test_warning_and_grace_are_recorded_once_without_a_review_or_call(self):
        clock = self.new_clock()
        for instant in (479.0, 480.0, 600.0, 899.999):
            self.now = instant
            gate = self.gate(clock)
            self.assertEqual(gate["reviews"], [])
            self.assertEqual((clock.directory / "warning.json").exists(), instant >= 480)
            self.assertEqual((clock.directory / "grace.json").exists(), instant >= 600)
        self.assertFalse(any(clock.directory.glob("review-*.request.json")))
        self.assertFalse(self.read(clock.directory / "warning.json")["automatic_provider_call"])

    def test_review_pauses_before_admission_and_continue_excludes_waiting_time(self):
        clock = self.new_clock()
        original = (clock.directory / "clock.json").read_bytes()
        self.now = 900.0
        with self.answer(clock, wait=120):
            gate = self.gate(clock)
        request = self.read(clock.directory / "review-01.request.json")
        ack = self.read(clock.directory / "review-01.ack.json")
        self.assertTrue(request["controller_paused"])
        self.assertEqual(request["slot_id"], self.slot)
        self.assertEqual(request["financial"], self.financial)
        self.assertEqual((self.now, gate["soft_deadline_monotonic"], ack["paused_seconds"]),
                         (1020, 1620, 120))
        self.assertEqual((self.last_decision["provider_calls"],
                          self.last_decision["financial_authority_changed"]), (0, False))
        self.assertEqual((clock.directory / "clock.json").read_bytes(), original)
        self.now = 1619.99
        self.assertEqual(len(self.gate(clock)["reviews"]), 1)
        with self.assertRaisesRegex(ContractError, "already closed"):
            self.timing.decide(clock.directory / "review-01.request.json", "continue")

    def test_operator_stop_and_no_answer_timeout_are_terminal_before_a_new_intent(self):
        for decision, reason in (("stop", "operator_stop"), (None, "review_timeout")):
            with self.subTest(decision=decision):
                clock = self.new_clock()
                self.now = 900.0
                pause = (self.answer(clock, "stop") if decision else patch.object(
                    self.timing.time, "sleep", side_effect=lambda _: setattr(self, "now", 2700.0)))
                with pause, self.assertRaises(self.timing.TimingStop) as stopped:
                    self.gate(clock)
                self.assertEqual(stopped.exception.reason, reason)
                self.assertEqual(self.read(clock.directory / "review-01.ack.json")["outcome"], reason)
                self.assertEqual(clock.reviews, [])

    def test_late_local_admission_pause_still_grants_full_time_from_resume(self):
        clock = self.new_clock()
        self.now = 2000.0
        with self.answer(clock, wait=120):
            gate = self.gate(clock)
        self.assertEqual((self.now, gate["soft_deadline_monotonic"]), (2120, 2720))
        self.now = 2719.999
        self.assertEqual(len(self.gate(clock)["reviews"]), 1)

    def test_local_notice_write_rechecks_soft_and_hard_deadlines_before_admission(self):
        for initial, after_write in ((899.0, 901.0), (65399.0, 65401.0)):
            with self.subTest(initial=initial):
                clock = self.new_clock()
                self.now = initial
                original_write = self.timing.write_once

                def delayed(path, value):
                    original_write(path, value)
                    if path.name == "warning.json":
                        self.now = after_write

                with patch.object(self.timing, "write_once", side_effect=delayed), self.answer(clock):
                    if after_write < 65400:
                        gate = self.gate(clock)
                        self.assertEqual(gate["soft_deadline_monotonic"], after_write + 600)
                        self.assertEqual(len(gate["reviews"]), 1)
                    else:
                        with self.assertRaises(self.timing.TimingStop) as stopped:
                            self.gate(clock)
                        self.assertEqual(stopped.exception.reason, "hard_lifetime")
                        self.assertFalse((clock.directory / "review-01.request.json").exists())

    def test_slow_ack_persistence_keeps_only_the_slot_permission_just_granted(self):
        clock = self.new_clock()
        self.now = 900.0
        original_write = self.timing.write_once

        def delayed(path, value):
            original_write(path, value)
            if path.name == "review-01.ack.json":
                self.now = 1601.0

        with patch.object(self.timing, "write_once", side_effect=delayed), self.answer(clock):
            gate = self.gate(clock)
        self.assertEqual((gate["checked_monotonic"], gate["soft_deadline_monotonic"]), (900, 1500))
        self.assertEqual(self.now, 1601)
        self.assertEqual(gate["slot_id"], self.slot)
        with self.assertRaises(ContractError):
            self.timing.validate_gate(clock.record, gate,
                slot_id="p3b-01.adaptive.editor.select.seq2.t12", bindings=self.bindings, fixture=True)

    def test_original_hard_lifetime_cannot_be_extended_by_a_timing_review(self):
        clock = self.new_clock()
        self.now = clock.record["deadline_monotonic"] - 300
        with self.assertRaises(self.timing.TimingStop) as stopped:
            self.gate(clock)
        self.assertEqual(stopped.exception.reason, "hard_lifetime")
        self.assertFalse(any(clock.directory.glob("review-*.request.json")))

    def test_wrong_request_and_stale_decisions_are_rejected_without_ack_or_allowance(self):
        for change in ("request", "early", "expired", "action"):
            with self.subTest(change=change):
                clock = self.new_clock()
                self.now = 900.0

                def forged(_):
                    request = self.read(clock.directory / "review-01.request.json")
                    created = dt.datetime.fromisoformat(request["created_at_utc"])
                    if change == "early":
                        created -= dt.timedelta(seconds=1)
                    elif change == "expired":
                        created = dt.datetime.fromisoformat(request["expires_at_utc"])
                    decision = self.sealed({"kind": "phase3b-time-review-decision-v1",
                        "request_sha256": "0" * 64 if change == "request" else request["sha256"],
                        "decision": "retry" if change == "action" else "continue",
                        "created_at_utc": created.isoformat()})
                    (clock.directory / "review-01.decision.json").write_text(
                        json.dumps(decision), encoding="utf-8")

                with patch.object(self.timing.time, "sleep", side_effect=forged), self.assertRaises(ContractError):
                    self.gate(clock)
                self.assertEqual(clock.deadline, 900)
                self.assertFalse((clock.directory / "review-01.ack.json").exists())

    def test_decision_file_cannot_be_replayed_for_a_later_review(self):
        clock = self.new_clock()
        self.now = 900.0
        with self.answer(clock):
            self.gate(clock)
        prior = (clock.directory / "review-01.decision.json").read_bytes()
        self.now = 1500.0
        with patch.object(self.timing.time, "sleep", side_effect=lambda _: (
            clock.directory / "review-02.decision.json").write_bytes(prior)), self.assertRaises(ContractError):
            self.gate(clock)
        self.assertEqual(len(clock.reviews), 1)
        self.assertFalse((clock.directory / "review-02.ack.json").exists())

    def test_resealed_gate_cannot_change_its_allowance_source_or_session(self):
        clock = self.new_clock()
        self.now = 543.052
        gate = self.gate(clock)
        for change in ("allowance", "source", "session"):
            with self.subTest(change=change):
                altered, bindings, slot = copy.deepcopy(gate), dict(self.bindings), self.slot
                if change == "allowance":
                    altered["soft_deadline_monotonic"] += 1
                    altered = self.sealed({k: v for k, v in altered.items() if k != "sha256"})
                elif change == "source":
                    bindings["source_sha256"] = "0" * 64
                else:
                    slot = "p3b-02.adaptive.editor.select.seq2.t11"
                with self.assertRaises(ContractError):
                    self.timing.validate_gate(clock.record, altered, slot_id=slot,
                                              bindings=bindings, fixture=True)

    def test_hard_money_token_and_request_caps_precede_any_timing_pause(self):
        from . import accounting, workflow
        from .test_workflow_s2 import minimal_study

        study = minimal_study()
        slot = next(name for name, row in study["slots"].items()
                    if row["role"] == "native_selector" and row["turn"] == 1)
        meta = study["slots"][slot]
        for limit in ("money", "tokens", "requests"):
            with self.subTest(limit=limit):
                state = workflow._empty_state(study, True)
                if limit == "money":
                    state["spent_micro_usd"] = accounting.POLICY["phase_micro_usd"]
                elif limit == "tokens":
                    state["cells"][meta["cell"]]["input_tokens"] = accounting.POLICY["cell_input"]
                else:
                    state["attempts"] = accounting.WORKLIST_PROFILE["maximum_admitted_attempts"]
                ledger = accounting._DeadlineCore.__new__(accounting._DeadlineCore)
                ledger._lock, ledger.journal = threading.RLock(), self.base / "journal"
                ledger.hooks = Mock()
                ledger.hooks.before_intent.side_effect = AssertionError("timing pause bypassed hard limit")
                manifest = {"inputs": {"slots": study["slots"], "fixture": True,
                    "study_sha256": study["study_sha256"], "editor_tools": {},
                    "policy": study["policy"]}}
                with patch.object(accounting, "NATIVE", self.base), patch.object(
                    accounting.core, "writer_lock", return_value=threading.RLock()), patch.object(
                    accounting, "_replay", return_value=(state, [], manifest)), patch.object(
                    accounting, "_stop", return_value=None), patch.object(
                    accounting, "validate_request"), patch.object(accounting.core, "_append_event") as appended:
                    with self.assertRaises((accounting.PhaseBudgetStop, accounting.CellBudgetStop)):
                        ledger.dispatch(slot, "native_selector", {"synthetic": True})
                ledger.hooks.before_intent.assert_not_called()
                self.assertEqual(appended.call_args.args[1], "budget_stop")


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

    def bind(self, value, *, soft_timing=False):
        from . import ledger_core
        bindings = {key: "1" * 64 for key in ("study_sha256", "source_sha256", "policy_sha256", "launcher_sha256")}
        body = {"model": "claude-opus-5", "max_tokens": 16000, "thinking": {"type": "adaptive"},
                "output_config": {"effort": "high"}, "inference_geo": "global", "service_tier": "standard_only",
                "messages": [{"role": "user", "content": "SYNTHETIC selector fixture"}]}
        slot = "p3b-01.adaptive.editor.select.seq2.t01"
        meta = {"role": "native_selector", "pair": "p3b-01", "cell": "p3b-01:adaptive",
                "conversation": "p3b-01:adaptive:select.seq2"}
        if soft_timing:
            from . import deadline, transport
            from .support import NATIVE

            NATIVE.mkdir(parents=True, exist_ok=True)
            temporary = tempfile.TemporaryDirectory(prefix="soft-worker-", dir=NATIVE)
            self.addCleanup(temporary.cleanup)
            record = deadline.clock_record(study_sha256=bindings["study_sha256"],
                source_sha256=bindings["source_sha256"], pilot="p3b-01", label="select.seq2",
                fixture=True, editor_profile_sha256="5" * 64, started=time.monotonic() - 543.052)
            clock = deadline.Clock(record, Path(temporary.name))
            with patch.object(transport, "Clock", return_value=clock):
                value.register_conversation(meta["conversation"], record["deadline_monotonic"], clock=record)
            value.review_before_intent(slot, "native_selector", meta, bindings,
                                       {"spent_micro_usd": 0, "reserved_micro_usd": 0})
        else:
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
        self.assertEqual(audit["kind"], "phase3b-s2-transport-audit-v1")
        self.assertNotIn("conversation_timing", audit)
        self.assertEqual((result["status"], result["reserved_micro_usd"]), ("response", 0))
        self.assertEqual(audit["role"], "native_selector")
        self.assertTrue(audit["worker_stopped"] and audit["sdk_invoked"])
        self.assertEqual(len(self.http_calls), 1)

    def test_actual_pinned_soft_timing_sdk_audit_binds_clock_and_rejects_resealed_grace(self):
        from . import ledger_core
        from .transport import validate_audit

        value = self.fixture_transport()
        bindings, body, intent = self.bind(value, soft_timing=True)
        result = ledger_core._result(intent, value.create("native_selector", body))
        audit = value.commit(intent["slot_id"], result)
        validate_audit(audit, intent=intent, result=result, bindings=bindings)
        self.assertEqual(audit["kind"], "phase3b-s2-transport-audit-v2")
        self.assertIsNone(audit["budget"]["conversation_deadline"])
        self.assertEqual(audit["budget"]["effective_seconds"], 10)
        self.assertEqual(len(self.http_calls), 1)
        altered = copy.deepcopy(audit)
        gate = altered["conversation_timing"]["gate"]
        gate["soft_deadline_monotonic"] += 1
        gate["sha256"] = digest({k: v for k, v in gate.items() if k != "sha256"})
        altered["sha256"] = digest({k: v for k, v in altered.items() if k != "sha256"})
        with self.assertRaises(ContractError):
            validate_audit(altered, intent=intent, result=result, bindings=bindings)

    def test_snapshot_intervals_keep_study_binding_for_actual_soft_timing_sdk_audit(self):
        from buddha2.artifacts import file_hash

        from . import ledger_core, transport, workflow
        from .support import NATIVE

        value = self.fixture_transport()
        bindings, body, intent = self.bind(value, soft_timing=True)
        result = ledger_core._result(intent, value.create("native_selector", body))
        audit = value.commit(intent["slot_id"], result)
        NATIVE.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="snapshot-soft-audit-", dir=NATIVE) as raw:
            run = Path(raw)
            audit_file = run / "audit.json"
            audit_file.write_text(json.dumps(audit), encoding="utf-8")
            slot = intent["slot_id"]
            state = {"status": "ready", "results": {slot: result}, "intents": {slot: intent}}
            saved = {"branches": {}, "seals": {}, "assessments": {}, "readiness": None}
            actual_read = transport.read_audit

            def omit_study(*args, **kwargs):
                kwargs["bindings"] = {key: entry for key, entry in kwargs["bindings"].items()
                                      if key != "study_sha256"}
                return actual_read(*args, **kwargs)

            with patch.object(workflow, "paths", return_value=(run, run / "journal")), \
                    patch.object(workflow, "saved", return_value=saved), \
                    patch.object(transport, "audit_path", return_value=audit_file):
                records = workflow._snapshot_records(run / "study.json", bindings, state, True)
                interval = records["audit_intervals"][slot]
                self.assertEqual(interval["audit_file_sha256"], file_hash(audit_file))
                self.assertEqual(interval["started_at_utc"], audit["budget"]["started_utc"])
                self.assertEqual(interval["finished_at_utc"], audit["finished_utc"])
                self.assertNotIn("validation_failure", records)
                with patch.object(transport, "read_audit", side_effect=omit_study), \
                        self.assertRaises(ContractError):
                    workflow._snapshot_records(run / "study.json", bindings, state, True)
        self.assertEqual(len(self.http_calls), 1)

    def paused_ledger(self):
        from . import accounting, deadline, ledger_core
        from .support import ROOT
        from .test_workflow_s2 import minimal_study

        value = self.fixture_transport()
        study = minimal_study()
        study_id = digest(["synthetic-soft-ledger", time.time_ns()])
        bindings = {"source_sha256": "1" * 64, "policy_sha256": digest(accounting.POLICY),
                    "launcher_sha256": "2" * 64}
        authority = {"study_sha256": study_id, "authorization_id": "synthetic-timing-fixture",
            "authorized": False, "cap_micro_usd": accounting.POLICY["phase_micro_usd"],
            "canary_cap_micro_usd": accounting.POLICY["first_micro_usd"], "expansion_authorized": False,
            "control_policy_sha256": ledger_core.am1.CONTROL_SHA256,
            "billing_profile": ledger_core.am1.BILLING_PROFILE}
        slot = "p3b-01.adaptive.editor.select.seq2.t01"
        record = deadline.clock_record(study_sha256=study_id, source_sha256=bindings["source_sha256"],
            pilot="p3b-01", label="select.seq2", fixture=True,
            editor_profile_sha256="5" * 64, started=time.monotonic() - 900.001)
        value.register_conversation(record["conversation_id"], record["deadline_monotonic"], clock=record)
        clock = value._soft_clocks[record["conversation_id"]]
        guard_observations = []

        def guard(state):
            guard_observations.append(((clock.directory / "review-01.ack.json").exists(),
                                       len(self.http_calls), state["attempts"]))

        journal = accounting.canonical_journal(study_id, True)
        tools = json.loads((ROOT / "followups/phase3a_v1/editor-tools.json").read_text(encoding="utf-8"))
        ledger = accounting.Ledger(journal, study_sha256=study_id, slots=study["slots"],
            authority=authority, transport=value, bindings=bindings, editor_tools=tools, admission_guard=guard)
        body = {"model": "claude-opus-5", "max_tokens": 16000, "thinking": {"type": "adaptive"},
            "output_config": {"effort": "high"}, "inference_geo": "global", "service_tier": "standard_only",
            "messages": [{"role": "user", "content": "SYNTHETIC paused selector fixture"}]}
        return ledger, clock, slot, body, guard_observations

    def dispatch_paused(self, ledger, clock, slot, body, decision):
        from . import deadline, ledger_core

        returned, failures = [], []

        def dispatch():
            try:
                returned.append(ledger.dispatch(slot, "native_selector", body))
            except Exception as error:
                failures.append(error)

        thread = threading.Thread(target=dispatch, daemon=True)
        thread.start()
        target = clock.directory / "review-01.request.json"
        try:
            wait_until = time.monotonic() + 10
            while not target.exists() and thread.is_alive() and time.monotonic() < wait_until:
                time.sleep(.005)
            self.assertTrue(target.exists(), "controller never reached its existing pre-intent review")
            self.assertEqual(ledger_core._read_events(ledger.journal), ([], b""))
            self.assertEqual(self.http_calls, [])
            deadline.decide(target, decision)
        finally:
            if thread.is_alive() and target.exists() and not (
                    clock.directory / "review-01.decision.json").exists():
                deadline.decide(target, "stop")
            thread.join(timeout=20)
        self.assertFalse(thread.is_alive(), "fixture controller did not finish after the timing answer")
        return returned, failures

    def test_actual_ledger_pause_has_zero_intents_then_same_slot_and_post_wait_guard(self):
        from . import ledger_core

        ledger, clock, slot, body, guarded = self.paused_ledger()
        returned, failures = self.dispatch_paused(ledger, clock, slot, body, "continue")
        self.assertEqual(failures, [])
        self.assertEqual(guarded, [(True, 0, 0)])
        self.assertEqual(len(returned), 1)
        self.assertEqual(returned[0]["slot_id"], slot)
        self.assertEqual(len(self.http_calls), 1)
        events, tail = ledger_core._read_events(ledger.journal)
        self.assertEqual([event["kind"] for event in events], ["intent", "result"])
        self.assertFalse(tail)
        self.assertEqual(events[0]["record"]["slot_id"], slot)
        state = ledger.state()
        self.assertEqual((state["status"], state["attempts"], state["reserved_micro_usd"]), ("ready", 1, 0))
        self.assertEqual(state["transport_audit_summary"]["validated_audits"], 1)

    def test_actual_ledger_operator_stop_replays_as_operator_stop_without_sdk_or_intent(self):
        from . import deadline, ledger_core

        ledger, clock, slot, body, guarded = self.paused_ledger()
        returned, failures = self.dispatch_paused(ledger, clock, slot, body, "stop")
        self.assertEqual(returned, [])
        self.assertEqual(len(failures), 1)
        self.assertIsInstance(failures[0], deadline.TimingStop)
        self.assertEqual(failures[0].reason, "operator_stop")
        self.assertEqual(guarded, [])
        events, _ = ledger_core._read_events(ledger.journal)
        self.assertEqual([event["kind"] for event in events], ["halt"])
        state = ledger.state()
        self.assertEqual((state["status"], state["attempts"], state["spent_micro_usd"],
                          state["reserved_micro_usd"]), ("stopped-by-operator", 0, 0, 0))
        self.assertEqual(state["deadline_stop"]["kind"], "phase3b-timing-stop-v1")

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
