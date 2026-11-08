"""Synthetic P4 assessment checks; native cases require the pinned offline image."""
from __future__ import annotations

import copy
import json
import math
import os
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest
from buddha2.phase2_contracts import make_portfolio
from followups.phase4_cm1_v1 import assessment as p4


def portfolio():
    return make_portfolio(
        {"id": "p4-synthetic", "prompt": "Suggest one way to organize a reading room.",
         "domain": "synthetic", "source_context": {"dataset": "synthetic", "revision": "0" * 40,
          "source_sha256": "0" * 64, "source_task_id": "p4-synthetic"}},
        [{"id": f"r{i}", "text": f"Synthetic answer {i}", "status": "ok",
          "request_id": f"request.answer.{i:02d}"} for i in range(10)],
        method="B", repeat=1, model={"requested": "fixture-no-model", "returned": "fixture-no-model"},
        settings_sha256="0" * 64, procedure_sha256="1" * 64,
        request_ids=["request.plan", *[f"request.answer.{i:02d}" for i in range(10)]],
        study_sha256="2" * 64, fixture=True)


class SavedDispatcher:
    def __init__(self, evaluator, identity, *, corrupt=None):
        self.saved = {}
        self.calls = []
        self.corrupt = corrupt
        self.prefix = evaluator.slot_prefix(identity)
        self.reverse = evaluator.slot_prefix(identity + ":reverse") + ".group"

    def __call__(self, slot, role, request):
        if slot in self.saved:
            if self.saved[slot]["request_sha256"] != digest(request):
                raise AssertionError("replay tried to replace a request")
            return self.saved[slot]
        self.calls.append(slot)
        if role == "group":
            groups = ([[0, 9], *[[i] for i in range(1, 9)]] if slot == self.reverse
                      else [[i, i + 1] for i in range(0, 10, 2)])
            payload = {"groups": groups}
        else:
            payload = {"score": int(slot.rsplit(".", 1)[1]) + 1}
        record = {"slot_id": slot, "role": role, "fixture": True, "study_sha256": "2" * 64,
            "status": "response", "dispatch_id": "synthetic-" + slot,
            "request_sha256": digest(request), "spent_micro_usd": 0, "reserved_micro_usd": 0,
            "response": {"model": request["model"], "text": json.dumps(payload),
                "stop_reason": "stop" if role == "group" else "end_turn",
                "usage": {"input_tokens": 0, "output_tokens": 0}}}
        if self.corrupt:
            self.corrupt(record)
        self.saved[slot] = record
        return record


