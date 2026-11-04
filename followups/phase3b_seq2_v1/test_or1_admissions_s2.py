"""Pure temporary admission histories; no workflow, process or model dispatch."""
from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from buddha2.artifacts import ContractError

from .support import BASE, ROOT


class OR1AdmissionTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("or1_admission_unit", ROOT / "evidence/phase3b-seq2-c2-v1/launch_candidate.py")
        if spec is None or spec.loader is None:
            raise AssertionError("operator fixture cannot load")
        self.operator: Any = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.operator)
        BASE.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=BASE, prefix="or1-counter-unit-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.here = self.root / "evidence/phase3b-or1-v1"
        self.here.mkdir(parents=True)
        self.root_patch = patch.object(self.operator, "ROOT", self.root)
        self.here_patch = patch.object(self.operator, "HERE", self.here)
        self.root_patch.start()
        self.here_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.addCleanup(self.here_patch.stop)

    def candidate(self, number):
        value = {"source_sha256": str(number) * 64, "unit_fixture": True}
        (self.here / f"candidate-{number}.json").write_text(json.dumps(value), encoding="utf-8")
        (self.here / "release-config.json").write_text(json.dumps({"kind": "phase3b-or1-release-config-v1",
            "candidate": number, "verification": "verification-v" + str(4 + number),
            "authority": "evidence/phase3b-or1-v1/authority.json"}), encoding="utf-8")
        return value

    def test_count_before_work_per_candidate_and_global_caps(self):
        for number in (1, 2):
            value = self.candidate(number)
            self.operator.admit("candidate", value)
            for label in ("main", "S13", "saved", "cold"):
                row = self.operator.admit(label, value)
                self.assertTrue(row["consumed_before_child_work"])
                with self.assertRaises(ContractError):
                    self.operator.admit(label, value)
        final = self.candidate(3)
        self.operator.admit("candidate", final)
        for label in ("main", "S13", "saved", "cold"):
            with self.assertRaises(ContractError):
                self.operator.admit(label, final)
        with self.assertRaises(ContractError):
            self.operator.admit("candidate", final)

    def test_unadmitted_or_changed_history_cannot_admit(self):
        value = self.candidate(1)
        with self.assertRaises(ContractError):
            self.operator.admit("main", value)
        self.operator.admit("candidate", value)
        (self.here / "candidate-1.json").write_text(json.dumps({"source_sha256": "f" * 64}), encoding="utf-8")
        with self.assertRaises(ContractError):
            self.operator.admit("main", value)

    @unittest.skipUnless(os.name == "nt", "actual Windows host evidence writer")
    def test_host_evidence_writer_outside_runtime_base_is_exclusive(self):
        parent = ROOT / "evidence/phase3b-bd1-v1/host-writer-unit"
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            self.root = Path(directory)
            self.here = self.root / "evidence/phase3b-or1-v1"
            self.here.mkdir(parents=True)
            with patch.object(self.operator, "ROOT", self.root), patch.object(self.operator, "HERE", self.here):
                value = self.candidate(1)
                self.assertFalse(self.here.is_relative_to(BASE))
                row = self.operator.admit("candidate", value)
                target = self.here / "admissions/c1-candidate.json"
                before = target.read_bytes()
                self.assertEqual(json.loads(before), row)
                with self.assertRaises(ContractError):
                    self.operator.admit("candidate", value)
                self.assertEqual(target.read_bytes(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
