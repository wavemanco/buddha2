"""Every frozen request/order retains a status after failures or partial work."""

import unittest

from buddha2.artifacts import ContractError, digest
from buddha2.phase2_coverage import slot_coverage


class CoverageTests(unittest.TestCase):
    def setUp(self):
        from buddha2.phase2 import make_worklist, select_tasks

        rows = [{"id": str(i), "category": "creative", "prompt": f"Suggest a name {i}.",
                 "prompt_paraphrases": []} for i in range(12)]
        self.tasks = select_tasks(rows, "a" * 64, set())["tasks"]
        self.study = {"tasks": self.tasks, "worklist": make_worklist(self.tasks)}

    def prefix(self, method="B"):
        from buddha2.phase2_contracts import slot_prefix

        return slot_prefix(self.tasks[0]["id"], method, 1)

    @staticmethod
    def response(text, stop="end_turn"):
        return {"status": "response", "response": {"text": text, "stop_reason": stop}}

    def test_no_observation_retains_all_frozen_denominators(self):
        result = slot_coverage(self.study, {}, [], [])
        self.assertEqual(len(result["slots"]), 1320)
        self.assertEqual(len(result["orders"]), 72)
        self.assertEqual(result["slot_status_counts"], {"not_attempted": 1320})
        self.assertEqual(result["order_status_counts"], {"not_attempted": 72})

    def test_invalid_or_refused_or_truncated_plan_skips_every_dependent(self):
        for raw in (self.response("{}"), self.response("declined", "refusal"),
                    self.response('{"angles":[]}', "max_tokens")):
            with self.subTest(raw=raw):
                prefix, cp = self.prefix(), self.prefix("C")
                result = slot_coverage(self.study, {prefix + ".plan": raw}, [], [])
                self.assertEqual(result["orders"][prefix], "invalid_plan")
                self.assertEqual(result["orders"][cp], "invalid_plan")
                self.assertEqual(result["slots"][prefix + ".answer.00"], "skipped_invalid_plan")
                self.assertEqual(result["slots"][prefix + ".group"], "skipped_invalid_plan")
                self.assertEqual(result["slots"][cp + ".rank"], "skipped_invalid_plan")
                self.assertEqual(result["slots"][cp + ".quality.09"], "skipped_invalid_plan")
                self.assertEqual(sum(result["slot_status_counts"].values()), 1320)

    def test_unknown_liability_and_partial_answer_outcomes_stay_visible(self):
        a, b = self.prefix("A"), self.prefix("B")
        results = {
            a + ".answer.00": self.response("declined", "refusal"),
            a + ".answer.01": self.response(""),
            a + ".answer.02": self.response("unfinished", "max_tokens"),
            a + ".answer.03": {"status": "unknown", "response": None},
            b + ".plan": {"status": "unknown", "response": None},
        }
        result = slot_coverage(self.study, results, [], [])
        self.assertEqual(result["slots"][a + ".answer.00"], "refused")
        self.assertEqual(result["slots"][a + ".answer.01"], "empty")
        self.assertEqual(result["slots"][a + ".answer.02"], "truncated")
        self.assertEqual(result["slots"][a + ".answer.03"], "unknown_liability")
        self.assertEqual(result["orders"][b], "unresolved_plan")
        self.assertEqual(len(result["unknown_liability_slots"]), 2)
        self.assertEqual(result["slots"][a + ".answer.04"], "not_attempted")

    def test_downstream_dispatch_after_invalid_plan_is_a_contract_violation(self):
        prefix = self.prefix()
        with self.assertRaises(ContractError):
            slot_coverage(self.study, {prefix + ".plan": self.response("{}"),
                                      prefix + ".answer.00": self.response("an answer")}, [], [])

    def test_nonhead_quality_is_not_missing_and_bad_rank_skips_only_c(self):
        import json

        from buddha2.phase2_contracts import make_portfolio

        prefix = self.prefix()
        answer_slots = [f"{prefix}.answer.{i:02d}" for i in range(10)]
        plan = {"angles": [{"id": f"angle-{i:02d}", "angle": f"Direction {i}"}
                           for i in range(1, 11)]}
        results = {prefix + ".plan": self.response(json.dumps(plan))}
        results.update({slot: self.response(f"Answer {i}") for i, slot in enumerate(answer_slots)})
        results[prefix + ".group"] = self.response(json.dumps({"groups": [list(range(10))]}), "stop")
        results[prefix + ".quality.00"] = self.response('{"score":7}')
        cp = self.prefix("C")
        results[cp + ".rank"] = self.response('{"order":["missing"]}')
        portfolio = make_portfolio(
            self.tasks[0], [{"id": f"r{i}", "text": f"Answer {i}", "status": "ok", "request_id": slot}
                            for i, slot in enumerate(answer_slots)], method="B", repeat=1,
            model={"requested": "fixture-no-model", "returned": "fixture-no-model"},
            settings_sha256="0" * 64, procedure_sha256="1" * 64,
            request_ids=[prefix + ".plan", *answer_slots], study_sha256="2" * 64, fixture=True,
        )
        assessment = {"task_id": self.tasks[0]["id"], "method": "B", "repeat": 1,
                      "order_id": prefix, "portfolio_sha256": digest(portfolio),
                      "status": "scored", "fixture": True}
        result = slot_coverage(self.study, results, [portfolio], [assessment])
        self.assertEqual(result["slots"][prefix + ".quality.09"], "not_needed_nonhead")
        self.assertEqual(result["orders"][prefix], "scored")
        self.assertEqual(result["orders"][cp], "invalid_rank")
        self.assertEqual(result["slots"][cp + ".group"], "skipped_invalid_rank")
        results[prefix + ".quality.01"] = self.response('{"score":8}')
        with self.assertRaises(ContractError):
            slot_coverage(self.study, results, [portfolio], [assessment])


if __name__ == "__main__":
    unittest.main()
