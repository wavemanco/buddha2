"""Actual-SDK fixtures with deliberately inefficient, fully observed HI tool rounds."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

from buddha2.artifacts import ContractError, digest
from followups.phase3a_c1_completion_v3 import mocks as frozen
from followups.phase3a_compat_c1_v1.mocks import require, verify_delivery

from . import contract, strategy


class SDKMock(frozen.SDKMock):
    def __init__(self, *, fixture_mode: str = "normal", **kwargs):
        require(fixture_mode in {"normal", "terminal"}, "unknown HI fixture mode")
        self.fixture_mode = fixture_mode
        super().__init__(**kwargs)

    def __enter__(self):
        import httpx
        import httpx2

        from .transport import Transport

        self.transport = Transport(anthropic_api_key="fixture-not-a-secret", openai_api_key="fixture-not-a-secret",
            http_transports={"anthropic": httpx2.MockTransport(lambda req: self._handle(req, http_module=httpx2)),
                             "openai": httpx.MockTransport(lambda req: self._handle(req, http_module=httpx))})
        self.transport.select = self.select
        return self

    def register_contract(self, label: str, prepared: dict) -> None:
        manifest = copy.deepcopy(prepared["manifest"])
        system = prepared.get("authoring_system_text")
        require(manifest.get("label") == label and manifest.get("sha256") == digest({
            key: value for key, value in manifest.items() if key != "sha256"}), "HI fixture requires its sealed manifest")
        require(isinstance(system, str) and system.startswith(contract.SYSTEM_ID + "\n")
                and system == contract.authoring_system(prepared["effective_mission"], prepared["index_text"]),
                "HI fixture requires its exact declared authoring profile")
        if not isinstance(system, str):
            raise ContractError("missing HI authoring profile")
        require(label not in self._registered or self._registered[label] == manifest,
                "HI fixture logical contract changed")
        require(label not in self._registered_system or self._registered_system[label] == system,
                "HI fixture logical authoring profile changed")
        self._registered[label], self._registered_system[label] = manifest, system

    def _editor_content(self, body: dict, slot: str) -> tuple[list[dict], str]:
        content, stop = self._unsigned_editor_content(body, slot)
        if stop == "end_turn":
            return content, stop
        marker = slot.rsplit(".editor.", 1)[-1]
        opaque = [{"type": "thinking", "thinking": "", "signature": "synthetic-empty-" + marker},
                  {"type": "thinking", "thinking": "SYNTHETIC ONLY", "signature": "synthetic-visible-" + marker},
                  {"type": "redacted_thinking", "data": "synthetic-redacted-" + marker}]
        calls = [index for index, block in enumerate(content) if block["type"] == "tool_use"]
        if len(calls) >= 2:
            boundary = calls[0] + 1
            return [opaque[0], *content[:boundary], *opaque[1:], *content[boundary:]], stop
        return [*opaque, *content], stop

    def _unsigned_editor_content(self, body: dict, slot: str) -> tuple[list[dict], str]:
        match = re.search(r"\.editor\.((?:inv1|dom1|agg1)\.a[12])\.t(\d+)$", slot)
        require(match is not None, "fixture requires a declared HI editor slot")
        if match is None:
            raise ContractError("missing HI editor slot")
        label, turn = match.group(1), int(match.group(2))
        require(1 <= turn <= 15, "terminal16 must be refused before readiness SDK dispatch")
        system = "\n".join(part["text"] for part in body["system"])
        directory = re.search(r"Working directory: ([^\r\n]+)", system)
        require(directory is not None, "actual OpenCode working directory missing")
        if directory is None:
            raise ContractError("missing OpenCode workspace")
        cwd = Path(directory.group(1).strip())
        state = self._start(cwd, label) if turn == 1 else self._c1[label]
        require(state["cwd"] == cwd, "fixture session changed its workspace")
        configured = self._registered_system[label]
        require(system.startswith(contract.SYSTEM_ID + "\n") and configured in system
                and configured.endswith(contract.FINAL_RULE), "actual HI SYSTEM profile differs")
        proof = self.c1_sessions[label]
        proof.update(ordinary_rounds=turn, configured_system_visible_before_mission=True,
            authoring_system_sha256=hashlib.sha256(configured.encode()).hexdigest(),
            actual_system_sha256=hashlib.sha256(system.encode()).hexdigest(),
            R1_final_verbatim_rule_visible=True, HI_deliberately_inefficient_evidence_reading=True)
        if turn == 1:
            return self._tools([("r3_mission", "read", {"filePath": str(cwd / "MISSION.md")})]), "tool_use"
        mission = (cwd / "MISSION.md").read_text(encoding="utf-8")
        require(hashlib.sha256(mission.encode()).hexdigest() == state["manifest"]["effective_mission_sha256"],
                "actual mission differs from the prepared contract")
        if self.fixture_mode == "terminal":
            # This negative case cannot accidentally produce a qualifying final.
            return self._tools([(f"r3_terminal_read_{turn}", "read", {"filePath": str(cwd / "MISSION.md")})]), "tool_use"
        if turn == 2:
            proof["mission_delivery"] = verify_delivery(body, {str(cwd / "MISSION.md"): mission})
            proof["mission_visible_before_evidence"] = True
            return self._tools([("r3_manifest", "read", {"filePath": str(cwd / "context/C1_MANIFEST.json")}),
                ("r3_index", "read", {"filePath": str(cwd / "context/C1_INDEX.md")}),
                ("r3_current", "read", {"filePath": state["current_path"]})]), "tool_use"
        if 3 <= turn <= 6:
            reads = state["reads"]
            require(len(reads) >= 4, "fixture cannot split complete evidence into four nonempty batches")
            start, end = (turn - 3) * len(reads) // 4, (turn - 2) * len(reads) // 4
            proof["evidence_read_batches"] = turn - 2
            return self._tools([(f"r3_evidence_{turn}_{index}", "read", reads[index])
                                for index in range(start, end)]), "tool_use"
        if turn == 7:
            common = {str(cwd / "context" / name): (cwd / "context" / name).read_text(encoding="utf-8")
                      for name in ("C1_MANIFEST.json", "C1_INDEX.md", "harness/systemprompt.md")}
            proof["delivered_views"] = verify_delivery(body, state["expected"] | common)
            require(proof["mission_visible_before_evidence"] is True, "mission delivery was skipped")
            proof.update(source_evidence=copy.deepcopy(state["source_proof"]),
                         decision_after_complete_evidence=True, first_decision_round=turn)
            proposed = copy.deepcopy(state["initial"])
            if label.startswith("dom"):
                state["proposed"] = proposed
                return [{"type": "text", "text": "KEEP_BASE: complete delivered evidence; synthetic unchanged decision."},
                    *self._tools([("r3_verify", "read", {"filePath": state["current_path"]})])], "tool_use"
            if label.startswith("agg"):
                proposed = json.loads(self._context_file(cwd, "pool/inv1/harness/systemprompt.md").read_text(encoding="utf-8"))
                proposed["rank_system"] += "\nSynthetic C1 composition fixture instruction."
            else:
                proposed["answer_system"] += "\nSynthetic C1 procedure fixture instruction."
            state["proposed"] = proposed
            return [{"type": "text", "text": "EDIT: complete delivered evidence; synthetic test only."},
                *self._tools([("r3_write", "write", {"filePath": state["current_path"],
                    "content": json.dumps(proposed, sort_keys=True, ensure_ascii=False, indent=2) + "\n"})])], "tool_use"
        verify_turn = 8 if label.startswith("dom") else 9
        if turn == 8 and not label.startswith("dom"):
            return self._tools([("r3_verify", "read", {"filePath": state["current_path"]})]), "tool_use"
        if turn == verify_turn:
            current = self._context_file(cwd, "harness/systemprompt.md").read_text(encoding="utf-8")
            verify_delivery({"messages": body["messages"][-2:]}, {state["current_path"]: current})
            parsed = json.loads(current)
            require(parsed == state["proposed"] and set(parsed) == set(strategy.FIELDS)
                    and all(isinstance(value, str) and value.strip() for value in parsed.values()),
                    "reread harvest differs from the declared fixture decision")
            proof.update(verification_after_write=True, effective_changed=parsed != state["initial"])
            grounding = ("context/rollouts/base1.md and context/deliverables/base1/answers.json.txt"
                         if not label.startswith("agg") else "both candidates in context/pool and context/decisions")
            state["notes"] = ("<notes>\n" + ("kept" if label.startswith("dom") else "revised")
                + " -> " + proof["decision"] + " -> " + grounding + "; complete native evidence delivered in four read batches; "
                + "synthetic compatibility evidence only, no effectiveness inference.\n</notes>")
            return self._tools([("r3_notes", "write", {"filePath": str(cwd / "output/answer.md"),
                "content": state["notes"]})]), "tool_use"
        if turn == verify_turn + 1:
            return self._tools([("r3_verify_notes", "read", {"filePath": str(cwd / "output/answer.md")})]), "tool_use"
        require(turn == verify_turn + 2 and proof["verification_after_write"], "normal completion skipped strategy verification")
        verify_delivery({"messages": body["messages"][-2:]}, {str(cwd / "output/answer.md"): state["notes"]})
        proof.update(notes_reread_model_visible=True, normal_final=True)
        return [{"type": "text", "text": state["notes"]}], "end_turn"


class StudyMock(SDKMock):
    def __init__(self, **kwargs):
        self.active_pilot: str | None = None
        self.pilot_proofs: dict[str, dict] = {}
        super().__init__(**kwargs)

    def __enter__(self):
        super().__enter__()
        self.transport.register_contract = self.register_pilot
        self.transport.records = self.records
        return self

    def register_pilot(self, pilot: str, label: str, prepared: dict) -> None:
        if self.active_pilot != pilot:
            if self.active_pilot is not None:
                self.pilot_proofs[self.active_pilot] = copy.deepcopy(self.c1_sessions)
            self.active_pilot = pilot
            for value in (self._registered, self._registered_system, self._c1, self.c1_sessions):
                value.clear()
        self.register_contract(label, prepared)

    proofs = frozen.StudyMock.proofs
