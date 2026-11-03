"""Real Windows bootstrap denials and frozen S2 authority boundaries."""
from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

from buddha2.artifacts import ContractError

from .support import AUTHORITY, ROOT, read, safe, validate_authority


class LaunchBoundaryTests(unittest.TestCase):
    def test_authority_is_the_exact_whole_block_with_no_old_hold_release(self):
        value = validate_authority()
        self.assertEqual(value, read(AUTHORITY))
        self.assertEqual(value["new_cap_micro_usd"], 180000000)
        self.assertEqual(value["cumulative_max_exposure_micro_usd"], 248924365)
        self.assertFalse(value["historical_liability_release_authorized"])
        self.assertTrue(value["calls_require_offline_gate_and_fresh_masked_keys"])

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
