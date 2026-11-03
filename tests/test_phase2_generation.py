"""Fault checks on complete fixed procedures; no SDK or model is involved."""

import copy
import json
import unittest
from pathlib import Path

from buddha2.artifacts import ContractError, digest, read_json
from buddha2.phase2 import generate_order, rank_order
from buddha2.phase2_contracts import make_portfolio

TASK = {"id": "generation-boundary", "prompt": "Suggest a useful reading-room design.",
        "domain": "synthetic", "source_context": {"dataset": "synthetic", "revision": "0" * 40,
         "source_sha256": "1" * 64, "source_task_id": "generation-boundary"}}
STUDY = {"study_sha256": "2" * 64, "tasks": [TASK],
         "templates": read_json(Path(__file__).resolve().parents[1] / "strategies/fixed/phase2.json"),
         "shared_generator_settings_sha256": "3" * 64,
         "procedure_hashes": {"A": "4" * 64, "B": "5" * 64, "C": "6" * 64}}


class ScriptedDispatch:
    def __init__(self, mutate=None, fixture=True):
        self.calls, self.mutate, self.fixture = [], mutate, fixture

    def __call__(self, slot_id, role, request, *, checkpoint):
        self.calls.append((slot_id, role, copy.deepcopy(request), checkpoint))
        if role == "plan":
            text = json.dumps({"angles": [{"id": f"angle-{i:02d}", "angle": f"direction-{i}"}
                                          for i in range(1, 11)]})
        elif role == "rank":
            supplied = json.loads(request["messages"][0]["content"])
            text = json.dumps({"order": [row["id"] for row in reversed(supplied["responses"])]})
        else:
            text = "answer-" + slot_id.rsplit(".", 1)[-1]
        result = {"slot_id": slot_id, "role": role, "request_sha256": digest(request),
                  "dispatch_id": "fixture-" + slot_id, "status": "response",
                  "study_sha256": STUDY["study_sha256"], "fixture": self.fixture,
                  "spent_micro_usd": 1, "reserved_micro_usd": 0,
                  "response": {"model": request["model"], "text": text, "stop_reason": "end_turn",
                               "usage": {"input_tokens": 1, "output_tokens": 1}}}
        if self.mutate is not None:
            self.mutate(result, len(self.calls))
        return result


