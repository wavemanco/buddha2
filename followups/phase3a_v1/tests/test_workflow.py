"""Paired persistence, blind native judging and engineering-only progression."""
from __future__ import annotations

import copy
import json
import shutil
import tempfile
import threading
import unittest
from collections import Counter
from pathlib import Path
from typing import Any
from unittest.mock import patch

from harness2.core.proposer import Proposer, Reply
from harness2.core.spec import ChannelSpec

from buddha2 import phase2_am1_controls as am1
from buddha2.artifacts import ContractError, file_hash
from followups.phase3a_v1 import accounting, native, strategy
from followups.phase3a_v1 import workflow as w


class FixtureTransport:
    """No SDK/network: known usage and explicit synthetic responses only."""
    fixture = True

    def __init__(self, study: dict, *, fault: str | None = None):
        self.study, self.fault = study, fault
        self.calls: list[tuple[str, str]] = []
        self.context = threading.local()
        self.adaptive_prefixes = {native.Phase3NativeAssessment.slot_prefix(row["id"])
                                 for row in study["assessment_plan"] if row["arm"] == "adaptive"}

    def select(self, role: str, slot: str):
        self.context.slot = slot

    def create(self, role: str, request: dict) -> dict:
        slot = self.context.slot
        self.calls.append((slot, role))
        payload: Any
        if role == "plan":
            payload = {"angles": [{"id": f"angle-{i:02}", "angle": f"Synthetic direction {i}"}
                                  for i in range(1, 11)]}
        elif role == "rank":
            payload = {"order": [r["id"] for r in reversed(json.loads(request["messages"][0]["content"])["responses"])]}
        elif role == "fixed_selector":
            candidates = json.loads(request["messages"][0]["content"])["candidates"]
            payload = {"candidate_id": "foreign" if self.fault == "selector" else candidates[0]["id"]}
        elif role == "group":
            run, _ = w._paths(self.study, True)
            if not (run / "seals" / (self.study["slots"][slot]["pair"] + ".json")).is_file():
                raise AssertionError("a judge saw outputs before the pair was sealed")
            payload = {"groups": [list(range(10))]}
        elif role == "quality":
            payload = {"score": 7 if any(slot.startswith(p + ".") for p in self.adaptive_prefixes) else 8}
        else:
            payload = None
        text = json.dumps(payload) if payload is not None else "Synthetic useful answer " + slot
        usage = {"input_tokens": 80, "output_tokens": 24, "cache_creation_input_tokens": 0,
                 "cache_read_input_tokens": 0, "cache_creation": {
                     "ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 0},
                 "service_tier": "standard", "inference_geo": "global"}
        if role == "group":
            usage = am1.normalize_group_usage({"prompt_tokens": 80, "completion_tokens": 24, "total_tokens": 104,
                     "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                     "completion_tokens_details": {"reasoning_tokens": 0}}, "default")
        if self.fault == "unknown" or self.fault == "unknown-quality" and role == "quality":
            usage["unsupported_usage"] = 1
        return {"model": request["model"], "text": text, "usage": usage,
                "service_tier": "default" if role == "group" else "standard",
                "stop_reason": "stop" if role == "group" else "end_turn",
                "content": [{"type": "text", "text": text}]}


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        w.RESULTS.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="workflow-", dir=w.RESULTS)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # Snapshot only this test's stable source: other agents may be editing
        # their files while these isolated controller tests run.
        name = "followups/phase3a_v1/workflow.py"
        files = {name: file_hash(w.ROOT / name)}
        source = {"schema": "fixture-source", "files": files, "sha256": w.json_sha(files)}
        self.addCleanup(patch.stopall)
        patch.object(w, "source_identity", return_value=source).start()
        patch.object(w, "runtime_identity", return_value={"fixture": True}).start()
        # A unique release directory gives every test its own immutable study
        # identity without mutating the frozen task manifest or execution IDs.
        source["fixture_nonce"] = self.root.name
        source["sha256"] = w.json_sha(source)
        w.prepare(self.root / "release")
        self.study_path = self.root / "release/study.json"
        self.study = w.load_study(self.study_path)
        self.grant_path = self.root / "grant.json"
        authority = {"study_sha256": self.study["study_sha256"], "authorization_id": "workflow-fixture",
            "authorized": False, "cap_micro_usd": 205860000, "canary_cap_micro_usd": 50860000,
            "expansion_authorized": False, "control_policy_sha256": am1.CONTROL_SHA256,
            "billing_profile": am1.BILLING_PROFILE}
        grant = {"kind": "phase3a-grant-v1", "fixture": True,
            **{k: self.study[k] for k in ("study_sha256", "source_sha256", "policy_sha256", "launcher_sha256")},
            "authority": authority}
        w._publish(self.grant_path, w._seal(grant, "grant_sha256"))
        self.run_path, self.journal = w._paths(self.study, True)
        self.addCleanup(self._remove_run)

    def _remove_run(self):
        import shutil
        if self.run_path.exists():
            shutil.rmtree(self.run_path)

    def proposer_factory(self, **kwargs):
        study = self.study

        class FixtureProposer(Proposer):
            def call(self, mission, context_dir=None, label="", **options):
                harness = Path(self.audit_dir) / "synthetic-harvest" / label
                shutil.copytree(Path(context_dir) / "harness", harness)
                value = strategy.validate_harness(harness)["strategy"]
                value["answer_system"] += "\nSynthetic permitted " + label
                (harness / "systemprompt.md").write_text(json.dumps(value), encoding="utf-8")
                reply = Reply(label=label, text="Synthetic permitted edit", ok=True, attempts=1, workspace=harness)
                self._calls.append(reply)
                return reply

            def phase3a_evidence(self):
                return {"fixture": True, "study_sha256": study["study_sha256"],
                        "backend": "synthetic-test", "model": "no-model", "sessions": {}}

        return FixtureProposer(ChannelSpec("opencode", "anthropic/claude-opus-5", effort="high", steps=8,
                                           timeout=600), audit_dir=kwargs["audit_dir"])

    def execute(self, transport: FixtureTransport, stage="first"):
        return w.run(self.study_path, self.grant_path, stage=stage, transport=transport,
                     proposer_factory=self.proposer_factory, cutoff="2026-10-28T20:00:00Z")

    def test_full_pairs_first_review_duplicate_and_zero_call_exact_report_replay(self):
        transport = FixtureTransport(self.study)
        first = self.execute(transport)
        self.assertEqual(first["primary_scored"], 2)
        self.assertTrue(first["first_assessments_done"])
        self.assertFalse(first["first_assessments_closed"])
        self.assertEqual(len(transport.calls), 127)
        self.assertEqual({self.study["slots"][s]["pair"] for s, _ in transport.calls}, {w.FIRST})
        before = len(transport.calls)
        with self.assertRaises(ContractError):
            self.execute(transport, "remaining")
        self.assertEqual(len(transport.calls), before)
        first_snapshot = w.snapshot(self.study_path, self.grant_path, True)
        self.assertLess(first_snapshot["analysis"]["pairs"][0]["adaptive_minus_fixed"], 0)
        primary = first_snapshot["saved"]["assessments"][w._assessment_id(self.study, w.FIRST, "fixed")]
        duplicate = first_snapshot["saved"]["assessments"][w._assessment_id(self.study, w.FIRST, "fixed", diagnostic=True)]
        self.assertNotEqual(primary["requests"][0]["slot_id"], duplicate["requests"][0]["slot_id"])
        self.assertEqual(primary["requests"][0]["request_sha256"], duplicate["requests"][0]["request_sha256"])
        w.review_first(self.study_path, self.grant_path, True)
        final = self.execute(transport, "remaining")
        self.assertEqual(final["status"], "mock-complete")
        self.assertEqual(final["primary_scored"], 8)
        self.assertEqual(len(transport.calls), 502)
        self.assertEqual(Counter(role for _, role in transport.calls), {
            "plan": 40, "answer": 400, "rank": 40, "fixed_selector": 4, "group": 9, "quality": 9})
        full = w.snapshot(self.study_path, self.grant_path, True)
        self.assertLess(full["analysis"]["mean_adaptive_minus_fixed"], 0)
        self.assertIsNone(full["analysis"]["selected_method"])
        self.assertFalse(full["summary"]["authentic_live_path"])
        self.assertTrue(all(r["inference_accounting"]["spent_micro_usd"] > 0 for r in full["rows"]))
        self.assertEqual(full["coverage"]["scheduled_slots"], 775)
        before = len(transport.calls)
        self.assertEqual(self.execute(transport, "remaining"), final)
        self.assertEqual(len(transport.calls), before)
        for name in ("report", "replay"):
            w.report(self.study_path, self.grant_path, self.root / name, True)
        files = sorted(p.name for p in (self.root / "report").iterdir())
        self.assertEqual(len(files), 7)
        self.assertTrue(all((self.root / "report" / n).read_bytes() == (self.root / "replay" / n).read_bytes()
                            for n in files))
        seal_path = self.run_path / "seals/p3a-04.json"
        seal = w._read(seal_path)
        seal.pop("sha256")
        seal["journal_prefix"] = {"index": 0, "event_sha256": None}
        seal_path.write_bytes(w._bytes(w._seal(seal)))
        with self.assertRaises(ContractError):
            self.execute(transport, "remaining")
        self.assertEqual(len(transport.calls), before)

    def test_unknown_is_reportable_and_blocks_resume_without_a_second_call(self):
        transport = FixtureTransport(self.study, fault="unknown")
        result = self.execute(transport)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(result["journal_status"], "blocked-unknown")
        self.assertGreater(result["reserved_micro_usd"], 0)
        snap = w.snapshot(self.study_path, self.grant_path, True)
        self.assertEqual(snap["coverage"]["slot_counts"]["unknown_liability"], 1)
        with self.assertRaises(ContractError):
            self.execute(transport)
        self.assertEqual(len(transport.calls), 1)

    def test_resealed_study_and_wrong_mode_grant_fail_before_transport(self):
        transport = FixtureTransport(self.study)
        grant = w._read(self.grant_path)
        grant["fixture"] = False
        grant.pop("grant_sha256")
        self.grant_path.write_bytes(w._bytes(w._seal(grant, "grant_sha256")))
        with self.assertRaises(ContractError):
            self.execute(transport)
        self.assertEqual(transport.calls, [])
        changed = copy.deepcopy(self.study)
        changed["parent_decision_sha256"] = "0" * 64
        changed.pop("study_sha256")
        self.study_path.write_bytes(w._bytes(w._seal(changed, "study_sha256")))
        with self.assertRaises(ContractError):
            w.load_study(self.study_path)

    def test_unknown_quality_returns_incomplete_evidence_and_never_continues(self):
        transport = FixtureTransport(self.study, fault="unknown-quality")
        result = self.execute(transport)
        self.assertEqual(result["journal_status"], "blocked-unknown")
        self.assertEqual(Counter(role for _, role in transport.calls)["group"], 1)
        self.assertEqual(Counter(role for _, role in transport.calls)["quality"], 1)
        before = len(transport.calls)
        w.report(self.study_path, self.grant_path, self.root / "unknown-report", True)
        snap = w.snapshot(self.study_path, self.grant_path, True)
        self.assertEqual(snap["coverage"]["slot_counts"]["not_needed_nonhead"], 9)
        with self.assertRaises(ContractError):
            self.execute(transport)
        self.assertEqual(len(transport.calls), before)

    def test_invalid_selector_preserves_six_candidates_and_no_replacement_final(self):
        transport = FixtureTransport(self.study, fault="selector")
        result = self.execute(transport)
        self.assertEqual(result["primary_scored"], 1)
        self.assertTrue(result["first_assessments_done"])
        snap = w.snapshot(self.study_path, self.grant_path, True)
        fixed = snap["saved"]["branches"][w.FIRST, "fixed"]["result"]
        self.assertEqual(len(fixed["candidates"]), 6)
        self.assertTrue(all(c["status"] == "complete" for c in fixed["candidates"]))
        self.assertIsNone(fixed["portfolio"])
        self.assertEqual(fixed["reason"], "invalid_fixed_selection")
        self.assertEqual(Counter(role for _, role in transport.calls)["fixed_selector"], 1)
        self.assertEqual(Counter(role for _, role in transport.calls)["group"], 1)
        self.assertEqual(snap["coverage"]["slot_counts"]["skipped_missing_final"], 22)
        before = len(transport.calls)
        w.review_first(self.study_path, self.grant_path, True)
        self.assertEqual(len(transport.calls), before)

    def test_known_assessment_exhaustion_closes_missing_slots_without_fake_scores(self):
        branch = {"result": {"portfolio": {"placeholder": True}}}
        saved = {"seals": {w.FIRST: {}}, "branches": {(w.FIRST, a): branch for a in w.ARMS}, "assessments": {}}
        self.assertFalse(w._first_done(self.study, saved, {"assessment_stopped": False}))
        self.assertTrue(w._first_done(self.study, saved, {"assessment_stopped": True}))
        state = {"results": {}, "assessment_stopped": True}
        saved["branches"] = {}
        coverage = w._coverage(self.study, state, saved)
        self.assertEqual(coverage["slot_counts"]["not_attempted_assessment_budget"], 99)
        self.assertEqual(coverage["slot_counts"]["not_attempted"], 676)

    def test_saved_later_request_checked_before_earlier_missing_calls(self):
        transport = FixtureTransport(self.study)
        ledger = w._ledger(self.study, w._grant(self.study, self.grant_path, True), transport)
        entry = self.study["tasks"][-1]
        task = w._task(entry)
        run_id = w._fixed_id(self.study, entry["pilot_id"]) + "/candidate-06"
        slot = strategy.slot_ids(run_id)["plan"]
        request = strategy.render_strategy_request("plan", task, strategy.validate_harness(self.study_path.parent / "seed")["strategy"])
        # Accounting knows the immutable scope but deliberately does not know
        # benchmark prompt semantics. The workflow must catch this corruption
        # globally before it considers a missing first-pair request.
        request["messages"][0]["content"] += " altered task"
        with patch.object(accounting, "_admit", return_value=None):
            transport.select("plan", slot)
            ledger.dispatch(slot, "plan", request)
        before = len(transport.calls)
        with self.assertRaises(ContractError):
            self.execute(transport)
        self.assertEqual(len(transport.calls), before)

    def test_existing_journal_rejects_changed_authority_and_unknown_contents_before_calls(self):
        transport = FixtureTransport(self.study)
        self.journal.mkdir(parents=True)
        unexplained = self.journal / "unexpected.json"
        unexplained.write_text("{}", encoding="utf-8")
        with self.assertRaises(ContractError):
            w.preflight(self.study_path, self.grant_path, True)
        unexplained.unlink()
        orphan = self.run_path / "search"
        orphan.mkdir()
        with self.assertRaises(ContractError):
            w.preflight(self.study_path, self.grant_path, True)
        orphan.rmdir()
        w._ledger(self.study, w._grant(self.study, self.grant_path, True), transport)
        grant = w._read(self.grant_path)
        grant.pop("grant_sha256")
        grant["authority"]["authorization_id"] = "different-fixture-authority"
        self.grant_path.write_bytes(w._bytes(w._seal(grant, "grant_sha256")))
        with self.assertRaises(ContractError):
            w.preflight(self.study_path, self.grant_path, True)
        self.assertEqual(transport.calls, [])

    def test_component_integrity_stop_persists_global_hold_outside_dispatch(self):
        transport = FixtureTransport(self.study)
        with patch.object(strategy, "fixed_best6", side_effect=accounting.IntegrityStop("provenance mismatch")):
            result = self.execute(transport)
        self.assertEqual(result["journal_status"], "halted-integrity")
        self.assertEqual(transport.calls, [])
        with self.assertRaises(ContractError):
            self.execute(transport)
        self.assertEqual(transport.calls, [])

    def test_held_invalid_artifacts_report_no_science_and_never_follow_links(self):
        transport = FixtureTransport(self.study)
        ledger = w._ledger(self.study, w._grant(self.study, self.grant_path, True), transport)
        ledger.halt("fixture_provenance_mismatch")
        malformed = w._branch_path(self.run_path, w.FIRST, "fixed")
        malformed.parent.mkdir(parents=True)
        malformed.write_text("{", encoding="utf-8")
        outside = self.root / "outside.txt"
        outside.write_text("This ordinary fixture must not be read through the link.", encoding="utf-8")
        search = self.run_path / "search"
        search.mkdir()
        (search / "untrusted-link").symlink_to(outside)
        result = w.snapshot(self.study_path, self.grant_path, True)
        self.assertEqual(result["summary"]["journal_status"], "halted-integrity")
        self.assertTrue(all(r["status"] == "unvalidated_integrity_hold" for r in result["rows"]))
        self.assertIsNone(result["analysis"]["mean_adaptive_minus_fixed"])
        failure = result["analysis"]["held_evidence_failure"]
        self.assertEqual(failure["scientific_use"], "disqualified")
        self.assertEqual(failure["artifacts"]["search/untrusted-link"], {"status": "unread_nonordinary"})
        self.assertEqual(failure["artifacts"]["branches/p3a-01-fixed.json"]["sha256"], file_hash(malformed))
        w.report(self.study_path, self.grant_path, self.root / "held-report", True)
        with self.assertRaises(ContractError):
            self.execute(transport)
        self.assertEqual(transport.calls, [])

    def test_tool_only_editor_reply_is_classified_as_a_known_tool_response(self):
        slot = next(s for s, meta in self.study["slots"].items() if meta["role"] == "editor")
        state = {"results": {slot: {"status": "response", "role": "editor", "response": {
            "text": "", "stop_reason": "tool_use", "provider_response": {"content": [
                {"type": "tool_use", "name": "read", "id": "synthetic", "input": {"filePath": "MISSION.md"},
                 "caller": {"type": "direct"}}]}}}}}
        coverage = w._coverage(self.study, state, {"branches": {}, "assessments": {}})
        self.assertEqual(coverage["slots"][slot], "known_tool_response")

    def test_later_partial_editor_proof_tamper_blocks_all_earlier_calls(self):
        from followups.phase3a_v1 import editor

        transport = FixtureTransport(self.study)
        w._ledger(self.study, w._grant(self.study, self.grant_path, True), transport)
        pilot = self.study["tasks"][-1]["pilot_id"]
        proof = w._search_root(self.run_path, pilot, "adaptive") / "editor-audit/phase3a-sessions/inv1.a1.started.json"
        w._publish(proof, {"binding": {"fixture": True, "study_sha256": "0" * 64, "pilot": pilot,
            "source_sha256": file_hash(Path(editor.__file__))}, "label": "inv1.a1"})
        with self.assertRaises(accounting.IntegrityStop):
            w.preflight(self.study_path, self.grant_path, True)
        with self.assertRaises(accounting.IntegrityStop):
            self.execute(transport)
        self.assertEqual(transport.calls, [])


if __name__ == "__main__":
    unittest.main()
