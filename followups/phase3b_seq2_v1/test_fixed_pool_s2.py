"""S2-3/S2-6 negative controls: no failed-pool shrink or review-funded expansion."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest
from followups.phase3a_readiness_recovery_v1.test_rank_io import Dispatch
from followups.phase3a_v1.tests.test_strategy import STUDY, TASK

from . import accounting, strategy, workflow
from .support import BASE
from .test_native_s2 import ComponentMock
from .test_workflow_s2 import minimal_study


class FailedPlanMock(ComponentMock):
    """Return one known malformed plan through the actual pinned SDK HTTP transport."""
    def __init__(self, *, failed_slot: str):
        self.failed_slot = failed_slot
        super().__init__()

    def _handle(self, request, *, http_module):
        response = super()._handle(request, http_module=http_module)
        if self._selected == ("plan", self.failed_slot):
            body = json.loads(response.content)
            body["content"] = [{"type": "text", "text": "malformed offline plan"}]
            self.records[-1]["response"] = copy.deepcopy(body)
            return http_module.Response(200, json=body, headers=response.headers)
        return response


class FixedPoolCases(unittest.TestCase):
    def setUp(self):
        root = BASE / "fixed-pool-tests"
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.root = Path(self.temp.name)
        self.seed = self.root / "seed"
        strategy.materialize_seed(self.seed)

    def tearDown(self):
        self.temp.cleanup()

    def test_first_and_later_failed_candidate_stop_actual_sdk_control(self):
        for failed in (1, 7):
            run_id = f"fixed-failure-at-{failed}"
            failed_slot = strategy.slot_ids(f"{run_id}/candidate-{failed:02}")["plan"]
            with self.subTest(failed=failed), FailedPlanMock(failed_slot=failed_slot) as mock:
                dispatch = Dispatch(mock)
                record = strategy.fixed_best12(TASK, self.seed, study_sha256=STUDY, run_id=run_id,
                    dispatch=dispatch, fixture=True, known_results=dispatch.results)
                self.assertEqual(record["status"], "failed")
                self.assertEqual(record["reason"], "fixed_candidate_failed")
                self.assertIsNone(record["portfolio"])
                self.assertIsNone(record["selection"])
                self.assertEqual(len(record["candidates"]), 12)
                self.assertTrue(all(row["status"] == "complete" for row in record["candidates"][:failed-1]))
                self.assertEqual(record["candidates"][failed-1]["status"], "failed")
                self.assertTrue(all(row["status"] == "not_attempted" for row in record["candidates"][failed:]))
                self.assertEqual(mock.http_calls, 12 * (failed - 1) + 1)
                self.assertFalse(any(row["role"] == "fixed_selector" for row in mock.records))
                before = mock.http_calls
                with strategy.validation_scope(readonly=True):
                    strategy.validate_fixed(record, TASK, self.seed, study_sha256=STUDY, run_id=run_id,
                        fixture=True, results=dispatch.results)
                self.assertEqual(mock.http_calls, before)

    def test_budget_stop_retains_remaining_pool_without_selector(self):
        def stopped(*args, **kwargs):
            raise accounting.CellBudgetStop("offline first candidate ceiling")
        with patch.object(strategy, "execute_cn", side_effect=stopped):
            result = strategy.fixed_best12(TASK, self.seed, study_sha256=STUDY, run_id="fixed-budget-stop",
                dispatch=lambda *args, **kwargs: self.fail("selector or generation must not dispatch"), fixture=True)
        self.assertEqual(len(result["candidates"]), 12)
        self.assertEqual(result["candidates"][0]["status"], "budget_stop")
        self.assertTrue(all(row["status"] == "not_attempted" for row in result["candidates"][1:]))
        self.assertIsNone(result["selection"])

    def test_partial_replay_rejects_later_work_after_failed_candidate(self):
        failed = {"status": "failed", "validated_slots": ["failed-plan"]}
        later = {"status": "partial", "validated_slots": ["unreachable-plan"]}
        absent = {"status": "not_started", "validated_slots": []}
        with patch.object(strategy, "validate_partial", side_effect=[failed, later] + [absent] * 10):
            with self.assertRaises(ContractError):
                strategy.validate_fixed_partial(TASK, self.seed, study_sha256=STUDY, run_id="unreachable-later",
                    fixture=True, results={})

    def test_first_and_later_fixed_failure_stop_workflow_before_other_paid_work(self):
        for failed_pilot in ("p3b-01", "p3b-03"):
            study = minimal_study()
            study.update(source_sha256="b" * 64, policy_sha256=digest(study["policy"]), launcher_sha256="d" * 64)
            study["editor_tools"] = {}
            study["tasks"][2]["arm_order"] = ["fixed", "adaptive"]
            run = self.root / failed_pilot
            journal = run / "journal"
            state = workflow._empty_state(study, True)
            state.update(engineering_review="c" * 64, first_assessments_closed=True)
            records: dict = {"branches": {}, "seals": {}, "assessments": {}, "readiness": {"passed": True}}
            index = list(accounting.PAIRS).index(failed_pilot)
            for pilot in accounting.PAIRS[:index]:
                for arm in ("fixed", "adaptive"):
                    records["branches"][pilot, arm] = {"result": {"portfolio": {"id": pilot + arm}}}
                records["seals"][pilot] = {"fixture": True}
                for row in study["assessment_plan"]:
                    if row["pilot"] == pilot:
                        records["assessments"][row["id"]] = {"status": "scored"}
            if failed_pilot == "p3b-01":
                records["branches"][failed_pilot, "adaptive"] = {"result": {"portfolio": {"id": "native"}}}
            result: dict = {"status": "failed", "portfolio": None, "candidates": [], "selection": None}
            class Ledger:
                def __init__(self, *args, **kwargs):
                    pass
                def state(self):
                    return state
                def halt(self, *args, **kwargs):
                    raise AssertionError("unexpected halt")
            with self.subTest(pilot=failed_pilot), patch.object(workflow, "paths", return_value=(run, journal)), \
                patch.object(workflow, "saved", return_value=records), patch.object(workflow, "_state", return_value=state), \
                patch.object(accounting, "Ledger", Ledger), \
                patch.object(strategy, "fixed_best12", return_value=result) as fixed, \
                patch.object(workflow.native, "run_adaptation", side_effect=AssertionError("later native work forbidden")) as native, \
                patch.object(workflow.native, "Phase3NativeAssessment") as evaluator:
                workflow._run_stage(self.root / "study.json", study, {"authority": {}}, "first" if index == 0 else "remaining",
                    type("Fixture", (), {"fixture": True})(), self.root / "grant.json", _summary=False)
                self.assertEqual(fixed.call_count, 1)
                self.assertEqual(native.call_count, 0)
                self.assertEqual(evaluator.return_value.assess.call_count, 0)
                marker = workflow.read(run / "primary-stop.json")
                self.assertEqual(marker["pilot"], failed_pilot)
                self.assertEqual(marker["reason"], "missing_required_final_or_checkpoint")

    def test_known_first_assessment_checkpoint_stop_is_irrecoverable(self):
        study = minimal_study()
        study.update(source_sha256="b" * 64, policy_sha256=digest(study["policy"]), launcher_sha256="d" * 64)
        study["editor_tools"] = {}
        state = workflow._empty_state(study, True)
        state.update(engineering_review="c" * 64, first_assessments_closed=False)
        run = self.root / "known-first-assessment-stop"
        fixed = {"result": {"portfolio": {"id": "fixed"}}}
        native = {"result": {"portfolio": {"id": "c1"}, "checkpoints": {"c1": {"id": "c1"}, "c2": {"id": "c2"}}}}
        records = {"branches": {("p3b-01", "fixed"): fixed, ("p3b-01", "adaptive"): native},
            "seals": {"p3b-01": {"fixture": True}}, "assessments": {}, "readiness": {"passed": True}}
        class Ledger:
            def __init__(self, *args, **kwargs):
                pass
            def state(self):
                return state
        with patch.object(workflow, "paths", return_value=(run, run / "journal")), \
            patch.object(workflow, "saved", return_value=records), patch.object(workflow, "_state", return_value=state), \
            patch.object(accounting, "Ledger", Ledger), \
            patch.object(workflow.native, "Phase3NativeAssessment") as evaluator:
            evaluator.return_value.assess.side_effect = accounting.CheckpointStop("known included25USD ceiling")
            workflow._run_stage(self.root / "study.json", study, {"authority": {}}, "first",
                type("Fixture", (), {"fixture": True})(), self.root / "grant.json", _summary=False)
            self.assertEqual(evaluator.return_value.assess.call_count, 1)
            self.assertEqual(workflow.read(run / "primary-stop.json")["reason"], "primary_assessment_pool_exhausted")


if __name__ == "__main__":
    unittest.main()