class GenerationBoundaryTests(unittest.TestCase):
    def generate(self, method="A", dispatch=None, fixture=True):
        return generate_order(STUDY, TASK, 1, method, dispatch or ScriptedDispatch(fixture=fixture),
                              checkpoint="canary", fixture=fixture)

    def test_a_has_ten_fresh_identical_task_only_requests_in_index_order(self):
        dispatch = ScriptedDispatch()
        portfolio = self.generate(dispatch=dispatch)
        self.assertEqual(len(dispatch.calls), 10)
        self.assertEqual({call[1] for call in dispatch.calls}, {"answer"})
        self.assertTrue(all(call[2]["messages"] == [{"role": "user", "content": TASK["prompt"]}]
                            for call in dispatch.calls))
        self.assertEqual([row["text"] for row in portfolio["responses"]],
                         [f"answer-{i:02d}" for i in range(10)])
        self.assertEqual(len({call[0] for call in dispatch.calls}), 10)

    def test_b_has_one_plan_and_only_the_assigned_angle_per_fresh_answer(self):
        dispatch = ScriptedDispatch()
        portfolio = self.generate("B", dispatch)
        self.assertEqual([call[1] for call in dispatch.calls], ["plan"] + ["answer"] * 10)
        self.assertEqual(len(portfolio["provenance"]["request_ids"]), 11)
        for index, call in enumerate(dispatch.calls[1:], 1):
            content = call[2]["messages"][0]["content"]
            self.assertTrue(content.startswith(TASK["prompt"]))
            angle = json.loads(content.split("\n")[-1])
            self.assertEqual(angle, {"id": f"angle-{index:02d}", "angle": f"direction-{index}"})
            self.assertNotIn("answer-", content)
            self.assertEqual(len(call[2]["messages"]), 1)

    def test_each_identity_mismatch_stops_before_a_second_call(self):
        mutations = {
            "slot": lambda row: row.update(slot_id="wrong-slot"),
            "role": lambda row: row.update(role="quality"),
            "request": lambda row: row.update(request_sha256="f" * 64),
            "study": lambda row: row.update(study_sha256="f" * 64),
            "fixture": lambda row: row.update(fixture=False),
            "model": lambda row: row["response"].update(model="substitute-model"),
            "usage": lambda row: row["response"].pop("usage"),
            "dispatch": lambda row: row.pop("dispatch_id"),
            "accounting": lambda row: row.update(spent_micro_usd=None),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                dispatch = ScriptedDispatch(lambda row, _: mutate(row))
                with self.assertRaises(ContractError):
                    self.generate(dispatch=dispatch)
                self.assertEqual(len(dispatch.calls), 1)

    def test_unexpected_tool_pause_or_stop_sequence_is_not_a_success(self):
        for stop in ("tool_use", "pause_turn", "stop_sequence", None):
            with self.subTest(stop=stop):
                dispatch = ScriptedDispatch(lambda row, _: row["response"].update(stop_reason=stop))
                with self.assertRaises(ContractError):
                    self.generate(dispatch=dispatch)
                self.assertEqual(len(dispatch.calls), 1)

    def test_declared_failure_outcomes_are_preserved_without_replacement(self):
        outcomes = {1: {"stop_reason": "refusal", "text": "declined"},
                    2: {"stop_reason": "max_tokens", "text": ""},
                    3: {"stop_reason": "end_turn", "text": "  "}}
        dispatch = ScriptedDispatch(lambda row, index: row["response"].update(outcomes.get(index, {})))
        portfolio = self.generate(dispatch=dispatch)
        self.assertEqual(len(dispatch.calls), 10)
        self.assertEqual([row["status"] for row in portfolio["responses"][:3]],
                         ["refused", "truncated", "empty"])
        self.assertTrue(all(row["text"].strip() for row in portfolio["responses"]))

    def test_invalid_plan_stops_after_its_one_counted_request(self):
        dispatch = ScriptedDispatch(lambda row, _: row["response"].update(text="{}"))
        with self.assertRaises(ContractError):
            self.generate("B", dispatch)
        self.assertEqual(len(dispatch.calls), 1)

    def test_changed_plan_or_answer_actual_model_stops_immediately(self):
        for method in ("A", "B"):
            with self.subTest(method=method):
                dispatch = ScriptedDispatch(lambda row, index: row["response"].update(
                    model=row["response"]["model"] + "-20261025" if index == 1 else row["response"]["model"]))
                with self.assertRaises(ContractError):
                    self.generate(method, dispatch)
                self.assertEqual(len(dispatch.calls), 2)

    def test_unknown_task_is_rejected_before_dispatch(self):
        dispatch = ScriptedDispatch()
        with self.assertRaises(ContractError):
            generate_order(STUDY, TASK | {"prompt": "altered prompt"}, 1, "A", dispatch,
                           checkpoint="canary", fixture=True)
        self.assertEqual(dispatch.calls, [])

    def test_c_is_only_one_rank_call_and_preserves_exact_parent_rows(self):
        parent = self.generate("B")
        dispatch = ScriptedDispatch()
        child = rank_order(STUDY, parent, dispatch, checkpoint="canary")
        self.assertEqual(len(dispatch.calls), 1)
        self.assertEqual(dispatch.calls[0][1], "rank")
        self.assertEqual(child["responses"], list(reversed(parent["responses"])))
        self.assertEqual(child["provenance"]["parent_sha256"], digest(parent))
        self.assertEqual(child["provenance"]["study_sha256"], parent["provenance"]["study_sha256"])

    def test_invalid_or_foreign_parent_rejected_before_rank_dispatch(self):
        good = self.generate("B")
        variants = [self.generate("A")]
        for field, value in (("study_sha256", "f" * 64), ("settings_sha256", "f" * 64),
                             ("procedure_sha256", "f" * 64)):
            provenance = good["provenance"] | {field: value}
            variants.append(make_portfolio(good["task"], good["responses"], fixture=True,
                                            **provenance))
        variants.append(make_portfolio(TASK | {"prompt": "altered"}, good["responses"],
                                       fixture=True, **good["provenance"]))
        for parent in variants:
            with self.subTest(parent=parent["portfolio_id"]):
                dispatch = ScriptedDispatch()
                with self.assertRaises(ContractError):
                    rank_order(STUDY, parent, dispatch, checkpoint="canary")
                self.assertEqual(dispatch.calls, [])

    def test_live_ranker_must_match_its_parent_actual_model(self):
        parent = self.generate("B", ScriptedDispatch(fixture=False), fixture=False)
        dispatch = ScriptedDispatch(lambda row, _: row["response"].update(
            model=row["response"]["model"] + "-20261025"), fixture=False)
        with self.assertRaises(ContractError):
            rank_order(STUDY, parent, dispatch, checkpoint="canary")
        self.assertEqual(len(dispatch.calls), 1)

    def test_invalid_parent_returned_model_rejected_before_rank_dispatch(self):
        good = self.generate("B", ScriptedDispatch(fixture=False), fixture=False)
        provenance = good["provenance"] | {"model": {
            "requested": "claude-sonnet-5-5", "returned": "substituted-model"}}
        parent = make_portfolio(good["task"], good["responses"], fixture=False, **provenance)
        dispatch = ScriptedDispatch(fixture=False)
        with self.assertRaises(ContractError):
            rank_order(STUDY, parent, dispatch, checkpoint="canary")
        self.assertEqual(dispatch.calls, [])

    def test_rank_failure_or_repeated_id_never_generates_replacements(self):
        parent = self.generate("B")
        variants = ({"text": json.dumps({"order": [parent["responses"][0]["id"]] * 10})},
                    {"stop_reason": "refusal"}, {"stop_reason": "max_tokens"})
        for variant in variants:
            with self.subTest(variant=variant):
                dispatch = ScriptedDispatch(lambda row, _: row["response"].update(variant))
                with self.assertRaises(ContractError):
                    rank_order(STUDY, parent, dispatch, checkpoint="canary")
                self.assertEqual(len(dispatch.calls), 1)


if __name__ == "__main__":
    unittest.main()
