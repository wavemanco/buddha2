"""Hermetic startup cases; actual agent/Windows rehearsal is separate S13 evidence."""
from __future__ import annotations

import contextlib
import copy
import datetime as dt
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest

from . import launch, supervision


class SupervisionTests(unittest.TestCase):
    def setUp(self):
        parent = launch.ROOT / "runs/phase3a-readiness-recovery-v1/unit-supervision" if os.name == "nt" else supervision.BASE
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
        checked.update(fixture=fixture, supervisor_agent="/root/rp2_supervisor", mode="mock" if fixture else "provider")
        checked["run"] = str(self.base / "native" / checked["study_sha256"] / ("mock" if fixture else "live"))
        inspection = {"container": {"container_id": "2" * 64}, "preflight": checked}
        inspection["inspection_sha256"] = digest(inspection)
        return checked, inspection

    def observation(self, request, *, status="running"):
        return {"kind": "phase3a-rp2-supervisor-observation-v1", "tool": "collaboration.list_agents",
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

    def test_s11_timeout_clears_keys_before_transport_claim_or_binding(self):
        from .tests_launch import checked
        value = checked("provider")
        keys = {"anthropic_api_key": "fixture-not-a-secret", "openai_api_key": "fixture-not-a-secret"}
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(launch, "preflight", return_value=value))
            stack.enter_context(patch.object(launch, "writer_lock", return_value=contextlib.nullcontext()))
            stack.enter_context(patch.object(launch, "_completion_path", side_effect=lambda p: p))
            stack.enter_context(patch.object(launch, "read_json", return_value={"inspection_sha256": "0" * 64}))
            stack.enter_context(patch.object(launch, "validate_inspection"))
            stack.enter_context(patch.object(Path, "iterdir", return_value=iter([Path("lo"), Path("eth0")])))
            stack.enter_context(patch.dict(os.environ, {"BUDDHA2_RELEASE_LAUNCH_MODE": "provider", "BUDDHA2_OFFLINE": "0"}))
            stack.enter_context(patch.object(launch, "_credentials", return_value=keys))
            stack.enter_context(patch.object(supervision, "wait_for_attachment", side_effect=ContractError("fixture attachment timeout")))
            claim = stack.enter_context(patch.object(launch, "_live_study_claim", side_effect=AssertionError("claim before ACK")))
            bind = stack.enter_context(patch.object(launch, "_bind_credentials", side_effect=AssertionError("binding before ACK")))
            run = stack.enter_context(patch.object(launch, "_workflow_run", side_effect=AssertionError("workflow before ACK")))
            sdk = stack.enter_context(patch("followups.phase3a_readiness_recovery_v1.transport.Transport",
                                            side_effect=AssertionError("SDK construction before ACK")))
            with self.assertRaisesRegex(ContractError, "attachment timeout"):
                launch.execute(Path(value["study_path"]), Path(value["grant_path"]), "all", "provider", Path("inspection.json"),
                               supervisor_agent="/root/rp2_supervisor")
            claim.assert_not_called()
            bind.assert_not_called()
            run.assert_not_called()
            sdk.assert_not_called()
        self.assertEqual(set(keys.values()), {""})

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
