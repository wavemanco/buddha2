"""Actual pinned selector behavior for missing and invalid candidates; zero SDK calls."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from harness2.core import selection
from harness2.core.proposer import Proposer, Reply
from harness2.core.spec import BenchSpec, ChannelSpec, RunView

from buddha2.artifacts import ContractError

from . import contract, editor, native
from .support import BASE


class SelectorAdapter:
    def __init__(self, root: Path, delivered: set[str]):
        self.spec = BenchSpec(name="seq2-selector-component", runs_root=root,
            install_mode="workspace_config", channels={"proposer": ChannelSpec("opencode", "anthropic/claude-opus-5"),
                "selector": ChannelSpec("opencode", "anthropic/claude-opus-5")}, prompts=contract.benchmark_prompts())
        self._delivered = delivered

    def delivered(self, run_dir):
        return Path(run_dir).name in self._delivered

    def deliverable_text(self, run_dir):
        return "Complete synthetic candidate " + Path(run_dir).name

    def task_prompt(self, task_id):
        return "Synthetic component request only."


class ChoiceProposer(Proposer):
    def __init__(self, chosen: str):
        super().__init__(ChannelSpec("opencode", "anthropic/claude-opus-5", effort="high", steps=24, timeout=600), attempts=1)
        self.chosen, self.calls = chosen, 0

    def call(self, mission, context_dir=None, label="", **kwargs):
        self.calls += 1
        prepared = contract.prepare_selector_contract(mission, Path(context_dir), label)
        assert prepared["manifest"]["role"] == "SELECT"
        return Reply(label=label, text="<why>Synthetic only</why>\n```choice\n" + self.chosen + "\n```", ok=True)


class SelectorS2Tests(unittest.TestCase):
    def test_selector_snapshot_accepts_only_explicit_owned_native_context(self):
        with tempfile.TemporaryDirectory(prefix="harness2-prop-") as temporary:
            root = Path(temporary)
            context = root / "context"
            (context / "candidates").mkdir(parents=True)
            files = {"task.md": "synthetic task", "candidates/A.md": "complete candidate"}
            for name, text in files.items():
                (context / name).write_text(text, encoding="utf-8")
            inventory = {name: {"bytes": len(text.encode()), "sha256": hashlib.sha256(text.encode()).hexdigest()}
                         for name, text in files.items()}
            (context / "C1_MANIFEST.json").write_text(json.dumps({"role": "SELECT", "label": "select.seq2",
                "context_inventory": inventory}), encoding="utf-8")
            with self.assertRaises(ContractError):
                editor.selector_snapshot(context)
            snapshot = editor.selector_snapshot(context, owned_workspace=root)
            self.assertEqual(snapshot["files"], inventory)
            with self.assertRaises(ContractError):
                editor.selector_snapshot(context, owned_workspace=root.parent)

    def fresh(self):
        BASE.mkdir(parents=True, exist_ok=True)
        return Path(tempfile.mkdtemp(prefix="selector-component-", dir=BASE))

    def candidates(self, root):
        result = {}
        for label in ("c1", "c2"):
            path = root / "rollouts" / label
            path.mkdir(parents=True)
            result[label] = RunView(label=label, run_id="synthetic/" + label,
                                    run_dir=path, ok=True, delivered=True)
        return result

    def test_invalid_choice_preserves_native_fallback_but_not_normal_success(self):
        root = self.fresh()
        prop = ChoiceProposer("FORGED")
        result = selection.run_selection("synthetic-task", 2, "seq", self.candidates(root),
            adapter=SelectorAdapter(root, {"c1", "c2"}), prop=prop, work_dir=root, pool_kind="finals")
        self.assertEqual(prop.calls, 1)
        self.assertFalse(result.ok)
        self.assertTrue(result.fallback)
        self.assertIn(result.chosen_label, {"c1", "c2"})
        self.assertFalse(native._selector_normal({"sessions": {}}, result.to_dict(), {}))

    def test_one_survivor_still_uses_native_selector_session(self):
        root = self.fresh()
        prop = ChoiceProposer("A")
        candidates = self.candidates(root)
        candidates["c2"].delivered = False
        result = selection.run_selection("synthetic-task", 2, "seq", candidates,
            adapter=SelectorAdapter(root, {"c1"}), prop=prop, work_dir=root, pool_kind="finals")
        self.assertEqual(prop.calls, 1)
        self.assertTrue(result.ok)
        self.assertFalse(result.trivial)
        self.assertEqual(result.n_candidates, 1)
        self.assertEqual(result.chosen_label, "c1")
        self.assertIn("c2", result.dropped)

    def test_selector_snapshot_seal_rejects_tamper(self):
        with self.assertRaises(ContractError):
            editor._validated_snapshot({"kind": "phase3b-selector-input-v1", "files": {},
                "effective_strategy_sha256": None, "sha256": "0" * 64}, "select.seq2")


if __name__ == "__main__":
    unittest.main()
