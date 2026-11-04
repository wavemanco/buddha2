"""Finite accounting/analysis checks frozen in workflow-acceptance-cases.json."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from buddha2.artifacts import ContractError, digest

from . import accounting, ledger_core, report, workflow


def minimal_study() -> dict:
    tasks = [
        {
            "pilot_id": pilot,
            "parent_task_id": f"development-{index}",
            "prompt": "Offline fixture",
            "source_context": [],
            "arm_order": ["adaptive", "fixed"],
        }
        for index, pilot in enumerate(accounting.PAIRS)
    ]
    study = {
        "study_sha256": "a" * 64,
        "execution_tag": "phase3b-unit",
        "tasks": tasks,
        "policy": copy.deepcopy(accounting.POLICY),
        "fixture": True,
        "prior_live_episode": {
            "known_spent_micro_usd": 46044365,
            "reserved_micro_usd": 22880000,
            "provider_calls": 1997,
            "known_requests": 1995,
            "unknown_requests": 2,
        },
    }
    study["slots"], study["assessment_plan"] = workflow._plan_slots(study)
    return study


def completed_fixture() -> tuple[dict, dict, dict]:
    study = minimal_study()
    state = workflow._empty_state(study, True)
    state["engineering_review"] = "b" * 64
    state["first_assessments_closed"] = True
    saved: dict = {"branches": {}, "seals": {}, "assessments": {}, "readiness": {"passed": True}}
    for pilot in accounting.PAIRS:
        candidates = {key: {"id": f"{pilot}:{key}"} for key in ("fixed", "c1", "c2")}
        def result_for(role):
            slot = next(name for name, row in study["slots"].items() if row["role"] == role and row["pair"] == pilot)
            result = {"slot_id": slot, "role": role, "status": "response", "response": {
                "text": "fixture result", "stop_reason": "end_turn", "model": "claude-opus-5",
                "usage": {"input_tokens": 0, "output_tokens": 0}}, "spent_micro_usd": 0, "reserved_micro_usd": 0}
            state["results"][slot] = result
            state["intents"][slot] = {"role": role, "request": {"model": "claude-opus-5"},
                "reservation": {"micro_usd": 11440000}}
            state["attempts"] += 1
            return slot, result
        fixed_slot, fixed_result = result_for("fixed_selector")
        native_slot, _ = result_for("native_selector")
        fixed_id = workflow._fixed_id(study, pilot)
        fixed_candidates = [{"run_id": f"{fixed_id}/candidate-{index:02}", "status": "complete",
            "portfolio": candidates["fixed"] if index == 1 else {"id": f"{pilot}:fixed:{index}"}}
            for index in range(1, 13)]
        fixed = {"portfolio": candidates["fixed"], "status": "complete", "run_id": fixed_id,
            "selected_run_id": fixed_candidates[0]["run_id"], "candidates": fixed_candidates,
            "selection": {"slot_id": fixed_slot, "result": fixed_result,
                "candidate_map": {f"candidate-{index:02}": candidate["run_id"]
                    for index, candidate in enumerate(fixed_candidates, 1)}}}
        native = {
            "portfolio": candidates["c1"],
            "checkpoints": {key: candidates[key] for key in ("c1", "c2")},
            "selected_checkpoint": "c1",
            "rollouts": {label: {"effective_strategy_sha256": value * 64}
                for label, value in (("c1", "a"), ("c2", "b"))},
            "status": "complete",
            "authentic": False,
            "native": {"selections": {"seq": {"ok": True, "chosen_label": "c1"}}},
            "editor_evidence": {"sessions": {"select.seq2": {"result_slots": [native_slot],
                "status": "valid", "model_backed": True, "authentic_eligible": True, "terminal_note_used": False}}},
        }
        for arm, result in (("fixed", fixed), ("adaptive", native)):
            saved["branches"][pilot, arm] = {"result": result, "failure": None}
        saved["seals"][pilot] = {"fixture": True}
        for target, value in (("fixed", 5), ("c1", 5), ("c2", 6)):
            planned = next(
                row
                for row in study["assessment_plan"]
                if row["pilot"] == pilot and row["target"] == target
            )
            saved["assessments"][planned["id"]] = {
                "status": "scored",
                "metrics": {"utility": value, "distinct": 10},
                "native": {
                    "fields": {"generation_scores": [8] * 10},
                    "partition_fields": {"partition": list(range(10))},
                },
            }
    return study, state, saved


class WorklistCases(unittest.TestCase):
    def test_old_phase_identity_does_not_supply_a_new_grant(self):
        self.assertIn("517b8efcdfc68bbb3e6ac6d260dc2e7e0541fdb02ea46784afc4ca5e2d300ed8",
            accounting.RETIRED_SOURCES)
        with self.assertRaises(ContractError):
            accounting.canonical_journal("bc86391000266d413276de0f9ca8fb7f4f5b65632aa509d650f8236a48735be8", True)

    def test_frozen_policy_and_population(self):
        frozen = json.loads(
            (
                Path(__file__).resolve().parents[2]
                / "evidence/phase3b-seq2-v1/workflow-acceptance-cases.json"
            ).read_text(encoding="utf-8")
        )["expected"]
        study = minimal_study()
        for key in (
            "cell_micro_usd",
            "cell_http",
            "cell_input",
            "cell_output",
            "assessment_micro_usd",
            "first_micro_usd",
            "first_assessment_micro_usd",
            "editor_turns",
            "editor_payload_bytes",
        ):
            self.assertEqual(study["policy"][key], frozen[key])
        self.assertEqual(study["policy"]["phase_micro_usd"], frozen["global_micro_usd"])
        self.assertEqual(len(study["slots"]), 2344)
        self.assertEqual(len(study["assessment_plan"]), 12)
        for pilot in accounting.PAIRS:
            self.assertEqual(
                sum(row["cell"] == pilot + ":adaptive" for row in study["slots"].values()), 408
            )
            self.assertEqual(
                sum(row["cell"] == pilot + ":fixed" for row in study["slots"].values()), 145
            )
            self.assertEqual(
                sum(
                    row["pair"] == pilot and row["role"] in {"group", "quality"}
                    for row in study["slots"].values()
                ),
                33,
            )
        self.assertEqual(
            sum(row["role"] == "native_selector" for row in study["slots"].values()), 96
        )

    def test_changed_slot_cannot_borrow_or_restart(self):
        slots = minimal_study()["slots"]
        accounting._slot_scope(slots)
        for edit in ("missing", "wrong_cell", "wrong_turn", "wrong_conversation", "wrong_role"):
            changed = copy.deepcopy(slots)
            slot = next(key for key, row in changed.items() if row["role"] == "native_selector")
            if edit == "missing":
                del changed[slot]
            elif edit == "wrong_cell":
                changed[slot]["cell"] = "assessment"
            elif edit == "wrong_turn":
                changed[slot]["turn"] = 25
            elif edit == "wrong_conversation":
                changed[slot]["conversation"] += ".restart"
            else:
                changed[slot]["role"] = "fixed_selector"
            with self.subTest(edit=edit), self.assertRaises(ContractError):
                accounting._slot_scope(changed)

    def test_reservations_do_not_depend_on_byte_capacity(self):
        self.assertEqual(
            ledger_core._reservation("native_selector"), ledger_core._reservation("quality")
        )
        self.assertEqual(ledger_core._reservation("native_selector")["micro_usd"], 11440000)
        self.assertEqual(ledger_core._reservation("answer")["micro_usd"], 2540960)
        self.assertEqual(ledger_core._reservation("group")["micro_usd"], 1661880)

    def test_exact_payload_boundary_is_preintent_and_selector_specific(self):
        request: dict = {
            "model": "claude-opus-5",
            "max_tokens": 16000,
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": "high"},
            "service_tier": "standard_only",
            "inference_geo": "global",
            "messages": [{"role": "user", "content": ""}],
        }
        overhead = len(ledger_core._wire(request))
        request["messages"][0]["content"] = "x" * (2097152 - overhead)
        self.assertEqual(len(ledger_core._wire(request)), 2097152)
        ledger_core.validate_request("native_selector", request)
        ledger_core.validate_request("fixed_selector", request)
        request["messages"][0]["content"] += "x"
        with self.assertRaises(ContractError):
            ledger_core.validate_request("native_selector", request)
        request["messages"] = [{"role": "user", "content": "Read the candidate."}]
        tool = {
            "name": "read",
            "description": "Read an allowed file",
            "input_schema": {"type": "object"},
        }
        request["tools"] = [tool]
        ledger_core.validate_request("native_selector", request, editor_tools={"read": tool})
        with self.assertRaises(ContractError):
            ledger_core.validate_request("fixed_selector", request, editor_tools={"read": tool})

    def test_joint_cell_and_phase_reservation_boundaries(self):
        study = minimal_study()
        state = workflow._empty_state(study, True)
        meta = {"pair": "p3b-01", "cell": "p3b-01:adaptive", "role": "native_selector"}
        reserve = ledger_core._reservation("native_selector")
        state["cells"][meta["cell"]]["spent_micro_usd"] = 23560000
        ledger_core._admit(state, meta, reserve)
        state["cells"][meta["cell"]]["spent_micro_usd"] += 1
        with self.assertRaises(ledger_core.CellBudgetStop):
            ledger_core._admit(state, meta, reserve)
        state["cells"][meta["cell"]]["spent_micro_usd"] = 0
        state["spent_micro_usd"] = 168560001
        with self.assertRaises(ledger_core.PhaseBudgetStop):
            ledger_core._admit(state, meta, reserve)
        state["spent_micro_usd"] = 0
        state["cells"][meta["cell"]]["attempts"] = 448
        with self.assertRaises(ledger_core.CellBudgetStop):
            ledger_core._admit(state, meta, reserve)

    def test_first_and_assessment_pools_are_not_added_funding(self):
        state = workflow._empty_state(minimal_study(), True)
        meta = {"pair": "p3b-01", "cell": "assessment", "role": "quality"}
        reserve = ledger_core._reservation("quality")
        state["first_assessment"]["spent_micro_usd"] = 13560001
        with self.assertRaises(ledger_core.CheckpointStop):
            ledger_core._admit(state, meta, reserve)
        state["first_assessment"]["spent_micro_usd"] = 0
        state["assessment"]["spent_micro_usd"] = 58560001
        with self.assertRaises(ledger_core.AssessmentBudgetStop):
            ledger_core._admit(state, meta, reserve)

    def test_first_caps_stay_binding_after_engineering_review(self):
        for reviewed in (False, True):
            state = workflow._empty_state(minimal_study(), True)
            state["engineering_review"] = "b" * 64 if reviewed else None
            meta = {"pair": "p3b-01", "cell": "p3b-01:adaptive", "role": "native_selector"}
            reserve = ledger_core._reservation("native_selector")
            state["first_pair"]["spent_micro_usd"] = 43560000
            ledger_core._admit(state, meta, reserve)
            state["first_pair"]["spent_micro_usd"] += 1
            with self.subTest(reviewed=reviewed, cap="first55"), self.assertRaises(ledger_core.CheckpointStop):
                ledger_core._admit(state, meta, reserve)
            state["first_pair"]["spent_micro_usd"] = 0
            meta.update(cell="assessment", role="quality")
            state["first_assessment"]["spent_micro_usd"] = 13560000
            ledger_core._admit(state, meta, reserve)
            state["first_assessment"]["spent_micro_usd"] += 1
            with self.subTest(reviewed=reviewed, cap="first25"), self.assertRaises(ledger_core.CheckpointStop):
                ledger_core._admit(state, meta, reserve)

    def test_unknown_liability_and_remaining_gate(self):
        state = workflow._empty_state(minimal_study(), True)
        meta = {"pair": "p3b-02", "cell": "p3b-02:adaptive", "role": "answer"}
        with self.assertRaises(ledger_core.AuthorityError):
            ledger_core._admit(state, meta, ledger_core._reservation("answer"))
        state["status"] = "blocked-unknown"
        with self.assertRaises(ledger_core.LiabilityStop):
            ledger_core._admit(state, meta, ledger_core._reservation("answer"))


class AnalysisCases(unittest.TestCase):
    def test_different_checkpoint_outputs_do_not_imply_changed_instructions(self):
        study, state, saved = completed_fixture()
        result = saved["branches"]["p3b-01", "adaptive"]["result"]
        result["rollouts"]["c2"]["effective_strategy_sha256"] = "a" * 64
        data = report.build(study, state, saved, True)
        self.assertNotEqual(result["checkpoints"]["c1"], result["checkpoints"]["c2"])
        attribution = data["analysis"]["checkpoint_deltas"][0]["strategy_attribution"]
        self.assertFalse(attribution["c2_changed_from_c1"])
        self.assertTrue(attribution["fresh_rollout_also_changes_sampling"])

    def test_incomplete_fixed_pool_or_abnormal_native_selector_cannot_complete(self):
        for fault in ("fixed_pool11", "fixed_failed", "selector_terminal", "selector_fallback", "selector_missing"):
            study, state, saved = completed_fixture()
            if fault.startswith("fixed"):
                result = saved["branches"]["p3b-04", "fixed"]["result"]
                if fault == "fixed_pool11":
                    result["candidates"].pop()
                else:
                    result["candidates"][3]["status"] = "failed"
            else:
                result = saved["branches"]["p3b-04", "adaptive"]["result"]
                if fault == "selector_terminal":
                    result["editor_evidence"]["sessions"]["select.seq2"]["terminal_note_used"] = True
                elif fault == "selector_fallback":
                    result["native"]["selections"]["seq"]["fallback"] = True
                else:
                    result["editor_evidence"]["sessions"].clear()
            data = report.build(study, state, saved, True)
            with self.subTest(fault=fault):
                self.assertEqual(data["summary"]["primary_scored"], 8)
                self.assertEqual(data["summary"]["assessment_scored"], 12)
                self.assertEqual(data["summary"]["status"], "incomplete")
                self.assertFalse(data["summary"]["complete_method_execution"])
                self.assertIsNone(data["analysis"]["mean_adaptive_minus_fixed"])
                self.assertIsNone(data["analysis"]["selected_method"])

    def test_checkpoint_targets_and_selected_aliases(self):
        study, state, saved = completed_fixture()
        data = report.build(study, state, saved, True)
        self.assertEqual(len(data["rows"]), 12)
        self.assertEqual(len(data["coverage"]["primary_rows"]), 8)
        self.assertEqual(data["summary"]["status"], "mock-complete")
        self.assertFalse(data["summary"]["scientific_complete"])
        self.assertEqual(data["analysis"]["mean_adaptive_minus_fixed"], 0)
        self.assertEqual(data["analysis"]["descriptive_direction"], "tie")
        self.assertIsNone(data["analysis"]["selected_method"])
        self.assertEqual(data["analysis"]["mean_c2_minus_c1"], 1)
        self.assertEqual(data["analysis"]["mean_selected_minus_c1"], 0)
        attribution = data["analysis"]["checkpoint_deltas"][0]["strategy_attribution"]
        self.assertEqual(attribution["c1_effective_strategy_sha256"], "a" * 64)
        self.assertEqual(attribution["c2_effective_strategy_sha256"], "b" * 64)
        self.assertTrue(attribution["c2_changed_from_c1"])
        self.assertTrue(attribution["fresh_rollout_also_changes_sampling"])
        for row in data["coverage"]["primary_rows"]:
            if row["arm"] == "adaptive":
                self.assertTrue(row["assessment_is_alias"])
                self.assertIn(":c1:", row["assessment_id"])

    def test_missing_unselected_checkpoint_is_not_full_completion(self):
        study, state, saved = completed_fixture()
        row = next(
            row
            for row in study["assessment_plan"]
            if row["pilot"] == "p3b-04" and row["target"] == "c2"
        )
        del saved["assessments"][row["id"]]
        data = report.build(study, state, saved, True)
        self.assertEqual(data["summary"]["primary_scored"], 8)
        self.assertEqual(data["summary"]["assessment_scored"], 11)
        self.assertEqual(data["summary"]["status"], "incomplete")
        self.assertIsNone(data["analysis"]["mean_c2_minus_c1"])
        self.assertIsNone(data["analysis"]["selected_method"])

    def test_invalid_selection_or_nonalias_cannot_report(self):
        for edit in ("outsider", "mismatch"):
            study, state, saved = completed_fixture()
            result = saved["branches"]["p3b-01", "adaptive"]["result"]
            if edit == "outsider":
                result["selected_checkpoint"] = "base1"
            else:
                result["portfolio"] = {"id": "other"}
            with self.subTest(edit=edit), self.assertRaises(ContractError):
                report.build(study, state, saved, True)

    def test_saved_analysis_is_deterministic_and_preserves_inputs(self):
        study, state, saved = completed_fixture()
        before = digest(
            {
                "study": study,
                "state": state,
                "saved": sorted((str(key), value) for key, value in saved["branches"].items()),
            }
        )
        first = report.build(study, state, saved, True)
        self.assertEqual(first, report.build(study, state, saved, True))
        after = digest(
            {
                "study": study,
                "state": state,
                "saved": sorted((str(key), value) for key, value in saved["branches"].items()),
            }
        )
        self.assertEqual(before, after)

    def test_fixture_does_not_add_real_historical_cost(self):
        study, state, saved = completed_fixture()
        data = report.build(study, state, saved, True)
        self.assertEqual(data["summary"]["prior_real_phase3a_spent_micro_usd"], 46044365)
        self.assertEqual(data["summary"]["prior_real_phase3a_reserved_micro_usd"], 22880000)
        self.assertIsNone(data["summary"]["cumulative_real_phase3a_spent_micro_usd"])


if __name__ == "__main__":
    unittest.main()
