"""Integration checks for the native Harness² offline fixture boundary."""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness2.core.proposer import ProposerError
from harness2.core.spec import ChannelSpec

from buddha2.engine import (
    FIXTURE_TASK,
    FixtureEngineError,
    _FixtureAdapter,
    _FixtureProposer,
    run_fixture,
)

STRATEGY = Path(__file__).resolve().parents[1] / "strategies" / "planner"


@unittest.skipUnless(os.name == "posix", "Native Harness² scheduler requires POSIX fcntl")
class NativeEngineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="buddha2-engine-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def run_engine(self, destination=None, strategy=None):
        return run_fixture(destination or self.root / "run", strategy or STRATEGY, dict(FIXTURE_TASK))

    def test_native_control_flow_and_materialized_harness_change_outputs(self):
        with patch("harness2.core.proposer.Proposer.call", side_effect=AssertionError("provider path")):
            result = self.run_engine()

        self.assertTrue(result["fixture"])
        self.assertEqual(result["provider_calls"], 0)
        self.assertEqual(result["execution_count"], 4)
        self.assertEqual(result["proposer_calls"], ["inv1.a1", "dom1.a1", "agg1.a1"])
        self.assertEqual(result["selected_label"], "agg1")
        self.assertEqual(len(result["generations"]), 10)
        self.assertEqual(len(set(result["generations"])), 10)
        selected = Path(result["selected_run_dir"])
        self.assertTrue(selected.is_absolute())
        self.assertTrue(Path(result["selected_harness_dir"]).is_dir())
        portfolios = list((self.root / "run" / "executions").rglob("portfolio.json"))
        self.assertEqual(len(portfolios), 4)
        base_path = next(path for path in portfolios if path.parent.name == "base1")
        base = json.loads(base_path.read_text())["generations"]
        self.assertEqual(len(set(base)), 1)
        self.assertNotEqual(base, result["generations"])
        materialization = json.loads((selected / "materialization.json").read_text())
        self.assertTrue(materialization["materialized_sha256"]["guardrails.md"])
        self.assertTrue(materialization["native_source_fingerprint"])
        self.assertEqual(materialization["fixture"], True)
        for trace in result["trace_paths"]:
            self.assertTrue(Path(trace).is_file(), trace)
        summary_path = next((self.root / "run" / "adapt").rglob("summary.json"))
        summary = json.loads(summary_path.read_text())
        self.assertTrue(summary["selections"]["agg"]["trivial"])
        self.assertEqual(summary["modes"]["agg"]["ledger"]["R"], 4)
        self.assertEqual(summary["modes"]["agg"]["ledger"]["P"], 3)

    def test_same_run_label_changes_only_when_materialized_policy_changes(self):
        strategy = self.root / "changed-strategy"
        shutil.copytree(STRATEGY, strategy)
        guardrails = strategy / "guardrails.md"
        guardrails.write_text(guardrails.read_text().replace(
            "<!-- fixture-angle-policy: repeated -->", "<!-- fixture-angle-policy: distinct -->"
        ))
        first = _FixtureAdapter(self.root / "first", STRATEGY, dict(FIXTURE_TASK))
        changed = _FixtureAdapter(self.root / "changed", strategy, dict(FIXTURE_TASK))
        first_run = first.execute(FIXTURE_TASK["id"], STRATEGY, "same-label")
        changed_run = changed.execute(FIXTURE_TASK["id"], strategy, "same-label")
        first_portfolio = json.loads((first_run / "portfolio.json").read_text())
        changed_portfolio = json.loads((changed_run / "portfolio.json").read_text())
        self.assertEqual(first_portfolio["task"], changed_portfolio["task"])
        self.assertEqual(len(set(first_portfolio["generations"])), 1)
        self.assertEqual(len(set(changed_portfolio["generations"])), 10)
        with self.assertRaisesRegex(FixtureEngineError, "different effective harness"):
            first.execute(FIXTURE_TASK["id"], strategy, "same-label")

    def test_resume_preserves_selected_output_without_duplicate_execution(self):
        first = self.run_engine()
        second = self.run_engine()
        self.assertEqual(first["selected_run_dir"], second["selected_run_dir"])
        self.assertEqual(first["generations"], second["generations"])
        self.assertEqual(second["execution_count"], 0)
        self.assertEqual(second["proposer_calls"], [])
        self.assertEqual(len(list((self.root / "run" / "executions").rglob("portfolio.json"))), 4)

    def test_prompt_edit_changes_identity_and_cannot_reuse_existing_run(self):
        strategy = self.root / "strategy"
        shutil.copytree(STRATEGY, strategy)
        self.run_engine(strategy=strategy)
        source = strategy / "systemprompt.md"
        source.write_text(source.read_text() + "\nPreserve clear, direct wording.\n")
        with self.assertRaisesRegex(ValueError, "different effective inputs"):
            self.run_engine(strategy=strategy)
        changed = self.run_engine(destination=self.root / "new-run", strategy=strategy)
        self.assertEqual(changed["execution_count"], 4)

    def test_nonfixture_and_unrelated_tasks_refuse_before_dispatch(self):
        for change in ({"fixture": False}, {"prompt": "An unrelated real request"}, {"id": "../escape"}):
            with self.subTest(change=change), patch("subprocess.run") as launch:
                with self.assertRaisesRegex(ValueError, "exact declared fixture"):
                    run_fixture(self.root / "rejected", STRATEGY, dict(FIXTURE_TASK) | change)
                launch.assert_not_called()

    def test_unexpected_editor_label_never_falls_through_to_provider(self):
        proposer = _FixtureProposer(ChannelSpec("opencode", "local/deterministic"), audit_dir=self.root)
        with patch("harness2.core.proposer.Proposer.call") as provider:
            with self.assertRaisesRegex(ProposerError, "Unexpected fixture label"):
                proposer.call("", self.root, "select.agg1")
            provider.assert_not_called()

    def test_modified_executable_helper_is_rejected_before_dispatch(self):
        strategy = self.root / "strategy"
        shutil.copytree(STRATEGY, strategy)
        helper = strategy / "scripts" / "fixture_portfolio.py"
        helper.write_text(helper.read_text() + "\nraise RuntimeError('changed helper')\n")
        with patch("subprocess.run") as launch:
            with self.assertRaisesRegex(ValueError, "known fixture helper"):
                self.run_engine(strategy=strategy)
            launch.assert_not_called()

    def test_missing_and_non_utf8_strategy_inputs_refuse_before_dispatch(self):
        for malformed in ("missing", "non-utf8"):
            with self.subTest(malformed=malformed):
                strategy = self.root / malformed
                shutil.copytree(STRATEGY, strategy)
                if malformed == "missing":
                    (strategy / "guardrails.md").unlink()
                else:
                    (strategy / "systemprompt.md").write_bytes(b"planner\xff")
                with patch("subprocess.run") as launch:
                    with self.assertRaises(ValueError):
                        self.run_engine(strategy=strategy)
                    launch.assert_not_called()

    def test_corrupted_selected_output_cannot_be_silently_resumed(self):
        first = self.run_engine()
        portfolio = Path(first["selected_run_dir"]) / "portfolio.json"
        portfolio.write_text("{}")
        with self.assertRaises(FixtureEngineError):
            self.run_engine()


if __name__ == "__main__":
    unittest.main()
