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

    def optional_context(self, label="c1.a1", *, omitted=()):
        """Synthetic trusted proof; native journal validation is tested separately."""
        stage = label.split(".", 1)[0]
        target = self.root / stage
        allowed, _ = contract._layout("AGG", label)
        strategy.materialize_seed(target / "harness")
        for prior in contract._HISTORY[stage]:
            strategy.materialize_seed(target / "pool" / prior / "harness")
        for name in allowed:
            path = target / name
            if name not in omitted and not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("SYNTHETIC complete source " + name, encoding="utf-8")
        tree = context.ContextTree(root=target, task_id="p3b-02", rollouts=["base1", "base2"],
            deliverables=["base1", "base2"], harness_files=1 + len(contract.frozen._COMPATIBILITY),
            library=False, pool=list(contract._HISTORY[stage]), decisions=len(contract._HISTORY[stage]))
        job = prompts.compose_round(contract.benchmark_prompts(), strategy._public_surface(), t=int(stage[-1]), k=2)
        run_id = "synthetic-known-inv1-failure"
        slots = strategy.slot_ids(run_id)
        proof = {"run_id": run_id, "failure_sha256": digest({"synthetic": "known failure"}),
            "effective_strategy_sha256": strategy.validate_harness(target / "pool/inv1/harness")["effective_strategy_sha256"],
            "result_sha256": {slot: digest({"synthetic_result": slot})
                for slot in (slots["plan"], *slots["answers"], slots["rank"])},
            "reason": "ranker_not_finished"}
        return target, context.mission(tree, job=job), {"inv1": proof}

    def test_known_optional_absence_keeps_all_remaining_contract_evidence(self):
        missing = "pool/inv1/produced.md"
        target, mission, failures = self.optional_context(omitted=(missing,))
        prepared = contract.prepare_contract(mission, target, "c1.a1", failed_probes=failures)
        manifest = prepared["manifest"]
        self.assertEqual(manifest["failed_probes"], failures)
        self.assertNotIn(missing, manifest["context_inventory"])
        self.assertIn("pool/inv1/rollout.md", manifest["context_inventory"])
        self.assertIn("pool/dom1/produced.md", manifest["context_inventory"])
        original, _ = evidence._sources(target, "unused", manifest, {}, supplied=prepared["evidence_files"])
        self.assertEqual(set(original), {row["path"] for row in manifest["required_evidence"]})
        self.assertNotIn(missing, original)
        self.assertFalse((target / missing).exists())

    def test_known_failure_with_present_output_keeps_original_contract(self):
        target, mission, failures = self.optional_context()
        original = contract.prepare_contract(mission, target, "c1.a1")
        supplied = contract.prepare_contract(mission, target, "c1.a1", failed_probes=failures)
        self.assertEqual(original, supplied)
        self.assertNotIn("failed_probes", supplied["manifest"])
        self.assertIn("pool/inv1/produced.md", supplied["manifest"]["context_inventory"])

    def test_missing_produced_without_trusted_proof_is_rejected_even_with_failure_prose(self):
        target, mission, _ = self.optional_context(omitted=("pool/inv1/produced.md",))
        (target / "pool/inv1/rollout.md").write_text("(unavailable: synthetic known failure)", encoding="utf-8")
        for proof in (None, {}):
            with self.subTest(proof=proof), self.assertRaises(contract.ContractError):
                contract.prepare_contract(mission, target, "c1.a1", failed_probes=proof)

    def test_optional_proof_cannot_waive_required_checkpoint_or_other_source(self):
        target, mission, failures = self.optional_context("c2.a1", omitted=("pool/c1/produced.md",))
        for proof in (failures, {"c1": failures["inv1"]}):
            with self.subTest(proof_stage=tuple(proof)), self.assertRaises(contract.ContractError):
                contract.prepare_contract(mission, target, "c2.a1", failed_probes=proof)
        target, mission, failures = self.optional_context(omitted=("pool/inv1/produced.md", "pool/inv1/rollout.md"))
        with self.assertRaises(contract.ContractError):
            contract.prepare_contract(mission, target, "c1.a1", failed_probes=failures)

    def test_optional_proof_strategy_must_match_candidate_and_saved_evidence(self):
        target, mission, failures = self.optional_context(omitted=("pool/inv1/produced.md",))
        changed = copy.deepcopy(failures)
        changed["inv1"]["effective_strategy_sha256"] = "0" * 64
        with self.assertRaises(contract.ContractError):
            contract.prepare_contract(mission, target, "c1.a1", failed_probes=changed)
        prepared = contract.prepare_contract(mission, target, "c1.a1", failed_probes=failures)
        for corruption in ("drop", "strategy"):
            manifest = copy.deepcopy(prepared["manifest"])
            if corruption == "drop":
                del manifest["failed_probes"]
            else:
                manifest["failed_probes"]["inv1"]["effective_strategy_sha256"] = "0" * 64
            with self.subTest(corruption=corruption), self.assertRaises(ContractError):
                evidence._sources(target, "unused", manifest, {}, supplied=prepared["evidence_files"])

    def test_optional_proof_rejects_missing_extra_or_foreign_result_binding(self):
        target, mission, failures = self.optional_context(omitted=("pool/inv1/produced.md",))
        for corruption in ("missing", "extra", "run_id", "result_slot"):
            proof = copy.deepcopy(failures)
            if corruption == "missing":
                del proof["inv1"]["failure_sha256"]
            elif corruption == "extra":
                proof["inv1"]["synthetic_untrusted_field"] = True
            elif corruption == "run_id":
                proof["inv1"]["run_id"] = "synthetic-other-candidate"
            else:
                proof["inv1"]["result_sha256"] = {"synthetic.foreign.slot": "1" * 64}
            with self.subTest(corruption=corruption), self.assertRaises(contract.ContractError):
                contract.prepare_contract(mission, target, "c1.a1", failed_probes=proof)

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
            native_output="```choice\nA\n```",
            response={"stop_reason": "end_turn", "content": [{"type": "text", "text": "```choice\nA\n```"}]})
        self.assertTrue(proof["passed"])
        self.assertIsNone(proof["notes_delivery"])

    def test_author_direct_final_still_obeys_existing_saved_notes_rule(self):
        prepared = self.prepared()
        request = self.request(prepared)
        evidence.verify_information_before_decision(request, prepared, cwd=self.cwd, label="inv2.a1")
        with self.assertRaisesRegex(ContractError, "mandatory saved notes"):
            evidence.verify_normal_session(request, prepared, cwd=self.cwd, label="inv2.a1",
                native_output="<notes>kept -> KEEP_BASE -> synthetic.</notes>",
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
            response=response, native_output=notes, saved_output=notes, harvested_strategy=current,
            mutation_witnesses=self.completion_witnesses(request, notes=notes))
        self.assertTrue(proof["passed"])
        with self.assertRaises(ContractError):
            evidence.verify_normal_session(request, prepared, cwd=self.cwd, label="inv2.a1",
                response=response, native_output=notes, saved_output=notes,
                harvested_strategy=current + "SYNTHETIC unbound output")
        changed = copy.deepcopy(request)
        changed["messages"] = changed["messages"][:-2]
        incomplete = evidence.verify_normal_session(changed, prepared, cwd=self.cwd, label="inv2.a1",
            response=response, native_output=notes, saved_output=notes, harvested_strategy=current,
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
                    response=response, native_output=notes, saved_output=notes,
                    harvested_strategy=json.dumps(expected, indent=4) + "\n",
                    mutation_witnesses=self.completion_witnesses(request, strategy=json.dumps(expected, indent=4) + "\n", notes=notes))
                self.assertTrue(proof["strategy_mutation_binding"]["actual_text_matches"])
                self.assertFalse(proof["strategy_delivery"]["complete"])
                wrong = {**expected, "answer_system": "SYNTHETIC OPERATOR B"}
                with self.assertRaises(ContractError):
                    evidence.verify_normal_session(request, prepared, cwd=self.cwd, label="inv2.a1",
                        response=response, native_output=notes, saved_output=notes, harvested_strategy=json.dumps(wrong),
                        mutation_witnesses=self.completion_witnesses(request, strategy=json.dumps(expected, indent=4) + "\n", notes=notes))
                different_final = {"stop_reason": "end_turn", "content": [{"type": "text", "text": "SYNTHETIC final acknowledgement."}]}
                proof = evidence.verify_normal_session(request, prepared, cwd=self.cwd, label="inv2.a1",
                    response=different_final, native_output=notes, saved_output=notes,
                    harvested_strategy=json.dumps(expected, indent=4) + "\n",
                    mutation_witnesses=self.completion_witnesses(request, strategy=json.dumps(expected, indent=4) + "\n", notes=notes))
                self.assertFalse(proof["final_matches_native_output"])
                with self.assertRaises(ContractError):
                    evidence.verify_normal_session(request, prepared, cwd=self.cwd, label="inv2.a1",
                        response=different_final, native_output=notes + "SYNTHETIC changed native return", saved_output=notes,
                        harvested_strategy=json.dumps(expected, indent=4) + "\n",
                        mutation_witnesses=self.completion_witnesses(request, strategy=json.dumps(expected, indent=4) + "\n", notes=notes))

    def test_selector_saved_output_is_authoritative_when_final_prose_or_choice_differs(self):
        prepared = self.prepared(selector=True)
        request = self.request(prepared)
        saved = "<why>SYNTHETIC saved reasoning.</why>\n```choice\nB\n```"
        request["messages"].extend(pair("write-answer", "write", self.cwd + "/output/answer.md", saved))
        for final in (saved.replace("saved", "different final"), "```choice\nA\n```", "SYNTHETIC done."):
            with self.subTest(final=final):
                proof = evidence.verify_normal_session(request, prepared, cwd=self.cwd, label="select.seq2",
                    response={"stop_reason": "end_turn", "content": [{"type": "text", "text": final}]},
                    native_output=saved, saved_output=saved,
                    mutation_witnesses=self.completion_witnesses(request, notes=saved))
                self.assertTrue(proof["passed"])
                self.assertEqual(proof["kind"], "phase3b-s2-normal-session-delivery-v2")
                self.assertEqual(proof["native_output"], saved)
                self.assertEqual(proof["saved_output"], saved)
                self.assertEqual(proof["native_output_source"], "saved_file")
                self.assertFalse(proof["final_matches_native_output"])
                self.assertTrue(proof["notes_mutation_binding"]["actual_text_matches"])

    def test_selector_stdout_fallback_uses_actual_native_aggregate_with_absent_or_empty_file(self):
        from harness2.core.proposer import _opencode_stdout

        prepared = self.prepared(selector=True)
        final = "```choice\nB\n```"
        wire = "\n".join(json.dumps({"type": "text", "part": {"type": "text", "text": text}})
                         for text in ("SYNTHETIC earlier progress.", final))
        actual, error = _opencode_stdout(wire)
        self.assertFalse(error)
        self.assertNotEqual(actual, final)
        for saved in (None, ""):
            request = self.request(prepared)
            if saved is not None:
                request["messages"].extend(pair("empty-answer", "write", self.cwd + "/output/answer.md", saved))
            with self.subTest(saved_file_exists=saved is not None):
                proof = evidence.verify_normal_session(request, prepared, cwd=self.cwd, label="select.seq2",
                    response={"stop_reason": "end_turn", "content": [{"type": "text", "text": final}]},
                    native_output=actual, saved_output=saved,
                    mutation_witnesses=self.completion_witnesses(request, notes=saved))
                self.assertTrue(proof["passed"])
                self.assertEqual(proof["native_output_source"], "native_stdout")
                self.assertFalse(proof["final_matches_native_output"])

    def test_native_output_binding_rejects_unwitnessed_changed_or_missing_artifacts(self):
        prepared = self.prepared(selector=True)
        saved = "<why>SYNTHETIC saved.</why>\n```choice\nB\n```"
        original = self.request(prepared)
        original["messages"].extend(pair("write-answer", "write", self.cwd + "/output/answer.md", saved))
        for mutation in ("missing_file", "changed_file", "changed_native_return", "no_witness", "no_write", "failed_write", "wrong_path"):
            request = copy.deepcopy(original)
            native, observed = saved, saved
            witnesses = self.completion_witnesses(request, notes=saved)
            if mutation == "missing_file":
                observed = None
            elif mutation == "changed_file":
                observed += "SYNTHETIC changed artifact"
                native = observed
            elif mutation == "changed_native_return":
                native = saved.replace("\nB\n", "\nA\n")
            elif mutation == "no_witness":
                witnesses = []
            elif mutation == "no_write":
                request["messages"] = request["messages"][:-2]
                witnesses = []
            elif mutation == "failed_write":
                request["messages"][-1]["content"][0]["is_error"] = True
            else:
                request["messages"][-2]["content"][0]["input"]["filePath"] += ".foreign"
            with self.subTest(mutation=mutation), self.assertRaises(ContractError):
                evidence.verify_normal_session(request, prepared, cwd=self.cwd, label="select.seq2",
                    response={"stop_reason": "end_turn", "content": [{"type": "text", "text": "SYNTHETIC done."}]},
                    native_output=native, saved_output=observed, mutation_witnesses=witnesses)

    def test_native_selector_choice_and_normal_end_remain_required(self):
        prepared = self.prepared(selector=True)
        for invalid, reason in (("```choice\nFORGED\n```", "end_turn"),
                                ("SYNTHETIC no choice", "end_turn"), ("```choice\nA\n```", "max_tokens")):
            request = self.request(prepared)
            request["messages"].extend(pair("write-answer", "write", self.cwd + "/output/answer.md", invalid))
            with self.subTest(output=invalid, stop_reason=reason), self.assertRaises(ContractError):
                evidence.verify_normal_session(request, prepared, cwd=self.cwd, label="select.seq2",
                    response={"stop_reason": reason, "content": [{"type": "text", "text": "SYNTHETIC done."}]},
                    native_output=invalid, saved_output=invalid,
                    mutation_witnesses=self.completion_witnesses(request, notes=invalid))

    def test_author_cannot_substitute_stdout_for_empty_saved_notes(self):
        prepared = self.prepared()
        request = self.request(prepared)
        request["messages"].extend(pair("empty-notes", "write", self.cwd + "/output/answer.md", ""))
        notes = "<notes>SYNTHETIC stdout-only notes.</notes>"
        with self.assertRaises(ContractError):
            evidence.verify_normal_session(request, prepared, cwd=self.cwd, label="inv2.a1",
                response={"stop_reason": "end_turn", "content": [{"type": "text", "text": notes}]},
                native_output=notes, saved_output="",
                harvested_strategy=(self.root / "author/harness/systemprompt.md").read_text(encoding="utf-8"),
                mutation_witnesses=self.completion_witnesses(request, notes=""))

    def test_earlier_completion_witness_accepts_only_block_cache_changes(self):
        for use_edit in (False, True):
            native = self.root / ("cache-edit" if use_edit else "cache-write")
            (native / "context/harness").mkdir(parents=True)
            path = native / "context/harness/systemprompt.md"
            fields = {"plan_system": "SYNTHETIC plan", "answer_system": "SYNTHETIC A", "rank_system": "SYNTHETIC rank"}
            request = {"messages": pair("strategy-write", "write", str(path), json.dumps(fields))}
            if use_edit:
                request["messages"].extend([{"role": "assistant", "content": [{"type": "tool_use",
                    "id": "strategy-edit", "name": "edit", "caller": {"type": "direct"}, "input": {
                        "filePath": str(path), "oldString": "SYNTHETIC A", "newString": "SYNTHETIC B"}}]},
                    {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "strategy-edit",
                        "content": "Edit applied successfully."}]}])
                fields["answer_system"] = "SYNTHETIC B"
            actual = json.dumps(fields, indent=2) + "\n"
            path.write_text(actual, encoding="utf-8")
            # Nested payload data is protected even when its key happens to be cache_control.
            request["messages"][-2]["content"][0]["input"]["opaque"] = {"cache_control": "SYNTHETIC argument"}
            request["messages"][-1]["content"][0]["content"] = [{"type": "text", "text": "SYNTHETIC applied",
                "opaque": {"cache_control": "SYNTHETIC result"}}]
            for variant in ("add", "remove", "move"):
                earlier = copy.deepcopy(request)
                if variant != "add":
                    earlier["messages"][-2]["content"][0]["cache_control"] = {"type": "ephemeral"}
                witnesses = evidence.observe_mutation_completion(earlier, cwd=native,
                    slot="SYNTHETIC earlier observation", previous=[])
                later = copy.deepcopy(earlier)
                later["messages"][-2]["content"][0].pop("cache_control", None)
                if variant in ("add", "move"):
                    later["messages"][-1]["content"][0]["cache_control"] = {"type": "ephemeral"}
                if variant == "add":
                    later["messages"][-2]["content"][0]["cache_control"] = {"type": "ephemeral"}
                before = digest(later)
                with self.subTest(edit=use_edit, cache=variant):
                    self.assertNotEqual(digest(earlier), before)
                    bound = evidence.bind_mutation_completion(later, cwd=str(native),
                        target="context/harness/systemprompt.md", actual=actual, witnesses=witnesses)
                    self.assertTrue(bound["actual_text_matches"])
                    self.assertEqual(evidence.observe_mutation_completion(later, cwd=native,
                        slot="SYNTHETIC later observation", previous=witnesses), witnesses)
                    self.assertEqual(digest(later), before)
            for mutation in ("nested_input", "nested_result", "result_text", "identity", "path", "strategy"):
                changed, harvested = copy.deepcopy(later), actual
                call, result = changed["messages"][-2]["content"][0], changed["messages"][-1]["content"][0]
                if mutation == "nested_input":
                    call["input"]["opaque"]["cache_control"] = "SYNTHETIC changed argument"
                elif mutation == "nested_result":
                    result["content"][0]["opaque"]["cache_control"] = "SYNTHETIC changed result"
                elif mutation == "result_text":
                    result["content"][0]["text"] = "SYNTHETIC changed tool result"
                elif mutation == "identity":
                    call["id"] = result["tool_use_id"] = "SYNTHETIC foreign mutation"
                elif mutation == "path":
                    call["input"]["filePath"] += ".foreign"
                else:
                    harvested += "SYNTHETIC changed strategy"
                with self.subTest(edit=use_edit, mutation=mutation), self.assertRaises(ContractError):
                    evidence.bind_mutation_completion(changed, cwd=str(native),
                        target="context/harness/systemprompt.md", actual=harvested, witnesses=witnesses)

    def test_normal_final_fingerprint_matches_native_newline_normalization(self):
        prepared = self.prepared()
        request = self.request(prepared)
        notes = "<notes>\r\nSYNTHETIC first line\r\nSYNTHETIC second line\r\n</notes>\r\n"
        request["messages"].extend(pair("write-notes", "write", self.cwd + "/output/answer.md", notes))
        proof = evidence.verify_normal_session(request, prepared, cwd=self.cwd, label="inv2.a1",
            native_output=notes.replace("\r\n", "\n"), saved_output=notes,
            response={"stop_reason": "end_turn", "content": [{"type": "text", "text": "\r\n" + notes}]},
            harvested_strategy=(self.root / "author/harness/systemprompt.md").read_text(encoding="utf-8"),
            mutation_witnesses=self.completion_witnesses(request, notes=notes))
        native_answer = notes.replace("\r\n", "\n")
        self.assertEqual(proof["native_output_normalized_sha256"], hashlib.sha256(native_answer.strip().encode()).hexdigest())
        self.assertEqual(proof["final_normalized_sha256"], hashlib.sha256(native_answer.strip().encode()).hexdigest())
        self.assertEqual(proof["final_sha256"], hashlib.sha256(("\r\n" + notes).encode()).hexdigest())

    def saved_selector(self, saved, final, actual, *, failed_target=None):
        from harness2.core.selection import _CHOICE

        prepared = self.prepared(selector=True)
        base = self.request(prepared)
        first = {**base, "messages": base["messages"][:1]}
        tools, returned = [], []
        for candidate in ("A", "B"):
            entry = next(e for e in prepared["manifest"]["required_evidence"] if e["path"] == "candidates/" + candidate + ".md")
            chunk = entry["chunks"][0]
            messages = pair("read-" + candidate, "read", self.cwd + "/context/" + chunk["path"],
                prepared["evidence_files"][chunk["path"]], limit=chunk["limit"])
            tools.append(messages[0]["content"][0])
            returned.append(messages[1]["content"][0])
        second = copy.deepcopy(first)
        second["messages"].extend([{"role": "assistant", "content": tools}, {"role": "user", "content": returned}])
        requests = [first, second]
        content = [tools]
        if saved is not None:
            written = pair("write-answer", "write", self.cwd + "/output/answer.md", saved)
            third = copy.deepcopy(second)
            third["messages"].extend(written)
            requests.append(third)
            content.append(written[0]["content"])
        if failed_target is not None:
            failed = [{"role": "assistant", "content": [{"type": "tool_use", "id": "failed-edit", "name": "edit",
                "caller": {"type": "direct"}, "input": {"filePath": self.cwd + "/" + failed_target,
                    "oldString": "SYNTHETIC missing text", "newString": "SYNTHETIC unapplied replacement"}}]},
                {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "failed-edit",
                    "is_error": True, "content": "SYNTHETIC edit failed"}]}]
            following = copy.deepcopy(requests[-1])
            following["messages"].extend(failed)
            requests.append(following)
            content.append(failed[0]["content"])
        content.append([{"type": "text", "text": final}])
        prefix = "p3b-02.adaptive.editor.select.seq2"
        slots = [prefix + f".t{i:02}" for i in range(1, len(requests) + 1)]
        intents = {slot: {"request": request, "request_sha256": digest(request)} for slot, request in zip(slots, requests)}
        results = {slot: {"role": "native_selector", "status": "response", "response": {
            "text": final if index == len(slots) - 1 else "", "provider_response": {
                "stop_reason": "end_turn" if index == len(slots) - 1 else "tool_use", "content": blocks}}}
            for index, (slot, blocks) in enumerate(zip(slots, content))}
        guard = history.HistoryGuard(lambda slot, role, request: results[slot], prefix)
        for slot in slots:
            guard(slot, "native_selector", intents[slot]["request"])
        witnesses = self.completion_witnesses(requests[-1], notes=saved)
        for witness in witnesses:
            witness["observed_slot_id"] = slots[-1]
            witness["sha256"] = digest({key: value for key, value in witness.items() if key != "sha256"})
        normal = evidence.verify_normal_session(requests[-1], prepared, cwd=self.cwd, label="select.seq2",
            response=results[slots[-1]]["response"]["provider_response"], native_output=actual,
            saved_output=saved, mutation_witnesses=witnesses)
        search = self.root / "saved-selector"
        audit = search / "editor-audit/c1-contracts/select.seq2"
        audit.mkdir(parents=True)
        (audit / "manifest.json").write_text(json.dumps(prepared["manifest"], sort_keys=True, indent=2) + "\n", encoding="utf-8")
        (audit / "configured-agent-prompt.md").write_text(prepared["authoring_system_text"], encoding="utf-8")
        for name, value in prepared["evidence_files"].items():
            target = audit / "context-view" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(value, encoding="utf-8")
        session = {"status": "valid", "model_backed": True, "authentic_eligible": True, "terminal_note_used": False,
            "result_slots": slots, "history_guard_audits": guard.audits, "mutation_witnesses": witnesses,
            "information_proof": evidence.verify_information_before_decision(second, prepared, cwd=self.cwd, label="select.seq2"),
            "normal_session_proof": normal, "input_snapshot": {"files": prepared["manifest"]["context_inventory"]},
            "selector_answer": actual}
        choice = _CHOICE.search(actual)
        assert choice is not None
        selection = {"ok": True, "fallback": False, "chosen_id": choice.group(1).strip(), "id_map": {"A": "c1", "B": "c2"}}
        def validate():
            # Storage loading alone is replaced; history, source, inspection and choice validation are real.
            with patch.object(editor, "validate_persisted_sessions", return_value={"select.seq2": session}):
                return editor.validate_selector_evidence(search=search, study_sha256="a" * 64, pilot="p3b-02",
                    fixture=True, session=session, results=results, intents=intents, selection=selection)
        return session, selection, validate

    def test_saved_selector_accepts_output_representation_but_rejects_changed_content(self):
        text = "<why>SYNTHETIC choice.</why>\n```choice\nA\n```"
        session, selection, validate = self.saved_selector(None, text, text)
        for answer in (text, "\n" + text + "\n", "\r\n" + text.replace("\n", "\r\n") + "\r\n"):
            session["selector_answer"] = answer
            with self.subTest(answer_hash=hashlib.sha256(answer.encode()).hexdigest()):
                self.assertTrue(validate()["passed"])
        for answer in (text.replace("\nA\n", "\nB\n"), text.replace("SYNTHETIC", "CHANGED")):
            session["selector_answer"] = answer
            with self.subTest(changed_hash=hashlib.sha256(answer.encode()).hexdigest()), self.assertRaises(ContractError):
                validate()
        session["selector_answer"] = text
        selection["chosen_id"] = "B"
        with self.assertRaises(ContractError):
            validate()

    def test_saved_selector_replays_actual_written_output_with_different_final_prose(self):
        saved = "<why>SYNTHETIC saved rationale.</why>\n```choice\nB\n```"
        final = "<why>SYNTHETIC final rationale differs.</why>\n```choice\nB\n```"
        session, _, validate = self.saved_selector(saved, final, saved)
        self.assertFalse(session["normal_session_proof"]["final_matches_native_output"])
        self.assertTrue(validate()["passed"])
        session["selector_answer"] = saved.replace("saved", "unwitnessed")
        with self.assertRaises(ContractError):
            validate()

    def test_failed_permitted_edit_does_not_replace_successful_saved_output(self):
        saved = "<why>SYNTHETIC saved rationale.</why>\n```choice\nB\n```"
        session, _, validate = self.saved_selector(saved, "SYNTHETIC done.", saved,
            failed_target="output/answer.md")
        self.assertTrue(session["normal_session_proof"]["notes_mutation_binding"]["actual_text_matches"])
        self.assertTrue(validate()["passed"])

    def test_failed_edit_of_candidate_evidence_still_violates_selector_ownership(self):
        saved = "<why>SYNTHETIC saved rationale.</why>\n```choice\nB\n```"
        with self.assertRaises(ContractError):
            _, _, validate = self.saved_selector(saved, "SYNTHETIC done.", saved,
                failed_target="context/candidates/A.md")
            validate()

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
            native_output="```choice\nA\n```",
            response={"stop_reason": "end_turn", "content": [{"type": "text", "text": "```choice\nA\n```"}]})
        self.assertTrue(final["passed"])
        with self.assertRaisesRegex(ContractError, "no valid candidate choice"):
            evidence.verify_normal_session(request, prepared, cwd=self.cwd, label="select.seq2",
                native_output="```choice\nFORGED\n```",
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
