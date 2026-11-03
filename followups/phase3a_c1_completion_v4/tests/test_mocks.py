"""Actual native/OpenCode and owned SDK-worker coverage for the R3 boundary."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest, file_hash
from followups.phase3a_c1_completion_v4 import accounting, workflow
from followups.phase3a_c1_completion_v4.mocks import StudyMock


@unittest.skipUnless(Path("/opt/phase3a-opencode").is_dir(), "requires pinned actual OpenCode")
class ActualCLITests(unittest.TestCase):
    def setUp(self):
        workflow.BASE.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="r3-actual-cli-", dir=workflow.BASE)
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name)
        name = "followups/phase3a_c1_completion_v4/workflow.py"
        files = {name: file_hash(workflow.ROOT / name)}
        self.source = {"kind": "isolated-controller-test-source", "files": files,
                       "sha256": digest(files), "fixture_nonce": self.output.name}
        self.runtime = workflow.runtime_identity()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(workflow, "source_identity", return_value=self.source))
        stack.enter_context(patch.object(workflow, "runtime_identity", return_value=self.runtime))
        self.study_path = self.output / "release/study.json"
        self.study = workflow.prepare(self.study_path.parent, source=self.source, runtime=self.runtime)
        self.grant_path = self.study_path.parent / "mock-grant.json"
        self.grant_path.write_text(json.dumps(workflow.make_grant(self.study_path, True)), encoding="utf-8")
        self.native_path, self.journal = workflow.paths(self.study, True)
        self.addCleanup(self.remove_run)

    def remove_run(self):
        for target, boundary in ((self.native_path.parent, workflow.NATIVE),
                                 (self.journal.parent.parent, workflow.BASE)):
            self.assertTrue(target.is_relative_to(boundary) and target != boundary)
            if target.exists():
                shutil.rmtree(target)

    def test_more_than_seven_ordinary_rounds_complete_with_unchanged_dom(self):
        with StudyMock() as mock:
            summary = workflow.run(self.study_path, self.grant_path, stage="readiness", transport=mock.transport)
            state = accounting.replay(self.journal)
            self.assertEqual(state["attempts"], 80, json.dumps(summary, sort_keys=True))
            self.assertEqual(mock.http_calls, 80)
            self.assertEqual(state["status"], "ready")
            self.assertEqual(state["reserved_micro_usd"], 0)
            self.assertTrue(all(row["status"] == "response" for row in state["results"].values()))
            self.assertEqual(Counter(row["role"] for row in state["results"].values()),
                             {"plan": 4, "answer": 40, "rank": 4, "editor": 32})
            sessions = mock.proofs()["p3a-01"]
            self.assertEqual({name: row["ordinary_rounds"] for name, row in sessions.items()},
                             {"inv1.a1": 11, "dom1.a1": 10, "agg1.a1": 11})
            for proof in sessions.values():
                self.assertTrue(proof["normal_final"])
                self.assertTrue(proof["notes_reread_model_visible"])
                self.assertTrue(proof["decision_after_complete_evidence"])
                self.assertEqual(proof["evidence_read_batches"], 4)
                self.assertGreater(proof["ordinary_rounds"], 7)
                self.assertLessEqual(proof["ordinary_rounds"], 15)
                self.assertFalse(proof.get("terminal_note_used", False))
            self.assertFalse(sessions["dom1.a1"]["effective_changed"])
            self.assertTrue(sessions["inv1.a1"]["effective_changed"])
            self.assertTrue(sessions["agg1.a1"]["effective_changed"])
            branch = workflow.checked(workflow.read(self.native_path / "branches/p3a-01-adaptive.json"))
            self.assertEqual(branch["result"]["status"], "complete")
            self.assertFalse(branch["result"]["authentic"], "a synthetic fixture cannot establish live authenticity")
            proof = workflow._readiness_check(self.study, self.native_path, state,
                                              workflow.saved(self.study_path, self.study, state, True), True)
            self.assertTrue(proof["passed"])
            self.assertFalse((self.native_path / "readiness-failure.json").exists())
            self.assertFalse((self.native_path / "readiness-review.json").exists())

    def test_terminal_sixteenth_is_refused_before_intent_or_sdk(self):
        with StudyMock(fixture_mode="terminal") as mock:
            summary = workflow.run(self.study_path, self.grant_path, stage="readiness", transport=mock.transport)
            state = accounting.replay(self.journal)
            self.assertEqual(state["attempts"], 27, json.dumps(summary, sort_keys=True))
            self.assertEqual(mock.http_calls, 27)
            self.assertEqual(state["status"], "ready")
            self.assertEqual(state["reserved_micro_usd"], 0)
            self.assertTrue(all(row["status"] == "response" for row in state["results"].values()))
            self.assertEqual(Counter(row["role"] for row in state["results"].values()),
                             {"plan": 1, "answer": 10, "rank": 1, "editor": 15})
            self.assertFalse(any(slot.endswith(".t16") for slot in state["intents"]))
            self.assertFalse(any(row["role"] in {"group", "quality", "fixed_selector"}
                                 for row in state["results"].values()))
            stop = workflow.checked(workflow.read(self.native_path / "readiness-failure.json"))
            self.assertEqual(stop["reason"], "forced_terminal_control_before_dispatch")
            self.assertFalse(stop["unknown_charge_inferred"])
            self.assertFalse(summary["readiness_passed"])
            self.assertFalse((self.native_path / "readiness-review.json").exists())
            before = mock.http_calls
            with self.assertRaises(ContractError):
                workflow.run(self.study_path, self.grant_path, stage="all", transport=mock.transport)
            self.assertEqual(mock.http_calls, before)
