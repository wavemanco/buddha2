"""Independent track selection and lineage checks over unchanged saved evidence."""

import copy
import unittest

from buddha2.artifacts import ContractError, digest
from buddha2.phase2_decisions import (
    POLICIES,
    build_decision,
    continuation_compatibility,
    validate_decision,
)
from buddha2.phase2_human import make_human_assessment
from tests.test_phase2_analysis import completed_forms, fixture_bundle


def human_assessment(study, portfolios, *, concern=None, cannot=False):
    forms = completed_forms(study, portfolios)
    if concern is not None:
        forms[0]["judgments"][concern]["status"] = "substantive concern"
    if cannot:
        forms[0]["judgments"][0]["status"] = "cannot judge"
    submissions = [{"form": form, "delivered_at": "2026-10-25T10:00:00Z",
                    "first_exposed_at": "2026-10-25T11:00:00Z",
                    "received_at": "2026-10-26T12:00:00Z"} for form in forms]
    return make_human_assessment(study, portfolios, submissions,
                                 cutoff="2026-10-26T13:00:00Z", fixture=True,
                                 window={form["reader_id"]: {"delivered_at": "2026-10-25T10:00:00Z",
                                                            "due_date": form["due_date"]} for form in forms})


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.study, self.portfolios, self.assessments, self.state, self.native = fixture_bundle()
        self.before = digest([self.study, self.portfolios, self.assessments, self.state])

    def build(self, track="benchmark", **kwargs):
        return build_decision(self.study, self.portfolios, self.assessments, self.state,
                              self.native, track=track, cutoff="2026-10-26T15:00:00Z",
                              fixture=True, **kwargs)

    def test_benchmark_selects_without_humans_and_preserves_historical_identity(self):
        bundle = self.build()
        decision = bundle["decision"]
        self.assertEqual(decision["synthetic_selected_method"], "A")
        self.assertIsNone(decision["selected_method"])
        self.assertEqual(decision["human_status"], "not-required")
        self.assertFalse(decision["policy_predeclared_for_execution"])
        self.assertEqual(decision["study_sha256"], self.study["study_sha256"])
        self.assertEqual(self.before, digest([self.study, self.portfolios, self.assessments, self.state]))
        self.assertEqual(bundle, self.build())
        self.assertNotIn("human_compromised_or_cannot_judge", bundle["analysis"])

    def test_missing_human_evidence_only_affects_optional_track(self):
        benchmark = self.build()["decision"]
        human = self.build("human-augmented", parent=benchmark)["decision"]
        self.assertEqual(human["status"], "inconclusive")
        self.assertEqual(human["human_status"], "absent")
        self.assertEqual(human["benchmark_decision_sha256"], benchmark["decision_sha256"])
        self.assertEqual(self.build()["decision"], benchmark)
        with self.assertRaisesRegex(ContractError, "do not ingest"):
            self.build(human_assessment={"malformed": "human data never influences benchmark"})

    def test_exact_ties_use_cost_then_simplicity_and_utility_has_priority(self):
        a_requests = {slot for portfolio in self.portfolios if portfolio["provenance"]["method"] == "A"
                      for slot in portfolio["provenance"]["request_ids"]}
        for result in self.state["results"].values():
            if result["role"] == "answer":
                result["spent_micro_usd"] = 11 if result["slot_id"] in a_requests else 10
            elif result["role"] == "plan":
                result["spent_micro_usd"] = 10
            elif result["role"] == "rank":
                result["spent_micro_usd"] = 0
        self.state["spent_micro_usd"] = sum(r["spent_micro_usd"] for r in self.state["results"].values())
        tied = self.build()["decision"]
        self.assertEqual(len(set(tied["candidate_cost_micro_usd"].values())), 1)
        self.assertEqual(tied["synthetic_selected_method"], "A")
        original = self.native.finalize

        def finalize(portfolio, group, quality):
            result = original(portfolio, group, quality)
            result["metrics"]["utility"] = 7 if portfolio["provenance"]["method"] == "C" else 4
            return result

        self.native.finalize = finalize
        for assessment in self.assessments:
            if assessment["method"] == "C":
                assessment["metrics"]["utility"] = 7
        self.assertEqual(self.build()["decision"]["synthetic_selected_method"], "C")

    def test_later_humans_can_retain_or_change_seed_without_native_changes(self):
        benchmark_bundle = self.build()
        benchmark = benchmark_bundle["decision"]
        humans = human_assessment(self.study, self.portfolios)
        retained = self.build("human-augmented", parent=benchmark, human_assessment=humans)
        self.assertEqual(retained["decision"]["synthetic_selected_method"], "A")
        humans = human_assessment(self.study, self.portfolios, concern=0)
        changed = self.build("human-augmented", parent=benchmark, human_assessment=humans)
        self.assertEqual(changed["decision"]["synthetic_selected_method"], "B")
        self.assertEqual(changed["execution"], benchmark_bundle["execution"])
        self.assertEqual(changed["native_assessment"], benchmark_bundle["native_assessment"])
        self.assertEqual(changed["analysis"], benchmark_bundle["analysis"])
        self.assertEqual(self.before, digest([self.study, self.portfolios, self.assessments, self.state]))

    def test_cannot_judge_and_compromised_humans_only_make_optional_decision_inconclusive(self):
        benchmark = self.build()["decision"]
        humans = human_assessment(self.study, self.portfolios, cannot=True)
        optional = self.build("human-augmented", parent=benchmark, human_assessment=humans)["decision"]
        self.assertEqual(optional["status"], "inconclusive")
        self.assertEqual(self.build()["decision"], benchmark)
        forged = copy.deepcopy(humans)
        forged["eligible_methods"] = ["A", "B", "C"]
        forged["selection_inconclusive"] = False
        forged["assessment_sha256"] = digest({k: v for k, v in forged.items() if k != "assessment_sha256"})
        with self.assertRaises(ContractError):
            self.build("human-augmented", parent=benchmark, human_assessment=forged)

    def test_missing_native_coverage_or_unknown_liability_prevents_benchmark_selection(self):
        self.assessments.pop()
        self.assertEqual(self.build()["decision"]["status"], "inconclusive")
        self.setUp()
        self.state["status"] = "blocked-unknown"
        self.assertEqual(self.build()["decision"]["status"], "inconclusive")

    def test_native_forgery_and_unreconciled_accounting_rejected_for_every_track(self):
        benchmark = self.build()["decision"]
        self.assessments[0]["metrics"]["utility"] = 10
        for track in POLICIES:
            with self.assertRaises(ContractError):
                self.build(track, **({"parent": benchmark} if track != "benchmark" else {}))
        self.setUp()
        self.state["spent_micro_usd"] += 1
        with self.assertRaisesRegex(ContractError, "reconcile"):
            self.build()

    def test_parent_must_bind_exact_saved_evidence_and_not_future_cutoff(self):
        benchmark = self.build()["decision"]
        for field, value in (("execution_sha256", "0" * 64),
                             ("native_evidence_sha256", "0" * 64),
                             ("selected_procedure_sha256", "0" * 64),
                             ("cutoff", "2027-01-01T00:00:00Z")):
            forged = {**benchmark, field: value}
            forged["decision_sha256"] = digest({k: v for k, v in forged.items() if k != "decision_sha256"})
            with self.assertRaises(ContractError):
                self.build("human-augmented", parent=forged)
        with self.assertRaisesRegex(ContractError, "reference"):
            self.build("human-augmented")
        optional = self.build("human-augmented", parent=benchmark)["decision"]
        with self.assertRaisesRegex(ContractError, "benchmark root"):
            self.build("human-augmented", parent=optional)

    def test_changed_policy_and_fixture_relabelling_are_rejected(self):
        decision = self.build()["decision"]
        for field, value in (("track", "wrong"), ("selected_method", "A"),
                             ("synthetic_selected_method", "B")):
            forged = {**decision, field: value}
            forged["decision_sha256"] = digest({k: v for k, v in forged.items() if k != "decision_sha256"})
            with self.assertRaises(ContractError):
                validate_decision(forged)
        for cutoff in ("2026-10-26", "2026-10-26T15:00:00+00:00", "2026-13-01T00:00:00Z"):
            with self.assertRaises(ContractError):
                build_decision(self.study, self.portfolios, self.assessments, self.state,
                               self.native, track="benchmark", cutoff=cutoff, fixture=True)

    def test_same_seed_is_insufficient_for_reuse_and_changed_confirmation_requires_fresh_data(self):
        benchmark = self.build()["decision"]
        retained = self.build("human-augmented", parent=benchmark,
                              human_assessment=human_assessment(self.study, self.portfolios))["decision"]
        context = {"task_outputs_sha256": "1" * 64, "effective_method_sha256": "2" * 64,
                   "model_settings_sha256": "3" * 64, "budget_policy_sha256": "4" * 64,
                   "information_access_sha256": "5" * 64, "native_mode": "agg-k1"}
        shared = continuation_compatibility(benchmark, retained, context, context)
        self.assertTrue(shared["can_reuse"])
        self.assertFalse(shared["independent_replication"])
        for key in context:
            changed = {**context, key: "changed" if key == "native_mode" else "6" * 64}
            divergent = continuation_compatibility(benchmark, retained, context, changed,
                                                    confirmation_opened=True, claim="retrospective")
            self.assertFalse(divergent["can_reuse"])
            self.assertTrue(divergent["fresh_confirmation_required"])
            self.assertIn(key, divergent["differences"])
            with self.assertRaisesRegex(ContractError, "fresh unopened"):
                continuation_compatibility(benchmark, retained, context, changed,
                                           confirmation_opened=True, claim="confirmatory")
        with self.assertRaisesRegex(ContractError, "exact task/output"):
            continuation_compatibility(benchmark, retained, {}, {})


if __name__ == "__main__":
    unittest.main()
