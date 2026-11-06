"""The native engine's swallowed failure must not permit further paid coverage."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness2.core.proposer import ProposerError
from harness2.core.spec import ChannelSpec

from followups.phase3a_readiness_recovery_v1.test_rank_io import Dispatch
from followups.phase3a_v1.tests.test_strategy import STUDY, TASK

from . import accounting, deadline, native, strategy
from .support import BASE
from .test_fixed_pool_s2 import FailedPlanMock
from .test_native_s2 import SyntheticProposer


class RequiredCheckpointCases(unittest.TestCase):
    def setUp(self):
        root = BASE / "required-checkpoint-tests"
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.root = Path(self.temp.name)
        self.seed = self.root / "seed"
        strategy.materialize_seed(self.seed)

    def tearDown(self):
        self.temp.cleanup()

    def test_actual_native_c1_c2_failure_stops_before_any_more_sdk_admission(self):
        for failed, expected_calls in (("c1", 49), ("c2", 85)):
            events, blocked, stopped = [], [], []
            tag = "known-required-failure-" + failed
            run_root = self.root / failed
            failed_slot = strategy.slot_ids(native.adaptive_run_ids(TASK["id"], tag)[failed])["plan"]
            def observe(event):
                events.append(event)
                stopped.append(True)
            class GuardedProposer(SyntheticProposer):
                def call(self, mission, context_dir=None, label="", **kwargs):
                    if stopped:
                        blocked.append(label)
                        raise ProposerError("known mandatory coverage stop")
                    return super().call(mission, context_dir, label, **kwargs)
            with self.subTest(checkpoint=failed), FailedPlanMock(failed_slot=failed_slot) as mock:
                dispatch = Dispatch(mock)
                def guarded_dispatch(*args, **kwargs):
                    if stopped:
                        self.fail("provider dispatch after known mandatory checkpoint failure")
                    return dispatch(*args, **kwargs)
                with self.assertRaises(native.RequiredCheckpointStop):
                    native.run_adaptation(TASK, self.seed, study_sha256=STUDY, run_root=run_root, tag=tag,
                        dispatch=guarded_dispatch, fixture=True, prop=GuardedProposer(),
                        known_results=dispatch.results, result_snapshot=lambda: dispatch.results,
                        on_required_failure=observe)
                self.assertEqual(mock.http_calls, expected_calls)
                self.assertEqual(len(events), 1)
                self.assertEqual(events[0]["checkpoint"], failed)
                self.assertEqual(events[0]["category"], "known_solver_failure")
                self.assertTrue((run_root / "rollouts" / failed / "failure.json").is_file())
                self.assertNotIsInstance(native.RequiredCheckpointStop("known"), accounting.IntegrityStop)
                self.assertFalse(any(row["role"] == "native_selector" for row in mock.records))
                if failed == "c2":
                    self.assertIn("select.seq2", blocked)
                before = mock.http_calls
                resume_events: list[dict] = []
                with self.assertRaises(native.RequiredCheckpointStop):
                    native.run_adaptation(TASK, self.seed, study_sha256=STUDY, run_root=run_root, tag=tag,
                        dispatch=guarded_dispatch, fixture=True, prop=GuardedProposer(),
                        known_results=dispatch.results, result_snapshot=lambda: dispatch.results,
                        on_required_failure=resume_events.append)
                self.assertEqual(mock.http_calls, before)
                self.assertEqual(len(resume_events), 1)
                self.assertEqual(resume_events[0]["category"], "saved_known_failure")

    def _adapter(self, name, observer):
        return native.PortfolioAdapter(TASK, self.seed, study_sha256=STUDY, run_root=self.root / name,
            tag="observer-" + name, dispatch=lambda *args: self.fail("unexpected provider request"),
            fixture=True, channel=ChannelSpec("opencode", "anthropic/claude-opus-5", effort="high", steps=24, timeout=deadline.NATIVE_TIMEOUT),
            known_results={}, on_required_failure=observer)

    def test_required_preintent_budget_stop_notifies_once(self):
        for label in ("c1", "c2"):
            events: list[dict] = []
            adapter = self._adapter("budget-" + label, events.append)
            with patch.object(strategy, "execute_cn", side_effect=accounting.CellBudgetStop("offline known ceiling")):
                for _ in range(2):
                    with self.assertRaises(accounting.CellBudgetStop):
                        adapter._execute(TASK["id"], self.seed, adapter.ids[label])
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["category"], "known_budget_stop")
            record = native.read_json(adapter.run_root / "rollouts" / label / "halt.json")
            self.assertEqual(record["category"], "known_checkpoint_budget")

    def test_probe_failures_and_unknown_holds_are_not_known_checkpoint_failures(self):
        for label, error in (("inv1", strategy.KnownOutcomeError("offline probe", {"status": "failed"})),
            ("c1", accounting.LiabilityStop("offline unresolved liability"))):
            events: list[dict] = []
            adapter = self._adapter("noncoverage-" + label, events.append)
            with patch.object(strategy, "execute_cn", side_effect=error):
                with self.assertRaises(type(error)):
                    adapter._execute(TASK["id"], self.seed, adapter.ids[label])
            self.assertEqual(events, [])
            self.assertIsNone(adapter.required_failure)

    def test_observer_latches_before_failure_artifact_write_can_fail(self):
        events: list[dict] = []
        adapter = self._adapter("failure-io", events.append)
        def fail_write(*args, **kwargs):
            self.assertEqual(len(events), 1)
            raise OSError("offline failure artifact unavailable")
        error = strategy.KnownOutcomeError("offline required failure", {"status": "failed"})
        with patch.object(strategy, "execute_cn", side_effect=error), patch.object(native, "write_once", side_effect=fail_write):
            with self.assertRaises(OSError):
                adapter._execute(TASK["id"], self.seed, adapter.ids["c1"])
        self.assertEqual(events[0]["category"], "known_solver_failure")
        self.assertIsNotNone(adapter.required_failure)


if __name__ == "__main__":
    unittest.main()
