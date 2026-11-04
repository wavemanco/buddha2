"""Real Windows bootstrap denials and frozen S2 authority boundaries."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError

from . import launch, support, workflow
from .support import AUTHORITY, ROOT, read, safe, validate_authority


class CurrentOfflineReadinessTests(unittest.TestCase):
    def setUp(self):
        output = support.BASE if os.environ.get("BUDDHA2_OUTPUT_ROOT") else ROOT / "evidence/phase3b-seq2-v1"
        output.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="readiness-v2-unit-", dir=output)
        self.directory = Path(temporary.name)
        self.assertTrue(self.directory.resolve().is_relative_to(output.resolve()))
        self.addCleanup(temporary.cleanup)
        self.study = self.directory / "study.json"
        self.bindings = {key: char * 64 for key, char in zip(support.READINESS_BINDINGS, "abcde", strict=True)}

    def write(self, name, body):
        target = self.directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        value = support.seal(body)
        target.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return value

    def profile(self, *, receipt_changes=None, review_changes=None):
        common = {**self.bindings, "passed": True, "provider_calls": 0, "real_credentials_used": False}
        references = {}
        for name in sorted(support.READINESS_CHECKS):
            body = {**common, "kind": "buddha2-offline-check-v2", "check": name,
                "command": ["python", "-B", "-m", "unittest", "synthetic." + name],
                "exit_code": 0, "tests_run": 1, "test_ids": ["synthetic." + name],
                "failures": 0, "errors": 0, "skipped": 0}
            if receipt_changes and name == "financial":
                body.update(receipt_changes)
            filename = f"offline-checks/{name}.json"
            self.write(filename, body)
            references[name] = {"path": filename, "sha256": support.file_hash(self.directory / filename)}
        manifest = self.write("offline-readiness.json", {**common,
            "kind": "buddha2-offline-readiness-v2", "checked_by": "test-operator", "checks": references})
        review = {**common, "kind": "buddha2-offline-independent-review-v2",
            "manifest_sha256": manifest["sha256"],
            "manifest_file_sha256": support.file_hash(self.directory / "offline-readiness.json"),
            "reviewer": "separate-test-reviewer", "independent": True,
            "notes": "Synthetic validator fixture only; this is not accepted research readiness."}
        review.update(review_changes or {})
        self.write("independent-review.json", review)
        return manifest

    def test_current_six_receipts_and_separate_review_pass_without_archive(self):
        self.profile()
        result = support.offline_readiness(self.study, self.bindings)
        self.assertEqual(result["profile"], "buddha2-offline-readiness-v2")
        self.assertEqual(set(self.directory.iterdir()), {self.directory / name for name in (
            "offline-checks", "offline-readiness.json", "independent-review.json")})

    def test_failed_skipped_empty_or_foreign_checks_cannot_pass_even_when_resealed(self):
        for change in ({"passed": False}, {"skipped": 1}, {"tests_run": 0, "test_ids": []},
                {"provider_calls": 1}, {"real_credentials_used": True}, {"source_sha256": "f" * 64},
                {"test_ids": ["repeated", "repeated"], "tests_run": 2}):
            with self.subTest(change=change):
                self.profile(receipt_changes=change)
                with self.assertRaises(ContractError):
                    support.offline_readiness(self.study, self.bindings)

    def test_missing_or_changed_receipts_and_private_paths_fail_closed(self):
        manifest = self.profile()
        receipt = self.directory / "offline-checks/financial.json"
        receipt.write_text("{}", encoding="utf-8")
        with self.assertRaises(ContractError):
            support.offline_readiness(self.study, self.bindings)
        self.profile()
        receipt.unlink()
        with self.assertRaises(ContractError):
            support.offline_readiness(self.study, self.bindings)
        manifest["checks"]["financial"]["path"] = "credential-binding.json"
        self.write("offline-readiness.json", {key: value for key, value in manifest.items() if key != "sha256"})
        original = support.read
        def public_read(target):
            self.assertNotEqual(Path(target).name, "credential-binding.json")
            return original(target)
        with patch.object(support, "read", side_effect=public_read), self.assertRaises(ContractError):
            support.offline_readiness(self.study, self.bindings)

    def test_missing_stale_or_same_actor_review_cannot_supply_independence(self):
        for change in ({"manifest_file_sha256": "0" * 64}, {"manifest_sha256": "0" * 64},
                {"independent": False}, {"reviewer": " TEST-OPERATOR "}, {"runtime_sha256": "f" * 64}):
            with self.subTest(change=change):
                self.profile(review_changes=change)
                with self.assertRaises(ContractError):
                    support.offline_readiness(self.study, self.bindings)
        self.profile()
        (self.directory / "independent-review.json").unlink()
        with self.assertRaises(ContractError):
            support.offline_readiness(self.study, self.bindings)

    def test_old_gate_cannot_substitute_for_current_profile(self):
        self.write("offline-gate.json", {"passed": True})
        with self.assertRaises(ContractError):
            support.offline_readiness(self.study, self.bindings)

    def test_live_workflow_preflight_requires_current_readiness_before_accounting(self):
        study = {**self.bindings, "fixture_boundary_contract": False}
        with patch.object(workflow, "load_study", return_value=study), \
                patch.object(workflow, "grant_for", return_value={}), \
                patch.object(workflow, "paths", return_value=(self.directory / "owner", self.directory / "journal")), \
                patch.object(workflow, "path", side_effect=lambda value: value), \
                patch.object(workflow, "offline_readiness", side_effect=ContractError("current gate required")) as gate, \
                patch.object(workflow, "_state", side_effect=AssertionError("accounting opened before readiness")):
            with self.assertRaisesRegex(ContractError, "current gate required"):
                workflow.preflight(self.study, self.directory / "grant.json", False)
            gate.assert_called_once_with(self.study, self.bindings)

    def test_provider_launcher_requires_current_readiness_before_live_claim(self):
        study_hash = self.bindings["study_sha256"]
        grant = self.directory / "grant.json"
        value = {**self.bindings, "grant_sha256": "f" * 64, "fixture": False,
            "provider_calls": 0, "credentials_read": False,
            "run": str(support.NATIVE / study_hash / "live"),
            "journal": str(launch.accounting.canonical_journal(study_hash, False))}
        def artifact(target):
            return {"fixture": False, "authority": {}} if target == grant else {"slots": {}, "editor_tools": {}}
        with patch.object(launch.accounting, "runtime_guard"), \
                patch.object(launch, "_completion_path", side_effect=lambda target: target), \
                patch.object(launch, "read_json", side_effect=artifact), \
                patch.object(launch, "_workflow_preflight", return_value=value), \
                patch.object(launch.accounting, "journal_identity", return_value="f" * 64), \
                patch.object(Path, "exists", return_value=False), \
                patch.object(launch, "offline_readiness", side_effect=ContractError("current gate required")) as gate, \
                patch.object(launch, "_live_study_claim", side_effect=AssertionError("live claim before readiness")):
            with self.assertRaisesRegex(ContractError, "current gate required"):
                launch.preflight(self.study, grant, "all", "provider", supervisor_agent="/root/test_reviewer")
            gate.assert_called_once_with(self.study, self.bindings)


class LaunchBoundaryTests(unittest.TestCase):
    def test_authority_is_the_exact_whole_block_with_no_old_hold_release(self):
        value = validate_authority()
        self.assertEqual(value, read(AUTHORITY))
        self.assertEqual(value["new_cap_micro_usd"], 167471253)
        self.assertEqual(value["first_cap_micro_usd"], 42471253)
        self.assertEqual(value["historical_known_micro_usd"], 58573112)
        self.assertEqual(value["new_max_attempts"], 2222)
        self.assertEqual(value["cumulative_max_exposure_micro_usd"], 248924365)
        self.assertFalse(value["historical_liability_release_authorized"])
        self.assertTrue(value["calls_require_offline_gate_and_fresh_masked_keys"])

    def test_repeat_claim_is_fixed_and_preserves_the_closed_claim(self):
        parent = ROOT / "runs/phase3b-seq2-v1" if os.name == "nt" else support.BASE
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="repeat-claim-", dir=parent) as temporary:
            directory = Path(temporary)
            closed = directory / "live-study.json"
            closed.write_bytes(b'{"closed":true}\n')
            checked = {key: char * 64 for key, char in zip(launch._BINDINGS, "abcdef", strict=True)}
            study = checked["study_sha256"]
            checked.update(mode="provider", fixture=False, run=str(support.NATIVE / study / "live"),
                           journal=str(launch.accounting.canonical_journal(study, False)))
            with patch.object(launch, "BASE", directory):
                record = launch._live_study_claim(checked, publish=True)
                self.assertEqual(record["cap_micro_usd"], 167471253)
                self.assertEqual(record["first_cap_micro_usd"], 42471253)
                self.assertEqual(closed.read_bytes(), b'{"closed":true}\n')
                self.assertTrue((directory / "live-study-read-diagnostic-r1.json").is_file())
                self.assertEqual(launch._live_study_claim(checked), record)
                checked.update(study_sha256="f" * 64, run=str(support.NATIVE / ("f" * 64) / "live"),
                               journal=str(launch.accounting.canonical_journal("f" * 64, False)))
                with self.assertRaises(ContractError):
                    launch._live_study_claim(checked)

    def test_repeat_authority_cannot_reset_consumed_money_attempts_or_holds(self):
        valid = validate_authority()
        for change in ({"new_cap_micro_usd": 180000000}, {"first_cap_micro_usd": 55000000},
                       {"new_max_attempts": 2344}, {"historical_known_micro_usd": 46044365},
                       {"historical_reserved_micro_usd": 0}, {"closed_parent_reserved_micro_usd": 1},
                       {"authorized_repeat": False}, {"closed_parent_study": "f" * 64}):
            with self.subTest(change=change), patch.object(support, "read", return_value=valid | change):
                with self.assertRaises(ContractError):
                    validate_authority()

    def test_private_cached_and_foreign_paths_are_rejected_lexically(self):
        for part in (".ENV", "auth.json", "Credentials.json", ".writer.lock", "stdout.log", "stderr.log", "__pycache__"):
            with self.subTest(part=part), self.assertRaises(ContractError):
                safe(ROOT / "runs/phase3b-seq2-v1" / part)
        with self.assertRaises(ContractError):
            safe(ROOT / ".." / "foreign")

    def _bootstrap_denial(self, study: str):
        executable = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        environment = {key: value for key, value in os.environ.items() if key.upper() in {
            "PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "PATHEXT",
        }}
        result = subprocess.run(  # nosec B603
            [str(executable), "-NoProfile", "-File", str(ROOT / "phase3b-seq2.ps1"),
             "-Action", "preflight", "-Study", study, "-Grant", "phase3b-seq2-v1/missing.json"],
            cwd=ROOT, env=environment, capture_output=True, text=True, check=False, timeout=20,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("bootstrap rejected", result.stderr.lower())

    @unittest.skipUnless(os.name == "nt", "actual Windows bootstrap case runs on host")
    def test_actual_windows_bootstrap_rejects_private_input_before_metadata(self):
        self._bootstrap_denial("phase3b-seq2-v1/.ENV")

    @unittest.skipUnless(os.name == "nt", "actual Windows bootstrap case runs on host")
    def test_actual_windows_bootstrap_rejects_foreign_phase_before_metadata(self):
        self._bootstrap_denial("phase3a-readiness-recovery-v1/missing.json")
