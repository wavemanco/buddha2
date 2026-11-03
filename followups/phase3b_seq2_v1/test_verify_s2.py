"""The synthetic whole gate must require normality without claiming live authenticity."""
from __future__ import annotations

import copy
import unittest

from . import native
from .verify import normal_fixture_path


class FixtureClassificationTests(unittest.TestCase):
    def sample(self):
        slot = "p3b-01.adaptive.editor.select.seq2.t01"
        branch = {"fixture": True, "authentic": False,
            "stage_dispositions": [{"label": stage, "fell_back": False,
                "accepted_editor_sessions": [stage + ".a1"], "model_backed": True,
                "authentic_eligible": True, "terminal_note_used": False} for stage in native.STAGES],
            "rollouts": dict.fromkeys(native.LABELS, {}), "checkpoints": {"c1": {}, "c2": {}},
            "native": {"selections": {"seq": {"ok": True, "chosen_label": "c1"}}},
            "editor_evidence": {"sessions": {"select.seq2": {"status": "valid", "model_backed": True,
                "authentic_eligible": True, "terminal_note_used": False, "result_slots": [slot]}}}}
        return branch, {slot: {"role": "native_selector", "status": "response"}}

    def test_normal_mock_is_eligible_without_live_authenticity(self):
        branch, results = self.sample()
        self.assertTrue(normal_fixture_path(branch, results))
        self.assertFalse(branch["authentic"])

    def test_claimed_live_authenticity_or_incomplete_normality_cannot_pass_fixture_gate(self):
        branch, results = self.sample()
        for field in ("authentic", "terminal", "fallback", "missing_stage", "selector"):
            changed = copy.deepcopy(branch)
            if field == "authentic":
                changed["authentic"] = True
            elif field == "terminal":
                changed["stage_dispositions"][0]["terminal_note_used"] = True
            elif field == "fallback":
                changed["stage_dispositions"][0]["fell_back"] = True
            elif field == "missing_stage":
                changed["stage_dispositions"].pop()
            else:
                changed["native"]["selections"]["seq"]["ok"] = False
            with self.subTest(field=field):
                self.assertFalse(normal_fixture_path(changed, results))
