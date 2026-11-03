"""Host orchestration contracts; these synthetic checks are not S13 execution."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import digest

from . import host_checks as host


class HostGlueTests(unittest.TestCase):
    def setUp(self):
        parent = host.ROOT / "runs" / host.PREFIX / "host-unit" if os.name == "nt" else Path("/results") / host.PREFIX
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="host-glue-", dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / "runs" / host.PREFIX / "verification"
        self.output.mkdir(parents=True)
        self.root_patch = patch.object(host, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        body = {key: digest(key) for key in host.BINDINGS if key != "study_sha256"}
        body.update(fixture_supervision_rehearsal=False, tasks=["fixed mock task inventory"])
        self.study = {**body, "study_sha256": digest(body)}
        fresh_body = {**body, "fixture_supervision_rehearsal": True}
        self.fresh = {**fresh_body, "study_sha256": digest(fresh_body)}
        prefix = "/results/" + self.output.relative_to(self.root / "runs").as_posix()
        self.matrix = {"passed": True, "mock_http_calls": 711,
            **{key: self.study[key] for key in host.BINDINGS}, "study_path": prefix + "/release/study.json",
            "mock_grant_path": prefix + "/release/mock-grant.json", "live_grant_path": prefix + "/release/live-grant.json"}
        self.prepared = {**{key: self.fresh[key] for key in host.BINDINGS}, "fixture": True,
            "fixture_supervision_rehearsal": True, "provider_calls": 0, "provider_grant_permitted": False,
            "study_path": prefix + "/operational-rehearsal/release/study.json",
            "mock_grant_path": prefix + "/operational-rehearsal/release/mock-grant.json",
            "run": "/results/" + host.PREFIX + "/native/" + self.fresh["study_sha256"] + "/mock"}
        self.write(self.output / "operational-rehearsal/prepared.json", self.prepared)
        self.write(self.output / "operational-rehearsal/release/study.json", self.fresh)
        self.agent = "/root/rp2_fixture_supervisor"

    def write(self, target, value, *, seal=False):
        if seal:
            value = {**value, "sha256": digest({k: v for k, v in value.items() if k != "sha256"})}
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value), encoding="utf-8")
        return value

    def test_fresh_mock_only_release_is_distinct_but_same_scientific_profile(self):
        fresh, prepared, run = host.rehearsal_inputs(self.output, self.study, self.matrix)
        self.assertEqual(fresh, self.fresh)
        self.assertEqual(prepared, self.prepared)
        self.assertNotEqual(fresh["study_sha256"], self.study["study_sha256"])
        self.assertFalse(run.exists())

    def test_handoff_export_targets_pass_actual_inspect_namespace_without_launch(self):
        from . import inspect_adapter
        fresh, prepared, run = host.rehearsal_inputs(self.output, self.study, self.matrix)
        handoff = host.supervisor_handoff(self.output, fresh, prepared, run, self.agent)
        with patch.object(inspect_adapter, "ROOT", self.root), \
                patch.object(inspect_adapter, "read_snapshot", side_effect=RuntimeError("namespace accepted; stop before payload IO")), \
                patch.object(inspect_adapter, "_host_command", side_effect=AssertionError("must not launch")) as command:
            for name in ("first-pair", "closure"):
                target = Path(handoff["export_outputs"][name])
                expected = self.root / "runs" / host.PREFIX / "visibility-exports" / fresh["study_sha256"] / "mock" / name / "supervised"
                self.assertEqual(target, expected)
                self.assertEqual(inspect_adapter.output_path(target), target)
                with self.subTest(checkpoint=name), self.assertRaisesRegex(RuntimeError, "namespace accepted"):
                    inspect_adapter.host_export(run / "visibility" / name / "snapshot", target)
                with self.assertRaisesRegex(inspect_adapter.ProjectionError, "separate visibility-exports"):
                    inspect_adapter.host_export(run / "visibility" / name / "snapshot", self.output / "operational-rehearsal/exports" / name)
            command.assert_not_called()

    def test_private_stream_paths_reject_before_metadata_and_json_is_strict(self):
        for target in (self.root / "live.STDOUT.json", self.root / "unknown_stderr.txt", self.root / "AUTH.JSON"):
            with self.subTest(path=target), patch.object(Path, "lstat", side_effect=AssertionError("private metadata reached")):
                for function in (host.read, host.sha):
                    with self.assertRaises(ValueError):
                        function(target)
        target = self.output / "bad-proof.json"
        for raw in ('{"passed":false,"passed":true}', '{"value":NaN}'):
            target.write_text(raw, encoding="utf-8")
            with self.assertRaises(ValueError):
                host.read(target)

    def test_existing_run_or_journal_cannot_be_resumed_as_operational_proof(self):
        for kind in ("run", "journal"):
            if kind == "run":
                target = self.root / "runs" / self.prepared["run"].removeprefix("/results/")
            else:
                target = self.root / "runs" / host.PREFIX / self.fresh["study_sha256"] / "mock/journal"
            target.mkdir(parents=True)
            with self.subTest(existing=kind), self.assertRaisesRegex(ValueError, "already exist"):
                host.rehearsal_inputs(self.output, self.study, self.matrix)
            target.rmdir()

    def test_foreign_rehearsal_settings_flag_or_public_paths_are_rejected(self):
        for field, wrong in (("fixture_supervision_rehearsal", False), ("provider_grant_permitted", True),
                             ("study_path", self.matrix["study_path"]), ("source_sha256", "0" * 64)):
            altered = {**self.prepared, field: wrong}
            self.write(self.output / "operational-rehearsal/prepared.json", altered)
            with self.subTest(field=field), self.assertRaises(ValueError):
                host.rehearsal_inputs(self.output, self.study, self.matrix)
        self.write(self.output / "operational-rehearsal/prepared.json", self.prepared)
        altered = {**self.fresh, "tasks": ["different task"]}
        altered["study_sha256"] = digest({k: v for k, v in altered.items() if k != "study_sha256"})
        self.write(self.output / "operational-rehearsal/release/study.json", altered)
        with self.assertRaises(ValueError):
            host.rehearsal_inputs(self.output, self.study, self.matrix)

    def test_launcher_routes_fresh_supervised_mock_and_main_configuration_separately(self):
        directory = self.root / "runs" / host.PREFIX / "launcher"
        commands = []
        def execute(command, **kwargs):
            commands.append(command)
            action = command[command.index("-Action") + 1]
            is_mock = action == "mock"
            expected = self.fresh if is_mock else self.study
            checked = {**{k: expected[k] for k in host.BINDINGS}, "mode": "mock" if is_mock else "provider-config",
                "fixture": is_mock, "provider_calls": 0, "supervisor_agent": self.agent if is_mock else None,
                "fixture_supervision_rehearsal": is_mock}
            inspection = {"preflight": checked, "container": {"image": host.IMAGE,
                "network_mode": "none" if is_mock else "bridge", "state_at_inspection": "created", "read_only_rootfs": True}}
            self.write(directory / (action + ".inspection.json"), inspection)
            if is_mock:
                self.write(directory / (action + ".result.json"), {"action": "mock", "preflight": checked,
                    "exit_code": 0, "state": "exited", "actual_credentials_supplied": False})
            return {"exit_code": 0, "stdout": "explicit fake-key fixture only", "stderr": ""}
        with patch.object(host, "execute", side_effect=execute), patch.object(host, "supervision_checks") as checked:
            host.launch_checks(self.output, self.study, self.matrix, supervisor_agent=self.agent)
        self.assertEqual(len(commands), 2)
        self.assertEqual(commands[0][commands[0].index("-Study") + 1], self.prepared["study_path"].removeprefix("/results/"))
        self.assertEqual(commands[0][commands[0].index("-SupervisorAgent") + 1], self.agent)
        self.assertEqual(commands[1][commands[1].index("-Study") + 1], self.matrix["study_path"].removeprefix("/results/"))
        self.assertNotIn("-Live", commands[1])
        self.assertNotIn("-SupervisorAgent", commands[1])
        checked.assert_called_once()

    def golden_service(self):
        from .inspect_adapter import IMAGE as INSPECT_IMAGE
        fresh, prepared, run = host.rehearsal_inputs(self.output, self.study, self.matrix)
        handoff = host.supervisor_handoff(self.output, fresh, prepared, run, self.agent)
        observation = {"tool": "collaboration.list_agents", "request_sha256": "filled below",
                       "agent": {"agent_name": self.agent, "agent_status": "running"}}
        request = self.write(run / "supervision/request.json", {**{k: fresh[k] for k in host.BINDINGS},
            "supervisor_agent": self.agent, "fixture": True}, seal=True)
        observation["request_sha256"] = request["sha256"]
        ack = self.write(run / "supervision/ack.json", {"request": request, "supervisor_observation": observation}, seal=True)
        self.write(run / "supervision/receipt.json", {"request": request, "request_sha256": request["sha256"], "ack_sha256": ack["sha256"]}, seal=True)
        for name in ("readiness", "first"):
            barrier = {"study_sha256": fresh["study_sha256"], "fixture": True, "evidence_sha256": digest(name)}
            self.write(run / ("barrier-" + name + ".json"), barrier, seal=True)
            inspection = self.write(run / ("inspection-" + name + ".json"), {**barrier,
                "supervisor_agent": self.agent, "no_quality_continuation_gate": True, "notes": "Synthetic host-glue case, not S13."})
            self.write(run / ("readiness-review.json" if name == "readiness" else "first-review.json"), {"inspection": inspection}, seal=True)
        for name in ("first-pair", "closure"):
            self.write(run / "visibility" / name / "status.json", {**{k: fresh[k] for k in host.BINDINGS},
                "fixture": True, "visibility_status": "complete", "canonical_status": "complete",
                "worker_stopped": True, "reports_published": True}, seal=True)
            result = {"study_sha256": fresh["study_sha256"], "checkpoint": name, "provider_calls": 0,
                "exporter_stopped": True, "cleanup_verified": True}
            self.write(run / "visibility" / name / "result.json", result)
            target = Path(handoff["export_outputs"][name])
            self.write(target / "visibility-result.json", result)
            self.write(target / "export/result.json", {"roundtrip_equal": True, "samples": 8,
                "source_attachment_bytes_preserved": True, "model_network_attempts": {"fixture": 0}})
            self.write(target / "actual-container.json", {"image": INSPECT_IMAGE, "network_mode": "none", "read_only_root": True})
            self.write(target / "cleanup.json", {"exit_code": 0})
        self.write(run / "reports/final/summary.json", {"study_sha256": fresh["study_sha256"], "fixture": True,
            "primary_scored": 8, "readiness_passed": True, "attempts": 711, "scientific_complete": False,
            "authentic_live_path": False, "reserved_micro_usd": 0, "pending_intents": 0, "durable_unknown_results": 0})
        service = {"kind": "phase3a-rp2-supervisor-service-v1", **{k: fresh[k] for k in host.BINDINGS},
            "fixture": True, "provider_calls": 0, "parent_chat_ack_required": False,
            "supervisor_agent": self.agent, "handoff_sha256": handoff["sha256"],
            "references": {name: {"path": target, "sha256": host.sha(self.root / target)} for name, target in handoff["references"].items()}}
        self.write(self.output / "operational-rehearsal/service.json", service)
        return fresh, run, handoff

    def test_service_binds_actual_handoffs_with_explicit_fixture_science_separation(self):
        fresh, run, handoff = self.golden_service()
        proof = host.supervision_checks(self.output, self.study, fresh, run, handoff, 711)
        self.assertTrue(proof["passed"])
        self.assertFalse(proof["scientific_complete"])
        self.assertFalse(proof["authentic_live_path"])
        self.assertEqual(set(proof["references"]), {"attachment", "readiness", "first", "first-pair", "closure"})

    def test_service_cannot_omit_actor_hashes_or_depend_on_parent_reply(self):
        fresh, run, handoff = self.golden_service()
        target = self.output / "operational-rehearsal/service.json"
        service = host.read(target)
        for field, wrong in (("supervisor_agent", "/root/other"), ("references", {}), ("parent_chat_ack_required", True)):
            self.write(target, {**service, field: wrong})
            with self.subTest(field=field), self.assertRaises(ValueError):
                host.supervision_checks(self.output, self.study, fresh, run, handoff, 711)

    def test_mock_completion_cannot_claim_science_or_reuse_zero_call_resume(self):
        fresh, run, handoff = self.golden_service()
        target = run / "reports/final/summary.json"
        summary = host.read(target)
        for field, wrong in (("attempts", 0), ("scientific_complete", True), ("reserved_micro_usd", 1)):
            self.write(target, {**summary, field: wrong})
            with self.subTest(field=field), self.assertRaises(ValueError):
                host.supervision_checks(self.output, self.study, fresh, run, handoff, 711)

    def test_native_fixture_rejects_writable_old_data_before_start(self):
        from . import verify
        commands = []
        owner = "3" * 64
        def args(output, *, mode):
            return ["docker", "create", "--mount", f"type=bind,source={self.root / 'runs' / host.PREFIX},target=/results/{host.PREFIX}", host.IMAGE]
        def execute(command, **kwargs):
            commands.append(command)
            if command[:2] == ["docker", "create"]:
                return {"exit_code": 0, "stdout": owner, "stderr": ""}
            if command[:2] == ["docker", "inspect"]:
                isolated = self.output / "native-fixtures/terminal-readiness"
                actual = {"Image": host.IMAGE, "HostConfig": {"NetworkMode": "none", "ReadonlyRootfs": True},
                    "Mounts": [{"Source": str(self.root), "Destination": "/workspace", "RW": False},
                        {"Source": str(isolated), "Destination": "/results/" + host.PREFIX, "RW": True},
                        {"Source": str(self.root / "runs/phase3a-rc1-pilot-v1"), "Destination": "/results/phase3a-rc1-pilot-v1", "RW": True},
                        {"Source": str(self.output / "am1-inputs/hi"), "Destination": "/results/phase3a-h1-integrated-v1", "RW": False}],
                    "State": {"Running": False}}
                return {"exit_code": 0, "stdout": json.dumps([actual]), "stderr": ""}
            if command[:2] == ["docker", "rm"]:
                return {"exit_code": 0, "stdout": owner, "stderr": ""}
            raise AssertionError("unsafe fixture was started")
        with patch.object(verify, "ROOT", self.root), patch.object(host, "container_args", side_effect=args), patch.object(host, "execute", side_effect=execute):
            with self.assertRaisesRegex(ValueError, "isolation differs"):
                host.native_fixture_checks(self.output, self.study)
        self.assertFalse(any(command[:2] == ["docker", "start"] for command in commands))
        self.assertIn(["docker", "rm", owner], commands)

    def test_shared_mount_contract_keeps_both_historical_inputs_read_only(self):
        from . import verify
        with patch.object(verify, "ROOT", self.root):
            mounts = host.expected_mounts(self.output)
        self.assertIn((str(self.root / "runs/phase3a-rc1-pilot-v1"), "/results/phase3a-rc1-pilot-v1", False), mounts)
        self.assertIn((str(self.output / "am1-inputs/hi"), "/results/phase3a-h1-integrated-v1", False), mounts)
        self.assertEqual(sum(writable for _, _, writable in mounts), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
