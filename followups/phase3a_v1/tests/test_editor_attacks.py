"""Finite adversarial tool outputs against the actual pinned OpenCode process."""
from __future__ import annotations

import copy
import json
import re
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from harness2.core.proposer import ProposerError

from followups.phase3a_v1 import accounting, editor, strategy
from followups.phase3a_v1.mocks import SDKMock
from followups.phase3a_v1.support import RESULTS
from followups.phase3a_v1.tests.test_accounting import AUTHORITY, BINDINGS, STUDY, request, slots


class AttackMock(SDKMock):
    def __init__(self, attack: str, marker: Path, forbidden: Path, witness: dict):
        super().__init__()
        self.attack, self.marker, self.forbidden, self.witness = attack, marker, forbidden, witness

    def _handle(self, outgoing, *, http_module):
        response = super()._handle(outgoing, http_module=http_module)
        if self.records[-1]["role"] != "editor":
            return response
        body = self.records[-1]["request"]
        system = "\n".join(block["text"] for block in body["system"])
        match = re.search(r"Working directory: ([^\r\n]+)", system)
        if match is None:
            raise AssertionError("actual OpenCode working-directory evidence missing")
        cwd = Path(match.group(1).strip())
        self.witness["before_config"] = (cwd / "opencode.json").read_bytes()
        if self.attack == "outside-read":
            name, arguments = "read", {"filePath": str(self.marker)}
        elif self.attack == "write-config":
            name, arguments = "write", {"filePath": str(cwd / "opencode.json"), "content": "forbidden replacement"}
        elif self.attack == "bash":
            name, arguments = "bash", {"command": "echo forbidden > " + str(self.forbidden)}
        elif self.attack == "server-caller":
            name, arguments = "read", {"filePath": str(cwd / "MISSION.md")}
        else:
            raise AssertionError("unknown finite attack fixture")
        payload = response.json()
        payload.update(stop_reason="tool_use", content=[{"type": "tool_use", "id": "attack-tool",
            "name": name, "input": arguments, "caller": {"type": "code_execution_20250825", "tool_id": "srvtoolu_fixture"}
            if self.attack == "server-caller" else {"type": "direct"}}])
        self.records[-1]["response"] = copy.deepcopy(payload)
        return http_module.Response(200, json=payload, headers={"request-id": "fixture-editor-attack"})


class ObservedProposer(editor.AccountedProposer):
    def __init__(self, *args, witness: dict, **kwargs):
        self.witness = witness
        super().__init__(*args, **kwargs)

    def _opencode(self, cwd, mission, system, wall):
        try:
            return super()._opencode(cwd, mission, system, wall)
        finally:
            config = cwd / "opencode.json"
            if config.exists():
                self.witness["after_config"] = config.read_bytes()


@unittest.skipUnless(Path("/opt/phase3a-opencode").is_dir(), "requires the actual pinned OpenCode runtime")
class ActualEditorAttackTests(unittest.TestCase):
    def setUp(self):
        target = RESULTS / "editor-attack-tests"
        target.mkdir(parents=True, exist_ok=True)
        self.results = tempfile.TemporaryDirectory(prefix="case-", dir=target)
        self.workspace = tempfile.TemporaryDirectory(prefix="phase3a-editor-attack-")
        self.addCleanup(self.workspace.cleanup)
        self.addCleanup(self.results.cleanup)
        self.root, self.task = Path(self.results.name), Path(self.workspace.name)
        self.context = self.task / "input"
        strategy.materialize_seed(self.context / "harness")
        self.marker = self.root / "outside-marker.txt"
        self.marker_text = "SYNTHETIC_MARKER_MUST_NOT_LEAK_" + uuid.uuid4().hex
        self.marker.write_text(self.marker_text, encoding="utf-8")
        self.forbidden = self.root / "bash-created.txt"
        self.tools = json.loads((strategy.ROOT / "followups/phase3a_v1/editor-tools.json").read_text(encoding="utf-8"))

    def exercise_tool_attack(self, attack: str):
        witness: dict = {}
        with AttackMock(attack, self.marker, self.forbidden, witness) as mock:
            ledger = accounting.Ledger(self.root / "journal", study_sha256=STUDY, slots=slots(),
                authority=AUTHORITY, transport=mock.transport, bindings=BINDINGS, editor_tools=self.tools)
            prop = ObservedProposer(pilot="p3a-01", study_sha256=STUDY, dispatch=ledger.dispatch,
                audit_dir=self.task / "audit", fixture=True, halt=ledger.halt, witness=witness)
            # Only backoff time is skipped; the actual native two-attempt loop runs.
            with patch("harness2.core.proposer.time.sleep", return_value=None), self.assertRaises(ProposerError):
                prop.call("Inspect the supplied task and strategy, then report completion.", self.context,
                          "inv1.a1", harvest="context/harness", max_attempts=2)
            self.assertEqual(mock.http_calls, 1)
            state = accounting.replay(self.root / "journal")
            self.assertEqual(state["status"], "halted-integrity")
            self.assertEqual(state["attempts"], 1)
            self.assertEqual(state["reserved_micro_usd"], 0)
            self.assertGreater(state["spent_micro_usd"], 0)
            with self.assertRaises(accounting.IntegrityStop):
                ledger.dispatch("p3a-01.fixed.plan.00", "plan", request())
            self.assertEqual(mock.http_calls, 1)
            self.assertNotIn(self.marker_text, json.dumps(mock.records, ensure_ascii=False))
            self.assertEqual(self.marker.read_text(encoding="utf-8"), self.marker_text)
            self.assertFalse(self.forbidden.exists())
            self.assertEqual(witness["before_config"], witness["after_config"])

    def test_actual_outside_read_is_blocked_before_tool_execution(self):
        self.exercise_tool_attack("outside-read")

    def test_actual_config_write_is_blocked_before_tool_execution(self):
        self.exercise_tool_attack("write-config")

    def test_actual_bash_tool_is_blocked_before_tool_execution(self):
        self.exercise_tool_attack("bash")

    def test_actual_server_caller_history_is_blocked_before_second_provider_request(self):
        self.exercise_tool_attack("server-caller")

    def test_context_symlink_is_blocked_before_copy_or_http(self):
        (self.context / "outside-link").symlink_to(self.marker)
        witness: dict = {}
        with AttackMock("outside-read", self.marker, self.forbidden, witness) as mock:
            ledger = accounting.Ledger(self.root / "journal", study_sha256=STUDY, slots=slots(),
                authority=AUTHORITY, transport=mock.transport, bindings=BINDINGS, editor_tools=self.tools)
            prop = ObservedProposer(pilot="p3a-01", study_sha256=STUDY, dispatch=ledger.dispatch,
                audit_dir=self.task / "audit", fixture=True, halt=ledger.halt, witness=witness)
            with self.assertRaises(ProposerError):
                prop.call("Inspect supplied context.", self.context, "inv1.a1", harvest="context/harness", max_attempts=2)
            self.assertEqual(mock.http_calls, 0)
            self.assertEqual(accounting.replay(self.root / "journal")["status"], "halted-integrity")
            with self.assertRaises(accounting.IntegrityStop):
                ledger.dispatch("p3a-01.fixed.plan.00", "plan", request())
            self.assertEqual(mock.http_calls, 0)
            self.assertNotIn(self.marker_text, json.dumps(prop.phase3a_evidence(), ensure_ascii=False))
            self.assertEqual(self.marker.read_text(encoding="utf-8"), self.marker_text)


if __name__ == "__main__":
    unittest.main()
