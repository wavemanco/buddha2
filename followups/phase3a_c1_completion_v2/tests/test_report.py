"""Reporting gates over explicit synthetic assessment/ledger records; no dispatch."""
import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest
from followups.phase3a_c1_completion_v2 import report
from followups.phase3a_v1 import accounting, workflow
from followups.phase3a_v1.native import Phase3NativeAssessment

PARTITION = [0] * 5 + [1] * 5


def native_stub():
    def heads(partition):
        return [i for i, value in enumerate(partition) if value not in partition[:i]]

    return SimpleNamespace(slot_prefix=Phase3NativeAssessment.slot_prefix,
        modules={"score": SimpleNamespace(heads=heads)},
        fold_group=lambda *args, **kwargs: {"partition": PARTITION})


def records(*, fixture=False, authentic=True):
    """Minimal projections, not claimed valid provider receipts or benchmark data."""
    tasks: list[dict[str, Any]] = [{"pilot_id": f"p3a-{i:02}", "parent_task_id": f"report-synthetic-{i}",
        "prompt": "SYNTHETIC report fixture", "arm_order": ["adaptive", "fixed"],
        "source_context": {"dataset": "explicit report unit fixture", "revision": "0" * 40,
            "source_sha256": digest({"unit": i}), "source_task_id": f"unit-{i}"}} for i in range(1, 5)]
    study: dict[str, Any] = {"execution_tag": "report-unit", "tasks": tasks, "study_sha256": "a" * 64,
        "source_sha256": "b" * 64, "runtime": {"harness2_commit": "1" * 40},
        "policy": copy.deepcopy(accounting.POLICY), "prior_live_episode": {
            "known_spent_micro_usd": 11279643, "reserved_micro_usd": 11440000,
            "provider_calls": 861, "known_requests": 860, "unknown_requests": 1}}
    study["slots"], study["assessment_plan"] = workflow._plan_slots(study)
    state: dict[str, Any] = {"fixture": fixture, "status": "ready", "results": {}, "intents": {}, "cells": {},
        "spent_micro_usd": 0, "reserved_micro_usd": 0, "attempts": 0, "provider_calls": 0,
        "stopped_cells": [], "assessment_stopped": False, "engineering_review": {"passed": True},
        "first_assessments_closed": True}
    saved: dict[str, Any] = {"branches": {}, "seals": {}, "assessments": {},
             "readiness": {"passed": True, "status": "passed", "fixture": fixture}}
    for task in tasks:
        for arm in report.ARMS:
            saved["branches"][task["pilot_id"], arm] = {"failure": None, "result": {
                "status": "complete", "portfolio": {"unit": task["pilot_id"] + arm, "fixture": fixture},
                "authentic": arm == "adaptive" and authentic and not fixture,
                "native": {"modes": {"agg": {"ledger": {"P": 3, "R": 4}}}},
                "stage_dispositions": [{"label": "inv1", "kept_base": True, "fell_back": False}],
                "candidates": [{"run_id": "synthetic-candidate", "status": "complete"}]}}
    for entry in study["assessment_plan"]:
        utility = 7.0 if entry["arm"] == "adaptive" else 6.0
        scores = [8, None, None, None, None, 7, None, None, None, None]
        if entry["diagnostic"]:
            utility, scores = 5.5, [7, None, None, None, None, 8, None, None, None, None]
        saved["assessments"][entry["id"]] = {"status": "scored", "metrics": {"utility": utility, "distinct": 2},
            "native": {"fields": {"utility": utility, "generation_scores": scores},
                       "partition_fields": {"partition": ([1] * 5 + [0] * 5) if entry["diagnostic"] else PARTITION}}}
        prefix = Phase3NativeAssessment.slot_prefix(entry["id"])
        for slot, role in [(prefix + ".group", "group"), (prefix + ".quality.00", "quality"),
                           (prefix + ".quality.05", "quality")]:
            request = {"model": "gpt-5.6-luna" if role == "group" else "claude-opus-5"}
            state["intents"][slot] = {"role": role, "request": request, "reservation": {"micro_usd": 1}}
            state["results"][slot] = {"role": role, "status": "response", "spent_micro_usd": 1,
                "reserved_micro_usd": 0, "response": {"model": request["model"], "text": "synthetic",
                    "stop_reason": "end_turn", "usage": {"input_tokens": 1, "output_tokens": 1}}}
    state.update(attempts=len(state["results"]), spent_micro_usd=len(state["results"]),
                 provider_calls=0 if fixture else len(state["results"]))
    return study, state, saved


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.native = patch.object(report.parent, "_native", return_value=native_stub())
        self.native.start()
        self.addCleanup(self.native.stop)

    def test_complete_live_projection_preserves_inputs_and_uses_four_paired_units(self):
        study, state, saved = records()
        before = copy.deepcopy((study, state, saved))
        data = report.build(study, state, saved, False)
        self.assertEqual(before, (study, state, saved))
        self.assertEqual(data["summary"]["status"], "complete")
        self.assertTrue(data["analysis"]["scientific_complete"])
        self.assertEqual(data["analysis"]["mean_adaptive_minus_fixed"], 1)
        self.assertEqual(data["analysis"]["selected_method"], "adaptive")
        self.assertEqual(data["analysis"]["independent_prompt_units"], 4)
        self.assertEqual(data["coverage"]["scheduled_slots"], 775)
        self.assertEqual(len(data["coverage"]["assessments"]), 9)
        self.assertEqual(data["coverage"]["slot_counts"]["not_needed_nonhead"], 72)
        self.assertEqual(data["rows"][0]["first_answer_quality"], 8)
        self.assertIsNone(data["rows"][0]["inference_accounting"])
        self.assertFalse(data["rows"][1]["native_action_cost_is_authoritative"])
        self.assertEqual(data["summary"]["cumulative_real_phase3a_spent_micro_usd"], 11279643 + 27)
        self.assertEqual(data["summary"]["cumulative_real_phase3a_reserved_micro_usd"], 11440000)
        self.assertEqual(data["summary"]["cumulative_real_phase3a_max_exposure_micro_usd"], 22719643 + 27)
        self.assertEqual(data["summary"]["cumulative_real_phase3a_provider_calls"], 861 + 27)
        self.assertEqual(data["summary"]["prior_real_phase3a_known_responses"], 860)
        self.assertEqual(data["summary"]["prior_real_phase3a_unknown_responses"], 1)

    def test_all_scores_without_live_authenticity_or_readiness_never_select_method(self):
        for missing in ("authenticity", "readiness"):
            with self.subTest(missing=missing):
                study, state, saved = records(authentic=missing != "authenticity")
                if missing == "readiness":
                    saved.pop("readiness")
                data = report.build(study, state, saved, False)
                self.assertEqual(data["summary"]["primary_scored"], 8)
                self.assertFalse(data["summary"]["complete_primary"])
                self.assertIsNone(data["analysis"]["mean_adaptive_minus_fixed"])
                self.assertIsNone(data["analysis"]["selected_method"])

    def test_unknown_and_pending_do_not_turn_missing_cost_into_zero(self):
        for held in ("unknown", "pending"):
            with self.subTest(held=held):
                study, state, saved = records()
                slot = next(s for s, r in state["results"].items() if r["role"] == "quality")
                if held == "unknown":
                    state["results"][slot].update(status="unknown", spent_micro_usd=None,
                                                   reserved_micro_usd=11440000, response=None)
                else:
                    del state["results"][slot]
                state.update(status="blocked-unknown", reserved_micro_usd=11440000)
                data = report.build(study, state, saved, False)
                self.assertFalse(data["summary"]["complete_primary"])
                self.assertIsNone(data["analysis"]["mean_adaptive_minus_fixed"])
                receipt = next(r for r in data["protocol"]["requests"] if r["slot_id"] == slot)
                self.assertIsNone(receipt["spent_micro_usd"])
                self.assertGreater(data["summary"]["cumulative_real_phase3a_reserved_micro_usd"], 11440000)

    def test_duplicate_stays_diagnostic_and_compares_partition_equivalence(self):
        study, state, saved = records()
        data = report.build(study, state, saved, False)
        diagnostic = data["analysis"]["diagnostic"]
        self.assertTrue(diagnostic["primary_unchanged"])
        self.assertTrue(diagnostic["partition_equal"])
        self.assertEqual(diagnostic["shared_head_score_disagreements"], 2)
        self.assertEqual(diagnostic["utility_difference"], -.5)
        self.assertEqual(data["rows"][0]["metrics"]["utility"], 6)
        self.assertEqual(data["analysis"]["mean_adaptive_minus_fixed"], 1)

    def test_fixture_can_mock_complete_without_real_authenticity_or_cumulative_claims(self):
        study, state, saved = records(fixture=True)
        data = report.build(study, state, saved, True)
        self.assertEqual(data["summary"]["status"], "mock-complete")
        self.assertFalse(data["summary"]["authentic_live_path"])
        self.assertFalse(data["summary"]["scientific_complete"])
        self.assertIsNone(data["analysis"]["selected_method"])
        self.assertIsNone(data["summary"]["cumulative_real_phase3a_spent_micro_usd"])
        self.assertIsNone(data["summary"]["cumulative_real_phase3a_provider_calls"])
        with self.assertRaises(ContractError):
            report.build(study, state, saved, False)

    def test_diagnostic_must_be_classified_but_need_not_succeed(self):
        study, state, saved = records()
        aid = next(row["id"] for row in study["assessment_plan"] if row["diagnostic"])
        saved["assessments"][aid]["status"] = "failed"
        data = report.build(study, state, saved, False)
        self.assertTrue(data["summary"]["complete_primary"])
        del saved["assessments"][aid]
        data = report.build(study, state, saved, False)
        self.assertFalse(data["summary"]["complete_primary"])
        self.assertFalse(data["summary"]["diagnostic_classified"])
        self.assertIsNone(data["analysis"]["mean_adaptive_minus_fixed"])

    def test_missing_primary_and_invalid_scored_metrics_cannot_produce_mean(self):
        study, state, saved = records()
        aid = next(row["id"] for row in study["assessment_plan"] if not row["diagnostic"])
        saved["assessments"][aid]["status"] = "failed"
        data = report.build(study, state, saved, False)
        self.assertEqual(data["summary"]["primary_scored"], 7)
        self.assertIsNone(data["analysis"]["mean_adaptive_minus_fixed"])
        saved["assessments"][aid]["status"] = "scored"
        saved["assessments"][aid]["metrics"]["utility"] = float("nan")
        with self.assertRaises(ContractError):
            report.build(study, state, saved, False)

    def test_failed_refused_assessment_can_have_no_native_fields(self):
        study, state, saved = records()
        entry = next(row for row in study["assessment_plan"] if not row["diagnostic"])
        saved["assessments"][entry["id"]].update(status="failed", metrics={"utility": None, "distinct": None})
        saved["assessments"][entry["id"]]["native"]["fields"] = None
        slot = Phase3NativeAssessment.slot_prefix(entry["id"]) + ".quality.00"
        state["results"][slot]["response"]["refusal"] = True
        data = report.build(study, state, saved, False)
        row = next(row for row in data["rows"] if row["assessment_id"] == entry["id"])
        self.assertIsNone(row["first_answer_quality"])
        self.assertIsNone(row["metrics"]["utility"])
        self.assertEqual(data["coverage"]["slots"][slot], "refused")
        self.assertFalse(data["summary"]["complete_primary"])

    def test_untrusted_saved_evidence_is_disqualified_even_with_scored_records(self):
        study, state, saved = records()
        saved["validation_failure"] = {"kind": "held-evidence", "scientific_use": "disqualified"}
        data = report.build(study, state, saved, False)
        self.assertFalse(data["summary"]["complete_primary"])
        self.assertEqual(data["summary"]["primary_scored"], 0)
        self.assertTrue(all(row["status"] == "unvalidated_integrity_hold" for row in data["rows"]))
        self.assertIsNone(data["analysis"]["mean_adaptive_minus_fixed"])

    def test_unknown_fixture_does_not_fabricate_cumulative_real_spend(self):
        study, state, saved = records(fixture=True)
        slot = next(iter(state["results"]))
        state["results"][slot].update(status="unknown", response=None, spent_micro_usd=None,
                                      reserved_micro_usd=1661880)
        state.update(status="blocked-unknown", reserved_micro_usd=1661880)
        data = report.build(study, state, saved, True)
        self.assertEqual(data["summary"]["unknown_results"], 1)
        self.assertFalse(data["summary"]["complete_primary"])
        self.assertIsNone(data["summary"]["cumulative_real_phase3a_max_exposure_micro_usd"])

    def test_writer_is_immutable_and_foreign_paths_fail_before_probes(self):
        study, state, saved = records(fixture=True)
        data = report.build(study, state, saved, True)
        base = (Path("/results") if sys.platform == "linux" and os.environ.get("BUDDHA2_OUTPUT_ROOT") == "/results"
                else report.ROOT / "runs") / "phase3a-compat-c1-v1/completion-v2/unit-reports"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temporary:
            output = Path(temporary) / "report"
            report.write_report(data, output)
            report.write_report(data, output)
            self.assertEqual(len(list(output.iterdir())), 8)
            self.assertIn("Synthetic evidence only", (output / "PHASE3A_REPORT.md").read_text())
            changed = copy.deepcopy(data)
            changed["summary"]["status"] = "changed"
            with self.assertRaises(ContractError):
                report.write_report(changed, output)
            foreign = Path(temporary) / "owned-journal"
            foreign.mkdir()
            (foreign / "manifest.json").write_text("synthetic existing owner")
            with self.assertRaises(ContractError):
                report.write_report(data, foreign)
        with patch.object(Path, "is_symlink", side_effect=AssertionError("foreign path probed")):
            with self.assertRaises(ContractError):
                report.write_report(data, Path("/foreign/forbidden"))
            for target in ("/results/phase3a-compat-c1-v1/completion-v1/closed/report",
                           "/results/phase3a-c1-completion-v1/closed/report",
                           "/results/phase3a-c1-completion-v2",
                           "/results/phase3a-c1-completion-v2/private/CREDENTIAL-BINDING.JSON/report"):
                with self.assertRaises(ContractError):
                    report.write_report(data, Path(target))
        release = (Path("/results") if sys.platform == "linux" and os.environ.get("BUDDHA2_OUTPUT_ROOT") == "/results"
                   else report.ROOT / "runs") / "phase3a-c1-completion-v2/unit-reports"
        release.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=release) as temporary:
            report.write_report(data, Path(temporary) / "report")


if __name__ == "__main__":
    unittest.main()
