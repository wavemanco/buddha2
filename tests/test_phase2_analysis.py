"""Bound saved evidence and blinded reader forms; all examples are synthetic."""

import copy
import unittest

from buddha2.artifacts import ContractError, digest
from buddha2.phase2_analysis import (
    build_human_packets,
    build_human_templates,
    validate_analysis_evidence,
    validate_human_evidence,
)


def fixture_bundle():
    from buddha2.phase2 import (
        WalkthroughTransport,
        _templates,
        generate_order,
        make_worklist,
        rank_order,
    )
    from buddha2.phase2_contracts import slot_prefix

    tasks: list[dict] = [{"id": f"test-{i}", "prompt": f"Suggest an explanation of topic {i}.",
              "domain": "synthetic", "source_context": {
                  "dataset": "synthetic", "revision": "0" * 40,
                  "source_sha256": "0" * 64, "source_task_id": str(i)}} for i in range(12)]
    body = {"tasks": tasks, "templates": _templates(), "worklist": make_worklist(tasks),
            "human_check": {"task_ids": [t["id"] for t in tasks[:2]], "repeat": 1},
            "shared_generator_settings_sha256": "a" * 64,
            "procedure_hashes": {m: digest(m) for m in ("A", "B", "C")},
            "native_evaluator": {"id": "test-only-native-oracle"}}
    study = body | {"study_sha256": digest(body)}
    results: dict[str, dict] = {}
    transport = WalkthroughTransport()

    def dispatch(slot, role, request, **_):
        transport.slot = slot
        response = transport.create(role, request)
        result = {"slot_id": slot, "role": role, "request_sha256": digest(request),
                  "fixture": True, "study_sha256": study["study_sha256"],
                  "status": "response", "response": response, "spent_micro_usd": 5,
                  "dispatch_id": f"test:{len(results)}", "reserved_micro_usd": 0}
        results[slot] = result
        return result

    class Oracle:
        identity = body["native_evaluator"]

        def finalize(self, portfolio, group, quality):
            return {"fixture": True, "evaluator": self.identity,
                    "portfolio_sha256": digest(portfolio), "task_id": portfolio["task"]["id"],
                    "status": "scored", "metrics": {"utility": 4, "distinct": 1},
                    "requests": [group, *quality]}

    native = Oracle()
    portfolios, assessments = [], []
    for task in tasks:
        for repeat in (1, 2):
            a = generate_order(study, task, repeat, "A", dispatch,
                               checkpoint="canary", fixture=True)
            b = generate_order(study, task, repeat, "B", dispatch,
                               checkpoint="canary", fixture=True)
            c = rank_order(study, b, dispatch, checkpoint="canary")
            for portfolio in (a, b, c):
                method = portfolio["provenance"]["method"]
                prefix = slot_prefix(task["id"], method, repeat)
                group = dispatch(prefix + ".group", "group", {"model": "test-group"})
                quality = dispatch(prefix + ".quality.00", "quality", {"model": "test-quality",
                                  "messages": [{"content": "Fixture group 0"}]})
                assessment = native.finalize(portfolio, group, [quality]) | {
                    "study_sha256": study["study_sha256"], "method": method,
                    "repeat": repeat, "order_id": prefix}
                portfolios.append(portfolio)
                assessments.append(assessment)
    state = {"fixture": True, "status": "ready", "reserved_micro_usd": 0,
             "spent_micro_usd": len(results) * 5, "results": results}
    return study, portfolios, assessments, state, native


def completed_forms(study, portfolios):
    forms = copy.deepcopy(list(build_human_packets(study, portfolios, fixture=True)["packets"].values()))
    for form in forms:
        form["reader_reference"] = "synthetic-reference-" + form["reader_id"]
        form["eligibility"] = {key: key != "actual_human" for key in form["eligibility"]}
        form["delivered_on"], form["due_date"] = "2026-10-25", "2026-10-30"
        for row in form["judgments"]:
            row.update(status="acceptable", reason="Synthetic example; no real reader.",
                       task_fitness_notes="Synthetic fit note", variety_notes="Synthetic variety note",
                       duplication_notes="Synthetic duplication note", recognition=False,
                       missing_context=False)
    return forms


