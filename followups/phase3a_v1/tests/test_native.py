"""Actual unchanged Harness² scheduling with synthetic editor/provider boundaries."""
import copy
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness2.core.proposer import Proposer, Reply
from harness2.core.spec import ChannelSpec

from buddha2.artifacts import ContractError
from followups.phase3a_v1 import native, strategy
from followups.phase3a_v1.tests.test_strategy import STUDY, TASK, FakeDispatch


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", str(strategy.ROOT / "runs"))))
        self.root = Path(self.temp.name)
        self.seed = self.root / "seed"
        strategy.materialize_seed(self.seed)

    def tearDown(self):
        self.temp.cleanup()

    def proposer(self, *, invalid=False):
        native._modules()
        owner = self

        class FixtureProposer(Proposer):
            labels: list[str]

            def call(self, mission, context_dir=None, label="", **kwargs):
                self.labels.append(label)
                context = Path(context_dir)
                harness = owner.root / "fixture-proposals" / label
                shutil.copytree(context / "harness", harness)
                value = (json.loads((harness / "systemprompt.md").read_text(encoding="utf-8"))
                         if invalid else strategy.validate_harness(harness)["strategy"])
                if invalid:
                    value["extra"] = "off contract"
                elif label.startswith("inv1"):
                    value["answer_system"] += "\nKeep ideas concrete."
                elif label.startswith("dom1"):
                    value["plan_system"] += "\nUse varied practical situations."
                else:
                    owner.assertTrue((context / "pool/inv1/rollout.md").exists())
                    owner.assertTrue((context / "pool/dom1/rollout.md").exists())
                    value = strategy.validate_harness(context / "pool/inv1/harness")["strategy"]
                    value["plan_system"] = strategy.validate_harness(context / "pool/dom1/harness")["strategy"]["plan_system"]
                (harness / "systemprompt.md").write_text(json.dumps(value), encoding="utf-8")
                reply = Reply(label=label, text="<notes>Synthetic edit only.</notes>",
                    ok=True, attempts=1, workspace=harness)
                self._calls.append(reply)
                return reply

            def phase3a_evidence(self):
                return {"fixture": True, "study_sha256": STUDY, "backend": "synthetic-test",
                        "model": "no-model", "sessions": {}}

        value = FixtureProposer(ChannelSpec("opencode", "anthropic/claude-opus-5",
                                effort="high", steps=8, timeout=600), audit_dir=self.root / "audit")
        value.labels = []
        return value

    def test_real_native_agg1_counts_composition_trivial_selection_and_zero_call_replay(self):
        dispatch = FakeDispatch()
        proposer = self.proposer()
        run = self.root / "adapt"
        with patch("subprocess.run", side_effect=AssertionError("no CLI or provider in fixture check")):
            record = native.run_adaptation(TASK, self.seed, study_sha256=STUDY, run_root=run,
                tag="test", dispatch=dispatch, fixture=True, prop=proposer, known_results={},
                result_snapshot=lambda: dispatch.results)
        self.assertEqual(record["status"], "complete")
        self.assertFalse(record["authentic"])
        self.assertEqual(set(record["rollouts"]), set(native.LABELS))
        self.assertEqual(sorted(proposer.labels), ["agg1.a1", "dom1.a1", "inv1.a1"])
        self.assertEqual(len(dispatch.sent), 48)
        selection = record["native"]["selections"]["agg"]
        self.assertTrue(selection["trivial"])
        self.assertEqual(selection["chosen_label"], "agg1")
        self.assertEqual(record["native"]["modes"]["agg"]["ledger"]["R"], 4)
        self.assertEqual(record["native"]["modes"]["agg"]["ledger"]["P"], 3)
        before = copy.deepcopy((dispatch.sent, proposer.labels))
        self.assertEqual(native.validate_adaptation(record, TASK, self.seed, study_sha256=STUDY,
            run_root=run, tag="test", fixture=True, results=dispatch.results), record)
        self.assertEqual(native.run_adaptation(TASK, self.seed, study_sha256=STUDY, run_root=run,
            tag="test", dispatch=dispatch, fixture=True, prop=proposer,
            known_results=dispatch.results), record)
        self.assertEqual((dispatch.sent, proposer.labels), before)
        forged = copy.deepcopy(record)
        forged["authentic"] = True
        with self.assertRaises(ContractError):
            native.validate_adaptation(forged, TASK, self.seed, study_sha256=STUDY,
                run_root=run, tag="test", fixture=True, results=dispatch.results)
        native_summary = next((run / "native").rglob("summary.json"))
        native_summary.write_text("{}", encoding="utf-8")
        with self.assertRaises(ContractError):
            native.validate_adaptation(record, TASK, self.seed, study_sha256=STUDY,
                run_root=run, tag="test", fixture=True, results=dispatch.results)

    def test_native_repairs_and_automatic_fallback_are_explicit_not_model_success(self):
        dispatch = FakeDispatch()
        proposer = self.proposer(invalid=True)
        record = native.run_adaptation(TASK, self.seed, study_sha256=STUDY, run_root=self.root / "fallback",
            tag="fallback", dispatch=dispatch, fixture=True, prop=proposer, known_results={},
            result_snapshot=lambda: dispatch.results)
        self.assertEqual(len(proposer.labels), 6)
        self.assertTrue(all(stage["fell_back"] for stage in record["stage_dispositions"]))
        self.assertFalse(record["authentic"])
        self.assertIsNotNone(record["portfolio"])
        self.assertEqual(record["native"]["selections"]["agg"]["chosen_label"], "agg1")

    def test_native_artifact_tamper_and_wrong_editor_profile_rejected(self):
        wrong = self.proposer()
        wrong.spec = native._modules()["spec"].ChannelSpec("opencode", "anthropic/claude-opus-5", steps=9)
        dispatch = FakeDispatch()
        with self.assertRaises(ContractError):
            native.run_adaptation(TASK, self.seed, study_sha256=STUDY, run_root=self.root / "wrong",
                tag="wrong", dispatch=dispatch, fixture=True, prop=wrong, known_results={})
        self.assertEqual(dispatch.sent, [])

    def test_later_native_partial_is_checked_before_missing_base_or_editor_calls(self):
        modules = native._modules()
        channel = ChannelSpec("opencode", "anthropic/claude-opus-5", effort="high", steps=8, timeout=600)
        run = self.root / "partial"
        old = FakeDispatch()
        adapter = native.PortfolioAdapter(TASK, self.seed, study_sha256=STUDY, run_root=run,
            tag="partial", dispatch=old, fixture=True, channel=channel, known_results={})
        later = run / "rollouts/agg1/harness"
        strategy.materialize_seed(later)
        foreign = TASK | {"prompt": "A foreign task with the same logical ID"}
        strategy.execute_cn(foreign, later, study_sha256=STUDY,
            run_id=adapter.ids["agg1"], dispatch=old, fixture=True, arm="adaptive")
        slot = strategy.slot_ids(adapter.ids["agg1"])["plan"]
        partial = {slot: old.results[slot]}
        fresh = FakeDispatch()
        proposer = self.proposer()
        with self.assertRaises(ContractError):
            native.run_adaptation(TASK, self.seed, study_sha256=STUDY, run_root=run, tag="partial",
                dispatch=fresh, fixture=True, prop=proposer, known_results=partial)
        self.assertEqual(fresh.sent, [])
        self.assertEqual(proposer.labels, [])
        self.assertEqual(modules["schedule"].ROLLOUT_PARALLEL, 2)

    def test_native_assessment_ids_are_separate_and_raw_scoring_is_unchanged(self):
        dispatch = FakeDispatch()
        portfolio = strategy.execute_cn(TASK, self.seed, study_sha256=STUDY,
            run_id="for-scoring", dispatch=dispatch, fixture=True)["portfolio"]
        evaluator = native.Phase3NativeAssessment(strategy.ROOT / ".upstream/novelty-bench")
        first = evaluator.assess(portfolio, dispatch, assessment_id="fixed-primary")
        self.assertEqual(first["status"], "scored")
        self.assertEqual(first["metrics"]["distinct"], 5)
        grouped, *quality = first["requests"]
        self.assertEqual(evaluator.fold_group(portfolio, grouped, assessment_id="fixed-primary")["distinct"], 5)
        self.assertEqual(evaluator.finalize(portfolio, grouped, quality, assessment_id="fixed-primary"), first)
        with self.assertRaises(ContractError):
            evaluator.finalize(portfolio, grouped, quality, assessment_id="other")
        second = evaluator.assess(portfolio, dispatch, assessment_id="fixed-anchor")
        self.assertEqual(first["metrics"], second["metrics"])
        self.assertNotEqual(first["requests"][0]["slot_id"], second["requests"][0]["slot_id"])
        self.assertEqual(first["requests"][0]["request_sha256"], second["requests"][0]["request_sha256"])

    def test_native_swallowed_model_mismatch_still_persists_global_halt(self):
        dispatch = FakeDispatch()
        holds: list = []
        proposer = self.proposer()

        def changed(slot, role, request):
            if holds:
                self.fail("native attempted another strategy request after the integrity hold")
            result = dispatch(slot, role, request)
            if role == "plan":
                result["response"]["model"] += "-20261028"
                dispatch.results[slot] = copy.deepcopy(result)
            return result

        result = native.run_adaptation(TASK, self.seed, study_sha256=STUDY,
            run_root=self.root / "model-hold", tag="model-hold", dispatch=changed,
            fixture=True, prop=proposer, known_results={}, result_snapshot=lambda: dispatch.results,
            halt=lambda *args, **kwargs: holds.append((args, kwargs)))
        self.assertEqual(len(holds), 1)
        self.assertEqual([role for _, role in dispatch.sent], ["plan", "answer"])
        self.assertEqual(proposer.labels, [])
        self.assertEqual(result["status"], "missing")
        self.assertFalse(result["authentic"])


if __name__ == "__main__":
    unittest.main()
