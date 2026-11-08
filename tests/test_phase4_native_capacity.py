"""P4 delivery and native context boundaries with synthetic, maximum-size answers."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from harness2.core import context, prompts

from buddha2.artifacts import ContractError, digest, read_json, write_once
from buddha2.phase2_contracts import MAX_RESPONSE_CHARS
from followups.phase3a_v1.tests.test_strategy import STUDY, FakeDispatch
from followups.phase3b_seq2_v1 import contract, editor, ledger_core, native, strategy
from followups.phase3b_seq2_v1.history import HistoryGuard
from followups.phase3b_seq2_v1.support import BASE
from followups.phase4_cm1_v1 import policy
from tests.test_phase2_native import sample_portfolio
from tests.test_phase4_policy import profile_for


class LargeAnswers(FakeDispatch):
    """No transport: actual C-N builders consume deliberately large synthetic outputs."""
    def __call__(self, slot, role, request):
        value = super().__call__(slot, role, request)
        if role == "answer":
            value["response"]["text"] = "\U0001f642" * MAX_RESPONSE_CHARS
        value["intent_sha256"] = digest({"kind": "synthetic-p4-capacity-intent", "slot": slot, "request": request})
        self.results[slot] = value
        return value


class Phase4NativeCapacityTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.blocked = [self.stack.enter_context(patch(name, side_effect=AssertionError("external activity")))
            for name in ("anthropic.Anthropic", "anthropic.AsyncAnthropic", "openai.OpenAI",
                         "openai.AsyncOpenAI", "socket.create_connection", "socket.socket.connect",
                         "socket.socket.connect_ex", "subprocess.Popen", "subprocess.run")]
        BASE.mkdir(parents=True, exist_ok=True)
        temporary = self.stack.enter_context(tempfile.TemporaryDirectory(prefix="p4-native-capacity-", dir=BASE))
        self.root = Path(temporary)
        self.profile, _ = profile_for()

    def tearDown(self):
        self.assertTrue(all(mock.call_count == 0 for mock in self.blocked))

    def rollout(self):
        seed = self.root / "harness"
        strategy.materialize_seed(seed)
        task = sample_portfolio()["task"]
        dispatch = LargeAnswers()
        dispatch.wrapped_rank = False
        record = strategy.execute_cn(task, seed, study_sha256=STUDY,
            run_id="synthetic-p4-capacity", dispatch=dispatch, fixture=True,
            arm="adaptive", request_policy=self.profile)
        write_once(self.root / "rollout.json", record)
        adapter = object.__new__(native.PortfolioAdapter)
        adapter.request_policy = self.profile
        return record, adapter

    def test_real_large_rollout_delivers_exact_answers_and_full_trajectory(self):
        record, adapter = self.rollout()
        path = self.root / "rollout.json"
        self.assertGreater(path.stat().st_size, 2_000_000)
        self.assertTrue(adapter.delivered(self.root))
        text = adapter.deliverable_text(self.root)
        self.assertEqual(json.loads(text), [row["text"] for row in record["portfolio"]["responses"]])
        self.assertEqual(adapter.deliverable_files(self.root), {"answers.json": text})
        trajectory = adapter.trajectory(self.root, obs_trunc=50_000)
        self.assertIn("[ACTION] rank", trajectory)
        self.assertGreater(len(trajectory.encode("utf-8")), 2_000_000)
        self.assertEqual(native.read_artifact(path, request_policy=self.profile), record)
        with self.assertRaises(ContractError):
            read_json(path)
        adapter.request_policy = None
        self.assertFalse(adapter.delivered(self.root))
        with self.assertRaises(ContractError):
            adapter.deliverable_text(self.root)

    def test_actual_author_and_selector_contracts_accept_large_deliveries_only_in_p4(self):
        record, adapter = self.rollout()
        directory = self.root / "context"
        strategy.materialize_seed(directory / "harness")
        allowed, _ = contract._layout("INV", "inv1.a1")
        for name in allowed:
            target = directory / name
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            text = (adapter.trajectory(self.root, obs_trunc=50_000) if name.startswith("rollouts/")
                    else adapter.deliverable_text(self.root) if name.endswith("answers.json.txt")
                    else "Synthetic capacity task and routing evidence.")
            target.write_text(text, encoding="utf-8")
        tree = context.ContextTree(root=directory, task_id=record["task_id"],
            rollouts=["base1", "base2"], deliverables=["base1", "base2"],
            harness_files=1 + len(contract.frozen._COMPATIBILITY), library=False, pool=[], decisions=0)
        job = prompts.propose(contract.benchmark_prompts(), "INV", strategy._public_surface(),
                              k=2, index=1, round_t=1)
        mission = context.mission(tree, job=job)
        limits = policy.context_limits(self.profile)
        limits = {key: limits[key] for key in ("context_file_bytes", "context_total_bytes")}
        with self.assertRaises(contract.ContractError):
            contract.prepare_contract(mission, directory, "inv1.a1")
        prepared = contract.prepare_contract(mission, directory, "inv1.a1", context_limits=limits)
        self.assertGreater(sum(row["bytes"] for row in prepared["manifest"]["context_inventory"].values()), 8_000_000)
        self.assertEqual(prepared["manifest"]["context_inventory"]["deliverables/base1/answers.json.txt"]["bytes"],
                         len(adapter.deliverable_text(self.root).encode("utf-8")))
        selector = self.root / "selector"
        (selector / "candidates").mkdir(parents=True)
        (selector / "task.md").write_text(record["task_id"], encoding="utf-8")
        for name in ("A", "B"):
            (selector / "candidates" / (name + ".md")).write_text(adapter.deliverable_text(self.root), encoding="utf-8")
        mission = contract.selector_mission(["A", "B"])
        with self.assertRaises(contract.ContractError):
            contract.prepare_selector_contract(mission, selector, "select.seq2")
        selected = contract.prepare_selector_contract(mission, selector, "select.seq2", context_limits=limits)
        self.assertEqual(len(selected["manifest"]["required_evidence"]), 3)

    def test_policy_and_json_boundaries_reject_bad_limits_and_duplicate_artifacts(self):
        path = self.root / "ordinary.json"
        path.write_text('{"value":1}', encoding="utf-8")
        for limit in (True, 0, -1, 1_500_000_001, "2000000"):
            with self.subTest(limit=limit), self.assertRaises(ContractError):
                read_json(path, max_bytes=limit)
        with self.assertRaises(ContractError):
            read_json(path, max_bytes=1)
        self.assertEqual(read_json(path, max_bytes=20), {"value": 1})
        bad = dict(self.profile, artifact_limits={})
        with self.assertRaises(ContractError):
            native.read_artifact(path, request_policy=bad)
        path.write_text('{"value":1,"value":2}', encoding="utf-8")
        with self.assertRaises(ContractError):
            native.read_artifact(path, request_policy=self.profile)
        for limits in ({"context_file_bytes": True, "context_total_bytes": 100},
                       {"context_file_bytes": 200, "context_total_bytes": 100}):
            with self.subTest(limits=limits), self.assertRaises(contract.ContractError):
                contract._inventory(self.root, set(), context_limits=limits)

    def test_actual_c2_index_context_and_owned_history_cross_the_old_gate_without_changing_text(self):
        seed = self.root / "harness"
        strategy.materialize_seed(seed)
        task = sample_portfolio()["task"]
        dispatch = LargeAnswers()
        dispatch.wrapped_rank = False
        original_call = dispatch.__class__.__call__

        def controls(slot, role, request):
            value = original_call(dispatch, slot, role, request)
            if role == "answer":
                value["response"]["text"] = "\x01" * MAX_RESPONSE_CHARS
                dispatch.results[slot] = value
            return value

        record = strategy.execute_cn(task, seed, study_sha256=STUDY, run_id="synthetic-c2-capacity",
            dispatch=controls, fixture=True, arm="adaptive", request_policy=self.profile)
        write_once(self.root / "rollout.json", record)
        adapter = object.__new__(native.PortfolioAdapter)
        adapter.request_policy = self.profile
        trajectory, answers = adapter.trajectory(self.root, obs_trunc=50_000), adapter.deliverable_text(self.root)
        directory = self.root / "c2-context"
        allowed, _ = contract._layout("AGG", "c2.a1")
        for prefix in ("harness", *["pool/" + label + "/harness" for label in contract._HISTORY["c2"]]):
            strategy.materialize_seed(directory / prefix)
        for name in allowed:
            target = directory / name
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            text = (trajectory if name.endswith("rollout.md") or name.startswith("rollouts/")
                    else answers if name.endswith("produced.md") or name.endswith("answers.json.txt")
                    else "Synthetic retained c2 evidence; no provider or study result.")
            target.write_text(text, encoding="utf-8")
        tree = context.ContextTree(root=directory, task_id=task["id"], rollouts=["base1", "base2"],
            deliverables=["base1", "base2"], harness_files=1 + len(contract.frozen._COMPATIBILITY),
            library=False, pool=list(contract._HISTORY["c2"]), decisions=len(contract._HISTORY["c2"]))
        job = prompts.compose_round(contract.benchmark_prompts(), strategy._public_surface(), t=2, k=2)
        mission = context.mission(tree, job=job)
        bounds = policy.context_limits(self.profile)
        limits = {key: bounds[key] for key in ("context_file_bytes", "context_total_bytes")}
        prepared = contract.prepare_contract(mission, directory, "c2.a1", context_limits=limits)
        self.assertGreater(len(prepared["evidence_files"]), 1000)
        # Exercise the actual installed-context byte/file consumer. Only its
        # native subprocess handoff is substituted; no OpenCode process runs.
        for name, text in list(prepared["evidence_files"].items())[:1001]:
            target = directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        proposer = object.__new__(editor.AccountedProposer)
        proposer.audit_dir, proposer.halt, proposer._local = self.root / "audit", lambda *a: None, SimpleNamespace()
        proposer._known_provider_terminal = None
        proposer._installed_limits = {key: bounds[key] for key in ("installed_context_files", "installed_context_bytes")}
        with patch.object(editor.Proposer, "call", return_value="synthetic-native-handoff"):
            self.assertEqual(proposer.call(mission, directory, "c2.a1"), "synthetic-native-handoff")
            proposer._installed_limits = {"installed_context_files": 1000, "installed_context_bytes": 8_000_000}
            with self.assertRaises(editor.ProposerError):
                proposer.call(mission, directory, "c2.a1")
        views = sorted(prepared["evidence_files"].items(), key=lambda item: len(item[1]), reverse=True)[:96]
        read_tools = [{"type": "tool_use", "id": f"read-{i}", "name": "read",
                       "input": {"filePath": "/tmp/harness2-prop-synthetic/context/" + name}}
                      for i, (name, _) in enumerate(views)]
        tools = {"read": {"name": "read", "input_schema": {"type": "object"}}}
        raw = {"model": "claude-opus-5", "max_tokens": 16000, "stream": True,
            "thinking": {"type": "adaptive"}, "output_config": {"effort": "high"},
            "system": [{"type": "text", "text": prepared["authoring_system_text"]}],
            "tools": list(tools.values()), "messages": [{"role": "user", "content": "Synthetic c2 invocation"}]}
        calls = []

        def result(slot, role, request):
            ledger_core.validate_request(role, request, editor_tools=tools, policy=self.profile)
            calls.append(slot)
            return {"status": "response", "response": {"provider_response": {
                "stop_reason": "tool_use", "content": read_tools}}}

        guard = HistoryGuard(result, "p4-01.adaptive.editor.c2.a1")
        guard("p4-01.adaptive.editor.c2.a1.t01", "editor", editor.effective_request(raw, turn=1))
        raw["messages"].extend([{"role": "assistant", "content": read_tools}, {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": f"read-{i}", "content": text}
            for i, (_, text) in enumerate(views)]}])
        wire = json.dumps(raw, ensure_ascii=False, separators=(",", ":")).encode()
        self.assertGreater(len(wire), 2_097_152)
        self.assertLess(len(wire), self.profile["role_payload_bytes"]["editor"])
        with self.assertRaises(ContractError):
            editor._relay_body(io.BytesIO(wire), len(wire))
        restored = editor._relay_body(io.BytesIO(wire), len(wire), request_policy=self.profile)
        self.assertEqual(restored, raw)
        body = editor.effective_request(restored, turn=2)
        guard("p4-01.adaptive.editor.c2.a1.t02", "editor", body)
        with self.assertRaises(ContractError):
            ledger_core.validate_request("editor", body, editor_tools=tools)
        raw["messages"][0]["content"] = "Tampered original invocation"
        with self.assertRaises(ContractError):
            guard("p4-01.adaptive.editor.c2.a1.t03", "editor", editor.effective_request(raw, turn=3))
        self.assertEqual(calls, ["p4-01.adaptive.editor.c2.a1.t01", "p4-01.adaptive.editor.c2.a1.t02"])
