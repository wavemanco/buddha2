"""Remaining-profile launch metadata and a separate immutable allowance claim."""
from __future__ import annotations

import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest

from . import accounting, launch, remaining, support
from .test_remaining_s2 import study_fixture


class RemainingLaunchTests(unittest.TestCase):
    def setUp(self):
        parent = support.ROOT / "runs/phase3b-seq2-v1" if os.name == "nt" else support.BASE
        parent = parent / "remaining-pairs-v1"
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="launch-unit-", dir=parent)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.native = self.root / "native"
        self.journal = self.root / "journal"
        self.study_path, self.grant_path = self.root / "study.json", self.root / "grant.json"
        self.checked = {key: char * 64 for key, char in zip(launch._BINDINGS, "abcdef", strict=True)}
        self.checked.update(mode="provider", fixture=False, policy_sha256=digest(remaining.POLICY),
            execution_pilots=list(remaining.PILOTS), cap_micro_usd=remaining.POLICY["phase_micro_usd"],
            first_pair_cap_micro_usd=remaining.POLICY["first_micro_usd"],
            readiness_included_micro_usd=remaining.POLICY["cell_micro_usd"],
            run=str(self.native / ("a" * 64) / "live"), journal=str(self.journal))

    def scope(self):
        return (patch.object(launch, "BASE", self.root), patch.object(launch, "NATIVE", self.native),
                patch.object(accounting, "canonical_journal", return_value=self.journal))

    def test_new_profile_claim_preserves_closed_claim_and_cannot_reset_identity(self):
        closed = self.root / "live-study-timing-continuation-v1.json"
        closed.write_bytes(b'{"closed":true}\n')
        base, native, journal = self.scope()
        with base, native, journal:
            value = launch._live_study_claim(self.checked, publish=True)
            self.assertEqual(value["cap_micro_usd"], 350_000_000)
            self.assertEqual(value["readiness_included_micro_usd"], 50_000_000)
            self.assertEqual(value["execution_pilots"], list(remaining.PILOTS))
            self.assertTrue((self.root / "live-study-remaining-pairs-v1.json").is_file())
            self.assertEqual(launch._live_study_claim(self.checked), value)
            changed = {**self.checked, "grant_sha256": "0" * 64}
            with self.assertRaisesRegex(ContractError, "already claims"):
                launch._live_study_claim(changed)
        self.assertEqual(closed.read_bytes(), b'{"closed":true}\n')

    def test_foreign_pilots_or_changed_caps_cannot_claim_remaining_allowance(self):
        base, native, journal = self.scope()
        with base, native, journal:
            for change in ({"execution_pilots": ["p3b-01", "p3b-02", "p3b-03"]},
                           {"cap_micro_usd": 351_000_000}, {"first_pair_cap_micro_usd": 50_000_000},
                           {"readiness_included_micro_usd": 0}, {"policy_sha256": "0" * 64}):
                with self.subTest(change=change), self.assertRaises(ContractError):
                    launch._live_study_claim(self.checked | change, publish=True)
        self.assertFalse((self.root / "live-study-remaining-pairs-v1.json").exists())

    def test_preflight_metadata_uses_the_validated_profile_and_preserves_legacy_defaults(self):
        for continuation in (False, True):
            value = {**self.checked, "provider_calls": 0, "credentials_read": False}
            if not continuation:
                value.pop("execution_pilots")
                value["policy_sha256"] = digest(accounting.POLICY)
            slots = study_fixture()["slots"] if continuation else {}
            prepared = {"slots": slots, "editor_tools": {}}
            if continuation:
                prepared.update(execution_pilots=list(remaining.PILOTS), policy=copy.deepcopy(remaining.POLICY),
                    maximum_admitted_attempts=1758, readiness_max_micro_usd=50_000_000)

            def artifact(path):
                return {"fixture": False, "authority": {}} if path == self.grant_path else prepared

            with self.subTest(continuation=continuation), patch.object(accounting, "runtime_guard"), \
                    patch.object(launch, "_completion_path", side_effect=Path), \
                    patch.object(launch, "_assessment_only", return_value=False), \
                    patch.object(launch, "read_json", side_effect=artifact), \
                    patch.object(launch, "_workflow_preflight", return_value=value), \
                    patch.object(launch, "NATIVE", self.native), \
                    patch.object(accounting, "canonical_journal", return_value=self.journal), \
                    patch.object(accounting, "journal_identity", return_value="f" * 64):
                result = launch.preflight(self.study_path, self.grant_path, "all", "provider-config")
            policy = remaining.POLICY if continuation else accounting.POLICY
            self.assertEqual(result["cap_micro_usd"], policy["phase_micro_usd"])
            self.assertEqual(result["first_pair_cap_micro_usd"], policy["first_micro_usd"])
            self.assertEqual(result["readiness_included_micro_usd"], policy["cell_micro_usd"])
            self.assertEqual(result["slot_count"], 1758 if continuation
                             else accounting.WORKLIST_PROFILE["potential_request_slots"])
            self.assertEqual(result["maximum_admitted_attempts"], 1758 if continuation
                             else accounting.WORKLIST_PROFILE["maximum_admitted_attempts"])
            self.assertTrue(result["configuration_only"])
            self.assertFalse(result["credential_access"])


if __name__ == "__main__":
    unittest.main()
