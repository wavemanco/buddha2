"""Read gaps cannot suppress a benchmark result or erase the closed attempt's cost."""
from __future__ import annotations

import copy
import unittest

from . import report
from .test_workflow_s2 import completed_fixture


class ReadAuditReportingCases(unittest.TestCase):
    def test_incomplete_audit_is_retained_without_blocking_completed_fixture(self):
        study, state, saved = completed_fixture()
        audit = {"policy_id": "read-consumption-diagnostic-v1", "complete": False,
                 "files": {"context/C1_MANIFEST.json": {"missing_ranges": [[1599, 1682]]}},
                 "read_errors": [], "parse_errors": []}
        for (pilot, arm), branch in saved["branches"].items():
            if arm != "adaptive":
                continue
            branch["result"]["editor_evidence"]["sessions"] = {
                label: {"status": "valid", "information_proof": {"delivery": copy.deepcopy(audit)},
                        "normal_session_proof": {"notes_delivery": None, "strategy_delivery": None},
                        "result_slots": branch["result"]["editor_evidence"]["sessions"]["select.seq2"]["result_slots"],
                        "model_backed": True, "authentic_eligible": True, "terminal_note_used": False}
                for label in ("inv1.a1", "dom1.a1", "c1.a1", "inv2.a1", "dom2.a1", "c2.a1", "select.seq2")
            }
        result = report.build(study, state, saved, True)
        self.assertEqual(result["summary"]["status"], "mock-complete")
        self.assertEqual(result["analysis"]["mean_adaptive_minus_fixed"], 0)
        diagnostic = result["analysis"]["read_consumption_audit"]
        self.assertFalse(diagnostic["complete"])
        self.assertFalse(diagnostic["blocking"])
        self.assertEqual(diagnostic["recorded_sessions"], 28)
        self.assertEqual(diagnostic["missing_stages"], [])
        self.assertEqual(diagnostic["sessions"][0]["audits"]["before_decision"], audit)

    def test_absent_audits_are_unavailable_not_complete(self):
        audit = report._read_consumption_audit({})
        self.assertFalse(audit["complete"])
        self.assertEqual(audit["recorded_sessions"], 0)
        self.assertEqual(len(audit["missing_stages"]), 28)

    def test_closed_attempt_is_added_once_without_relabelling_phase3a(self):
        study, state, _ = completed_fixture()
        state.update(fixture=False, spent_micro_usd=1000000, reserved_micro_usd=0, provider_calls=10)
        row = report._historical_resources(study, state)
        self.assertEqual(row["prior_real_phase3a_spent_micro_usd"], 46044365)
        self.assertEqual(row["prior_closed_phase3b_attempt"]["known_spent_micro_usd"], 12528747)
        self.assertEqual(row["lineage_spent_micro_usd"], 59573112)
        self.assertEqual(row["lineage_reserved_micro_usd"], 22880000)
        self.assertEqual(row["lineage_max_exposure_micro_usd"], 82453112)
        self.assertEqual(row["lineage_provider_calls"], 2129)
        self.assertFalse(row["historical_unknown_released"])


if __name__ == "__main__":
    unittest.main()
