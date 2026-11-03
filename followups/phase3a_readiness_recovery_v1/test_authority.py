"""The amended release cannot be prepared with stale or altered authority."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError

from . import support


class AmendmentAuthorityTests(unittest.TestCase):
    def test_approved_fixture_amendment_retains_one_bounded_pilot(self):
        authority = support.validate_authority()
        self.assertTrue(authority["am1"]["authorized"])
        self.assertEqual(authority["new_cap_micro_usd"], 190000000)
        self.assertFalse(authority["am1"]["additional_paid_repetition_authorized"])
        self.assertTrue(authority["am1"]["mandatory_reads_unchanged"])

    def test_altered_amendment_or_cases_cannot_prepare_a_release(self):
        support.BASE.mkdir(parents=True, exist_ok=True)
        for field in ("AM1_AUTHORITY", "AM1_CASES"):
            with self.subTest(field=field), tempfile.TemporaryDirectory(
                prefix="authority-", dir=support.BASE,
            ) as directory:
                changed = json.loads(getattr(support, field).read_bytes())
                changed["unauthorized_fixture_override"] = True
                target = Path(directory) / "changed.json"
                target.write_text(json.dumps(changed), encoding="utf-8")
                with patch.object(support, field, target), self.assertRaisesRegex(
                    ContractError, "frozen AM1 authority/cases differ",
                ):
                    support.validate_authority()
