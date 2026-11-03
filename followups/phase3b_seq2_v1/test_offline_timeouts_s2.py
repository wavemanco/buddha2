"""OT01-OT05: outer offline waits cannot change experimental deadlines."""
from __future__ import annotations

import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import digest, file_hash

from . import host_checks, verify
from .support import BASE, ROOT


class OfflineTimeoutCases(unittest.TestCase):
    def setUp(self):
        BASE.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="offline-wait-tests-", dir=BASE)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_only_whole_inside_wait_gets_three_hours(self):
        for mode in ("inside", "supervised", "seal"):
            with self.subTest(mode=mode):
                calls = []
                owner = "f" * 64
                output = self.root / "runs" / verify.PREFIX / mode
                output.mkdir(parents=True)

                def execute(command, **kwargs):
                    calls.append((command, kwargs))
                    value = ""
                    if command[1] == "create":
                        value = owner + "\n"
                    elif command[1] == "inspect":
                        value = json.dumps([{
                            "Image": verify.IMAGE,
                            "HostConfig": {"NetworkMode": "none", "ReadonlyRootfs": True},
                            "State": {"Running": False},
                            "Mounts": [{"Source": source, "Destination": destination, "RW": rw}
                                       for source, destination, rw in verify.expected_mounts(output)],
                        }])
                    return {"command": command, "exit_code": 0, "stdout": value, "stderr": ""}

                with patch.object(verify, "ROOT", self.root), patch.object(verify, "execute", side_effect=execute):
                    self.assertEqual(verify.contained(output, mode), 0)
                waits = [options["timeout"] for command, options in calls if command[1] == "start"]
                self.assertEqual(waits, [10800 if mode == "inside" else 7200])
                self.assertEqual([options["timeout"] for command, options in calls if command[1] == "create"], [60])
                self.assertEqual([options["timeout"] for command, options in calls if command[1] == "rm"], [30])

    def test_actual_host_calls_extend_mock_only(self):
        calls = []
        output = self.root / "proof"
        output.mkdir()
        main = {key: "1" * 64 for key in verify.BINDINGS}
        fresh = {key: "2" * 64 for key in verify.BINDINGS}
        prepared = {"study_path": "/results/mock/release/study.json",
                    "mock_grant_path": "/results/mock/release/mock-grant.json"}
        matrix = {"study_path": "/results/main/release/study.json",
                  "live_grant_path": "/results/main/release/live-grant.json", "mock_http_calls": 1364}
        run = self.root / "run"
        supervisor = "/root/offline_timeout_unit"

        def execute(command, **kwargs):
            action = command[command.index("-Action") + 1]
            calls.append((action, kwargs))
            fixture = action == "mock"
            checked = {**(fresh if fixture else main), "mode": "mock" if fixture else "provider-config",
                       "fixture": fixture, "provider_calls": 0, "supervisor_agent": supervisor,
                       "fixture_supervision_rehearsal": fixture}
            directory = self.root / "runs" / host_checks.PREFIX / "launcher"
            verify.save(directory / (action + ".inspection.json"), {
                "preflight": checked, "container": {"image": verify.IMAGE,
                    "network_mode": "none" if fixture else "bridge", "state_at_inspection": "created",
                    "read_only_rootfs": True}})
            if fixture:
                verify.save(directory / (action + ".result.json"), {"action": "mock", "preflight": checked,
                    "exit_code": 0, "state": "exited", "actual_credentials_supplied": False})
            return {"command": command, "exit_code": 0, "stdout": "", "stderr": ""}

        with patch.object(host_checks, "ROOT", self.root), \
             patch.object(host_checks, "rehearsal_inputs", return_value=(fresh, prepared, run)), \
             patch.object(host_checks, "supervisor_handoff", return_value={}), \
             patch.object(host_checks, "supervision_checks") as supervision, \
             patch.object(host_checks, "execute", side_effect=execute), \
             patch.object(host_checks, "record") as record:
            host_checks.launch_checks(output, main, matrix, supervisor_agent=supervisor)
        self.assertEqual([(action, options["timeout"]) for action, options in calls],
                         [("mock", 10800), ("config", 7200)])
        self.assertEqual(supervision.call_count, 1)
        self.assertEqual(record.call_count, 1)  # Unit result is never a canonical gate record.
        self.assertEqual(inspect.signature(verify.execute).parameters["timeout"].default, 7200)

    def test_experimental_controls_are_byte_identical_to_a0(self):
        old = json.loads((ROOT / "runs/phase3b-seq2-v1/verification-v1/release/study.json").read_text(encoding="utf-8"))
        self.assertEqual(old["source_sha256"], "ba914c1c00376646cd3eaf29f4dd560d36edcfff731e419e5f631d010e6743c9")
        self.assertEqual(digest(old["source"]["files"]), old["source_sha256"])
        modules = ("accounting", "ledger_core", "deadline", "transport", "native", "editor", "adapter",
                   "contract", "strategy", "rank_io", "supervision", "snapshot", "inspect_adapter",
                   "inspect_projection", "core_view", "evidence", "delivery", "capacity", "mocks",
                   "native_fixture", "report", "history")
        names = ["followups/phase3b_seq2_v1/" + name + ".py" for name in modules]
        names.extend(("phase3b-seq2.ps1", "phase3b-seq2-core.ps1", "PHASE3B_DEFINITION.md",
                      "evidence/phase3b-seq2-v1/authorization.json"))
        for name in names:
            with self.subTest(control=name):
                self.assertEqual(file_hash(ROOT / name), old["source"]["files"][name])


if __name__ == "__main__":
    unittest.main()