@unittest.skipUnless(os.getenv("BUDDHA2_NB_UPSTREAM"), "requires pinned native offline image")
class NativeSupplementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from followups.phase3a_v1.native import Phase3NativeAssessment
        cls.native = Phase3NativeAssessment(Path(os.environ["BUDDHA2_NB_UPSTREAM"]))

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.blocked = [self.stack.enter_context(patch(name, side_effect=AssertionError("external activity")))
            for name in ("anthropic.Anthropic", "anthropic.AsyncAnthropic", "openai.OpenAI",
                         "openai.AsyncOpenAI", "socket.create_connection", "socket.socket.connect",
                         "socket.socket.connect_ex", "subprocess.Popen", "subprocess.run")]

    def tearDown(self):
        self.assertTrue(all(mock.call_count == 0 for mock in self.blocked))

    def test_official_is_preserved_heads_reused_permutations_mapped_and_replay_is_free(self):
        original = portfolio()
        before = copy.deepcopy(original)
        dispatch = SavedDispatcher(self.native, "p4-test")
        result = p4.assess_target(self.native, original, "p4-test", dispatch)
        self.assertEqual(original, before)
        view, request = p4._group_view(self.native, original, p4.PERMUTATIONS["reverse"])
        self.assertEqual(view["generations"], [row["text"] for row in original["responses"]][::-1])
        self.assertNotIn("provenance", view)
        self.assertEqual(request["response_format"], self.native.group_request(original)["response_format"])
        self.assertTrue(result["complete"])
        self.assertEqual(result["quality_scores"], list(range(1, 11)))
        self.assertEqual(len(dispatch.calls), 13)
        self.assertEqual(set(dispatch.calls), set(p4.target_slots(self.native, "p4-test")))
        self.assertEqual(result["official"]["metrics"]["distinct"], 5)
        self.assertEqual(len(result["official"]["requests"]), 6)
        reverse = result["sensitivity"]["reverse"]
        self.assertEqual(reverse["partition"][0], reverse["partition"][9])
        self.assertEqual(reverse["fields"]["distinct"], 9)
        expected = sum((i + 1) * 0.8 ** i for i in range(9)) / sum(0.8 ** i for i in range(10))
        self.assertAlmostEqual(reverse["fields"]["utility"], expected)
        self.assertEqual(p4.assess_target(self.native, original, "p4-test", dispatch,
                                        official=result["official"]), result)
        self.assertEqual(len(dispatch.calls), 13)

    def test_three_targets_have_thirty_nine_slots(self):
        slots = [slot for target in p4.TARGETS for slot in p4.target_slots(self.native, target)]
        self.assertEqual(len(slots), len(set(slots)))
        self.assertEqual(len(slots), 39)
        calls = []
        for target in p4.TARGETS:
            dispatch = SavedDispatcher(self.native, target)
            self.assertTrue(p4.assess_target(self.native, portfolio(), target, dispatch)["complete"])
            calls.extend(dispatch.calls)
        self.assertEqual(set(calls), set(slots))
        self.assertEqual(len(calls), 39)

    def test_unavailable_official_target_has_no_supplemental_calls(self):
        def corrupt(record):
            if record["role"] == "group":
                record["response"].update(refusal="Synthetic refusal", text="")
        dispatch = SavedDispatcher(self.native, "p4-primary-refused", corrupt=corrupt)
        result = p4.assess_target(self.native, portfolio(), "p4-primary-refused", dispatch)
        self.assertFalse(result["complete"])
        self.assertEqual(result["official"]["status"], "group_refused")
        self.assertEqual(len(dispatch.calls), 1)
        self.assertEqual(result["quality_scores"], [None] * 10)

    def test_supplemental_refusal_preserves_primary_without_fallback(self):
        def corrupt(record):
            if record["slot_id"].endswith(".quality.01"):
                record["response"]["stop_reason"] = "refusal"
        result = p4.assess_target(self.native, portfolio(), "p4-supplement-refused",
            SavedDispatcher(self.native, "p4-supplement-refused", corrupt=corrupt))
        self.assertEqual(result["official"]["status"], "scored")
        self.assertEqual(result["quality_failures"], {"1": "quality_refused"})
        self.assertFalse(result["complete"])

    def test_bad_supplemental_quality_is_missing_not_zero_or_a_changed_primary(self):
        def corrupt(record):
            if record["slot_id"].endswith(".quality.01"):
                record["response"]["text"] = '{"score":11}'
        result = p4.assess_target(self.native, portfolio(), "p4-bad-quality",
                                 SavedDispatcher(self.native, "p4-bad-quality", corrupt=corrupt))
        self.assertEqual(result["official"]["status"], "scored")
        self.assertIsNone(result["quality_scores"][1])
        self.assertFalse(result["complete"])
        self.assertEqual(result["quality_failures"], {"1": "invalid_quality"})

    def test_semantic_group_failure_does_not_hold_valid_official_result(self):
        dispatcher = SavedDispatcher(self.native, "p4-bad-group")
        def corrupt(record):
            if record["slot_id"] == dispatcher.reverse:
                record["response"]["text"] = '{"groups":[[0,0]]}'
        dispatcher.corrupt = corrupt
        result = p4.assess_target(self.native, portfolio(), "p4-bad-group", dispatcher)
        self.assertEqual(result["official"]["status"], "scored")
        self.assertEqual(result["sensitivity"]["reverse"]["status"], "invalid_group")
        self.assertEqual(result["sensitivity"]["rotate"]["status"], "scored")
        self.assertFalse(result["complete"])

    def test_foreign_or_unresolved_supplement_is_a_hard_error(self):
        for change in (lambda r: r.update(status="unknown"),
                       lambda r: r.update(request_sha256="f" * 64),
                       lambda r: r["response"].update(model="substituted")):
            def corrupt(record):
                if record["slot_id"].endswith(".quality.01"):
                    change(record)
            dispatch = SavedDispatcher(self.native, "p4-foreign", corrupt=corrupt)
            with self.subTest(change=change), self.assertRaises(ContractError):
                p4.assess_target(self.native, portfolio(), "p4-foreign", dispatch)
            self.assertNotIn(dispatch.reverse, dispatch.calls)

    def test_foreign_permuted_group_cannot_be_downgraded_to_a_diagnostic(self):
        dispatch = SavedDispatcher(self.native, "p4-foreign-group")
        def corrupt(record):
            if record["slot_id"] == dispatch.reverse:
                record["request_sha256"] = "f" * 64
        dispatch.corrupt = corrupt
        with self.assertRaises(ContractError):
            p4.assess_target(self.native, portfolio(), "p4-foreign-group", dispatch)


def bundle(prompt, target, utility, *, distinct=10, sensitivity=None):
    evaluator = {"id": "synthetic-native"}
    record = {"kind": p4.KIND, "assessment_id": prompt + ":" + target,
        "portfolio_sha256": digest([prompt, target]), "evaluator_sha256": digest(evaluator),
        "fixture": True, "official": {"task_id": prompt, "status": "scored",
            "portfolio_sha256": digest([prompt, target]), "evaluator": evaluator, "fixture": True,
            "metrics": {"utility": utility, "distinct": distinct}},
        "quality_scores": [7] * 10, "complete": True,
        "sensitivity": {name: {"status": "scored", "fields": {
            "utility": utility if sensitivity is None else sensitivity, "distinct": distinct}}
            for name in p4.PERMUTATIONS}}
    record["sha256"] = digest(record)
    return record


