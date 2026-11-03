"""Optional readers and immutable late supplements, with synthetic forms only."""

import copy
import unittest

from buddha2.artifacts import ContractError, digest
from buddha2.phase2_human import (
    make_human_assessment,
    prepare_reader_packets,
    timestamp,
    validate_human_assessment,
)
from tests.test_phase2_analysis import completed_forms, fixture_bundle


class OptionalHumanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.study, cls.portfolios, *_ = fixture_bundle()

    def records(self):
        forms = completed_forms(self.study, self.portfolios)
        submissions = [{"form": form, "delivered_at": "2026-10-25T12:00:00Z",
                        "first_exposed_at": "2026-10-25T13:00:00Z",
                        "received_at": "2026-10-26T12:00:00Z"} for form in forms]
        window = {form["reader_id"]: {"delivered_at": "2026-10-25T12:00:00Z",
                                      "due_date": "2026-10-30"} for form in forms}
        return submissions, window

    def assess(self, submissions, *, cutoff="2026-10-26T15:00:00Z", previous=None, window=None):
        return make_human_assessment(self.study, self.portfolios, submissions, cutoff=cutoff,
                                     previous=previous, window=window, fixture=True)

    def test_zero_readers_stays_absent_and_packets_do_not_start_collection(self):
        record = self.assess([])
        self.assertFalse(record["complete"])
        self.assertTrue(record["selection_inconclusive"])
        self.assertEqual(record["missing_judgments"], 12)
        self.assertEqual(record["missing_readers"], ["fixture-R1", "fixture-R2"])
        self.assertIsNone(record["window"])
        self.assertFalse(record["collection_started_by_this_operation"])
        packets = prepare_reader_packets(self.study, self.portfolios, fixture=True)
        self.assertFalse(packets["planning_only"])
        self.assertTrue(all(form["reader_reference"] is None for form in packets["packets"].values()))
        self.assertEqual(validate_human_assessment(
            self.study, self.portfolios, record, fixture=True), record)

    def test_complete_forms_bind_execution_outputs_and_implementation_separately(self):
        submissions, window = self.records()
        before = digest(self.portfolios)
        record = self.assess(submissions, window=window)
        self.assertTrue(record["complete"])
        self.assertFalse(record["selection_inconclusive"])
        self.assertEqual(record["eligible_methods"], ["A", "B", "C"])
        self.assertEqual(record["study_sha256"], self.study["study_sha256"])
        self.assertEqual(len(record["portfolio_sha256s"]), 72)
        self.assertEqual(len(record["implementation"]["sha256"]), 64)
        self.assertEqual(digest(self.portfolios), before)
        submissions[0]["form"]["judgments"][0]["reason"] = "Changed outside immutable snapshot"
        self.assertNotEqual(record["submissions"], submissions)

    def test_missing_window_is_not_invented_from_form_dates(self):
        submissions, _ = self.records()
        with self.assertRaisesRegex(ContractError, "originally agreed collection window"):
            self.assess(submissions)

    def test_closed_window_preserves_missingness_then_late_originals_are_appended(self):
        submissions, window = self.records()
        first = self.assess(submissions[:1], cutoff="2026-10-30T23:59:59Z", window=window)
        first_hash = digest(first)
        self.assertFalse(first["complete"])
        self.assertTrue(all(first["window_closed_by_reader"].values()))
        late = copy.deepcopy(submissions[1])
        late["received_at"] = "2026-11-01T12:00:00Z"
        later = self.assess([late], cutoff="2026-11-02T12:00:00Z", previous=first)
        self.assertTrue(later["complete"])
        self.assertEqual(later["version"], 2)
        self.assertEqual(later["late_reader_ids"], ["fixture-R2"])
        self.assertEqual(later["previous_assessment_sha256"], first["assessment_sha256"])
        self.assertEqual(later["submissions"][0], first["submissions"][0])
        self.assertEqual(digest(first), first_hash)
        self.assertEqual(validate_human_assessment(
            self.study, self.portfolios, later, fixture=True), later)

    def test_late_first_version_or_unclosed_window_is_rejected(self):
        submissions, window = self.records()
        late = copy.deepcopy(submissions[1])
        late["received_at"] = "2026-11-01T12:00:00Z"
        with self.assertRaisesRegex(ContractError, "closing the agreed window"):
            self.assess([late], cutoff="2026-11-02T12:00:00Z", window=window)
        first = self.assess([], cutoff="2026-10-29T12:00:00Z", window=window)
        with self.assertRaisesRegex(ContractError, "closing the agreed window"):
            self.assess([late], cutoff="2026-11-02T12:00:00Z", previous=first)
        closed = self.assess([], cutoff="2026-10-30T23:59:59Z", previous=first)
        later = self.assess([late], cutoff="2026-11-02T12:00:00Z", previous=closed)
        self.assertEqual(later["late_reader_ids"], ["fixture-R2"])

    def test_existing_reader_cannot_be_replaced_and_prior_cutoff_cannot_hide_receipts(self):
        submissions, window = self.records()
        first = self.assess(submissions[:1], window=window)
        altered = copy.deepcopy(submissions[0])
        altered["received_at"] = "2026-10-27T12:00:00Z"
        with self.assertRaisesRegex(ContractError, "first submission"):
            self.assess([altered], cutoff="2026-10-28T12:00:00Z", previous=first)
        with self.assertRaisesRegex(ContractError, "already received"):
            self.assess(submissions[1:], cutoff="2026-10-28T12:00:00Z", previous=first)
        changed_window = copy.deepcopy(window)
        changed_window["fixture-R2"]["due_date"] = "2026-11-01"
        with self.assertRaisesRegex(ContractError, "revise the original agreed"):
            self.assess([], cutoff="2026-10-28T12:00:00Z", previous=first, window=changed_window)

    def test_cannot_judge_recognition_missing_context_and_ineligibility_are_inconclusive(self):
        for field, value in (("status", "cannot judge"), ("recognition", True),
                             ("missing_context", True)):
            submissions, window = self.records()
            submissions[0]["form"]["judgments"][0][field] = value
            record = self.assess(submissions, window=window)
            self.assertTrue(record["selection_inconclusive"])
            self.assertEqual(record["eligible_methods"], [])
        submissions, window = self.records()
        submissions[1]["form"]["eligibility"]["fresh_to_outputs"] = False
        self.assertTrue(self.assess(submissions, window=window)["compromised"])

    def test_substantive_concern_only_excludes_its_candidate(self):
        submissions, window = self.records()
        # R1's first unit is A; either reader's concern excludes this candidate.
        submissions[0]["form"]["judgments"][0]["status"] = "substantive concern"
        record = self.assess(submissions, window=window)
        self.assertTrue(record["complete"])
        self.assertFalse(record["selection_inconclusive"])
        self.assertEqual(record["eligible_methods"], ["B", "C"])

    def test_ordered_text_identity_and_derived_record_tampering_are_rejected(self):
        submissions, window = self.records()
        submissions[0]["form"]["judgments"][0]["responses"].reverse()
        with self.assertRaisesRegex(ContractError, "identity changed"):
            self.assess(submissions, window=window)
        submissions, window = self.records()
        record = self.assess(submissions, window=window)
        record["eligible_methods"] = ["A"]
        record["assessment_sha256"] = digest({k: v for k, v in record.items() if k != "assessment_sha256"})
        with self.assertRaisesRegex(ContractError, "differs from original forms"):
            validate_human_assessment(self.study, self.portfolios, record, fixture=True)

    def test_receipt_exposure_delivery_cutoff_and_utc_boundaries(self):
        for field, value in (("received_at", "2026-10-27T12:00:00Z"),
                             ("first_exposed_at", "2026-10-24T12:00:00Z"),
                             ("delivered_at", "2026-10-25T11:00:00Z")):
            submissions, window = self.records()
            submissions[0][field] = value
            with self.assertRaises(ContractError):
                self.assess(submissions, window=window)
        for value in ("2026-10-25", "2026-10-25T12:00:00+00:00", "2026-02-30T12:00:00Z", None):
            with self.assertRaises(ContractError):
                timestamp(value)

    def test_collection_can_activate_after_an_unactivated_missing_snapshot(self):
        absent = self.assess([], cutoff="2026-10-24T12:00:00Z")
        submissions, window = self.records()
        activated = self.assess(submissions, previous=absent, window=window)
        self.assertTrue(activated["complete"])
        self.assertIsNone(activated["previous"]["window"])


if __name__ == "__main__":
    unittest.main()
