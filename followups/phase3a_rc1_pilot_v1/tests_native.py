"""HI history and ownership boundaries; synthetic responses only."""
from __future__ import annotations

import copy
import os
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest
from followups.phase3a_history_compat_h1.guard import HistoryGuard as OrdinaryGuard
from followups.phase3a_v1.editor import session_eligibility, terminal_note

from . import contract, editor, strategy, workflow
from .history import HistoryGuard
from .support import safe


class HistoryTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "posix", "pinned Linux temporary-workspace check")
    def test_native_temporary_workspace_is_exact_scoped_and_private_safe(self):
        with tempfile.TemporaryDirectory(prefix="harness2-prop-") as directory, \
                tempfile.TemporaryDirectory(prefix="harness2-prop-") as sibling:
            cwd = Path(directory)
            harness = cwd / "context/harness"
            with self.assertRaises(ContractError):
                strategy.precheck_harness(harness)
            with strategy.native_workspace(cwd):
                strategy.materialize_seed(harness)
                with strategy.validation_scope(readonly=True):
                    self.assertEqual(strategy.validate_harness(harness)["tree"], strategy.seed_tree())
                with patch.object(Path, "lstat", side_effect=AssertionError("foreign metadata")):
                    with self.assertRaises(ContractError):
                        strategy.precheck_harness(Path(sibling) / "context/harness")
                    with self.assertRaises(ContractError):
                        strategy.precheck_harness(cwd / "context/foreign")
                real_lstat = Path.lstat
                def lstat(target, *args, **kwargs):
                    if target.name.casefold() == "auth.json":
                        self.fail("private temporary harness metadata reached")
                    return real_lstat(target, *args, **kwargs)
                with strategy.validation_scope(), patch.object(strategy.os, "listdir", return_value=["AUTH.JSON"]), \
                        patch.object(Path, "lstat", lstat):
                    with self.assertRaises(ContractError):
                        strategy.precheck_harness(harness)
            self.assertIsNone(strategy._NATIVE_HARNESS.get())
            with self.assertRaises(ContractError):
                strategy.precheck_harness(harness)
            with self.assertRaises(RuntimeError):
                with strategy.native_workspace(cwd):
                    raise RuntimeError("SYNTHETIC SCOPE FAILURE")
            self.assertIsNone(strategy._NATIVE_HARNESS.get())

    def conversation(self, count=15, guard_type=HistoryGuard):
        calls, contents = [], []
        def dispatch(slot, role, request):
            calls.append(copy.deepcopy(request))
            content = [{"type": "thinking", "thinking": "", "signature": "synthetic-empty"},
                       {"type": "thinking", "thinking": "VISIBLE", "signature": "synthetic-visible"},
                       {"type": "redacted_thinking", "data": "synthetic-redacted"},
                       {"type": "tool_use", "id": f"read-{len(calls)}", "name": "read",
                        "input": {"filePath": "/synthetic-only"}, "caller": {"type": "direct"}}]
            if len(calls) == 16:
                content = [{"type": "text", "text": "SYNTHETIC FINAL"}]
            contents.append(content)
            return {"status": "response", "response": {"provider_response": {
                "content": copy.deepcopy(content), "stop_reason": "end_turn" if len(calls) == 16 else "tool_use"}}}
        guard = guard_type(dispatch, "fixture")
        request: dict = {"model": "claude-opus-5", "system": "SYNTHETIC SYSTEM",
                   "messages": [{"role": "user", "content": "SYNTHETIC"}]}
        for turn in range(1, count + 1):
            before = digest(request)
            guard(f"fixture.t{turn:02}", "editor", request)
            self.assertEqual(before, digest(request))
            request["messages"].extend([
                {"role": "assistant", "content": copy.deepcopy(contents[-1])},
                {"role": "user", "content": [{"type": "tool_result",
                    "tool_use_id": f"read-{turn}", "content": "SYNTHETIC RESULT"}]}])
        return guard, calls, request

    def test_ordinary_matches_accepted_H1_and_preserves_actual_request(self):
        old, old_calls, _ = self.conversation(15, OrdinaryGuard)
        new, new_calls, _ = self.conversation()
        self.assertEqual(old_calls, new_calls)
        self.assertEqual(old.responses, new.responses)
        self.assertFalse(any(row["history_restored"] for row in new.audits))

    def test_terminal16_exact_extra_note_and_original_body(self):
        guard, calls, request = self.conversation()
        request["messages"].append({"role": "user", "content": [{"type": "text", "text": terminal_note()}]})
        before = digest(request)
        result = guard("fixture.t16", "editor", request)
        self.assertEqual(before, digest(request))
        self.assertEqual(calls[-1], request)
        self.assertEqual(result["response"]["provider_response"]["stop_reason"], "end_turn")
        self.assertTrue(guard.audits[-1]["terminal_control"])
        with self.assertRaises(ContractError):
            guard("fixture.t17", "editor", request)
        self.assertEqual(len(calls), 16)

    def test_terminal_and_history_tampering_never_delegate_or_recover(self):
        for mutation in ("missing-note", "wrong-note", "old-signature", "missing-thinking",
                         "changed-system", "different-conversation", "duplicate-note"):
            with self.subTest(mutation=mutation):
                guard, calls, request = self.conversation()
                request["messages"].append({"role": "user", "content": [{"type": "text", "text": terminal_note()}]})
                slot = "fixture.t16"
                if mutation == "missing-note":
                    request["messages"].pop()
                if mutation == "wrong-note":
                    request["messages"][-1]["content"][0]["text"] += "changed"
                if mutation == "old-signature":
                    request["messages"][-3]["content"][0]["signature"] = "changed"
                if mutation == "missing-thinking":
                    request["messages"][-3]["content"].pop(0)
                if mutation == "changed-system":
                    request["system"] += "changed"
                if mutation == "different-conversation":
                    slot = "foreign.t16"
                if mutation == "duplicate-note":
                    request["messages"].append(copy.deepcopy(request["messages"][-1]))
                with self.assertRaises(ContractError):
                    guard(slot, "editor", request)
                with self.assertRaises(ContractError):
                    guard("fixture.t16", "editor", request)
                self.assertEqual(len(calls), 15)
                self.assertTrue(guard.stopped)

    def test_early_terminal_never_becomes_an_ordinary_turn(self):
        guard, calls, request = self.conversation(1)
        request["messages"].append({"role": "user", "content": [{"type": "text", "text": terminal_note()}]})
        with self.assertRaises(ContractError):
            guard("fixture.t02", "editor", request)
        self.assertEqual(len(calls), 1)

    def test_unknown_malformed_and_delegate_error_latch(self):
        initial = {"messages": [{"role": "user", "content": "SYNTHETIC"}]}
        for result in ({"status": "unknown"}, {"status": "response", "response": {}},
                       {"status": "response", "response": {"provider_response": {
                           "content": [{"type": "thinking", "thinking": "", "signature": ""}], "stop_reason": "end_turn"}}}):
            calls = []
            def dispatch(*args):
                calls.append(args)
                return result
            guard = HistoryGuard(dispatch, "fixture")
            with self.assertRaises((ContractError, KeyError)):
                guard("fixture.t01", "editor", initial)
            with self.assertRaises(ContractError):
                guard("fixture.t01", "editor", initial)
            self.assertEqual(len(calls), 1)
        def broken(*args):
            raise RuntimeError("SYNTHETIC")
        guard = HistoryGuard(broken, "fixture")
        with self.assertRaises(RuntimeError):
            guard("fixture.t01", "editor", initial)
        self.assertTrue(guard.stopped)

    def test_terminal_changed_and_normal_KEEP_BASE_eligibility_unchanged(self):
        self.assertEqual(session_eligibility(False, "same", "same"), (False, True))
        self.assertEqual(session_eligibility(True, "same", "new"), (True, True))
        self.assertEqual(session_eligibility(True, "same", "same"), (False, False))
        self.assertEqual(session_eligibility(True, None, "new"), (None, False))

    def test_private_and_escaped_paths_rejected_before_metadata(self):
        for value in ("/results/phase3a-rc1-pilot-v1/.env", "/results/phase3a-rc1-pilot-v1/x/AUTH.JSON",
                      "/results/phase3a-rc1-pilot-v1/../foreign", "/foreign/public.json"):
            with self.subTest(value=value), patch.object(Path, "lstat", side_effect=AssertionError("metadata")):
                with self.assertRaises(ContractError):
                    safe(Path(value))

    def test_private_tool_paths_are_denied_before_any_filesystem_access(self):
        for name in ("AUTH.JSON", "credentials.json", ".env", ".writer.lock", "credential-binding.json", "stdout.txt", "stderr.json"):
            content = [{"type": "tool_use", "name": "read", "input": {"filePath": "/synthetic/context/" + name}}]
            with self.subTest(name=name), patch.object(Path, "is_symlink", side_effect=AssertionError("metadata")), \
                    patch.object(Path, "resolve", side_effect=AssertionError("metadata")):
                with self.assertRaises(ContractError):
                    editor.tool_boundary(content, Path("/synthetic"))

    def test_private_context_and_harness_entries_fail_before_leaf_metadata(self):
        root = Path("/results/phase3a-rc1-pilot-v1/synthetic-public-root")
        real_lstat = Path.lstat
        def lstat(target, *args, **kwargs):
            if target.name.casefold() == "auth.json":
                self.fail("private leaf metadata reached")
            return real_lstat(target, *args, **kwargs)
        with patch.object(Path, "lstat", lstat), patch.object(contract.os, "listdir", return_value=["AUTH.JSON"]):
            with self.assertRaises(contract.ContractError):
                contract._inventory(root, {"systemprompt.md"})
        with strategy.validation_scope(), patch.object(Path, "lstat", lstat), \
                patch.object(Path, "exists", return_value=True), patch.object(strategy.os, "listdir", return_value=["AUTH.JSON"]):
            with self.assertRaises(ContractError):
                strategy.precheck_harness(root)


