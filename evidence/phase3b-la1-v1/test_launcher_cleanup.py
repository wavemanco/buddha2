"""Deterministic failed-launch cleanup regressions: no process or Docker calls."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / ".upstream/harness2")]


def load(name, target):
    spec = importlib.util.spec_from_file_location(name, target)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OPERATOR = load("la1_fault_operator", ROOT / "evidence/phase3b-seq2-c2-v1/launch_candidate.py")
HOST = load("la1_fault_host", ROOT / "evidence/phase3b-la1-v1/host_acceptance.py")


def write(target, value):
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value), encoding="utf-8")


class FailedCleanupCases(unittest.TestCase):
    def setUp(self):
        parent = ROOT / "runs/phase3b-la1-v1/launcher-fault-tests"
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / "runs/phase3b-seq2-v1/verification-v5"
        write(self.root / "evidence/phase3b-or1-v1/release-config.json",
              {"kind": "phase3b-or1-release-config-v1", "candidate": 1, "verification": "verification-v5",
               "authority": "evidence/phase3b-or1-v1/authority.json"})

    def test_exceptional_child_retains_failure_and_attempts_cleanup(self):
        from followups.phase3b_seq2_v1 import support
        old = Path.cwd()
        self.addCleanup(os.chdir, old)
        os.chdir(self.root)
        failure = subprocess.TimeoutExpired(["harmless-driver"], 1, output=b"partial", stderr=b"diagnostic")
        with patch.object(OPERATOR, "ROOT", self.root), patch.object(OPERATOR, "HERE", self.root / "evidence"), \
             patch.object(OPERATOR, "authenticate_candidate", return_value={"source_sha256": "a", "operator_timeout_seconds": {"boundary": 1}}), \
             patch.object(support, "source_identity", return_value={"sha256": "a"}), \
             patch.object(OPERATOR, "admit", return_value={"unit_fixture": True}), \
             patch.object(OPERATOR, "run_child", side_effect=failure), \
             patch.object(OPERATOR, "settle_receipt_owners", return_value={"passed": False}) as cleanup, \
             patch.object(sys, "argv", ["operator", "boundary"]):
            self.assertEqual(OPERATOR.main(), 1)
        cleanup.assert_called_once_with("boundary")
        record = json.loads((self.output / "operator-boundary.json").read_text())
        self.assertEqual(record["exception_type"], "TimeoutExpired")
        self.assertEqual(record["partial_output_base64"], "cGFydGlhbA==")
        self.assertFalse(record["settled"])

    def test_malformed_boundary_discovery_still_settles_known_owner(self):
        from followups.phase3b_seq2_v1 import verify
        directory = self.output / "boundary-contract"
        write(directory / "core-create.json", {"exit_code": 0, "output": "a" * 64})
        write(directory / "fixture/prepared.json", {"study_sha256": "invalid"})
        calls = []
        def execute(command, **kwargs):
            calls.append(command)
            return {"exit_code": 1, "stdout": "", "stderr": "Error: No such object"}
        with patch.object(OPERATOR, "ROOT", self.root), patch.object(verify, "execute", side_effect=execute):
            result = OPERATOR.settle_receipt_owners("boundary")
        self.assertFalse(result["passed"])
        self.assertTrue(result["discovery_errors"])
        self.assertEqual(len(result["owners"]), 1)
        self.assertTrue(result["owners"][0]["passed"])
        self.assertTrue(all(command[-1] == "a" * 64 for command in calls))

    def test_malformed_host_discovery_still_settles_known_native_owner(self):
        from followups.phase3b_seq2_v1 import verify
        launcher = self.root / "runs/phase3b-seq2-v1/launcher"
        launcher.mkdir(parents=True)
        (launcher / ("a" * 32 + ".inspection.json")).write_text("invalid", encoding="utf-8")
        write(self.output / "host-launcher-before.json", {"names": []})
        write(self.output / "release/study.json", {"study_sha256": "b" * 64})
        write(self.output / "operational-rehearsal/release/study.json", {"study_sha256": "c" * 64})
        write(self.output / "native-fixtures/terminal-readiness/create.json", {"exit_code": 0, "stdout": "d" * 64})
        calls = []
        def execute(command, **kwargs):
            calls.append(command)
            return {"exit_code": 1, "stdout": "", "stderr": "Error: No such object"}
        with patch.object(HOST, "ROOT", self.root), patch.object(HOST, "OUTPUT", self.output), \
             patch.object(verify, "execute", side_effect=execute):
            result = HOST.emergency_cleanup()
        self.assertFalse(result["passed"])
        self.assertTrue(result["discovery_errors"])
        self.assertEqual(len(result["owners"]), 1)
        self.assertTrue(result["owners"][0]["passed"])
        self.assertTrue(all(command[-1] == "d" * 64 for command in calls))


if __name__ == "__main__":
    unittest.main(verbosity=2)
