"""R3 orchestration contracts; synthetic argv fixtures do not establish host readiness."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from followups.phase3a_c1_completion_v4 import verify


def proofs():
    result = {}
    for index in range(1, 5):
        result[f"p3a-{index:02}"] = {label: {"fixture": True, "normal_final": True,
            "notes_reread_model_visible": True, "decision_after_complete_evidence": True,
            "verification_after_write": True, "R3_deliberately_inefficient_evidence_reading": True,
            "terminal_note_used": False, "ordinary_rounds": 10 if label.startswith("dom") else 11,
            "evidence_read_batches": 4, "effective_changed": not label.startswith("dom")}
            for label in ("inv1.a1", "dom1.a1", "agg1.a1")}
    return result


class VerifyTests(unittest.TestCase):
    def test_complete_proof_requires_beyond7_normal_keepbase_and_full_delivery(self):
        original = proofs()
        self.assertTrue(verify.mock_profiles(original))
        for field, bad in (("ordinary_rounds", 7), ("ordinary_rounds", 16), ("normal_final", False),
                           ("notes_reread_model_visible", False), ("evidence_read_batches", 3),
                           ("terminal_note_used", True)):
            changed = copy.deepcopy(original)
            changed["p3a-01"]["inv1.a1"][field] = bad
            with self.subTest(field=field, bad=bad):
                self.assertFalse(verify.mock_profiles(changed))
        changed = copy.deepcopy(original)
        changed["p3a-01"]["dom1.a1"]["effective_changed"] = True
        self.assertFalse(verify.mock_profiles(changed))
        changed.pop("p3a-04")
        self.assertFalse(verify.mock_profiles(changed))

    def test_five_binding_record_does_not_accept_body_overrides(self):
        study = {key: str(index) * 64 for index, key in enumerate(verify.BINDINGS)}
        with patch("buddha2.artifacts.write_once") as written:
            record = verify._record(Path("/results/phase3a-c1-completion-v4/unit"), "fixture", study,
                {"passed": True, "source_sha256": "foreign"})
        self.assertEqual({key: record[key] for key in verify.BINDINGS}, study)
        written.assert_called_once()

    def test_old_private_or_traversing_scope_fails_before_metadata(self):
        for name in ("runs/phase3a-c1-completion-v3/old", "runs/phase3a-c1-completion-v4/../escape",
                     "runs/phase3a-c1-completion-v4/Credential-Binding.JSON", "runs/phase3a-c1-completion-v4/.env/child"):
            with self.subTest(name=name), patch.object(Path, "is_symlink", side_effect=AssertionError("metadata inspected")):
                with self.assertRaises(ValueError):
                    verify._host_output(name)

    def test_host_uses_fresh_literal_release_resource_limits_and_result_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pwsh = root / "pwsh"
            pwsh.write_text("SYNTHETIC executable marker", encoding="utf-8")
            output = root / "runs/phase3a-c1-completion-v4/verification"
            launcher = root / "runs/phase3a-c1-completion-v4/launcher"
            calls = []
            def execute(command, **kwargs):
                calls.append(command)
                if "--inside" in command:
                    self.assertIn("none", command)
                    for key, value in (("--cpus", "2"), ("--memory", "4g"), ("--pids-limit", "256")):
                        self.assertEqual(command[command.index(key) + 1], value)
                    self.assertIn("--read-only", command)
                    prefix = "/results/phase3a-c1-completion-v4/verification/release/"
                    (output / "matrix.json").write_text(json.dumps({"study_path": prefix + "study.json",
                        "mock_grant_path": prefix + "mock-grant.json", "live_grant_path": prefix + "live-grant.json"}), encoding="utf-8")
                elif "--windows" in command:
                    self.assertNotIn("ANTHROPIC_API_KEY", kwargs["env"])
                    self.assertNotIn("OPENAI_API_KEY", kwargs["env"])
                    self.assertTrue(kwargs["env"]["PATH"].startswith(str(pwsh.parent)))
                elif "-Action" in command:
                    self.assertTrue(command[command.index("-Study") + 1].startswith("phase3a-c1-completion-v4/"))
                    self.assertEqual(Path(command[command.index("-File") + 1]).name, "phase3a-c1-completion-r3.ps1")
                    launcher.mkdir(parents=True, exist_ok=True)
                    action = command[command.index("-Action") + 1]
                    (launcher / (action + ".inspection.json")).write_text("{}", encoding="utf-8")
                    if action == "mock":
                        (launcher / (action + ".result.json")).write_text("{}", encoding="utf-8")
                else:
                    self.assertIn("--seal", command)
                return SimpleNamespace(returncode=0)
            with (patch.object(verify, "ROOT", root), patch.object(verify, "PWSH", pwsh),
                  patch.object(verify.shutil, "which", return_value="/fixture/docker"),
                  patch.object(verify.subprocess, "check_output", return_value=(verify.IMAGE + "\n").encode()),
                  patch.object(verify.subprocess, "run", side_effect=execute)):
                self.assertEqual(verify.host("runs/phase3a-c1-completion-v4/verification"), 0)
            rows = json.loads((output / "launcher-host.json").read_text(encoding="utf-8"))
            self.assertEqual(len(calls), 5)
            self.assertTrue(rows[0]["runtime_path"].endswith("mock.result.json"))
            self.assertIsNone(rows[1]["runtime_path"])

    def test_duplicate_unittest_identity_is_rejected(self):
        test = unittest.FunctionTestCase(lambda: None)
        with patch.object(unittest.defaultTestLoader, "loadTestsFromNames", return_value=unittest.TestSuite([test, test])):
            with self.assertRaisesRegex(ValueError, "duplicate"):
                verify._suite()
