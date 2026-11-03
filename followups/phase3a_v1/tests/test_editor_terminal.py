"""Exact terminal control translation and real CLI bounded-harvest provenance."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from harness2.core.proposer import ProposerError

from buddha2.artifacts import ContractError, digest
from followups.phase3a_v1 import accounting, editor, native, strategy
from followups.phase3a_v1.mocks import SDKMock
from followups.phase3a_v1.tests.test_strategy import STUDY, TASK, FakeDispatch


@unittest.skipUnless(Path("/opt/phase3a-opencode").is_dir(), "requires pinned real OpenCode runtime")
class TerminalEditorTests(unittest.TestCase):
    def test_exact_eighth_terminal_translation_preserves_all_other_history_and_metadata(self):
        raw: dict = {"model": "claude-opus-5", "max_tokens": 16000, "thinking": {"type": "adaptive"},
            "output_config": {"effort": "high"}, "stream": True,
            "messages": [{"role": "user", "content": "task"},
                {"role": "assistant", "content": [
                    {"type": "thinking", "thinking": "synthetic", "signature": "unchanged-signature"},
                    {"type": "tool_use", "id": "tool-1", "name": "read", "input": {"filePath": "/tmp/input"},
                     "caller": {"type": "direct"}}]},
                {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "tool-1", "content": "fixture"}]},
                {"role": "assistant", "content": [{"type": "text", "text": editor.terminal_note(),
                    "cache_control": {"type": "ephemeral", "ttl": "5m"}}]}]}
        before = copy.deepcopy(raw)
        effective = editor.effective_request(raw, turn=8)
        expected = copy.deepcopy(raw)
        expected.pop("stream")
        expected.update(service_tier="standard_only", inference_geo="global")
        expected["messages"][-1]["role"] = "user"
        self.assertEqual(effective, expected)
        self.assertEqual(raw, before)
        for turn in (None, 1, 7, 9):
            with self.subTest(turn=turn), self.assertRaises(ContractError):
                editor.effective_request(raw, turn=turn)
        for content in (editor.terminal_note(), [{"type": "text", "text": editor.terminal_note() + " "}],
                        [{"type": "text", "text": editor.terminal_note(), "extra": 1}],
                        [{"type": "text", "text": editor.terminal_note()}, {"type": "text", "text": "extra"}]):
            malformed = copy.deepcopy(raw)
            malformed["messages"][-1]["content"] = content
            with self.assertRaises(ContractError):
                editor.effective_request(malformed, turn=8)

    def exercise(self, mode, *, invalid_input=False):
        with tempfile.TemporaryDirectory() as temporary, SDKMock(editor_mode=mode) as mock:
            root = Path(temporary)
            strategy.materialize_seed(root / "input/harness")
            if invalid_input:
                (root / "input/harness/systemprompt.md").write_text("{}", encoding="utf-8")
            input_hash = editor.input_snapshot(strategy.validate_harness_inventory(root / "input/harness"))["effective_strategy_sha256"]
            results: dict = {}
            intents: dict = {}
            holds: list = []
            tools = json.loads((strategy.ROOT / "followups/phase3a_v1/editor-tools.json").read_text(encoding="utf-8"))

            def dispatch(slot, role, request):
                accounting.validate_request(role, request, editor_tools=tools)
                mock.transport.select(role, slot)
                response = mock.transport.create(role, request)
                intent = {"slot_id": slot, "role": role, "cell": "p3a-01:adaptive", "pair": "p3a-01",
                    "study_sha256": STUDY, "fixture": True, "dispatch_id": "terminal-fixture:" + slot,
                    "request": request, "request_sha256": digest(request), "reservation": accounting._reservation(role)}
                result = accounting._result(intent, response)
                self.assertEqual(result["status"], "response")
                intents[slot], results[slot] = intent, result
                return result

            prop = editor.AccountedProposer(pilot="p3a-01", study_sha256=STUDY, dispatch=dispatch,
                audit_dir=root / "audit", fixture=True, halt=lambda *args, **kwargs: holds.append((args, kwargs)))
            if mode == "ninth_tool":
                with self.assertRaises(ProposerError):
                    prop.call("Use the declared harness and report completion.", root / "input", "inv1.a1",
                              harvest="context/harness", max_attempts=1)
                self.assertEqual(mock.http_calls, 8)
                self.assertEqual(len(results), 8)
                self.assertTrue(holds)
                self.assertEqual(prop.phase3a_evidence()["sessions"]["inv1.a1"]["status"], "boundary_stopped")
                return
            reply = prop.call("Use the declared harness and report completion.", root / "input", "inv1.a1",
                              harvest="context/harness", max_attempts=1)
            self.assertEqual(holds, [])
            expected_turns = 7 if mode == "seven_turn" else 8
            self.assertEqual(mock.http_calls, expected_turns)
            proof = prop.phase3a_evidence()["sessions"]["inv1.a1"]
            self.assertEqual(proof["input_effective_strategy_sha256"], input_hash)
            self.assertEqual(proof["status"], "valid")
            self.assertTrue(proof["model_backed"])
            self.assertEqual(proof["terminal_note_used"], mode != "seven_turn")
            self.assertEqual(proof["effective_changed_from_input"], None if invalid_input else mode != "terminal_unchanged")
            self.assertEqual(proof["authentic_eligible"], not invalid_input and mode != "terminal_unchanged")
            self.assertEqual(strategy.validate_harness(reply.workspace)["effective_strategy_sha256"], proof["effective_strategy_sha256"])
            self.assertEqual(editor.validate_persisted_sessions(root / "audit", study_sha256=STUDY,
                pilot="p3a-01", fixture=True, results=results, intents=intents)["inv1.a1"], proof)
            if mode != "seven_turn":
                last = mock.records[-1]["request"]
                self.assertEqual(last["messages"][-1]["role"], "user")
                self.assertTrue(editor._terminal_shape(last["messages"][-1]))
                self.assertEqual(proof["requests"][-1]["role_translation"], editor.terminal_translation())
                self.assertNotEqual(proof["requests"][-1]["raw_sha256"], proof["requests"][-1]["effective_sha256"])
            if mode == "terminal_unchanged":
                path = root / "audit/phase3a-sessions/inv1.a1.settled.json"
                forged = json.loads(path.read_text(encoding="utf-8"))
                forged["session"]["terminal_note_used"] = False
                forged["session"]["authentic_eligible"] = True
                for request in forged["session"]["requests"]:
                    request["role_translation"] = None
                forged["sha256"] = digest({key: value for key, value in forged.items() if key != "sha256"})
                path.write_text(json.dumps(forged, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")
                with self.assertRaises(accounting.IntegrityStop):
                    editor.validate_persisted_sessions(root / "audit", study_sha256=STUDY,
                        pilot="p3a-01", fixture=True, results=results, intents=intents)

    def test_actual_changed_harvest_sixth_and_final_seventh(self):
        self.exercise("seven_turn")

    def test_actual_terminal_eighth_unchanged_is_valid_but_ineligible(self):
        self.exercise("terminal_unchanged")

    def test_actual_terminal_eighth_changed_remains_eligible(self):
        self.exercise("terminal_changed")

    def test_actual_ninth_request_is_blocked_without_dispatch(self):
        self.exercise("ninth_tool")

    def test_actual_terminal_repair_from_invalid_input_is_conservatively_ineligible(self):
        self.exercise("terminal_changed", invalid_input=True)

    def test_native_terminal_unchanged_flags_and_authenticity_are_distinct(self):
        with tempfile.TemporaryDirectory() as temporary, SDKMock(editor_mode="terminal_unchanged") as mock:
            root = Path(temporary)
            strategy.materialize_seed(root / "seed")
            fake = FakeDispatch()
            holds: list = []
            tools = json.loads((strategy.ROOT / "followups/phase3a_v1/editor-tools.json").read_text(encoding="utf-8"))

            def dispatch(slot, role, request):
                if role != "editor":
                    return fake(slot, role, request)
                accounting.validate_request(role, request, editor_tools=tools)
                mock.transport.select(role, slot)
                intent = {"slot_id": slot, "role": role, "cell": "p3a-01:adaptive", "pair": "p3a-01",
                    "study_sha256": STUDY, "fixture": True, "dispatch_id": "native-terminal:" + slot,
                    "request": request, "request_sha256": digest(request), "reservation": accounting._reservation(role)}
                result = accounting._result(intent, mock.transport.create(role, request))
                fake.results[slot] = result
                return result

            prop = editor.AccountedProposer(pilot="p3a-01", study_sha256=STUDY, dispatch=dispatch,
                audit_dir=root / "adapt/editor-audit", fixture=True,
                halt=lambda *args, **kwargs: holds.append((args, kwargs)))
            record = native.run_adaptation(TASK, root / "seed", study_sha256=STUDY,
                run_root=root / "adapt", tag="terminal-native", dispatch=dispatch, fixture=True,
                prop=prop, known_results={}, result_snapshot=lambda: fake.results)
            self.assertEqual(holds, [])
            self.assertEqual(record["status"], "complete")
            self.assertFalse(record["authentic"])
            self.assertEqual(mock.http_calls, 24)
            for stage in record["stage_dispositions"]:
                self.assertTrue(stage["kept_base"])
                self.assertFalse(stage["fell_back"])
                self.assertTrue(stage["model_backed"])
                self.assertTrue(stage["cap_limited_unchanged"])
                self.assertFalse(stage["authentic_eligible"])
            # Exercise the authenticity fold's live/fixture-independent condition
            # with synthetic metadata; this is never published as live evidence.
            proof = copy.deepcopy(record["editor_evidence"])
            proof["fixture"] = False
            results = copy.deepcopy(fake.results)
            for session in proof["sessions"].values():
                for request in session["requests"]:
                    result = results[request["slot_id"]]
                    result["fixture"] = False
                    request["result_sha256"] = digest(result)
            _, authentic = native._stage_proof(record["native"], proof, TASK, root / "adapt",
                "terminal-native", False, STUDY, results)
            self.assertFalse(authentic)
            proof["sessions"]["inv1.a1"]["terminal_note_used"] = False
            proof["sessions"]["inv1.a1"]["authentic_eligible"] = True
            with self.assertRaises(accounting.IntegrityStop):
                native._stage_proof(record["native"], proof, TASK, root / "adapt",
                    "terminal-native", False, STUDY, results)


if __name__ == "__main__":
    unittest.main()
