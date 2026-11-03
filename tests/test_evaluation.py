"""Boundary checks plus an opt-in test of the real pinned native arithmetic."""

import copy
import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from buddha2.evaluation import evaluate_mechanical, evaluate_native

ROOT = Path(__file__).resolve().parents[1]


def portfolio():
    return {
        "schema_version": 1,
        "fixture": True,
        "task": json.loads((ROOT / "fixtures" / "task.json").read_text(encoding="utf-8")),
        "responses": [
            {"id": f"r{i}", "text": text}
            for i, text in enumerate(json.loads((ROOT / "fixtures" / "responses.json").read_text(encoding="utf-8")))
        ],
        "provenance": {"mode": "offline-fixture"},
    }


def grading_for(output):
    evidence = json.loads((ROOT / "fixtures" / "grading.json").read_text(encoding="utf-8"))
    canonical = json.dumps(output, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    evidence["portfolio_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return evidence


class EvaluationBoundaryTests(unittest.TestCase):
    def test_mechanical_assessment_references_unchanged_saved_portfolio(self):
        output = portfolio()
        before = copy.deepcopy(output)
        result = evaluate_mechanical(output)
        self.assertEqual(result["metrics"]["response_count"], 10)
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(result["portfolio_sha256"], grading_for(output)["portfolio_sha256"])
        self.assertEqual(output, before)

    def test_duplicate_text_is_valid_but_duplicate_response_identity_is_rejected(self):
        output = portfolio()
        output["responses"][1]["text"] = output["responses"][0]["text"]
        self.assertTrue(evaluate_mechanical(output)["checks"]["unique_ids"])
        output["responses"][1]["id"] = output["responses"][0]["id"]
        with self.assertRaisesRegex(ValueError, "unique"):
            evaluate_mechanical(output)

    def test_nonfixture_and_malformed_outputs_refuse_before_dispatch(self):
        for mutate in (
            lambda x: x.update(fixture=False),
            lambda x: x["task"].update(fixture=False),
            lambda x: x.update(schema_version=True),
            lambda x: x["responses"].pop(),
            lambda x: x["responses"][0].update(text="  "),
            lambda x: x.update(provenance=[]),
        ):
            output = portfolio()
            mutate(output)
            with self.subTest(output=output), self.assertRaises(ValueError):
                evaluate_mechanical(output)

    def test_grading_is_bound_to_the_exact_portfolio_before_dispatch(self):
        output = portfolio()
        evidence = grading_for(output)
        output["responses"][0]["text"] += " changed"
        with self.assertRaisesRegex(ValueError, "portfolio"):
            evaluate_native(output, evidence, ROOT / "does-not-exist")

    def test_rebinding_cannot_apply_frozen_grading_to_another_task_or_text(self):
        for mutate in (
            lambda x: x["task"].update(prompt="A different question"),
            lambda x: x["responses"][0].update(text="An arbitrary compatible answer"),
            lambda x: x["responses"].reverse(),
        ):
            output = portfolio()
            mutate(output)
            evidence = grading_for(output)  # Deliberately rebind a valid full-output hash.
            self.assertTrue(evaluate_mechanical(output)["checks"]["schema"])
            with self.subTest(output=output), self.assertRaisesRegex(ValueError, "fixture"):
                evaluate_native(output, evidence, ROOT / "does-not-exist")

    def test_rebinding_cannot_change_the_frozen_grading_profile(self):
        mutations = (
            lambda x: x["head_scores"].__setitem__(0, 1),
            lambda x: x.update(task_sha256="0" * 64),
            lambda x: x.update(response_texts_sha256="0" * 64),
        )
        for mutate in mutations:
            output = portfolio()
            evidence = grading_for(output)
            mutate(evidence)
            with self.subTest(evidence=evidence), self.assertRaisesRegex(ValueError, "fixture"):
                evaluate_native(output, evidence, ROOT / "does-not-exist")

    def test_incompatible_missing_or_invalid_grading_refuses_before_dispatch(self):
        mutations = (
            lambda x: x.pop("portfolio_sha256"),
            lambda x: x.update(task_id="another-task"),
            lambda x: x.update(version="1.0"),
            lambda x: x.update(patience=float("nan")),
            lambda x: x.update(patience=0.9),
            lambda x: x["partition"].pop(),
            lambda x: x["partition"].__setitem__(0, True),
            lambda x: x["head_scores"].__setitem__(0, None),
            lambda x: x["head_scores"].__setitem__(0, 11),
            lambda x: x["head_scores"].__setitem__(1, 7),
        )
        for mutate in mutations:
            output = portfolio()
            evidence = grading_for(output)
            mutate(evidence)
            with self.subTest(evidence=evidence), self.assertRaises(ValueError):
                evaluate_native(output, evidence, ROOT / "does-not-exist")

    def test_worker_revalidates_request_before_importing_native_dependencies(self):
        output = portfolio()
        evidence = grading_for(output)
        output["fixture"] = False
        completed = subprocess.run(
            [sys.executable, "-B", str(ROOT / "src" / "buddha2" / "nb_worker.py"), str(ROOT / "does-not-exist")],
            input=json.dumps({"portfolio": output, "grading": evidence}),
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertIn("ValueError", completed.stderr)
        self.assertNotIn("ModuleNotFoundError", completed.stderr)

    def test_worker_refuses_rebound_arbitrary_text_before_native_imports(self):
        output = portfolio()
        output["responses"][0]["text"] = "An arbitrary compatible answer"
        evidence = grading_for(output)
        completed = subprocess.run(
            [sys.executable, "-B", str(ROOT / "src" / "buddha2" / "nb_worker.py"), str(ROOT / "does-not-exist")],
            input=json.dumps({"portfolio": output, "grading": evidence}),
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("ValueError", completed.stderr)
        self.assertNotIn("FileNotFoundError", completed.stderr)
        self.assertEqual(completed.stdout, "")


@unittest.skipUnless(os.getenv("BUDDHA2_NB_UPSTREAM"), "set BUDDHA2_NB_UPSTREAM in the offline container")
class NativeIntegrationTests(unittest.TestCase):
    def test_native_loader_arithmetic_and_summary_match_independent_oracle(self):
        output = portfolio()
        before = copy.deepcopy(output)
        result = evaluate_native(output, grading_for(output), Path(os.environ["BUDDHA2_NB_UPSTREAM"]))
        # Frozen decimal oracle derived independently from weighted first-occurrence credit.
        self.assertEqual(result["metrics"]["distinct"], 5)
        self.assertAlmostEqual(result["metrics"]["utility"], 4.346485261239209, places=12)
        self.assertEqual(result["native"]["fields"]["partition_scores"], [9, 8, 7, 6, 5])
        self.assertEqual(result["native"]["summary"]["version"], "1.1")
        self.assertEqual(result["native"]["summary"]["mean_distinct"], 5)
        self.assertAlmostEqual(result["native"]["summary"]["mean_utility"], 4.346485261239209, places=12)
        self.assertEqual(result["native"]["generation_row"]["generations"], [r["text"] for r in output["responses"]])
        self.assertEqual(result["native"]["generation_row"]["id"], output["task"]["id"])
        for source in result["native"]["imports"].values():
            self.assertTrue(Path(source["path"]).is_relative_to(Path(os.environ["BUDDHA2_NB_UPSTREAM"]).resolve()))
            self.assertEqual(len(source["sha256"]), 64)
        self.assertEqual(output, before)


if __name__ == "__main__":
    unittest.main()