class AnalysisEvidenceTests(unittest.TestCase):
    def test_full_evidence_replays_and_cost_c_includes_parent_generation(self):
        study, portfolios, assessments, state, native = fixture_bundle()
        result = validate_analysis_evidence(study, assessments, portfolios, state, native, fixture=True)
        self.assertTrue(result["complete"])
        self.assertEqual(result["generation_costs_by_method"], {"A": 1200, "B": 1320, "C": 1440})
        self.assertFalse(result["selection_inconclusive"])

    def test_forged_metric_and_foreign_saved_request_are_rejected(self):
        study, portfolios, assessments, state, native = fixture_bundle()
        with self.assertRaisesRegex(ContractError, "actual pinned NativeAssessment"):
            validate_analysis_evidence(study, assessments, portfolios, state, native, fixture=False)
        changed = copy.deepcopy(assessments)
        changed[0]["metrics"]["utility"] = 10
        with self.assertRaises(ContractError):
            validate_analysis_evidence(study, changed, portfolios, state, native, fixture=True)
        state = copy.deepcopy(state)
        slot = portfolios[0]["responses"][0]["request_id"]
        state["results"][slot]["response"]["text"] = "Different saved answer"
        with self.assertRaises(ContractError):
            validate_analysis_evidence(study, assessments, portfolios, state, native, fixture=True)

    def test_partial_coverage_and_liabilities_are_inconclusive(self):
        study, portfolios, assessments, state, native = fixture_bundle()
        result = validate_analysis_evidence(study, assessments[:-1], portfolios, state, native, fixture=True)
        self.assertFalse(result["complete"])
        self.assertTrue(result["selection_inconclusive"])
        state = state | {"status": "blocked-unknown", "reserved_micro_usd": 100}
        self.assertTrue(validate_analysis_evidence(
            study, assessments, portfolios, state, native, fixture=True)["selection_inconclusive"])

    def test_packets_are_blinded_counterbalanced_and_c_preserves_b_ordered_texts(self):
        study, portfolios, *_ = fixture_bundle()
        bundle = build_human_packets(study, portfolios, fixture=True)
        first, second = bundle["packets"].values()
        self.assertEqual([r["unit_id"] for r in first["judgments"]],
                         list(reversed([r["unit_id"] for r in second["judgments"]])))
        self.assertTrue(all("method" not in row and "metrics" not in row and "model" not in row
                            for form in bundle["packets"].values() for row in form["judgments"]))
        for mapping in bundle["private_mapping"]:
            shown = next(r for r in bundle["packets"][mapping["reader_id"]]["judgments"]
                         if r["unit_id"] == mapping["unit_id"])
            original = next(p for p in portfolios if digest(p) == mapping["portfolio_sha256"])
            self.assertEqual(shown["responses"], [{"id": r["id"], "text": r["text"]}
                                                  for r in original["responses"]])

    def test_templates_are_planning_only_and_cannot_be_imported_as_completed_humans(self):
        study, portfolios, *_ = fixture_bundle()
        templates = build_human_templates(study)
        self.assertTrue(all(form["planning_only"] for form in templates["packets"].values()))
        with self.assertRaises(ContractError):
            validate_human_evidence(study, list(templates["packets"].values()), portfolios, fixture=True)

    def test_fresh_human_forms_bind_outputs_and_cannot_judge_is_globally_inconclusive(self):
        study, portfolios, *_ = fixture_bundle()
        forms = completed_forms(study, portfolios)
        result = validate_human_evidence(study, forms, portfolios, fixture=True)
        self.assertEqual(len(result["records"]), 12)
        self.assertTrue(result["complete"])
        self.assertFalse(result["selection_inconclusive"])
        forms[0]["judgments"][0]["status"] = "cannot judge"
        self.assertTrue(validate_human_evidence(study, forms, portfolios, fixture=True)["selection_inconclusive"])
        forms[0]["judgments"][0]["status"] = "acceptable"
        forms[0]["judgments"][0]["responses"].reverse()
        with self.assertRaises(ContractError):
            validate_human_evidence(study, forms, portfolios, fixture=True)

    def test_one_reader_recognition_and_duplicate_person_do_not_establish_independence(self):
        study, portfolios, *_ = fixture_bundle()
        forms = completed_forms(study, portfolios)
        self.assertTrue(validate_human_evidence(study, forms[:1], portfolios, fixture=True)["selection_inconclusive"])
        forms[0]["judgments"][0]["recognition"] = True
        self.assertTrue(validate_human_evidence(study, forms, portfolios, fixture=True)["compromised"])
        forms[1]["reader_reference"] = forms[0]["reader_reference"]
        self.assertTrue(validate_human_evidence(study, forms, portfolios, fixture=True)["selection_inconclusive"])

    def test_unknown_delivery_before_outputs_preserves_a_limited_analysis(self):
        from buddha2.phase2 import analyze

        study, portfolios, _, state, native = fixture_bundle()
        partial_humans = validate_human_evidence(study, [], portfolios[:1], fixture=True)
        self.assertEqual(partial_humans["missing_judgments"], 12)
        partial_report = analyze(study, [], [], {"A": None, "B": None, "C": None}, fixture=True,
                                 portfolios=portfolios[:1], state=state, native=native)
        self.assertEqual(partial_report["status"], "inconclusive")
        self.assertEqual(partial_report["human_records"], 0)
        slot = next(iter(state["results"]))
        unknown = {**state["results"][slot], "status": "unknown", "response": None,
                   "spent_micro_usd": None, "reserved_micro_usd": 100}
        state = {**state, "results": {slot: unknown}, "status": "blocked-unknown",
                 "reserved_micro_usd": 100, "spent_micro_usd": 0}
        humans = validate_human_evidence(study, [], [], fixture=True)
        self.assertEqual(humans["missing_judgments"], 12)
        self.assertTrue(humans["selection_inconclusive"])
        report = analyze(study, [], [], {"A": None, "B": None, "C": None}, fixture=True,
                         portfolios=[], state=state, native=native)
        self.assertEqual(report["status"], "inconclusive")
        self.assertEqual(report["missing_orders"], 72)
        self.assertEqual(report["human_records"], 0)
        self.assertEqual(report["unresolved_reservation_micro_usd"], 100)
        self.assertIsNone(report["selected_method"])
        self.assertIsNone(report["synthetic_selected_method"])


if __name__ == "__main__":
    unittest.main()
