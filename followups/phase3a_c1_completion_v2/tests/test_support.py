"""R1 public-input and prior-authority boundaries; no private-file reads or clients."""
from __future__ import annotations

import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError
from followups.phase3a_c1_completion_v2 import support as s


class SupportTests(unittest.TestCase):
    def test_duplicate_and_nonfinite_public_json_fail_closed(self):
        base = (s.ROOT / "runs/phase3a-c1-completion-v2" if os.name == "nt" else s.BASE) / "unit-support"
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
            target = s.ROOT / "runs/phase3a-c1-completion-v2/unit-support" / suffix
            with (self.subTest(suffix=suffix), patch.object(Path, "is_symlink", side_effect=AssertionError("private metadata accessed")),
                  self.assertRaises(ContractError)):
                s.read(target)

    def test_changed_prior_exposure_or_caps_cannot_authorize_dispatch(self):
        original = s.validate_authority()
        for key, value in (("historical_known_micro_usd", 10487885), ("historical_reserved_micro_usd", 0),
                           ("cumulative_max_exposure_micro_usd", 227787885), ("cumulative_max_attempts", 1617),
                           ("new_cap_micro_usd", 250000000), ("authorized", False)):
            changed = copy.deepcopy(original)
            changed[key] = value
            with self.subTest(key=key), patch.object(s, "read", return_value=changed), self.assertRaises(ContractError):
                s.validate_authority()

    def test_closed_archive_drift_is_rejected_without_rewriting_history(self):
        with (patch.object(s.parent, "preserve", return_value={"passed": True}),
              patch.object(s.c1, "sha", return_value="0" * 64), self.assertRaisesRegex(ContractError, "archive changed")):
            s.preserve()
