"""Later-pilot controlled read-history negatives for the shared live/replay guard."""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness2.core import context, prompts

from buddha2.artifacts import ContractError, digest
from followups.phase3a_readiness_recovery_v1.test_delivery import pair

from . import contract, editor, evidence, history, strategy
from .support import BASE


class InformationGuardTests(unittest.TestCase):
    def setUp(self):
        BASE.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="information-later-pilot-", dir=BASE)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cwd = "/tmp/harness2-prop-p3b02fixture"  # nosec B108: synthetic SYSTEM value; never used for filesystem access

    def prepared(self, selector=False):
        target = self.root / ("selector" if selector else "author")
        target.mkdir()
        if selector:
            (target / "candidates").mkdir()
            (target / "task.md").write_text("SYNTHETIC later-pilot request", encoding="utf-8")
            for name in ("A", "B"):
                (target / "candidates" / (name + ".md")).write_text("SYNTHETIC complete candidate " + name, encoding="utf-8")
            return contract.prepare_selector_contract(contract.selector_mission(["A", "B"]), target, "select.seq2")
        label, stage = "inv2.a1", "inv2"
        allowed, required = contract._layout("INV", label)
        strategy.materialize_seed(target / "harness")
        for prior in contract._HISTORY[stage]:
            strategy.materialize_seed(target / "pool" / prior / "harness")
        for name in allowed:
            path = target / name
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("SYNTHETIC complete source " + name, encoding="utf-8")
        tree = context.ContextTree(root=target, task_id="p3b-02", rollouts=["base1", "base2"],
            deliverables=["base1", "base2"], harness_files=1 + len(contract.frozen._COMPATIBILITY),
            library=False, pool=list(contract._HISTORY[stage]), decisions=len(contract._HISTORY[stage]))
        job = prompts.propose(contract.benchmark_prompts(), "INV", strategy._public_surface(), k=2, index=2, round_t=2)
        self.assertTrue(any(name.startswith("pool/c1/") for name, _ in required))
        return contract.prepare_contract(context.mission(tree, job=job), target, label)

    def request(self, prepared, *, omitted_view=None):
        system = prepared["authoring_system_text"] + (
            "\nYou are powered by the model named claude-opus-5. The exact model ID is anthropic/claude-opus-5\n"
            "Here is some useful information about the environment you are running in:\n<env>\n"
            f"  Working directory: {self.cwd}\n  Workspace root folder: /tmp\n"
            "  Is directory a git repo: no\n  Platform: linux\n  Today's date: Mon Nov 02 2026\n</env>")
        manifest = json.dumps(prepared["manifest"], ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
        reads = {self.cwd + "/MISSION.md": prepared["effective_mission"],
            self.cwd + "/context/C1_MANIFEST.json": manifest,
            self.cwd + "/context/C1_INDEX.md": prepared["index_text"]}
        reads.update({self.cwd + "/context/" + name: value for name, value in prepared["evidence_files"].items()
                      if name != omitted_view})
        messages = [{"role": "user", "content": "SYNTHETIC later-pilot invocation"}]
        for index, (path, text) in enumerate(reads.items()):
            messages.extend(pair(f"read-{index}", "read", path, text, limit=max(2000, len(text.splitlines()))))
        return {"system": [{"type": "text", "text": system}], "messages": messages}

    def completion_witnesses(self, request, *, strategy=None, notes=None):
        """Synthetic controller observations for the pure binding unit checks."""
        witnesses = []
        for target, text in (("context/harness/systemprompt.md", strategy), ("output/answer.md", notes)):
            if text is None:
                continue
            ids, history_sha, _ = evidence._mutation_history(request, self.cwd + "/" + target)
            if not ids:
                continue
            text = text.replace("\r\n", "\n")
            if target.startswith("output/"):
                text = text.strip()
            witness = {"kind": "phase3b-native-mutation-completion-v1", "target": target,
                "mutation_ids": ids, "mutation_history_sha256": history_sha,
                "observed_slot_id": "SYNTHETIC current request", "request_sha256": digest(request),
                "text_sha256": hashlib.sha256(text.encode()).hexdigest()}
            witness["sha256"] = digest(witness)
            witnesses.append(witness)
        return witnesses

    def test_complete_later_round_information_passes_without_requiring_an_edit(self):
        prepared = self.prepared()
        request = self.request(prepared)
        proof = evidence.verify_information_before_decision(request, prepared, cwd=self.cwd, label="inv2.a1")
        self.assertTrue(proof["passed"])
        self.assertTrue(proof["delivery"]["complete"])
        raw = proof["delivery"]["files"][self.cwd + "/context/harness/systemprompt.md"]
        self.assertFalse(raw["required"])
        self.assertFalse(raw["complete"])
        self.assertEqual(proof["label"], "inv2.a1")
        self.assertEqual(proof["provider_calls"], 0)

    def test_later_pilot_reports_omitted_prior_pool_view_without_stopping(self):
        prepared = self.prepared()
        entry = next(e for e in prepared["manifest"]["required_evidence"] if e["path"] == "pool/c1/produced.md")
        request = self.request(prepared, omitted_view=entry["chunks"][0]["path"])
        proof = evidence.verify_information_before_decision(request, prepared, cwd=self.cwd, label="inv2.a1")
        audit = proof["delivery"]
        self.assertTrue(proof["passed"])
        self.assertFalse(audit["complete"])
        missing = audit["files"][self.cwd + "/context/" + entry["chunks"][0]["path"]]
        self.assertEqual(missing["missing_ranges"], [[1, missing["source_lines"]]])

    def test_normal_direct_final_cannot_bypass_later_candidate_reads(self):
        prepared = self.prepared(selector=True)
        entry = next(e for e in prepared["manifest"]["required_evidence"] if e["path"] == "candidates/B.md")
        request = self.request(prepared, omitted_view=entry["chunks"][0]["path"])
        with self.assertRaisesRegex(ContractError, "inspect every anonymous candidate"):
            evidence.verify_information_before_decision(request, prepared, cwd=self.cwd, label="select.seq2")

    def test_complete_selector_direct_final_needs_no_output_write(self):
        prepared = self.prepared(selector=True)
        request = self.request(prepared)
        evidence.verify_information_before_decision(request, prepared, cwd=self.cwd, label="select.seq2")
        proof = evidence.verify_normal_session(request, prepared, cwd=self.cwd, label="select.seq2",
            response={"stop_reason": "end_turn", "content": [{"type": "text", "text": "```choice\nA\n```"}]})
        self.assertTrue(proof["passed"])
        self.assertIsNone(proof["notes_delivery"])

    def test_author_direct_final_still_obeys_existing_saved_notes_rule(self):
        prepared = self.prepared()
        request = self.request(prepared)
        evidence.verify_information_before_decision(request, prepared, cwd=self.cwd, label="inv2.a1")
        with self.assertRaisesRegex(ContractError, "mandatory saved notes"):
            evidence.verify_normal_session(request, prepared, cwd=self.cwd, label="inv2.a1",
                response={"stop_reason": "end_turn", "content": [{"type": "text", "text": "<notes>kept -> KEEP_BASE -> synthetic.</notes>"}]},
                harvested_strategy=(self.root / "author/harness/systemprompt.md").read_text(encoding="utf-8"))

    def test_normal_author_notes_reread_and_current_strategy_are_bound(self):
        prepared = self.prepared()
        request = self.request(prepared)
        evidence.verify_information_before_decision(request, prepared, cwd=self.cwd, label="inv2.a1")
        notes = "<notes>kept -> KEEP_BASE -> complete synthetic evidence.</notes>"
        request["messages"].extend(pair("write-notes", "write", self.cwd + "/output/answer.md", notes))
        request["messages"].extend(pair("read-notes", "read", self.cwd + "/output/answer.md", notes))
        response = {"stop_reason": "end_turn", "content": [{"type": "text", "text": notes}]}
        current = (self.root / "author/harness/systemprompt.md").read_text(encoding="utf-8")
        proof = evidence.verify_normal_session(request, prepared, cwd=self.cwd, label="inv2.a1",
            response=response, harvested_strategy=current,
            mutation_witnesses=self.completion_witnesses(request, notes=notes))
        self.assertTrue(proof["passed"])
        with self.assertRaises(ContractError):
            evidence.verify_normal_session(request, prepared, cwd=self.cwd, label="inv2.a1",
                response=response, harvested_strategy=current + "SYNTHETIC unbound output")
        changed = copy.deepcopy(request)
        changed["messages"] = changed["messages"][:-2]
        incomplete = evidence.verify_normal_session(changed, prepared, cwd=self.cwd, label="inv2.a1",
            response=response, harvested_strategy=current,
            mutation_witnesses=self.completion_witnesses(changed, notes=notes))
        self.assertTrue(incomplete["passed"])
        self.assertFalse(incomplete["notes_delivery"]["complete"])

    def test_successful_model_write_and_ordered_edit_bind_harvest_without_rereads(self):
        prepared = self.prepared()
        original = json.loads((self.root / "author/harness/systemprompt.md").read_text(encoding="utf-8"))
        written = {**original, "answer_system": "SYNTHETIC MODEL A"}
        notes = "<notes>SYNTHETIC mutation binding.</notes>"
        response = {"stop_reason": "end_turn", "content": [{"type": "text", "text": notes}]}
        for edit in (False, True):
            request = self.request(prepared)
            request["messages"].extend(pair("strategy-write", "write", self.cwd + "/context/harness/systemprompt.md",
                json.dumps(written, indent=2).replace("\n", "\r\n") + "\r\n"))
            expected = written
            if edit:
                request["messages"].extend([{"role": "assistant", "content": [{"type": "tool_use",
                    "id": "strategy-edit", "name": "edit", "caller": {"type": "direct"}, "input": {
                        "filePath": self.cwd + "/context/harness/systemprompt.md", "oldString": "SYNTHETIC MODEL A",
                        "newString": "SYNTHETIC MODEL C"}}]}, {"role": "user", "content": [{
                            "type": "tool_result", "tool_use_id": "strategy-edit", "content": "Edit applied successfully."}]}])
                expected = {**written, "answer_system": "SYNTHETIC MODEL C"}
            request["messages"].extend(pair("notes-write", "write", self.cwd + "/output/answer.md", notes))
            with self.subTest(edit=edit):
                proof = evidence.verify_normal_session(request, prepared, cwd=self.cwd, label="inv2.a1",
                    response=response, harvested_strategy=json.dumps(expected, indent=4) + "\n",
                    mutation_witnesses=self.completion_witnesses(request, strategy=json.dumps(expected, indent=4) + "\n", notes=notes))
                self.assertTrue(proof["strategy_mutation_binding"]["actual_text_matches"])
                self.assertFalse(proof["strategy_delivery"]["complete"])
                wrong = {**expected, "answer_system": "SYNTHETIC OPERATOR B"}
                with self.assertRaises(ContractError):
                    evidence.verify_normal_session(request, prepared, cwd=self.cwd, label="inv2.a1",
                        response=response, harvested_strategy=json.dumps(wrong),
                        mutation_witnesses=self.completion_witnesses(request, strategy=json.dumps(expected, indent=4) + "\n", notes=notes))
                wrong_final = {"stop_reason": "end_turn", "content": [{"type": "text", "text": "<notes>SYNTHETIC FOREIGN</notes>"}]}
                with self.assertRaisesRegex(ContractError, "consumed artifact differs"):
                    evidence.verify_normal_session(request, prepared, cwd=self.cwd, label="inv2.a1",
                        response=wrong_final, harvested_strategy=json.dumps(expected, indent=4) + "\n",
                        mutation_witnesses=self.completion_witnesses(request, strategy=json.dumps(expected, indent=4) + "\n", notes=notes))

    def test_diagnostic_policy_never_swallows_source_or_system_tamper(self):
        prepared = self.prepared()
        request = self.request(prepared)
        for mutation in ("source", "system", "manifest"):
            candidate, body = copy.deepcopy(prepared), copy.deepcopy(request)
            if mutation == "source":
                name = next(iter(candidate["evidence_files"]))
                candidate["evidence_files"][name] += "SYNTHETIC changed evidence"
            elif mutation == "system":
                body["system"][0]["text"] = "SYNTHETIC foreign instructions"
            else:
                candidate["manifest"]["label"] = "dom2.a1"
            with self.subTest(mutation=mutation), self.assertRaises(ContractError):
                evidence.verify_information_before_decision(body, candidate, cwd=self.cwd, label="inv2.a1")

    def test_controller_observes_native_completion_and_checks_full_write_fields(self):
        native = self.root / "native-completion"
        (native / "context/harness").mkdir(parents=True)
        (native / "output").mkdir()
        strategy_path = native / "context/harness/systemprompt.md"
        notes_path = native / "output/answer.md"
        fields = {"plan_system": "SYNTHETIC plan", "answer_system": "SYNTHETIC A", "rank_system": "SYNTHETIC rank"}
        strategy_path.write_text(json.dumps(fields, indent=4) + "\n", encoding="utf-8")
        notes_path.write_text("<notes>SYNTHETIC saved</notes>\n", encoding="utf-8")
        request = {"messages": pair("write-strategy", "write", str(strategy_path), json.dumps(fields))
            + pair("write-notes", "write", str(notes_path), "<notes>SYNTHETIC saved</notes>")}
        witnesses = evidence.observe_mutation_completion(request, cwd=native, slot="SYNTHETIC t02", previous=[])
        self.assertEqual(len(witnesses), 2)
        self.assertEqual(evidence.observe_mutation_completion(request, cwd=native,
            slot="SYNTHETIC t03", previous=witnesses), witnesses)
        strategy_path.write_text(json.dumps({**fields, "answer_system": "SYNTHETIC B"}), encoding="utf-8")
        with self.assertRaisesRegex(ContractError, "differs from model-produced fields"):
            evidence.observe_mutation_completion(request, cwd=native, slot="SYNTHETIC t02", previous=[])
        malformed = "SYNTHETIC invalid strategy awaiting native shape repair"
        strategy_path.write_text(malformed + "\n", encoding="utf-8")
        request["messages"][0]["content"][0]["input"]["content"] = malformed
        self.assertEqual(len(evidence.observe_mutation_completion(request, cwd=native,
            slot="SYNTHETIC t02", previous=[])), 2)

    def test_selector_partial_candidate_read_is_observed_but_not_complete(self):
        prepared = self.prepared(selector=True)
        request = self.request(prepared)
        entry = next(e for e in prepared["manifest"]["required_evidence"] if e["path"] == "candidates/B.md")
        path = self.cwd + "/context/" + entry["chunks"][0]["path"]
        for index, message in enumerate(request["messages"]):
            if message.get("role") != "assistant":
                continue
            call = message["content"][0]
            if call["input"]["filePath"] == path:
                call["input"]["limit"] = 1
                original = request["messages"][index + 1]["content"][0]["content"]
                row = next(line for line in original.splitlines() if line.startswith("1: "))
                request["messages"][index + 1]["content"][0]["content"] = (
                    f"<path>{path}</path>\n<type>file</type>\n<content>\n{row}\n"
                    f"(Showing lines 1-1 of {entry['chunks'][0]['limit']}. Use offset=2 to continue.)\n</content>")
                break
        proof = evidence.verify_information_before_decision(request, prepared, cwd=self.cwd, label="select.seq2")
        self.assertFalse(proof["delivery"]["complete"])
        final = evidence.verify_normal_session(request, prepared, cwd=self.cwd, label="select.seq2",
            response={"stop_reason": "end_turn", "content": [{"type": "text", "text": "```choice\nA\n```"}]})
        self.assertTrue(final["passed"])
        with self.assertRaisesRegex(ContractError, "no valid candidate choice"):
            evidence.verify_normal_session(request, prepared, cwd=self.cwd, label="select.seq2",
                response={"stop_reason": "end_turn", "content": [{"type": "text", "text": "```choice\nFORGED\n```"}]})


class HistoryGuardTests(unittest.TestCase):
    def conversation(self, turns):
        calls = []
        def dispatch(slot, role, request):
            calls.append(slot)
            content = [{"type": "thinking", "thinking": "", "signature": "SYNTHETIC-SIGNATURE"},
                {"type": "redacted_thinking", "data": "SYNTHETIC-OPAQUE"},
                {"type": "tool_use", "id": f"read-{len(calls)}", "name": "read",
                    "input": {"filePath": "/tmp/harness2-prop-historyfixture/MISSION.md"},
                    "caller": {"type": "direct"}}]
            return {"status": "response", "response": {"provider_response": {
                "stop_reason": "tool_use", "content": content}}}
        prefix = "p3b-01.adaptive.editor.inv1.a1"
        guard = history.HistoryGuard(dispatch, prefix)
        request: dict = {"model": "claude-opus-5", "messages": [{"role": "user", "content": "SYNTHETIC initial"}]}
        for turn in range(1, turns + 1):
            result = guard(f"{prefix}.t{turn:02}", "editor", request)
            content = result["response"]["provider_response"]["content"]
            request = copy.deepcopy(request)
            request["messages"].extend([{"role": "assistant", "content": copy.deepcopy(content)},
                {"role": "user", "content": [{"type": "tool_result", "tool_use_id": content[-1]["id"],
                    "content": "SYNTHETIC read result"}]}])
        return guard, calls, request, prefix

    def test_signed_normal_history_passes_but_prefix_or_signature_tamper_stops_before_dispatch(self):
        normal, calls, request, _ = self.conversation(2)
        self.assertEqual(len(calls), 2)
        self.assertEqual(request["messages"][1]["content"][0],
            {"type": "thinking", "thinking": "", "signature": "SYNTHETIC-SIGNATURE"})
        self.assertEqual(request["messages"][1]["content"][1]["data"], "SYNTHETIC-OPAQUE")
        self.assertTrue(all(audit["history_preserved"] and not audit["history_restored"] for audit in normal.audits))
        for mutation in ("prefix", "signature"):
            guard, calls, request, prefix = self.conversation(1)
            if mutation == "prefix":
                request["messages"][0]["content"] = "SYNTHETIC changed initial request"
            else:
                request["messages"][1]["content"][0]["signature"] = "SYNTHETIC changed signature"
            with self.subTest(mutation=mutation), self.assertRaises(ContractError):
                guard(prefix + ".t02", "editor", request)
            self.assertEqual(len(calls), 1)
            self.assertTrue(guard.stopped)

    def test_terminal_control_is_required_exactly_on_turn24_and_never_renews_history(self):
        terminal = {"role": "user", "content": [{"type": "text", "text": "SYNTHETIC terminal control"}]}
        # Exercise the real message-shape check with a synthetic note; runtime note bytes have their own pin.
        with patch.object(editor.frozen, "terminal_note", return_value="SYNTHETIC terminal control"):
            guard, calls, request, prefix = self.conversation(23)
            request["messages"].append(copy.deepcopy(terminal))
            guard(prefix + ".t24", "editor", request)
            self.assertEqual(len(calls), 24)
            self.assertFalse(any(audit["terminal_control"] for audit in guard.audits[:-1]))
            self.assertTrue(guard.audits[-1]["terminal_control"])
            with self.assertRaises(ContractError):
                guard(prefix + ".t25", "editor", request)
            self.assertEqual(len(calls), 24)
            for turns in (22, 23):
                guard, calls, request, prefix = self.conversation(turns)
                if turns == 22:
                    request["messages"].append(copy.deepcopy(terminal))
                with self.subTest(turn=turns + 1), self.assertRaises(ContractError):
                    guard(f"{prefix}.t{turns + 1:02}", "editor", request)
                self.assertEqual(len(calls), turns)


if __name__ == "__main__":
    unittest.main(verbosity=2)
