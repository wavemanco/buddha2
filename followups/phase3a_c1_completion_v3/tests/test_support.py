"""R2 public-input and preserved-liability boundaries; no clients/private reads."""
from __future__ import annotations

import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError, file_hash
from followups.phase3a_c1_completion_v3 import support as s


class SupportTests(unittest.TestCase):
    def test_duplicate_and_nonfinite_public_json_fail_closed(self):
        base = (s.ROOT / "runs/phase3a-c1-completion-v3" if os.name == "nt" else s.BASE) / "unit-support"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as directory:
            target = Path(directory) / "public.json"
            self.assertTrue(target.resolve().is_relative_to(base.resolve()))
            for raw in ('{"x":1,"x":2}', '{"x":NaN}', '[1,2]'):
                target.write_text(raw, encoding="utf-8")
                with self.subTest(raw=raw), self.assertRaises(ContractError):
                    s.read(target)

    def test_private_and_traversing_paths_reject_before_metadata(self):
        for suffix in ("Credential-Binding.JSON", ".writer.lock", ".env/child", "../foreign.json"):
            target = s.ROOT / "runs/phase3a-c1-completion-v3/unit-support" / suffix
            with (self.subTest(suffix=suffix), patch.object(Path, "is_symlink", side_effect=AssertionError("private metadata accessed")),
                  self.assertRaises(ContractError)):
                s.read(target)

    def test_changed_prior_exposure_or_caps_cannot_authorize_dispatch(self):
        original = {"authorized": True, "new_cap_micro_usd": 205860000, "first_cap_micro_usd": 50860000,
            "first_assessment_sublimit_micro_usd": 23700000, "new_max_attempts": 775,
            "historical_liability_release_authorized": False, "old_results_reused": False,
            "readiness_included_micro_usd": 20000000, "historical_known_micro_usd": 12231444,
            "historical_reserved_micro_usd": 22880000, "cumulative_max_exposure_micro_usd": 240971444,
            "cumulative_max_attempts": 1660, "definition_sha256": file_hash(s.DEFINITION)}
        with patch.object(s, "read", return_value=original):
            self.assertEqual(s.validate_authority(), original)
        for key, value in (("historical_known_micro_usd", 11279643), ("historical_reserved_micro_usd", 11440000),
                           ("cumulative_max_exposure_micro_usd", 228579643), ("cumulative_max_attempts", 1636),
                           ("new_cap_micro_usd", 250000000), ("authorized", False),
                           ("historical_known_micro_usd", 12231444.0), ("historical_liability_release_authorized", True)):
            changed = copy.deepcopy(original)
            changed[key] = value
            with self.subTest(key=key), patch.object(s, "read", return_value=changed), self.assertRaises(ContractError):
                s.validate_authority()

    def test_closed_archive_drift_is_rejected_without_rewriting_history(self):
        with (patch.object(s.parent, "preserve", return_value={"passed": True}),
              patch.object(s.c1, "sha", return_value="0" * 64), self.assertRaisesRegex(ContractError, "archive changed")):
            s.preserve()
