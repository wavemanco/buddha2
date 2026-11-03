"""Saved public synthetic transcript checks; no SDK, provider or native execution."""
from __future__ import annotations

import copy
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest
from followups.phase3a_c1_completion_v3 import evidence


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def seal(value: dict) -> dict:
    return {**value, "sha256": digest({k: v for k, v in value.items() if k != "sha256"})}


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        fixture_value = os.environ.get("BUDDHA2_R2_EVIDENCE_FIXTURE")
        if fixture_value is None:
            self.skipTest("fresh R1 matrix fixture required; full verifier provisions it")
        fixture = Path(fixture_value)
        self.assertTrue(fixture.is_absolute() and ".." not in fixture.parts)
        native_root = evidence.ROOT / "runs/phase3a-compat-c1-v1/completion-v3" if os.name == "nt" else evidence.NATIVE
        self.assertTrue(fixture.is_relative_to(native_root))
        base = native_root / "unit-evidence"
        base.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=base)
        self.run_path = Path(self.temporary.name)
        self.assertTrue(self.run_path.resolve().is_relative_to(base.resolve()))
        self.addCleanup(self.temporary.cleanup)
        self.search = self.run_path / "search/p3a-01/adaptive"
        self.search.mkdir(parents=True)
        source_search = fixture / "search/p3a-01/adaptive"
        for part in ("editor-audit/c1-contracts", "editor-audit/phase3a-sessions", "editor-audit/conversation-deadlines"):
            shutil.copytree(source_search / part, self.search / part)
        for stage in ("base1", "inv1", "dom1", "agg1"):
            destination = self.search / "rollouts" / stage / "harness"
            destination.mkdir(parents=True)
            shutil.copyfile(source_search / "rollouts" / stage / "harness/systemprompt.md", destination / "systemprompt.md")
        from followups.phase3a_c1_completion_v3 import accounting
        self.branch = read(fixture / "branches/p3a-01-adaptive.json")
        self.state = accounting.replay(accounting.canonical_journal(self.branch["study_sha256"], True))
        self.native = self.branch["result"]
        self.c1 = self.branch["c1_evidence"]
        manifest = read(accounting.canonical_journal(self.branch["study_sha256"], True) / "manifest.json")
        self.study = {"study_sha256": self.state["study_sha256"], **manifest["inputs"]["bindings"]}
        self.addCleanup(patch.stopall)
        patch.object(evidence, "NATIVE", base).start()
        # These guards fail if the pure report parser acquires network/client work.
        patch("socket.socket", side_effect=AssertionError("network forbidden")).start()
        patch("followups.phase3a_compat_c1_v1.mocks.SDKMock", side_effect=AssertionError("SDK mock construction forbidden")).start()
        patch("followups.phase3a_c1_completion_v3.transport.Transport", side_effect=AssertionError("transport forbidden")).start()

    def check(self):
        return evidence.verify_readiness(self.study, self.run_path, self.state, self.branch, True)

    def rebind(self, label: str):
        session = self.native["editor_evidence"]["sessions"][label]
        for row in session["requests"]:
            slot = row["slot_id"]
            intent, result = self.state["intents"][slot], self.state["results"][slot]
            intent["request_sha256"] = digest(intent["request"])
            result["request_sha256"] = intent["request_sha256"]
            result["intent_sha256"] = digest(intent)
            row["effective_sha256"] = digest(intent["request"])
            row["result_sha256"] = digest(result)
        target = self.search / "editor-audit/phase3a-sessions" / (label + ".settled.json")
        saved = read(target)
        saved["session"] = session
        target.write_text(json.dumps(seal(saved), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.branch = seal(self.branch)

    def test_positive_normal_readiness_and_stable_scope(self):
        original = digest(self.state)
        proof = self.check()
        self.assertTrue(proof["passed"])
        self.assertEqual(proof["readiness_adaptive_requests"], 68)
        self.assertEqual(proof["role_counts"], {"plan": 4, "answer": 40, "rank": 4, "editor": 20})
        self.assertEqual([s["effective_changed"] for s in proof["sessions"]], [True, False, True])
        self.assertTrue(proof["semantic_grounding_review_required"])
        self.assertEqual(digest(self.state), original)
        # Later fixed/judge work cannot change the sealed readiness proof.
        self.state["intents"]["later-fixed"] = {"cell": "p3a-01:fixed"}
        self.state["results"]["later-fixed"] = {"status": "response", "failure": None, "reserved_micro_usd": 0}
        self.assertEqual(proof, self.check())

    def test_absent_caller_normalizes_only_parser_copy_and_other_callers_reject(self):
        body: dict[str, Any] = {"messages": [{"role": "assistant", "content": [{"type": "tool_use", "id": "tool", "name": "read", "input": {}}]}]}
        before = copy.deepcopy(body)
        normalized: set[str] = set()
        actual = evidence._body(body, normalized)
        self.assertEqual(body, before)
        self.assertEqual(normalized, {"tool"})
        self.assertEqual(actual["messages"][0]["content"][0]["caller"], {"type": "direct"})
        for caller in (None, {"type": "server"}, {"type": "direct", "extra": True}):
            body["messages"][0]["content"][0]["caller"] = caller
            with self.subTest(caller=caller), self.assertRaises(ContractError):
                evidence._body(body, set())

    def test_missing_mission_delivery_rejects_even_with_valid_resealed_request(self):
        label = "inv1.a1"
        rows = self.native["editor_evidence"]["sessions"][label]["requests"]
        for row in rows[1:]:
            body = self.state["intents"][row["slot_id"]]["request"]
            for message in body["messages"]:
                if message.get("role") == "user" and isinstance(message.get("content"), list):
                    for block in message["content"]:
                        if block.get("tool_use_id") == "c1_mission":
                            block["content"] = "Mission read was issued but its content is missing."
        self.rebind(label)
        with self.assertRaisesRegex(ContractError, "absent or truncated"):
            self.check()

    def test_unexpected_system_layer_rejects(self):
        slot = "p3a-01.adaptive.editor.inv1.a1.t01"
        self.state["intents"][slot]["request"]["system"][0]["text"] += "\nUnspecified instruction layer."
        self.rebind("inv1.a1")
        with self.assertRaisesRegex(ContractError, "SYSTEM"):
            self.check()

    def test_missing_lossless_view_rejects(self):
        manifest = read(self.search / "editor-audit/c1-contracts/inv1.a1/manifest.json")
        chunk = manifest["required_evidence"][2]["chunks"][0]["path"]
        (self.search / "editor-audit/c1-contracts/inv1.a1/context-view" / chunk).unlink()
        with self.assertRaises(ContractError):
            self.check()

    def test_terminal_and_unknown_are_not_readiness(self):
        self.native["stage_dispositions"][0]["terminal_note_used"] = True
        self.branch = seal(self.branch)
        with self.assertRaisesRegex(ContractError, "normal eligible"):
            self.check()
        self.native["stage_dispositions"][0]["terminal_note_used"] = False
        self.branch = seal(self.branch)
        self.state["reserved_micro_usd"] = 11440000
        with self.assertRaisesRegex(ContractError, "hold/liability"):
            self.check()

    def test_missing_notes_reread_rejects(self):
        label = "inv1.a1"
        last = self.native["editor_evidence"]["sessions"][label]["requests"][-1]
        body = self.state["intents"][last["slot_id"]]["request"]
        for message in body["messages"]:
            if message.get("role") == "user" and isinstance(message.get("content"), list):
                for block in message["content"]:
                    if block.get("tool_use_id") == "c1_verify_notes":
                        block["content"] = "Notes reread content missing."
        self.rebind(label)
        with self.assertRaisesRegex(ContractError, "absent or truncated"):
            self.check()

    def test_verification_preface_and_suffix_still_fail_strict_readiness(self):
        label = "dom1.a1"
        slot = self.native["editor_evidence"]["sessions"][label]["requests"][-1]["slot_id"]
        original = copy.deepcopy(self.state["results"][slot]["response"])
        for prefix, suffix in (("Verified: unchanged and reread.\n\n", ""), ("", "\nVerified.")):
            with self.subTest(prefix=prefix, suffix=suffix):
                response = copy.deepcopy(original)
                response["text"] = prefix + original["text"] + suffix
                for block in response["provider_response"]["content"]:
                    if block.get("type") == "text":
                        block["text"] = prefix + block["text"] + suffix
                self.state["results"][slot]["response"] = response
                self.rebind(label)
                with self.assertRaisesRegex(ContractError, "one complete notes block"):
                    self.check()

    def test_foreign_saved_session_and_unsafe_run_reject(self):
        target = self.search / "editor-audit/phase3a-sessions/inv1.a1.settled.json"
        saved = read(target)
        saved["binding"]["study_sha256"] = "a" * 64
        target.write_text(json.dumps(seal(saved)), encoding="utf-8")
        with self.assertRaisesRegex(ContractError, "saved audit"):
            self.check()
        with self.assertRaises(ContractError):
            evidence.verify_readiness(self.study, self.run_path / ".." / "foreign", self.state, self.branch, True)


if __name__ == "__main__":
    unittest.main()
