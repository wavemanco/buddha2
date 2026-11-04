"""Pure OR1 unit fixtures; never publish invented readiness into canonical state."""
from __future__ import annotations

import copy
import unittest

from .snapshot import ProjectionError, build_snapshot, validate_projection
from .test_inspect_s2 import fixture_records


class BoundaryCompatibilityTests(unittest.TestCase):
    def test_ready_first_pair_unit_fixture_projects_three_targets_without_calls(self):
        records = fixture_records(first_only=True, no_calls=True)
        before = copy.deepcopy(records)
        payload = build_snapshot(*records, "first-pair")
        validate_projection(payload)
        scored = [row for row in payload["rows"] if row["status"] == "scored"]
        missing = [row for row in payload["rows"] if row["status"] == "missing_final"]
        self.assertEqual({(row["pilot"], row["target"]) for row in scored},
                         {("p3b-01", target) for target in ("fixed", "c1", "c2")})
        self.assertEqual(len(missing), 9)
        self.assertTrue(all(row["pilot"] != "p3b-01" and row["final_sha256"] is None for row in missing))
        self.assertEqual(sum(row["portfolio"] is None for row in payload["finals"]), 9)
        self.assertEqual(len(payload["native_assessments"]), 3)
        self.assertEqual(len(payload["selected_aliases"]), 8)
        self.assertTrue(payload["fixture"])
        self.assertFalse(payload["summary"]["scientific_complete"])
        self.assertFalse(payload["summary"]["complete_primary"])
        self.assertTrue(payload["summary"]["first_assessments_closed"])
        self.assertNotIn("engineering_review", payload["summary"])
        self.assertEqual(payload["requests"], [])
        self.assertEqual(payload["native_audit"]["requests"], [])
        self.assertEqual(records[0]["slots"], {})
        self.assertEqual(records, before)

    def test_first_pair_unit_fixture_rejects_unclosed_assessments(self):
        for value in (False, None):
            with self.subTest(first_assessments_closed=value):
                study, report, saved = fixture_records(first_only=True, no_calls=True)
                report["summary"]["first_assessments_closed"] = value
                with self.assertRaisesRegex(ProjectionError, "not completed canonical review/assessment"):
                    build_snapshot(study, report, saved, "first-pair")
        study, report, saved = fixture_records(first_only=True, no_calls=True)
        del report["summary"]["first_assessments_closed"]
        with self.assertRaises(ProjectionError):
            build_snapshot(study, report, saved, "first-pair")

    def test_first_pair_unit_fixture_rejects_missing_engineering_review(self):
        missing_reviews: tuple[object, ...] = (None, {}, False)
        for value in missing_reviews:
            with self.subTest(engineering_review=value):
                study, report, saved = fixture_records(first_only=True, no_calls=True)
                report["summary"]["engineering_review"] = value
                with self.assertRaisesRegex(ProjectionError, "not completed canonical review/assessment"):
                    build_snapshot(study, report, saved, "first-pair")
        study, report, saved = fixture_records(first_only=True, no_calls=True)
        del report["summary"]["engineering_review"]
        with self.assertRaises(ProjectionError):
            build_snapshot(study, report, saved, "first-pair")


if __name__ == "__main__":
    unittest.main(verbosity=2)
