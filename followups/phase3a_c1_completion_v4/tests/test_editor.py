"""R3 boundary checks: sixteen requests, strict replay and unchanged eligibility."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from buddha2.artifacts import ContractError, digest, write_once
from followups.phase3a_c1_completion_v4 import editor
from followups.phase3a_v1 import accounting, strategy


def raw(text: str = "SYNTHETIC") -> dict:
    return {"model": "claude-opus-5", "max_tokens": 16000, "stream": True,
            "thinking": {"type": "adaptive"}, "output_config": {"effort": "high"},
            "messages": [{"role": "user", "content": text}], "tools": []}


class EditorTests(unittest.TestCase):
    def setUp(self):
        root = (strategy.ROOT / "runs/phase3a-compat-c1-v1/completion-v4" if os.name == "nt"
                else Path("/results/phase3a-compat-c1-v1/completion-v4")) / "unit-editor"
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)

    def test_native_channel_build_and_frozen_body_parity(self):
        prop = editor.AccountedProposer(pilot="p3a-01", study_sha256="a" * 64,
            dispatch=lambda *a: self.fail("dispatch forbidden"), audit_dir=self.work / "audit",
            fixture=True, halt=lambda *a, **k: self.fail("unexpected halt"))
        self.assertEqual((prop.spec.steps, prop.spec.timeout), (16, 600))
        prop._local.url, prop._local.home = "http://127.0.0.1:1/v1", str(self.work)
        config = json.loads(prop.env()["OPENCODE_CONFIG_CONTENT"])
        self.assertEqual(config["agent"]["build"]["steps"], 16)
        old = editor.frozen.configuration(prop._local.url)
        old["agent"]["build"]["steps"] = 16
        self.assertEqual(config, old)
        body = raw()
        body["messages"] = [{"role": "assistant", "content": [
            {"type": "thinking", "thinking": "SYNTHETIC", "signature": "fixture"},
            {"type": "tool_use", "id": "read01", "name": "read", "input": {}, "caller": {"type": "direct"}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "read01", "content": "SYNTHETIC"}]}]
        body["system"] = [{"type": "text", "text": "SYNTHETIC", "cache_control": {"type": "ephemeral"}}]
        before = copy.deepcopy(body)
        for turn in (1, 8, 9, 15):
            self.assertEqual(editor.effective_request(body, turn=turn), editor.frozen.effective_request(body, turn=turn))
        self.assertEqual(body, before)

    def test_terminal_prefill_is_exactly_sixteen_and_preserves_raw_body(self):
        for content in ("SYNTHETIC ordinary user", [{"type": "tool_result", "tool_use_id": "fixture", "content": "SYNTHETIC"}]):
            ordinary = raw()
            ordinary["messages"][-1]["content"] = content
            with self.subTest(ordinary_content=content), self.assertRaises(ContractError):
                editor.effective_request(ordinary, turn=16)
        body = raw()
        body["messages"].append({"role": "assistant", "content": [{"type": "text", "text": editor.terminal_note()}]})
        before = copy.deepcopy(body)
        for turn in (None, 8, 15, 17, 0, True):
            with self.subTest(turn=turn), self.assertRaises(ContractError):
                editor.effective_request(body, turn=turn)
        actual = editor.effective_request(body, turn=16)
        self.assertEqual(actual["messages"][-1]["role"], "user")
        self.assertEqual(actual["messages"][-1]["content"], body["messages"][-1]["content"])
        self.assertEqual(body, before)
        body["messages"][-1]["content"][0]["text"] += "modified"
        with self.assertRaises(ContractError):
            editor.effective_request(body, turn=16)

    def test_actual_loopback_relay_sixteen_replay_and_seventeenth_rejection(self):
        seen, halted = [], []
        def dispatch(slot, role, request):
            seen.append((slot, role, request))
            return {"status": "response", "response": {"provider_response": {
                "id": "fixture", "type": "message", "role": "assistant", "model": "claude-opus-5",
                "content": [{"type": "text", "text": "SYNTHETIC"}], "stop_reason": "end_turn",
                "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1}}}}
        record: dict = {"fixture": True, "requests": []}
        def send(url, body):
            req = Request(url + "/messages", data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json", "x-api-key": editor._FALSE})
            with urlopen(req, timeout=5) as response:  # nosec B310: loopback-only fixture URL
                return response.read()
        with editor.relay(self.work, dispatch, "p3a-01.adaptive.editor.inv1.a1", record,
                          lambda *a, **k: halted.append((a, k))) as url:
            first = send(url, raw("first"))
            self.assertEqual(send(url, raw("first")), first)
            for turn in range(2, 17):
                body = raw(str(turn))
                if turn == 16:
                    body["messages"].append({"role": "assistant", "content": [{"type": "text", "text": editor.terminal_note()}]})
                send(url, body)
            with self.assertRaises(HTTPError) as error:
                send(url, raw("excess"))
            self.assertEqual(error.exception.code, 403)
        self.assertEqual(len(seen), 16)
        self.assertEqual(seen[-1][0], "p3a-01.adaptive.editor.inv1.a1.t16")
        self.assertEqual(record["local_response_replays"], 1)
        self.assertEqual(record["requests"][-1]["role_translation"], editor.terminal_translation())
        self.assertTrue(record["terminal_note_used"])
        self.assertEqual(len(halted), 1)

    def proof(self, count=16, terminal=True, changed=True):
        audit = self.work / "proof"
        snapshot = editor.input_snapshot({"systemprompt.md": json.dumps({
            "plan_system": "SYNTHETIC plan", "answer_system": "SYNTHETIC answer", "rank_system": "SYNTHETIC rank"}),
            **{name: "" for name in strategy.EMPTY_FILES}})
        binding = {"fixture": True, "study_sha256": "a" * 64, "pilot": "p3a-01",
            "source_sha256": hashlib.sha256(Path(editor.__file__).read_bytes()).hexdigest(),
            "editor_profile_sha256": digest(editor.profile())}
        requests, results, intents = [], {}, {}
        for turn in range(1, count + 1):
            slot = f"p3a-01.adaptive.editor.inv1.a1.t{turn:02}"
            body = raw(str(turn))
            translation = None
            if terminal and turn == 16:
                body["messages"].append({"role": "assistant", "content": [{"type": "text", "text": editor.terminal_note()}]})
                translation = editor.terminal_translation()
            request = editor.effective_request(body, turn=turn)
            result = {"role": "editor", "status": "response", "study_sha256": "a" * 64,
                "fixture": True, "request_sha256": digest(request)}
            requests.append({"slot_id": slot, "raw_sha256": "d" * 64,
                "effective_sha256": digest(request), "result_sha256": digest(result), "role_translation": translation})
            results[slot], intents[slot] = result, {"request": request}
        output_hash = "b" * 64 if changed else snapshot["effective_strategy_sha256"]
        session = {"fixture": True, "status": "valid", "requests": requests,
            "result_slots": list(results), "terminal_note_used": terminal, "input_snapshot": snapshot,
            "input_effective_strategy_sha256": snapshot["effective_strategy_sha256"], "model_backed": True,
            "harvest_raw_tree_sha256": "c" * 64, "effective_strategy_sha256": output_hash,
            "effective_changed_from_input": changed, "authentic_eligible": not terminal or changed}
        write_once(audit / "phase3a-sessions/inv1.a1.started.json", {"binding": binding, "label": "inv1.a1", "input_snapshot": snapshot})
        settled = {"binding": binding, "label": "inv1.a1", "session": session}
        settled["sha256"] = digest(settled)
        write_once(audit / "phase3a-sessions/inv1.a1.settled.json", settled)
        return audit, session, results, intents

    def test_persisted_sixteen_proof_and_terminal_changed_eligibility(self):
        audit, session, results, intents = self.proof()
        actual = editor.validate_persisted_sessions(audit, study_sha256="a" * 64, pilot="p3a-01",
            fixture=True, results=results, intents=intents)
        self.assertEqual(actual["inv1.a1"], session)
        with self.assertRaises(accounting.IntegrityStop):
            editor.frozen.validate_persisted_sessions(audit, study_sha256="a" * 64, pilot="p3a-01", fixture=True)
        path = audit / "phase3a-sessions/inv1.a1.settled.json"
        bad = json.loads(path.read_text())
        bad["session"]["requests"][7]["role_translation"] = editor.terminal_translation()
        bad["sha256"] = digest({k: v for k, v in bad.items() if k != "sha256"})
        path.write_text(json.dumps(bad, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        with self.assertRaises(accounting.IntegrityStop):
            editor.validate_persisted_sessions(audit, study_sha256="a" * 64, pilot="p3a-01", fixture=True)

    def test_normal_fifteen_keep_base_remains_eligible(self):
        audit, session, results, intents = self.proof(count=15, terminal=False, changed=False)
        self.assertTrue(session["authentic_eligible"])
        self.assertEqual(editor.validate_persisted_sessions(audit, study_sha256="a" * 64, pilot="p3a-01",
            fixture=True, results=results, intents=intents)["inv1.a1"], session)

    def test_constructor_rejects_private_or_old_scope_before_probe(self):
        for candidate in (self.work / "credential-binding.json" / "audit", strategy.ROOT / "runs/phase3a-compat-c1-v1/completion-v3/audit"):
            original = Path.is_symlink
            def guarded(path):
                if path == candidate:
                    self.fail("forbidden candidate metadata was probed")
                return original(path)
            with self.subTest(candidate=str(candidate)), patch.object(Path, "is_symlink", guarded), self.assertRaises(editor.ProposerError):
                editor.AccountedProposer(pilot="p3a-01", study_sha256="a" * 64, dispatch=lambda *a: None,
                    audit_dir=candidate, fixture=True, halt=lambda *a, **k: None)

    def test_persisted_private_entry_rejected_before_metadata(self):
        audit, _, _, _ = self.proof(count=15, terminal=False, changed=False)
        path = audit / "phase3a-sessions/.writer.lock"
        path.write_text("SYNTHETIC forbidden entry", encoding="utf-8")
        original = Path.is_symlink
        def guarded(candidate):
            if candidate == path:
                self.fail("private entry metadata was probed")
            return original(candidate)
        with patch.object(Path, "is_symlink", guarded), self.assertRaises(accounting.IntegrityStop):
            editor.validate_persisted_sessions(audit, study_sha256="a" * 64, pilot="p3a-01", fixture=True)

    def test_persisted_junction_rejects_before_directory_traversal(self):
        audit = self.work / "junction-audit"
        directory = audit / "phase3a-sessions"
        with patch.object(Path, "is_junction", lambda candidate: candidate == directory, create=True), \
                patch.object(Path, "iterdir", side_effect=AssertionError("junction traversal forbidden")), \
                self.assertRaises(accounting.IntegrityStop):
            editor.validate_persisted_sessions(audit, study_sha256="a" * 64, pilot="p3a-01", fixture=True)
        with patch.object(Path, "is_junction", lambda candidate: candidate == directory, create=True), \
                patch.object(Path, "mkdir", side_effect=AssertionError("junction mkdir forbidden")), \
                self.assertRaises(editor.ProposerError):
            editor.AccountedProposer(pilot="p3a-01", study_sha256="a" * 64,
                dispatch=lambda *a: self.fail("dispatch forbidden"), audit_dir=audit,
                fixture=True, halt=lambda *a, **k: None)

    def test_sixteenth_ordinary_request_is_rejected_before_relay_dispatch(self):
        seen = []
        def dispatch(slot, role, request):
            seen.append(slot)
            return {"status": "response", "response": {"provider_response": {
                "id": "fixture", "type": "message", "role": "assistant", "model": "claude-opus-5",
                "content": [{"type": "text", "text": "SYNTHETIC"}], "stop_reason": "end_turn",
                "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1}}}}
        record: dict = {"fixture": True, "requests": []}
        with editor.relay(self.work, dispatch, "p3a-02.adaptive.editor.inv1.a1", record,
                          lambda *a, **k: None) as url:
            for turn in range(1, 17):
                req = Request(url + "/messages", data=json.dumps(raw(str(turn))).encode(),
                    headers={"Content-Type": "application/json", "x-api-key": editor._FALSE})
                if turn == 16:
                    with self.assertRaises(HTTPError) as error:
                        urlopen(req, timeout=5)  # nosec B310: loopback-only fixture URL
                    self.assertEqual(error.exception.code, 403)
                else:
                    with urlopen(req, timeout=5) as response:  # nosec B310: loopback-only fixture URL
                        response.read()
        self.assertEqual(len(seen), 15)
        self.assertFalse(any(slot.endswith(".t16") for slot in seen))
        self.assertEqual(len(record["requests"]), 15)

    def test_sixteenth_ordinary_or_misbound_persisted_proof_cannot_be_eligible(self):
        audit, _, results, intents = self.proof()
        path = audit / "phase3a-sessions/inv1.a1.settled.json"
        original = json.loads(path.read_text())
        slot = "p3a-01.adaptive.editor.inv1.a1.t16"
        ordinary = editor.frozen.effective_request(raw("SYNTHETIC invalid ordinary16"), turn=16)
        for keep_terminal_flag in (False, True):
            bad = copy.deepcopy(original)
            row = bad["session"]["requests"][-1]
            intents[slot]["request"] = ordinary
            results[slot]["request_sha256"] = digest(ordinary)
            row["effective_sha256"], row["result_sha256"] = digest(ordinary), digest(results[slot])
            if not keep_terminal_flag:
                row["role_translation"] = None
                bad["session"]["terminal_note_used"] = False
            bad["sha256"] = digest({k: v for k, v in bad.items() if k != "sha256"})
            path.write_text(json.dumps(bad, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
            with self.subTest(keep_terminal_flag=keep_terminal_flag), self.assertRaises(accounting.IntegrityStop):
                editor.validate_persisted_sessions(audit, study_sha256="a" * 64, pilot="p3a-01",
                    fixture=True, results=results, intents=intents)
