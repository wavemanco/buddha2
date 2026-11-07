"""The finite continuation must accept its declared work and reject scope drift."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest
from followups.phase3a_readiness_recovery_v1.test_rank_io import Dispatch
from followups.phase3a_v1.tests.test_strategy import STUDY, TASK

from . import accounting, ledger_core, remaining, strategy, workflow
from .support import BASE, read
from .test_native_s2 import ComponentMock
from .test_workflow_s2 import minimal_study


def study_fixture() -> dict:
    study = minimal_study()
    study.update(execution_pilots=list(remaining.PILOTS), policy=copy.deepcopy(remaining.POLICY),
        fixture_supervision_rehearsal=False, fixture_boundary_contract=False)
    study["slots"], study["assessment_plan"] = workflow._plan_slots(study)
    return study


class RemainingPairsTests(unittest.TestCase):
    def test_each_later_pair_uses_its_own_review_without_reopening_first_review(self):
        parent = BASE / "remaining-unit"
        parent.mkdir(parents=True, exist_ok=True)
        study = study_fixture()
        for pilot in remaining.PILOTS[1:]:
            with self.subTest(pilot=pilot), tempfile.TemporaryDirectory(dir=parent) as raw:
                run = Path(raw)
                records = {"seals": {pilot: {"pilot": pilot, "fixture": True}}}
                with patch.object(workflow, "paths", return_value=(run, run / "journal")), \
                        patch.object(workflow, "_state", return_value={"fixture": True}), \
                        patch.object(workflow, "saved", return_value=records), \
                        patch.object(workflow, "_first_review") as first_review:
                    workflow._barrier(run / "study.json", study, run / "grant.json", True,
                        "pair-" + pilot, pilot=pilot)
                self.assertEqual(read(run / ("pair-" + pilot + "-review.json"))["pilot"], pilot)
                self.assertEqual(read(run / ("barrier-pair-" + pilot + ".json"))["proof"]["pair_seal"],
                    records["seals"][pilot])
                first_review.assert_not_called()

    def test_exact_three_pair_worklist_excludes_completed_pair_and_preserves_legacy(self):
        self.assertEqual(len(minimal_study()["slots"]), 2344)
        study = study_fixture()
        self.assertEqual(len(study["slots"]), 1758)
        self.assertEqual(len(study["assessment_plan"]), 9)
        self.assertEqual({row["pair"] for row in study["slots"].values()}, set(remaining.PILOTS))
        self.assertEqual(accounting.policy_for(study["slots"]), remaining.POLICY)
        for pilot in remaining.PILOTS:
            self.assertEqual(sum(row["cell"] == pilot + ":adaptive" for row in study["slots"].values()), 408)
            self.assertEqual(sum(row["cell"] == pilot + ":fixed" for row in study["slots"].values()), 145)
        for changed in ("missing", "foreign", "turn"):
            slots = copy.deepcopy(study["slots"])
            key = next(name for name, row in slots.items() if row["role"] == "editor")
            if changed == "missing":
                del slots[key]
            elif changed == "foreign":
                slots[key]["pair"] = "p3b-01"
            else:
                slots[key]["turn"] = 25
            with self.subTest(changed=changed), self.assertRaises(ContractError):
                accounting._slot_scope(slots)

    def test_new_authority_is_exact_and_old_grant_cannot_borrow_new_policy(self):
        study = study_fixture()
        grant = {"study_sha256": STUDY, "authorization_id": "remaining-fixture", "authorized": False,
            "cap_micro_usd": 350_000_000, "canary_cap_micro_usd": 350_000_000,
            "expansion_authorized": False, "control_policy_sha256": ledger_core.am1.CONTROL_SHA256,
            "billing_profile": ledger_core.am1.BILLING_PROFILE}
        bindings = {"source_sha256": "b" * 64, "launcher_sha256": "c" * 64,
            "policy_sha256": digest(study["policy"])}
        accounting.validate_authority(STUDY, grant, True, bindings)
        changed = {**grant, "cap_micro_usd": 350_000_001}
        with self.assertRaises(ContractError):
            accounting.validate_authority(STUDY, changed, True, bindings)
        with self.assertRaises(ContractError):
            accounting.validate_authority(STUDY, grant, True,
                {**bindings, "policy_sha256": digest(accounting.POLICY)})
        for slots, policy, auth_policy in (
            (study["slots"], remaining.POLICY, accounting.POLICY),
            (minimal_study()["slots"], accounting.POLICY, remaining.POLICY),
        ):
            crossed = {**grant, "cap_micro_usd": auth_policy["phase_micro_usd"],
                "canary_cap_micro_usd": auth_policy["first_micro_usd"]}
            with self.subTest(scope=policy["id"]), self.assertRaisesRegex(ContractError, "worklist policy"):
                accounting.journal_identity(study_sha256=STUDY, slots=slots, authority=crossed,
                    fixture=True, bindings={**bindings, "policy_sha256": digest(auth_policy)})

    def test_worklist_bounds_derive_from_actual_roles_and_reject_changed_role_maximum(self):
        study = study_fixture()
        remaining.validate_bounds(study["slots"])
        original = ledger_core._reservation

        def changed(role):
            value = original(role)
            return {**value, "input": value["input"] + 1} if role == "quality" else value

        with patch.object(ledger_core, "_reservation", side_effect=changed):
            with self.assertRaisesRegex(ContractError, "producer reservations"):
                accounting.policy_for(study["slots"])

    def test_derived_cell_bounds_accept_legitimate_cached_usage_but_keep_dollars_hard(self):
        study = study_fixture()
        state = workflow._empty_state(study, True)
        meta = {"pair": "p3b-02", "cell": "p3b-02:adaptive", "role": "editor"}
        reserve = ledger_core._reservation("editor")
        state["cells"][meta["cell"]]["input_tokens"] = 13_000_000
        accounting._admit(state, meta, reserve, policy=study["policy"])
        state["cells"][meta["cell"]]["spent_micro_usd"] = 50_000_000 - reserve["micro_usd"] + 1
        with self.assertRaises(accounting.CellBudgetStop):
            accounting._admit(state, meta, reserve, policy=study["policy"])
        state["cells"][meta["cell"]]["spent_micro_usd"] = 0
        state["spent_micro_usd"] = 350_000_000 - reserve["micro_usd"] + 1
        with self.assertRaises(accounting.PhaseBudgetStop):
            accounting._admit(state, meta, reserve, policy=study["policy"])

    def test_review_unknown_liability_and_exact_attempt_limit_remain_binding(self):
        study = study_fixture()
        state = workflow._empty_state(study, True)
        meta = {"pair": "p3b-03", "cell": "p3b-03:fixed", "role": "plan"}
        reserve = ledger_core._reservation("plan")
        with self.assertRaises(accounting.AuthorityError):
            accounting._admit(state, meta, reserve, policy=study["policy"])
        state.update(engineering_review="a" * 64, first_assessments_closed=True)
        accounting._admit(state, meta, reserve, policy=study["policy"])
        state["status"] = "blocked-unknown"
        with self.assertRaises(accounting.LiabilityStop):
            accounting._admit(state, meta, reserve, policy=study["policy"])
        state.update(status="ready", attempts=1758)
        with self.assertRaises(accounting.PhaseBudgetStop):
            accounting._admit(state, meta, reserve, policy=study["policy"])

    def test_candidate_ordinal_order_controls_actual_sdk_request_and_exact_replay(self):
        parent = BASE / "remaining-unit"
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as temporary, ComponentMock() as mock:
            seed = Path(temporary) / "seed"
            strategy.materialize_seed(seed)
            run_id = "remaining-fixed-permutation"
            order = [f"{run_id}/candidate-{index:02}" for index in range(12, 0, -1)]
            dispatch = Dispatch(mock)
            record = strategy.fixed_best12(TASK, seed, study_sha256=STUDY, run_id=run_id,
                dispatch=dispatch, fixture=True, candidate_order=order)
            self.assertEqual(list(record["selection"]["candidate_map"].values()), order)
            before = mock.http_calls
            strategy.validate_fixed(record, TASK, seed, study_sha256=STUDY, run_id=run_id,
                fixture=True, results=dispatch.results, candidate_order=order)
            self.assertEqual(mock.http_calls, before)
            with self.assertRaises(ContractError):
                strategy.validate_fixed(record, TASK, seed, study_sha256=STUDY, run_id=run_id,
                    fixture=True, results=dispatch.results, candidate_order=list(reversed(order)))
            self.assertEqual(mock.http_calls, before)
