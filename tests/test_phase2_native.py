"""Native v1.1 call construction, strict folding, and saved-output replay."""

import copy
import os
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar

from buddha2.artifacts import digest
from buddha2.phase2_contracts import export_native, make_portfolio, permute_portfolio, slot_prefix
from buddha2.phase2_native import NativeAssessment


def sample_portfolio(method="B"):
    prefix = slot_prefix("synthetic-native-check", method, 1)
    requests = ([prefix + ".plan"] if method == "B" else []) + [f"{prefix}.answer.{i:02d}" for i in range(10)]
    return make_portfolio(
        {
            "id": "synthetic-native-check",
            "prompt": "Suggest one way to organize a reading room.",
            "domain": "synthetic",
            "source_context": {"dataset": "synthetic", "revision": "0" * 40,
                               "source_sha256": "0" * 64, "source_task_id": "synthetic-native-check"},
        },
        [{"id": f"r{i}", "text": f"Synthetic answer {i}", "status": "ok",
          "request_id": f"{prefix}.answer.{i:02d}"} for i in range(10)],
        method=method, repeat=1, model={"requested": "fixture-no-model", "returned": "fixture-no-model"},
        settings_sha256="0" * 64, procedure_sha256="1" * 64, request_ids=requests, fixture=True,
        study_sha256="2" * 64,
    )


def result_for(slot_id, role, request, payload):
    import json

    return {
        "slot_id": slot_id,
        "role": role,
        "fixture": True,
        "study_sha256": "2" * 64,
        "status": "response",
        "dispatch_id": f"synthetic-{slot_id}",
        "request_sha256": digest(request),
        "response": {
            "model": request["model"],
            "text": json.dumps(payload),
            "stop_reason": "stop" if role == "group" else "end_turn",
            "usage": {"input_tokens": 0, "output_tokens": 0},
            "request_id": f"synthetic-{slot_id}",
            "message_id": f"synthetic-message-{slot_id}",
        },
        "spent_micro_usd": 0,
        "reserved_micro_usd": 0,
    }


