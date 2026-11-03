"""Focused actual-pinned native semantics and fixed-control checks; no live calls."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from harness2.core.proposer import Proposer, Reply
from harness2.core.spec import ChannelSpec

from buddha2.artifacts import ContractError, digest
from followups.phase3a_readiness_recovery_v1.test_rank_io import Dispatch
from followups.phase3a_v1.tests.test_strategy import STUDY, TASK

from . import adapter, contract, editor, native, strategy
from .mocks import SDKMock
from .support import BASE, NATIVE


class ComponentMock(SDKMock):
    """Component-only SDK calls; the whole lifecycle separately tests owned intents."""
    def __enter__(self):
        import httpx
        import httpx2

        from followups.phase3a_v1.transport import Transport
        self.transport = Transport(anthropic_api_key="fixture-not-a-secret", openai_api_key="fixture-not-a-secret",
            http_transports={"anthropic": httpx2.MockTransport(lambda req: self._handle(req, http_module=httpx2)),
                             "openai": httpx.MockTransport(lambda req: self._handle(req, http_module=httpx))})
        self.transport.select = self.select
        return self

    def __exit__(self, *exc):
        self.transport._anthropic.close()
        self.transport._openai.close()


class SyntheticProposer(Proposer):
    """A fixture direct return proves native control flow, never model authenticity."""
    def __init__(self):
        super().__init__(ChannelSpec("opencode", "anthropic/claude-opus-5", effort="high", steps=24, timeout=600), attempts=1)
        self.contexts = {}
        self.selector_label = "c1"

    def call(self, mission, context_dir=None, label="", **kwargs):
        context = Path(context_dir)
        if label == "select.seq2":
            prepared = contract.prepare_selector_contract(mission, context, label)
            self.contexts[label] = prepared["manifest"]
            from harness2.core.selection import assign_ids
            ids = assign_ids(["c1", "c2"], task_id=TASK["id"], k=2, mode="seq")
            chosen = next(anon for anon, target in ids.items() if target == self.selector_label)
            return Reply(label=label, text="<why>Synthetic only</why>\n```choice\n" + chosen + "\n```", ok=True)
        prepared = contract.prepare_contract(mission, context, label)
        self.contexts[label] = prepared["manifest"]
        harness = context / "harness"
        current = json.loads((harness / "systemprompt.md").read_text(encoding="utf-8"))
        if label.startswith("c1."):
            current["answer_system"] += "\nSynthetic first-round composition."
            (harness / "systemprompt.md").write_text(json.dumps(current, ensure_ascii=False), encoding="utf-8")
        return Reply(label=label, text="<notes>kept -> KEEP_BASE -> synthetic evidence only.</notes>",
                     ok=True, workspace=harness)


class NativeS2Tests(unittest.TestCase):
    def fresh(self):
        BASE.mkdir(parents=True, exist_ok=True)
        return Path(tempfile.mkdtemp(prefix="native-component-", dir=BASE))

    def test_mixed_namespaces_exact_eight_rollouts(self):
        with strategy.validation_scope():
            ids = native.adaptive_run_ids(TASK["id"], "fixture-tag")
        self.assertEqual(tuple(ids), native.LABELS)
        self.assertEqual(len(set(ids.values())), 8)
        self.assertTrue(all("agg2" in value for key, value in ids.items() if key.startswith("base")))
        self.assertTrue(all("seq2" in value for key, value in ids.items() if not key.startswith("base")))

    def test_round_layout_keeps_all_earlier_views_and_bases(self):
        allowed, required = contract._layout("AGG", "c2.a1")
        self.assertIn("rollouts/base2.md", allowed)
        self.assertIn("harness/systemprompt.md", allowed)
        for label in ("inv1", "dom1", "c1", "inv2", "dom2"):
            self.assertIn(f"pool/{label}/harness/systemprompt.md", allowed)
            self.assertIn(f"pool/{label}/produced.md", allowed)
            self.assertIn((f"decisions/{label}.md", "editor_decision"), required)
        self.assertNotIn("pool/c2/harness/systemprompt.md", allowed)
        with self.assertRaises(contract.ContractError):
            contract._layout("AGG")

    def test_round_contract_names_current_c1_and_twenty_four(self):
        rendered = contract._render("AGG", "c2.a1", None)
        self.assertIn("first composed checkpoint c1", rendered)
        self.assertIn("twenty-four provider requests", rendered)
        self.assertNotIn("agg,k=1", rendered)
        self.assertEqual(editor.MAX_STEPS, 24)
        self.assertEqual(editor.NORMAL_STEPS, 23)

    def test_selector_candidate_write_and_edit_rejected_before_effect(self):
        root = self.fresh()
        target = root / "context/candidates/A.md"
        target.parent.mkdir(parents=True)
        target.write_text("immutable synthetic candidate", encoding="utf-8")
        for name, extra in (("write", {"content": "changed"}),
                            ("edit", {"oldString": "synthetic", "newString": "forged"})):
            block = {"type": "tool_use", "id": name, "name": name,
                     "input": {"filePath": str(target), **extra}}
            with self.assertRaises(ContractError):
                editor.tool_boundary([block], root, selector=True)
            self.assertEqual(target.read_text(encoding="utf-8"), "immutable synthetic candidate")

    def test_selector_opencode_config_denies_candidate_mutation(self):
        root = self.fresh()
        audit = NATIVE / root.name / "editor-audit"
        audit.parent.mkdir(parents=True)
        prop = adapter.CompatibleProposer(pilot="p3b-01", study_sha256=STUDY,
            dispatch=lambda *args: self.fail("configuration cannot dispatch"), audit_dir=audit,
            fixture=True, halt=lambda *args, **kwargs: self.fail("unexpected configuration halt"))
        prop._local.label = "select.seq2"
        prop._local.url, prop._local.home, prop._local.cwd = "http://127.0.0.1:1/v1", str(root), root
        prop._c1_contracts["select.seq2"] = {"authoring_system_text": "SYNTHETIC CONFIGURATION ONLY"}
        configured = json.loads(prop.env()["OPENCODE_CONFIG_CONTENT"])
        permissions = configured["agent"]["build"]["permission"]["edit"]
        self.assertEqual(permissions["*"], "deny")
        self.assertEqual(permissions["output/answer.md"], "allow")
        self.assertTrue(all(path == "*" or path.endswith("output/answer.md") for path in permissions))
        self.assertEqual(prop.attempts, 1)

    def test_actual_native_two_round_keep_preserves_changed_c1_and_both_choices(self):
        root = self.fresh()
        seed = root / "seed"
        strategy.materialize_seed(seed)
        for selected in ("c1", "c2"):
            with ComponentMock() as mock:
                dispatch = Dispatch(mock)
                prop = SyntheticProposer()
                prop.selector_label = selected
                run = root / selected
                result = native.run_adaptation(TASK, seed, study_sha256=STUDY, run_root=run,
                    tag="actual-seq2-" + selected, dispatch=dispatch, fixture=True, prop=prop,
                    known_results=dispatch.results, result_snapshot=lambda: dispatch.results)
                self.assertEqual(tuple(result["rollouts"]), native.LABELS)
                self.assertEqual(result["selected_checkpoint"], selected, json.dumps(result["native"]))
                self.assertEqual(result["portfolio"], result["checkpoints"][selected])
                self.assertEqual(len(result["native"]["modes"]["seq"]["stages"]), 6)
                self.assertFalse(result["authentic"])
                c1 = strategy.validate_harness(run / "rollouts/c1/harness")
                c2 = strategy.validate_harness(run / "rollouts/c2/harness")
                self.assertEqual(c1["effective_strategy_sha256"], c2["effective_strategy_sha256"])
                self.assertNotEqual(c1["effective_strategy_sha256"], strategy.validate_harness(seed)["effective_strategy_sha256"])
                self.assertEqual(prop.contexts["inv2.a1"]["input_effective_strategy_sha256"], c1["effective_strategy_sha256"])
                self.assertEqual(len(dispatch.results), 96)
                before = mock.http_calls
                with strategy.validation_scope(readonly=True):
                    native.validate_adaptation(copy.deepcopy(result), TASK, seed, study_sha256=STUDY,
                        run_root=run, tag="actual-seq2-" + selected, fixture=True, results=dispatch.results)
                self.assertEqual(mock.http_calls, before)
                changed = copy.deepcopy(result)
                changed["checkpoints"][selected] = None
                with strategy.validation_scope(readonly=True), self.assertRaises(ContractError):
                    native.validate_adaptation(changed, TASK, seed, study_sha256=STUDY,
                        run_root=run, tag="actual-seq2-" + selected, fixture=True, results=dispatch.results)

    def test_fixed_twelve_exactly_145_requests_and_no_rewrite(self):
        root = self.fresh()
        seed = root / "seed"
        strategy.materialize_seed(seed)
        with ComponentMock() as mock:
            dispatch = Dispatch(mock)
            result = strategy.fixed_best12(TASK, seed, study_sha256=STUDY, run_id="s2-fixed",
                dispatch=dispatch, fixture=True, known_results=dispatch.results)
            self.assertEqual(len(result["candidates"]), 12)
            self.assertEqual(len(dispatch.results), 145)
            self.assertEqual(result["status"], "complete")
            selected = next(row for row in result["candidates"] if row["run_id"] == result["selected_run_id"])
            self.assertEqual(result["portfolio"], selected["portfolio"])
            self.assertEqual(len(result["selection"]["candidate_map"]), 12)
            before = mock.http_calls
            with strategy.validation_scope(readonly=True):
                replayed = strategy.validate_fixed(result, TASK, seed, study_sha256=STUDY,
                    run_id="s2-fixed", fixture=True, results=dispatch.results)
            self.assertEqual(digest(replayed), digest(result))
            self.assertEqual(mock.http_calls, before)


if __name__ == "__main__":
    unittest.main()
