"""Scoped installation, immutable bindings and fail-closed adapter inputs."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from harness2.core.proposer import ProposerError

from buddha2.artifacts import digest, read_json
from followups.phase3a_compat_c1_v1 import adapter, contract, support
from followups.phase3a_compat_c1_v1.tests import test_contract


class AdapterTests(unittest.TestCase):
    @unittest.skipUnless(Path("/opt/phase3a-opencode").is_dir(), "requires pinned editor sources")
    def test_supported_agent_prompt_replaces_default_and_preserves_other_configuration(self):
        self.prop._local.label = "inv1.a1"
        self.prop._local.url = "http://127.0.0.1:12345"
        self.prop._local.home = str(self.helper.work / "fake-home")
        prepared = self.helper.build(self.context)
        self.prop._c1_contracts["inv1.a1"] = prepared
        env = self.prop.env()
        expected = adapter.editor.configuration(self.prop._local.url)
        expected["agent"]["build"]["prompt"] = prepared["authoring_system_text"]
        self.assertEqual(json.loads(env["OPENCODE_CONFIG_CONTENT"]), expected)
        audit = self.helper.work / "audit/c1-contracts/inv1.a1"
        record = read_json(audit / "system-profile.json")
        self.assertEqual(record["steps"], 8)
        self.assertEqual(record["sources"], adapter.OPENCODE_FILES)
        self.assertEqual(record["profile"], contract.SYSTEM_ID)
        self.assertTrue((audit / "original-provider-prompt.md").is_file())

    def test_foreign_audit_rejected_before_parent_constructor_or_filesystem_inspection(self):
        with patch.object(adapter.editor.AccountedProposer, "__init__",
                          side_effect=AssertionError("must not create foreign proof directories")), \
                self.assertRaises(ProposerError):
            adapter.CompatibleProposer(pilot="p3a-01", study_sha256="a" * 64,
                dispatch=lambda *args: None, fixture=True,
                audit_dir=Path("/forbidden-outside-checkpoint/audit"), halt=lambda *args: None)

    def setUp(self):
        test_contract.ContractTests.setUpClass()
        self.helper = test_contract.ContractTests()
        self.helper.setUp()
        self.addCleanup(self.helper.doCleanups)
        self.context = self.helper.context()
        self.holds: list = []
        self.observed: list = []
        self.prop = adapter.CompatibleProposer(pilot="p3a-01", study_sha256="a" * 64,
            dispatch=lambda *args: self.fail("unit test must never dispatch"), fixture=True,
            audit_dir=self.helper.work / "audit", halt=self.holds.append,
            register_contract=lambda label, prepared: self.observed.append((label, prepared)))

    def test_scoped_context_removed_and_exact_raw_effective_identities_retained(self):
        before = self.helper.fingerprint(self.context)
        mission = self.helper.missions["inv1"]
        def parent_call(prop, effective, context, label, **kwargs):
            self.assertIn("KEEP_BASE is valid", effective)
            manifest = read_json(context / contract.MANIFEST_NAME)
            self.assertEqual(manifest, self.observed[0][1]["manifest"])
            self.assertTrue(all(len(line) < 2000 for line in
                (context / contract.MANIFEST_NAME).read_text().splitlines()))
            self.assertTrue((context / contract.INDEX_NAME).is_file())
            self.assertEqual(prop, self.prop)
            return SimpleNamespace(ok=True)
        with patch.object(adapter.editor.AccountedProposer, "call", parent_call):
            self.assertTrue(self.prop.call(mission, self.context, "inv1.a1").ok)
        self.assertEqual(before, self.helper.fingerprint(self.context))
        self.assertEqual(self.holds, [])
        evidence = self.prop.c1_evidence()
        record = evidence["sessions"]["inv1.a1"]
        self.assertTrue(record["auxiliary_removed"])
        self.assertEqual(record["status"], "returned")
        self.assertEqual(record["sha256"], digest({k: v for k, v in record.items() if k != "sha256"}))
        audit = self.helper.work / "audit/c1-contracts/inv1.a1"
        self.assertEqual((audit / "native-mission.md").read_bytes(), mission.encode())
        self.assertEqual(read_json(audit / "result.json"), record)
        evidence["sessions"].clear()
        self.assertTrue(self.prop.c1_evidence()["sessions"])
        with self.assertRaises(ProposerError):
            self.prop.call(mission, self.context, "inv1.a1")

    def test_parent_failure_removes_only_owned_auxiliary_and_records_failure(self):
        before = self.helper.fingerprint(self.context)
        with patch.object(adapter.editor.AccountedProposer, "call", side_effect=ProposerError("synthetic")):
            with self.assertRaises(ProposerError):
                self.prop.call(self.helper.missions["inv1"], self.context, "inv1.a1")
        self.assertEqual(before, self.helper.fingerprint(self.context))
        self.assertEqual(self.prop.c1_evidence()["sessions"]["inv1.a1"]["status"], "failed")

    def test_invalid_context_stage_and_derived_tamper_never_hide_failure(self):
        for context, label in ((None, "inv1.a1"), (self.context, "../bad"),
                               (self.context, []), (self.context.parent.parent, "inv1.a1")):
            with self.subTest(label=label), self.assertRaises(ProposerError):
                self.prop.call(self.helper.missions["inv1"], context, label)
        def tamper(prop, mission, context, label, **kwargs):
            (context / contract.MANIFEST_NAME).write_text("{}")
            return SimpleNamespace(ok=True)
        with patch.object(adapter.editor.AccountedProposer, "call", tamper):
            with self.assertRaises(ProposerError):
                self.prop.call(self.helper.missions["inv1"], self.context, "inv1.a1")
        self.assertIn("c1_derived_context_tampered", self.holds)

    def test_foreign_context_rejected_before_context_metadata_probes(self):
        outside = self.helper.work.parent / "forbidden-outside-task"
        original = Path.is_symlink
        def guarded(path):
            if path == outside:
                raise AssertionError("must reject foreign path before filesystem inspection")
            return original(path)
        with patch.object(Path, "is_symlink", guarded), self.assertRaises(ProposerError):
            self.prop.call(self.helper.missions["inv1"], outside, "inv1.a1")


class SupportTests(unittest.TestCase):
    def test_changed_closed_reference_rejected_before_consuming_its_member_map(self):
        with patch.object(support, "sha", return_value="0" * 64), \
                patch.object(support, "read", side_effect=AssertionError("must not parse untrusted map")):
            with self.assertRaises(ValueError):
                support.read_closed(support.OLD_STUDY)

    def test_private_or_traversing_paths_rejected_before_filesystem_inspection(self):
        with patch.object(Path, "is_symlink", side_effect=AssertionError("must not inspect")):
            for name in (".env", "a/credential-binding.json", "a/.writer.lock", "../outside",
                         "/absolute", "C:/outside", "a\\outside"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    support.safe(name)

    def test_source_identity_includes_new_code_tests_definition_and_detects_changes(self):
        test_contract.ContractTests.setUpClass()
        helper = test_contract.ContractTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        root = helper.work
        code = root / "followups/phase3a_compat_c1_v1"
        code.mkdir(parents=True)
        (code / "one.py").write_text("pass\n")
        (root / "definition.md").write_text("synthetic definition")
        (root / "old.json").write_text(json.dumps({"fixture": True}))
        with patch.object(support, "ROOT", root), patch.object(support, "DEFINITION", root / "definition.md"), \
                patch.object(support, "OLD_STUDY", "old.json"), \
                patch.object(support, "parent_source", return_value={"files": {}, "sha256": "a" * 64}):
            before = support.source_identity()
            self.assertEqual(len(before["files"]), 3)
            (code / "one.py").write_text("raise RuntimeError\n")
            self.assertNotEqual(before["sha256"], support.source_identity()["sha256"])


if __name__ == "__main__":
    unittest.main()