@unittest.skipUnless(os.getenv("BUDDHA2_NB_UPSTREAM"), "requires supported native environment")
class NativeAssessmentTests(unittest.TestCase):
    native: ClassVar[NativeAssessment]

    @classmethod
    def setUpClass(cls):
        cls.native = NativeAssessment(Path(os.environ["BUDDHA2_NB_UPSTREAM"]))

    def test_native_call_profiles_and_single_head_context_are_unchanged(self):
        portfolio = sample_portfolio()
        group = self.native.group_request(portfolio)
        self.assertEqual(group["model"], "gpt-5.6-luna")
        self.assertEqual(set(group), {"model", "messages", "response_format"})
        self.assertEqual(group["response_format"]["json_schema"]["name"], "Partition")
        self.assertTrue(group["response_format"]["json_schema"]["strict"])
        from openai.lib._parsing._completions import type_to_response_format_param

        self.assertEqual(group["response_format"], type_to_response_format_param(self.native.modules["partition"].Partition))
        partition = list(range(10))
        quality = self.native.quality_requests(portfolio, partition)
        self.assertEqual(len(quality), 10)
        for i, request in enumerate(quality):
            self.assertEqual(request["model"], "claude-opus-5")
            self.assertEqual(request["max_tokens"], 16000)
            self.assertEqual(request["thinking"], {"type": "adaptive"})
            self.assertEqual(request["output_config"]["effort"], "high")
            self.assertIn(f"<response>\nSynthetic answer {i}\n</response>", request["messages"][0]["content"])
            self.assertNotIn("<response index=", request["messages"][0]["content"])
        self.assertIn("src.partition.partition_calls", self.native.identity["native_calls"])

    def test_native_export_loader_preserves_the_verified_portfolio(self):
        portfolio = sample_portfolio()
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            export_native(portfolio, source)
            self.assertEqual(self.native.load_export(source), portfolio)
            self.assertIn("src.partition.load_instances", self.native.identity["native_calls"])

    def test_native_oracle_and_replay_do_not_generate_or_rebill(self):
        portfolio = sample_portfolio()
        frozen = copy.deepcopy(portfolio)
        saved = {}
        seen = []
        scores = iter([9, 8, 7, 6, 5])

        def dispatch(slot_id, role, request, **kwargs):
            seen.append((slot_id, role, request))
            payload = {"groups": [[i, i + 1] for i in range(0, 10, 2)]} if role == "group" else {"score": next(scores)}
            result = result_for(slot_id, role, request, payload)
            saved[slot_id] = result
            return result

        assessment = self.native.assess(portfolio, dispatch)
        self.assertEqual(assessment["status"], "scored")
        self.assertTrue(assessment["fixture"])
        self.assertEqual(assessment["metrics"]["distinct"], 5)
        self.assertIs(type(assessment["metrics"]["utility"]), float)
        self.assertIs(type(assessment["native"]["summary"]["mean_utility"]), float)
        self.assertAlmostEqual(assessment["metrics"]["utility"], 4.346485261239209, places=12)
        self.assertEqual(assessment["native"]["fields"]["generation_scores"], [9, None, 8, None, 7, None, 6, None, 5, None])
        self.assertEqual(assessment["native"]["summary"]["mean_distinct"], 5)
        self.assertEqual(len(seen), 6)
        self.assertEqual(portfolio, frozen)

        def replay(slot_id, role, request, **kwargs):
            self.assertEqual(saved[slot_id]["request_sha256"], digest(request))
            return saved[slot_id]

        self.assertEqual(self.native.assess(portfolio, replay), assessment)

    def test_every_order_gets_its_own_group_request(self):
        original = sample_portfolio()
        reordered = permute_portfolio(original, [f"r{i}" for i in reversed(range(10))],
                                       request_id="synthetic-rank", settings_sha256="0" * 64,
                                       procedure_sha256="1" * 64)
        groups = []

        def dispatch(slot_id, role, request, **kwargs):
            if role == "group":
                groups.append((slot_id, digest(request)))
            payload = {"groups": [list(range(10))]} if role == "group" else {"score": 7}
            return result_for(slot_id, role, request, payload)

        first = self.native.assess(original, dispatch)
        second = self.native.assess(reordered, dispatch)
        self.assertEqual(len(groups), 2)
        self.assertNotEqual(groups[0], groups[1])
        self.assertNotEqual(first["portfolio_sha256"], second["portfolio_sha256"])
        with self.assertRaises(ValueError):
            self.native.finalize(reordered, first["requests"][0], first["requests"][1:])

    def test_malformed_partition_is_unscored_without_quality_or_repair(self):
        for groups in (
            [[0, 0], list(range(1, 10))],
            [list(range(9))],
            [list(range(10)), [10]],
            [[], list(range(10))],
            [[True], list(range(1, 10))],
        ):
            seen = []

            def dispatch(slot_id, role, request, **kwargs):
                seen.append(role)
                return result_for(slot_id, role, request, {"groups": groups})

            with self.subTest(groups=groups):
                assessment = self.native.assess(sample_portfolio(), dispatch)
                self.assertEqual(assessment["status"], "invalid_group")
                self.assertIsNone(assessment["metrics"]["utility"])
                self.assertEqual(seen, ["group"])

    def test_out_of_range_quality_and_refusal_remain_unscored(self):
        for value in (0, 11, True, "9"):
            def dispatch(slot_id, role, request, **kwargs):
                payload = {"groups": [list(range(10))]} if role == "group" else {"score": value}
                return result_for(slot_id, role, request, payload)

            with self.subTest(value=value):
                result = self.native.assess(sample_portfolio(), dispatch)
                self.assertEqual(result["status"], "invalid_quality")
                self.assertIsNone(result["metrics"]["utility"])

        def refusal(slot_id, role, request, **kwargs):
            payload = {"groups": [list(range(10))]} if role == "group" else {"score": 7}
            result = result_for(slot_id, role, request, payload)
            if role == "quality":
                result["response"]["stop_reason"] = "refusal"
            return result

        result = self.native.assess(sample_portfolio(), refusal)
        self.assertEqual(result["status"], "quality_refused")
        self.assertIsNone(result["metrics"]["utility"])
        self.assertEqual(result["native"]["fields"]["unscored"], "judge_refusal")

    def test_structured_group_refusal_is_preserved_without_head_requests(self):
        seen = []

        def dispatch(slot_id, role, request, **kwargs):
            seen.append(role)
            result = result_for(slot_id, role, request, {})
            result["response"].update(text="", refusal="Synthetic declined judgment")
            return result

        result = self.native.assess(sample_portfolio(), dispatch)
        self.assertEqual(result["status"], "group_refused")
        self.assertIsNone(result["metrics"]["utility"])
        self.assertEqual(seen, ["group"])

    def test_synthetic_results_cannot_be_relabelled_as_a_live_assessment(self):
        synthetic = sample_portfolio()
        live = make_portfolio(
            synthetic["task"], synthetic["responses"], method="B", repeat=1,
            model={"requested": "claude-sonnet-5-5", "returned": "claude-sonnet-5-5"},
            settings_sha256="0" * 64, procedure_sha256="1" * 64,
            request_ids=synthetic["provenance"]["request_ids"], fixture=False,
            study_sha256="2" * 64,
        )

        def dispatch(slot_id, role, request, **kwargs):
            return result_for(slot_id, role, request, {"groups": [list(range(10))]})

        with self.assertRaises(ValueError):
            self.native.assess(live, dispatch)

    def test_result_request_mismatch_or_model_substitution_is_rejected(self):
        for mutation in (
            lambda r: r.update(request_sha256="f" * 64),
            lambda r: r.update(slot_id="another-slot"),
            lambda r: r.update(study_sha256="f" * 64),
            lambda r: r.update(fixture=False),
            lambda r: r["response"].update(model="a-different-model"),
        ):
            def dispatch(slot_id, role, request, **kwargs):
                result = result_for(slot_id, role, request, {"groups": [list(range(10))]})
                mutation(result)
                return result

            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.native.assess(sample_portfolio(), dispatch)


if __name__ == "__main__":
    unittest.main()
