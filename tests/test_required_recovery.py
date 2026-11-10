"""Explicit required-artifact recovery, with no providers or assessment data."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from buddha2.artifacts import ContractError, digest
from followups.phase3a_v1.tests.test_strategy import STUDY, TASK, FakeDispatch
from followups.phase3b_seq2_v1 import strategy
from followups.phase3b_seq2_v1.support import BASE
from followups.phase4_cm1_v1 import control, policy, workflow
from tests.test_phase4_policy import profile_for

RECOVERY = "required-plan-rank-once-v1"


class Trace(FakeDispatch):
    def __init__(self):
        super().__init__()
        self.wrapped_rank = False
        self.bad = set()
        self.refuse = set()

    def __call__(self, slot, role, request):
        existed = slot in self.results
        result = super().__call__(slot, role, request)
        if not existed:
            result["intent_sha256"] = digest([slot, digest(request)])
            if slot in self.bad:
                result["response"]["text"] = "{ malformed required artifact"
            if slot in self.refuse:
                result["response"]["stop_reason"] = "refusal"
            self.results[slot] = copy.deepcopy(result)
        return result


class RequiredRecoveryTests(unittest.TestCase):
    def setUp(self):
        folder = BASE / "required-recovery-tests"
        folder.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=folder)
        self.addCleanup(self.temp.cleanup)
        self.seed = Path(self.temp.name) / "seed"
        strategy.materialize_seed(self.seed)

    def execute(self, trace, run="synthetic-required", recovery=RECOVERY):
        return strategy.execute_cn(TASK, self.seed, study_sha256=STUDY, run_id=run,
            dispatch=trace, fixture=True, recovery_policy=recovery)

    def test_invalid_plan_recovers_once_and_exact_replay_sends_nothing(self):
        trace = Trace()
        run = "synthetic-required"
        trace.bad.add(strategy.slot_ids(run)["plan"])
        result = self.execute(trace)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(len(trace.sent), 13)
        self.assertEqual(result["requests"][1]["slot_id"], strategy.slot_ids(run)["plan"] + ".recovery1")
        self.assertEqual(len(result["required_artifact_failures"]), 1)
        self.assertEqual(strategy.validate_rollout(result, TASK, self.seed, study_sha256=STUDY,
            run_id=run, fixture=True, results=trace.results, recovery_policy=RECOVERY), result)
        self.assertEqual(len(trace.sent), 13)

    def test_invalid_rank_reuses_all_answers_and_recovers_only_the_rank(self):
        trace = Trace()
        trace.bad.add(strategy.slot_ids("synthetic-required")["rank"])
        result = self.execute(trace)
        self.assertEqual(result["status"], "complete")
        self.assertEqual([role for _, role in trace.sent].count("answer"), 10)
        self.assertEqual([role for _, role in trace.sent].count("rank"), 2)
        self.assertTrue(result["requests"][-1]["slot_id"].endswith(".rank.recovery1"))

    def test_second_failure_stays_missing_and_default_never_recovers(self):
        run = "synthetic-required"
        for recovery in (None, RECOVERY):
            trace = Trace()
            original = strategy.slot_ids(run)["plan"]
            trace.bad.update({original, original + ".recovery1"})
            with self.assertRaises(strategy.KnownOutcomeError):
                self.execute(trace, recovery=recovery)
            self.assertEqual(len(trace.sent), 1 if recovery is None else 2)
            self.assertFalse(any(slot.endswith(".recovery2") for slot, _ in trace.sent))

    def test_refusal_is_not_retried(self):
        trace = Trace()
        trace.refuse.add(strategy.slot_ids("synthetic-required")["plan"])
        with self.assertRaises(strategy.KnownOutcomeError):
            self.execute(trace)
        self.assertEqual(len(trace.sent), 1)

    def test_fixed_case_keeps_four_valid_candidates_and_all_failed_plan_cost(self):
        trace = Trace()
        run = "synthetic-case-one"
        pool = control.fixed_run_ids(run)[0]
        bad = strategy.slot_ids(pool + "/candidate-05")["plan"]
        trace.bad.add(bad)
        old = strategy.fixed_best12(TASK, self.seed, study_sha256=STUDY,
            run_id=pool, dispatch=trace, fixture=True)
        self.assertEqual(len(trace.sent), 49)
        first_four = copy.deepcopy(old["candidates"][:4])
        profile, _ = profile_for()
        completed = control.run_fixed(TASK, self.seed, study_sha256=STUDY, run_id=run,
            target_micro_usd=150, dispatch=trace, spent=lambda: sum(
                value["spent_micro_usd"] for value in trace.results.values()),
            fixture=True, request_policy=profile, recovery_policy=RECOVERY)
        self.assertEqual(completed["status"], "complete")
        self.assertEqual(completed["pools"][0]["candidates"][:4], first_four)
        self.assertEqual(len(trace.sent), 146)
        self.assertEqual(completed["spent_micro_usd"], 146)
        self.assertEqual(completed["pools"][0]["candidates"][4]["requests"][0], trace.results[bad])
        self.assertEqual(len(completed["pools"][0]["candidates"]), 12)

    def test_only_amended_worklists_admit_finite_required_recovery_slots(self):
        original = {"study_sha256": STUDY, "execution_tag": "synthetic-worklist"}
        normal = workflow.worklist(original, "inference", "p4-01", TASK)
        amended = {**original, "continuation": {"required_artifact_recovery": RECOVERY}}
        slots = workflow.worklist(amended, "inference", "p4-01", TASK)
        self.assertEqual(len(slots) - len(normal), 200)
        self.assertEqual(sum(name.endswith(".recovery1") for name in slots), 200)
        self.assertTrue(all(row["role"] in {"plan", "rank"}
                            for name, row in slots.items() if name.endswith(".recovery1")))
        with self.assertRaises(ContractError):
            policy._slot_scope(slots, "inference", "p4-01")
        policy._slot_scope(slots, "inference", "p4-01", recovery_policy=RECOVERY)


if __name__ == "__main__":
    unittest.main()
