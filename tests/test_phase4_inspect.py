"""Pure snapshot checks; actual Inspect roundtrip runs only in its passive image."""
from __future__ import annotations

import ast
import copy
import unittest
from pathlib import Path

from buddha2.artifacts import ContractError
from followups.phase4_cm1_v1 import inspect_export as e


def fixture_snapshot():
    usage = {"input_tokens": 2, "output_tokens": 3, "total_tokens": 6,
             "input_tokens_cache_write": 1, "input_tokens_cache_read": 0,
             "reasoning_tokens": None, "total_cost": 0.0001}
    case = {"id": "synthetic-01", "prompt": "SYNTHETIC task", "metrics": {
        "official": {"utility": 0.0, "distinct": 1}, "sensitivity": {"reverse": None, "rotate": None}},
        "outputs": {"fixed": ["SYNTHETIC answer"], "selected_native": None},
        "events": [{"timestamp": "2026-11-08T12:00:00Z", "source": "IMPORTED native interval",
                    "data": {"slot_id": "fixture.plan", "role": "plan", "requested_model": "claude-sonnet-5-5",
                             "status": "response", "spent_micro_usd": 100}}],
        "model_usage": {"claude-sonnet-5-5": usage}, "started_at": "2026-11-08T12:00:00Z",
        "completed_at": "2026-11-08T12:00:01Z"}
    missing = {"id": "synthetic-02", "prompt": "", "metrics": None, "outputs": None,
               "events": [], "model_usage": {}, "started_at": None, "completed_at": None}
    return {"kind": "phase4-cm1-snapshot-v1", "study_sha256": "a" * 64,
            "source_sha256": "b" * 64, "fixture": True, "status": "partial", "cases": [case, missing],
            "source_artifacts": [{"path": "runs/fixture/report.json", "sha256": "c" * 64}]}


class Phase4InspectTests(unittest.TestCase):
    def test_fixture_native_and_missing_case_metadata_are_accepted_without_mutation(self):
        payload = fixture_snapshot()
        before = copy.deepcopy(payload)
        e.validate_snapshot(payload)
        payload["fixture"] = False
        e.validate_snapshot(payload)
        payload["fixture"] = True
        self.assertEqual(payload, before)
        self.assertIsNone(payload["cases"][1]["outputs"])

    def test_invalid_identity_duplicate_case_naive_or_reversed_time_rejects(self):
        payload = fixture_snapshot()
        cases = [copy.deepcopy(payload) for _ in range(4)]
        cases[0]["source_sha256"] = "bad"
        cases[1]["cases"][1]["id"] = "synthetic-01"
        cases[2]["cases"][0]["started_at"] = "2026-11-08T12:00:00"
        cases[3]["cases"][0]["completed_at"] = "2026-11-08T11:00:00Z"
        for changed in cases:
            with self.subTest(changed=changed), self.assertRaises(ContractError):
                e.validate_snapshot(changed)

    def test_actual_info_event_shape_and_no_fabricated_model_event(self):
        payload = fixture_snapshot()
        table = e.audit_csv(payload)
        self.assertIn("2026-11-08T12:00:00Z", table)
        self.assertIn("fixture.plan", table)
        self.assertIn("requested_model", table.splitlines()[0])
        payload["cases"][0]["events"][0]["event"] = "model"
        with self.assertRaises(ContractError):
            e.validate_snapshot(payload)

    def test_usage_totals_nonfinite_values_and_bool_counters_reject(self):
        for key, value in (("total_tokens", 5), ("input_tokens", True), ("total_cost", float("nan"))):
            payload = fixture_snapshot()
            payload["cases"][0]["model_usage"]["claude-sonnet-5-5"][key] = value
            with self.subTest(key=key), self.assertRaises(ContractError):
                e.validate_snapshot(payload)

    def test_aggregate_known_usage_does_not_fill_unknown_optional_categories(self):
        payload = fixture_snapshot()
        extra = copy.deepcopy(payload["cases"][0])
        extra["model_usage"]["claude-sonnet-5-5"]["total_cost"] = None
        extra["model_usage"]["claude-sonnet-5-5"]["input_tokens_cache_write"] = None
        values = e.aggregate_usage([payload["cases"][0], extra])["claude-sonnet-5-5"]
        self.assertEqual(values["input_tokens"], 4)
        self.assertEqual(values["total_tokens"], 12)
        self.assertIsNone(values["total_cost"])
        self.assertIsNone(values["input_tokens_cache_write"])

    def test_no_provider_or_inspect_import_precedes_blocker(self):
        tree = ast.parse(Path(e.__file__).read_text(encoding="utf-8"))
        forbidden = {"anthropic", "openai", "harness2"}
        for node in ast.walk(tree):
            names = [v.name for v in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            self.assertFalse(any(name.split(".")[0] in forbidden for name in names))
        exporter = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "export_snapshot")
        blocker = next(node.lineno for node in ast.walk(exporter) if isinstance(node, ast.Call)
                       and isinstance(node.func, ast.Name) and node.func.id == "block_execution")
        inspect_imports = [node.lineno for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
                           and (node.module or "").startswith("inspect_ai")]
        self.assertTrue(inspect_imports and min(inspect_imports) > blocker)


if __name__ == "__main__":
    unittest.main()
