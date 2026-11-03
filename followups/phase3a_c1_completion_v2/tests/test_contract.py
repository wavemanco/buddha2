"""R1 changes final-output instructions; frozen evidence preparation is preserved."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from buddha2.artifacts import ContractError, digest
from followups.phase3a_c1_completion_v2 import contract
from followups.phase3a_c1_completion_v2.mocks import SDKMock
from followups.phase3a_compat_c1_v1 import contract as frozen


class ContractTests(unittest.TestCase):
    def setUp(self):
        history = frozen.ROOT / "runs/phase3a-r2-v1/17f35cf72cad95351e726cd9f02824be78db35a0a16c3f83db9e7bae9d762032/live/search/p3a-01/adaptive"
        self.native = next((history / "native").glob("*/*/context"))
        self.missions = {label: next((history / "editor-audit").glob(label + ".a1.*.mission.md")).read_text(encoding="utf-8")
                         for label in ("inv1", "dom1", "agg1")}
        output = Path(os.environ["BUDDHA2_OUTPUT_ROOT"]) if os.environ.get("BUDDHA2_OUTPUT_ROOT") else frozen.ROOT / "runs"
        base = output / "phase3a-compat-c1-v1/completion-v2/unit-contract"
        base.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)

    def context(self, label="inv1"):
        target = self.work / label
        shutil.copytree(self.native / label, target)
        for path in target.rglob("*"):
            if path.is_file() and "/harness/" not in path.as_posix():
                path.write_text("SYNTHETIC complete evidence; no creative finding.\n", encoding="utf-8")
        value = {"answer_system": "SYNTHETIC answer", "plan_system": "SYNTHETIC plan", "rank_system": "SYNTHETIC rank"}
        for path in target.rglob("systemprompt.md"):
            path.write_text(json.dumps(value), encoding="utf-8")
        return target

    @staticmethod
    def fingerprint(path):
        return {p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in path.rglob("*") if p.is_file()}

    def test_three_roles_preserve_exact_frozen_evidence_without_writing_context(self):
        preserved = ("role", "label", "upstream_commit", "upstream_files", "raw_mission_sha256", "context_inventory",
                     "context_inventory_sha256", "input_strategy_valid", "input_effective_strategy_sha256",
                     "native_repair_diagnostic", "required_evidence")
        for label in ("inv1", "dom1", "agg1"):
            with self.subTest(label=label):
                context = self.context(label)
                before = self.fingerprint(context)
                original = frozen.prepare_contract(self.missions[label], context, label + ".a1")
                new = contract.prepare_contract(self.missions[label], context, label + ".a1")
                self.assertEqual(before, self.fingerprint(context))
                self.assertEqual(original["evidence_files"], new["evidence_files"])
                for field in preserved:
                    self.assertEqual(original["manifest"][field], new["manifest"][field])
                self.assertNotEqual(original["manifest"]["policy_id"], new["manifest"]["policy_id"])
                self.assertEqual(new["manifest"]["sha256"], digest({k: v for k, v in new["manifest"].items() if k != "sha256"}))
                self.assertEqual(new["authoring_system_text"], contract.authoring_system(new["effective_mission"], new["index_text"]))
                self.assertTrue(new["effective_mission"].endswith(contract.FINAL_RULE))
                self.assertTrue(new["authoring_system_text"].endswith(contract.FINAL_RULE))
                self.assertTrue(new["authoring_system_text"].startswith(contract.SYSTEM_ID + "\n"))
                self.assertIn(new["manifest"]["sha256"], new["index_text"])
                self.assertIn("KEEP_BASE is valid", new["effective_mission"])
                self.assertEqual(new["manifest"]["effective_mission_sha256"], hashlib.sha256(new["effective_mission"].encode()).hexdigest())
                self.assertEqual(new, contract.prepare_contract(self.missions[label], context, label + ".a1"))

    def test_rule_demands_saved_complete_block_and_supplies_no_creative_answer(self):
        self.assertNotEqual(contract.SYSTEM_ID, frozen.SYSTEM_ID)
        for instruction in ("ALL verification commentary inside", "SAME COMPLETE block", "entire final assistant response",
                            "No verification sentence, preface", "not evidence supporting an edit or KEEP_BASE"):
            self.assertIn(instruction, contract.FINAL_RULE)
        self.assertEqual(len(re.findall(r"(?m)^<notes>$", contract.FINAL_RULE)), 2)
        self.assertEqual(len(re.findall(r"(?m)^</notes>$", contract.FINAL_RULE)), 2)

    def test_native_shape_repair_and_foreign_input_stay_delegated(self):
        context = self.context()
        (context / "harness/systemprompt.md").write_text("{}", encoding="utf-8")
        mission = self.missions["inv1"] + frozen._REPAIR + "invalid JSON shape" + frozen._REPAIR_END
        original = frozen.prepare_contract(mission, context, "inv1.a2")
        new = contract.prepare_contract(mission, context, "inv1.a2")
        self.assertEqual(original["evidence_files"], new["evidence_files"])
        self.assertFalse(new["manifest"]["input_strategy_valid"])
        self.assertEqual(new["manifest"]["native_repair_diagnostic"], "invalid JSON shape")
        with self.assertRaises(contract.ContractError):
            contract.prepare_contract(self.missions["inv1"] + "\nChanged native mission", context, "inv1.a1")

    def test_fixture_registration_requires_actual_new_profile_and_does_not_rewrite_it(self):
        context = self.context()
        prepared = contract.prepare_contract(self.missions["inv1"], context, "inv1.a1")
        before = copy.deepcopy(prepared)
        fixture = object.__new__(SDKMock)
        fixture._registered, fixture._registered_system = {}, {}
        fixture.register_contract("inv1.a1", prepared)
        self.assertEqual(prepared, before)
        self.assertEqual(fixture._registered_system["inv1.a1"], prepared["authoring_system_text"])
        original = frozen.prepare_contract(self.missions["inv1"], context, "inv1.a1")
        fixture._registered, fixture._registered_system = {}, {}
        with self.assertRaises(ContractError):
            fixture.register_contract("inv1.a1", original)


if __name__ == "__main__":
    unittest.main()