class CoordinatorTests(unittest.TestCase):
    def test_closure_reuses_worker_summary_and_preserves_prior_failure(self):
        summary = {"fixture": True, "status": "incomplete"}
        with patch.object(workflow, "_visibility_checkpoint", return_value={"canonical_summary": summary}) as checkpoint, \
                patch.object(workflow, "snapshot", side_effect=AssertionError("duplicate canonical fold")):
            self.assertIs(workflow._close_run(None, {}, None, True, Path("/synthetic/run")), summary)
        checkpoint.assert_called_once()
        stopped = ContractError("SYNTHETIC OWNERSHIP STOP")
        with patch.object(workflow, "_visibility_checkpoint", side_effect=stopped):
            with self.assertRaises(ContractError) as raised:
                workflow._close_run(None, {}, None, True, Path("/synthetic/run"))
            self.assertIs(raised.exception, stopped)
            self.assertIsNone(workflow._close_run(None, {}, None, True, Path("/synthetic/run"), stopped))

    def _stage_fixture(self, stopped=False, reviewed=False):
        task = {"pilot_id": "p3a-01", "parent_task_id": "synthetic-task", "prompt": "SYNTHETIC",
                "source_context": {}, "arm_order": ["adaptive", "fixed"]}
        study = {"study_sha256": "a" * 64, "source_sha256": "b" * 64, "policy_sha256": "c" * 64,
                 "launcher_sha256": "d" * 64, "slots": {}, "editor_tools": {}, "tasks": [task],
                 "assessment_plan": [{"id": "synthetic-primary", "pilot": "p3a-01", "arm": "fixed", "diagnostic": False}]}
        state = {"status": "ready", "reserved_micro_usd": 0, "assessment_stopped": stopped,
                 "engineering_review": reviewed, "first_assessments_closed": False,
                 "attempts": 1, "spent_micro_usd": 1}
        records = {"branches": {(task["pilot_id"], arm): {"result": {"portfolio": {"fixture": True}}}
                                  for arm in ("fixed", "adaptive")},
                   "seals": {"p3a-01": {}}, "assessments": {}}
        published = []
        stack = ExitStack()
        stack.enter_context(patch.object(workflow, "paths", return_value=(Path("/results/phase3a-rc1-pilot-v1/synthetic/run"), Path("/synthetic/journal"))))
        stack.enter_context(patch.object(workflow, "_state", return_value=state))
        stack.enter_context(patch.object(workflow, "saved", return_value=records))
        stack.enter_context(patch.object(workflow, "snapshot", return_value={"summary": {"fixture": True}}))
        stack.enter_context(patch.object(workflow, "publish", side_effect=lambda path, value: published.append((path, value))))
        stack.enter_context(patch.object(workflow.accounting, "Ledger", return_value=SimpleNamespace(state=lambda: state)))
        return stack, study, published

    def test_exhausted_full_pool_prevents_any_later_generation_or_assessment(self):
        for stage in ("first", "remaining"):
            stack, study, published = self._stage_fixture(stopped=True, reviewed=True)
            with stack, patch.object(workflow.native, "Phase3NativeAssessment", side_effect=AssertionError("new assessment")), \
                    patch.object(workflow.native, "run_adaptation", side_effect=AssertionError("new generation")):
                result = workflow._run_stage(Path("/synthetic/study.json"), study, {"authority": {}}, stage,
                                             SimpleNamespace(fixture=True), Path("/synthetic/grant.json"))
            if not isinstance(result, dict):
                self.fail("stage did not return its canonical result")
            self.assertTrue(result["fixture"])
            self.assertEqual([p.name for p, _ in published], ["primary-stop.json"])
            self.assertEqual(published[0][1]["reason"], "primary_assessment_pool_exhausted")

    def test_first_checkpoint_pause_is_not_full_pool_stop_and_original_slot_resumes(self):
        for reviewed in (False, True):
            stack, study, published = self._stage_fixture(reviewed=reviewed)
            called = []
            def assess(portfolio, dispatch, *, assessment_id):
                called.append(assessment_id)
                if not reviewed:
                    raise workflow.accounting.CheckpointStop("SYNTHETIC FIRST CHECKPOINT")
                return {"status": "scored", "fixture": True}
            evaluator = SimpleNamespace(assess=assess, slot_prefix=lambda value: value)
            with stack, patch.object(workflow.native, "Phase3NativeAssessment", return_value=evaluator), \
                    patch.object(workflow, "_first_review"):
                workflow._run_stage(Path("/synthetic/study.json"), study, {"authority": {}}, "first",
                                    SimpleNamespace(fixture=True), Path("/synthetic/grant.json"))
            self.assertEqual(called, ["synthetic-primary"])
            self.assertFalse(any(p.name == "primary-stop.json" for p, _ in published))
            self.assertEqual(any(p.name == "synthetic-primary.json" for p, _ in published), reviewed)

    def test_export_ownership_requires_stop_proof_but_not_visibility_success(self):
        request = {"study_sha256": "a" * 64, "checkpoint": "first-pair", "snapshot_sha256": "b" * 64,
                   "deadline_at_utc": "2026-10-31T00:10:00+00:00"}
        owner = {**request, "kind": "p3a-rp1-visibility-owner-v1", "exporter_started": True, "state": "claimed"}
        ack = {**request, "kind": "p3a-rp1-visibility-result-v1", "provider_calls": 0,
               "exporter_stopped": True, "visibility_status": "failed"}
        self.assertTrue(workflow._export_owner_settled(request, {**owner, "exporter_started": False, "state": "closed_without_export"}, None))
        with self.assertRaises(ContractError):
            workflow._export_owner_settled(request, None, None)
        self.assertTrue(workflow._export_owner_settled(request, owner, ack))
        for changed in (None, {**ack, "exporter_stopped": False}, {**ack, "snapshot_sha256": "c" * 64}):
            with self.assertRaises(ContractError):
                workflow._export_owner_settled(request, owner, changed)
        with self.assertRaises(ContractError):
            workflow._export_owner_settled(request, {**owner, "deadline_at_utc": "different"}, ack)


if __name__ == "__main__":
    unittest.main(verbosity=2)
