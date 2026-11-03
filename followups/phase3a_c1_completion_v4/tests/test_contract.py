"""Actual role contracts retain evidence and rules while declaring sixteen steps."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from buddha2.artifacts import digest
from followups.phase3a_c1_completion_v4 import adapter, contract, editor
from followups.phase3a_v1 import strategy


class ContractTests(unittest.TestCase):
    def setUp(self):
        root = (strategy.ROOT / "runs/phase3a-compat-c1-v1/completion-v4" if os.name == "nt"
                else Path("/results/phase3a-compat-c1-v1/completion-v4")) / "unit-contract"
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)

    def context(self, role):
        history = strategy.ROOT / "runs/phase3a-r2-v1/17f35cf72cad95351e726cd9f02824be78db35a0a16c3f83db9e7bae9d762032/live/search/p3a-01/adaptive"
        contexts = next((history / "native").glob("*/*/context"))
        context = self.work / role.lower()
        shutil.copytree(contexts / role.lower(), context)
        for path in context.rglob("*"):
            if path.is_file() and "/harness/" not in path.as_posix():
                path.write_text("SYNTHETIC complete evidence.\n", encoding="utf-8")
        for path in context.rglob("systemprompt.md"):
            path.write_text(json.dumps({"answer_system": "SYNTHETIC answer", "plan_system": "SYNTHETIC plan", "rank_system": "SYNTHETIC rank"}), encoding="utf-8")
        mission = next((history / "editor-audit").glob(role.lower() + ".a1.*.mission.md")).read_text(encoding="utf-8")
        return mission, context

    def test_only_budget_words_and_identity_change_for_all_native_roles(self):
        for role, label in (("INV", "inv1.a1"), ("DOM", "dom1.a1"), ("AGG", "agg1.a1")):
            with self.subTest(role=role):
                old = contract.parent._render(role, label, None)
                new = contract._render(role, label, None)
                expected = old.replace(contract.parent.POLICY_ID, contract.POLICY_ID, 1).replace(contract._OLD_ALLOWANCE, contract._NEW_ALLOWANCE, 1)
                self.assertEqual(new, expected)
                self.assertIn(contract.FINAL_RULE, new)
                self.assertIn("KEEP_BASE is valid", new)
                self.assertIn("fifteen are ordinary", new)

    def test_complete_prepare_rebinds_manifest_and_supported_actual_system(self):
        for role in ("INV1", "DOM1", "AGG1"):
            with self.subTest(role=role):
                mission, context = self.context(role)
                before = {x.relative_to(context).as_posix(): hashlib.sha256(x.read_bytes()).hexdigest()
                          for x in context.rglob("*") if x.is_file()}
                old = contract.parent.prepare_contract(mission, context, role.lower() + ".a1")
                actual = contract.prepare_contract(mission, context, role.lower() + ".a1")
                self.assertEqual(actual["evidence_files"], old["evidence_files"])
                self.assertEqual(actual["manifest"]["required_evidence"], old["manifest"]["required_evidence"])
                self.assertEqual(actual["manifest"]["context_inventory"], old["manifest"]["context_inventory"])
                self.assertEqual(actual["manifest"]["editor_profile_sha256"], digest(editor.profile()))
                self.assertEqual(before, {x.relative_to(context).as_posix(): hashlib.sha256(x.read_bytes()).hexdigest()
                    for x in context.rglob("*") if x.is_file()})
                prop = adapter.CompatibleProposer(pilot="p3a-01", study_sha256="a" * 64,
                    dispatch=lambda *a: self.fail("dispatch forbidden"), audit_dir=self.work / "audit" / role,
                    fixture=True, halt=lambda *a, **k: self.fail("unexpected halt"))
                prop._local.url, prop._local.home, prop._local.label = "http://127.0.0.1:1/v1", str(self.work), role.lower() + ".a1"
                prop._c1_contracts[prop._local.label] = actual
                value = json.loads(prop.env()["OPENCODE_CONFIG_CONTENT"])
                self.assertEqual(value["agent"]["build"]["steps"], 16)
                self.assertEqual(value["agent"]["build"]["prompt"], actual["authoring_system_text"])
                self.assertIn("editor_sha256", prop._c1_binding)
                profile = json.loads((Path(prop.audit_dir) / "c1-contracts" / prop._local.label / "system-profile.json").read_text())
                self.assertEqual(profile["editor_profile_sha256"], digest(editor.profile()))
