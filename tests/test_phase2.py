"""Phase 2 preparation: frozen selection, procedures and honest denominators."""

import copy
import unittest

from buddha2.artifacts import ContractError, digest
from buddha2.phase2 import (
    analyze,
    make_worklist,
    parse_angles,
    parse_order,
    render_request,
    select_tasks,
    slot_coverage,
)
from buddha2.phase2_contracts import slot_prefix


class PreparationTests(unittest.TestCase):
    def rows(self):
        return [{"id": str(i), "category": "creative", "prompt": f"Suggest a name for room {i}.",
                 "prompt_paraphrases": []} for i in range(15)]

    def test_selection_is_input_order_independent_excludes_aliases_and_deduplicates(self):
        rows = self.rows()
        rows += [dict(rows[0], id="alias", prompt="  SUGGEST A NAME FOR ROOM 0. ")]
        excluded = {digest("suggest a name for room 1.")}
        a = select_tasks(rows, "a" * 64, excluded)
        b = select_tasks(list(reversed(rows)), "a" * 64, excluded)
        self.assertEqual(a, b)
        self.assertEqual(len(a["tasks"]), 12)
        self.assertNotIn("suggest a name for room 1.",
                         [x["prompt"].casefold() for x in a["tasks"]])
        self.assertEqual(a["duplicate_aliases"], 1)
        self.assertEqual(len({x["id"] for x in a["tasks"]}), 12)

    def test_shortfall_and_bad_source_fail_before_allocation(self):
        with self.assertRaises(ContractError):
            select_tasks(self.rows()[:11], "a" * 64, set())
        rows = self.rows()
        rows[0]["id"] = True
        with self.assertRaises(ContractError):
            select_tasks(rows, "a" * 64, set())

    def test_worklist_freezes_1320_slots_55_canary_and_no_hidden_requests(self):
        tasks = select_tasks(self.rows(), "a" * 64, set())["tasks"]
        work = make_worklist(tasks)
        self.assertEqual(len(work["blocks"]), 24)
        self.assertEqual(len(work["slots"]), 1320)
        self.assertEqual(sum(v["checkpoint"] == "canary" for v in work["slots"].values()), 55)
        self.assertEqual(sum(v["role"] == "answer" for v in work["slots"].values()), 480)
        self.assertEqual(sum(v["role"] == "quality" for v in work["slots"].values()), 720)
        self.assertEqual([b["generation_order"] for b in work["blocks"][:2]],
                         [["A", "B"], ["B", "A"]])

    def test_angles_and_permutation_reject_extra_or_duplicate_members(self):
        angles = {"angles": [{"id": f"angle-{i:02d}", "angle": f"Content axis {i}"}
                             for i in range(1, 11)]}
        self.assertEqual(len(parse_angles(angles)), 10)
        broken = copy.deepcopy(angles)
        broken["angles"][1]["angle"] = "  CONTENT AXIS 1 "
        with self.assertRaises(ContractError):
            parse_angles(broken)
        with self.assertRaises(ContractError):
            parse_order({"order": ["x"] * 10}, [str(i) for i in range(10)])

    def test_plain_and_planned_requests_keep_original_task_and_fresh_context(self):
        task = select_tasks(self.rows(), "a" * 64, set())["tasks"][0]
        plain = render_request("answer", task)
        planned = render_request("answer", task, angle={"id": "angle-01", "angle": "A moon"})
        self.assertEqual(plain["system"], planned["system"])
        self.assertEqual(plain["messages"], [{"role": "user", "content": task["prompt"]}])
        self.assertEqual(len(planned["messages"]), 1)
        self.assertIn(task["prompt"], planned["messages"][0]["content"])
        self.assertNotIn("previous answers", planned["messages"][0]["content"])
        self.assertEqual(plain["max_tokens"], 4096)
        self.assertEqual(plain["output_config"], {"effort": "low"})

    def test_analysis_counts_prompts_not_responses_and_refuses_missing_coverage(self):
        tasks = select_tasks(self.rows(), "a" * 64, set())["tasks"]
        study = {"tasks": tasks, "human_check": {"task_ids": [t["id"] for t in tasks[:2]],
                                                "repeat": 1}}
        assessments = []
        for t in tasks:
            for repeat in (1, 2):
                for method, value in (("A", 2), ("B", 3), ("C", 3)):
                    assessments.append({"task_id": t["id"], "repeat": repeat, "method": method,
                                        "status": "ok", "fixture": True,
                                        "metrics": {"utility": value, "distinct": 5},
                                        "order_id": slot_prefix(t["id"], method, repeat)})
        human = [{"reader_id": reader, "task_id": t["id"], "repeat": 1, "method": method,
                  "fixture": True, "status": "acceptable", "reason": "Synthetic check"}
                 for reader in ("fixture-R1", "fixture-R2") for t in tasks[:2]
                 for method in ("A", "B", "C")]
        result = analyze(study, assessments, human, {"A": 10, "B": 20, "C": 21}, fixture=True)
        self.assertEqual(result["independent_prompts"], 12)
        self.assertEqual(result["contrasts"], {"B_minus_A": 1.0, "C_minus_B": 0.0})
        self.assertEqual(result["synthetic_selected_method"], "B")
        self.assertIsNone(result["selected_method"])
        ambiguous = copy.deepcopy(human)
        ambiguous[0]["status"] = "cannot judge"
        self.assertIsNone(analyze(study, assessments, ambiguous,
                                 {"A": 10, "B": 20, "C": 21}, fixture=True)["synthetic_selected_method"])
        self.assertIn("B_minus_A", result["paired_prompt_means"][0])
        self.assertIn("utility_range", result)
        self.assertIn("mean_distinct", result)
        result = analyze(study, assessments[:-1], human, {"A": 10, "B": 20, "C": 21}, fixture=True)
        self.assertEqual(result["status"], "inconclusive")
        with self.assertRaises(ContractError):
            analyze(study, assessments + [assessments[0]], human, {}, fixture=True)

    def test_invalid_plan_accounts_for_all_skipped_dependents_without_replacement(self):
        tasks = select_tasks(self.rows(), "a" * 64, set())["tasks"]
        study = {"tasks": tasks, "worklist": make_worklist(tasks)}
        prefix = slot_prefix(tasks[0]["id"], "B", 1)
        results = {prefix + ".plan": {"status": "response", "response": {
            "text": "{}", "stop_reason": "end_turn"}}}
        coverage = slot_coverage(study, results, [], [])
        self.assertEqual(len(coverage["slots"]), 1320)
        self.assertEqual(coverage["slots"][prefix + ".answer.00"], "skipped_invalid_plan")
        cp = slot_prefix(tasks[0]["id"], "C", 1)
        self.assertEqual(coverage["slots"][cp + ".rank"], "skipped_invalid_plan")
        self.assertEqual(coverage["orders"][prefix], "invalid_plan")


if __name__ == "__main__":
    unittest.main()