def rows():
    return [{"prompt_id": f"synthetic-{i}", "selected_checkpoint": "c2",
        "targets": {name: bundle(f"synthetic-{i}", name, 7 if name == "fixed" else 8)
                    for name in p4.TARGETS},
        "native_micro_usd": 1_000_000, "fixed_micro_usd": 1_000_000,
        "stage_dispositions": []} for i in range(24)]


class AnalysisTests(unittest.TestCase):
    def test_full_twenty_four_unit_interval_cost_and_secondary_panels(self):
        data = rows()
        for i, row in enumerate(data):
            row["targets"]["c2"] = bundle(row["prompt_id"], "c2", 7 + i / 24)
        result = p4.analyze_pairs(data)
        contrast = result["contrasts"]["official"]["utility"]
        self.assertTrue(result["scientific_complete"])
        self.assertEqual(contrast["n"], 24)
        expected_half = p4.T_CRITICAL_23 * math.sqrt(25 / 288) / math.sqrt(24)
        self.assertAlmostEqual(contrast["interval_95"][1] - contrast["mean"], expected_half)
        self.assertEqual(len(contrast["leave_one_out_means"]), 24)
        self.assertTrue(result["costs"]["approximately_matched"])
        self.assertIn("quality", result["pairs"][0])
        delta = result["pairs"][5]["selected_minus_fixed"]
        self.assertAlmostEqual(delta["utility_delta"],
                               delta["all_response_quality_delta"] + delta["placement_delta"])
        self.assertEqual(result["case_counts"]["provided"], 24)
        self.assertEqual(result["loss_prompt_ids"], [])

    def test_missing_unselected_target_prevents_full_claim_without_erasing_valid_pairs(self):
        data = rows()
        data[0]["targets"]["c1"] = None
        result = p4.analyze_pairs(data)
        self.assertFalse(result["primary_complete"])
        self.assertEqual(result["contrasts"]["official"]["utility"]["n"], 24)
        self.assertIsNone(result["contrasts"]["official"]["utility"]["interval_95"])
        self.assertFalse(result["matched_primary_benefit"])

    def test_loss_is_retained_beside_wins_with_exact_quality_placement_identity(self):
        data = rows()
        data[0]["targets"]["c2"] = bundle(data[0]["prompt_id"], "c2", 6)
        result = p4.analyze_pairs(data)
        self.assertEqual(result["loss_prompt_ids"], [data[0]["prompt_id"]])
        self.assertEqual(result["case_counts"]["losses"], 1)
        self.assertEqual(result["case_counts"]["wins"], 23)
        delta = result["pairs"][0]["selected_minus_fixed"]
        self.assertEqual(delta["all_response_quality_delta"], 0)
        self.assertEqual(delta["placement_delta"], -1)
        self.assertTrue(delta["descriptive_not_causal"])

    def test_zero_sensitivity_is_not_robust_positive_and_negative_is_sensitive(self):
        for score in (7, 6):
            data = rows()
            for row in data:
                row["targets"]["c2"] = bundle(row["prompt_id"], "c2", 8, sensitivity=score)
            result = p4.analyze_pairs(data)
            self.assertTrue(result["matched_primary_benefit"])
            self.assertFalse(result["positive_under_both_perturbations"])
            self.assertEqual(result["partition_sensitive"], score < 7)

    def test_cost_miss_keeps_all_pairs_and_cannot_claim_matched_benefit(self):
        data = rows()
        for row in data:
            row["fixed_micro_usd"] = 2_000_000
        result = p4.analyze_pairs(data)
        self.assertTrue(result["scientific_complete"])
        self.assertEqual(result["contrasts"]["official"]["utility"]["n"], 24)
        self.assertFalse(result["costs"]["approximately_matched"])
        self.assertFalse(result["matched_primary_benefit"])

    def test_missing_cost_is_not_zero_or_full_scientific_completion(self):
        data = rows()
        data[0]["fixed_micro_usd"] = None
        result = p4.analyze_pairs(data)
        self.assertTrue(result["primary_complete"])
        self.assertFalse(result["scientific_complete"])
        self.assertFalse(result["costs"]["coverage_complete"])
        self.assertIsNone(result["costs"]["pair_ratios"][0])

    def test_grouped_quality_is_not_mislabeled_as_a_placement_effect(self):
        data = rows()
        data[0]["targets"]["fixed"] = bundle(data[0]["prompt_id"], "fixed", 2, distinct=1)
        panel = p4.analyze_pairs(data)["pairs"][0]["quality"]["fixed"]
        self.assertEqual(panel["observed_count"], 10)
        self.assertEqual(panel["all_response_mean"], 7)
        self.assertIsNone(panel["placement_residual"])

    def test_changed_bundle_duplicate_unit_and_mixed_task_are_rejected(self):
        for mutate in (lambda d: d[0]["targets"]["fixed"]["official"]["metrics"].update(utility=9),
                       lambda d: d[1].update(prompt_id=d[0]["prompt_id"]),
                       lambda d: d[0]["targets"].update(fixed=bundle("another-task", "fixed", 7))):
            data = rows()
            mutate(data)
            with self.subTest(mutate=mutate), self.assertRaises(ContractError):
                p4.analyze_pairs(data)


if __name__ == "__main__":
    unittest.main()
