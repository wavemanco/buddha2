"""R1 fixture keeps actual SDK/wire evidence and versions only the authoring profile."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

from buddha2.artifacts import ContractError, digest
from followups.phase3a_compat_c1_v1.mocks import SDKMock as FrozenMock
from followups.phase3a_compat_c1_v1.mocks import require, verify_delivery
from followups.phase3a_v1 import strategy

from . import contract


class SDKMock(FrozenMock):
    def register_contract(self, label: str, prepared: dict) -> None:
        manifest = copy.deepcopy(prepared["manifest"])
        require(manifest.get("label") == label and manifest.get("sha256") ==
                digest({k: v for k, v in manifest.items() if k != "sha256"}),
                "R1 fixture requires the frozen stage manifest")
        require(label not in self._registered or self._registered[label] == manifest,
                "R1 fixture logical contract changed")
        system = prepared.get("authoring_system_text")
        if not isinstance(system, str):
            raise ContractError("R1 fixture system profile must be text")
        require(system.startswith(contract.SYSTEM_ID + "\n")
                and system == contract.authoring_system(prepared["effective_mission"], prepared["index_text"]),
                "R1 fixture requires its exact declared system profile")
        require(label not in self._registered_system or self._registered_system[label] == system,
                "R1 fixture logical system profile changed")
        self._registered[label] = manifest
        self._registered_system[label] = system

    def _editor_content(self, body: dict, slot: str) -> tuple[list[dict], str]:
        match = re.search(r"\.editor\.((?:inv1|dom1|agg1)\.a[12])\.t(\d+)$", slot)
        if match is None:
            raise ContractError("fixture requires a declared native editor slot")
        label, turn = match.group(1), int(match.group(2))
        system = "\n".join(part["text"] for part in body["system"])
        directory = re.search(r"Working directory: ([^\r\n]+)", system)
        if directory is None:
            raise ContractError("actual OpenCode workspace evidence is absent")
        cwd = Path(directory.group(1).strip())
        require(turn <= 7, "C1 fixture exhausted seven ordinary rounds")
        state = self._start(cwd, label) if turn == 1 else self._c1[label]
        require(state["cwd"] == cwd, "fixture logical session changed workspace")
        proof = self.c1_sessions[label]
        proof["ordinary_rounds"] = turn
        configured = self._registered_system[label]
        require(system.startswith(contract.SYSTEM_ID + "\n") and configured in system,
                "actual OpenCode system profile differs from its frozen C1 contract/index")
        require(configured.endswith(contract.FINAL_RULE) and contract.FINAL_RULE in system,
                "R1 final-verbatim rule is absent from the actual SYSTEM")
        proof["R1_final_verbatim_rule_visible"] = True
        proof["configured_system_visible_before_mission"] = True
        proof["authoring_system_sha256"] = hashlib.sha256(configured.encode("utf-8")).hexdigest()
        proof["actual_system_sha256"] = hashlib.sha256(system.encode("utf-8")).hexdigest()
        if turn == 1:
            return self._tools([("c1_mission", "read", {"filePath": str(cwd / "MISSION.md")})]), "tool_use"
        if turn == 2:
            mission = (cwd / "MISSION.md").read_text(encoding="utf-8")
            require(hashlib.sha256(mission.encode("utf-8")).hexdigest() == state["manifest"]["effective_mission_sha256"],
                    "actual native mission differs from the frozen effective role contract")
            proof["mission_delivery"] = verify_delivery(body, {str(cwd / "MISSION.md"): mission})
            proof["mission_visible_before_evidence"] = True
            reads = [("c1_manifest", "read", {"filePath": str(cwd / "context/C1_MANIFEST.json")}),
                     ("c1_index", "read", {"filePath": str(cwd / "context/C1_INDEX.md")}),
                     ("c1_current", "read", {"filePath": state["current_path"]})]
            reads += [(f"c1_evidence_{i}", "read", item) for i, item in enumerate(state["reads"])]
            return self._tools(reads), "tool_use"
        if turn == 3:
            require(proof["mission_visible_before_evidence"], "fixture skipped mission delivery")
            common = {str(cwd / "context" / name): (cwd / "context" / name).read_text(encoding="utf-8")
                      for name in ("C1_MANIFEST.json", "C1_INDEX.md", "harness/systemprompt.md")}
            proof["delivered_views"] = verify_delivery(body, state["expected"] | common)
            proof["source_evidence"] = copy.deepcopy(state["source_proof"])
            proof["decision_after_complete_evidence"] = True
            proposed = copy.deepcopy(state["initial"])
            if not label.startswith("dom"):
                if label.startswith("agg"):
                    inv_path = self._context_file(cwd, "pool/inv1/harness/systemprompt.md")
                    proposed = json.loads(inv_path.read_text(encoding="utf-8"))
                    proposed["rank_system"] += "\nSynthetic C1 composition fixture instruction."
                else:
                    proposed["answer_system"] += "\nSynthetic C1 procedure fixture instruction."
                state["proposed"] = proposed
                return [{"type": "text", "text": "EDIT: complete declared evidence was delivered; synthetic test only."},
                    *self._tools([("c1_write", "write", {"filePath": state["current_path"],
                        "content": json.dumps(proposed, ensure_ascii=False, sort_keys=True, indent=2) + "\n"})])], "tool_use"
            state["proposed"] = proposed
            return [{"type": "text", "text": "KEEP_BASE: synthetic unchanged decision after complete evidence delivery."},
                    *self._tools([("c1_verify", "read", {"filePath": state["current_path"]})])], "tool_use"
        verify_turn = 4 if label.startswith("dom") else 5
        if turn == 4 and not label.startswith("dom"):
            return self._tools([("c1_verify", "read", {"filePath": state["current_path"]})]), "tool_use"
        if turn == verify_turn:
            current = self._context_file(cwd, "harness/systemprompt.md").read_text(encoding="utf-8")
            # The read after the decision must supply the current file, not an earlier unchanged read.
            last = {"messages": body["messages"][-2:]}
            verify_delivery(last, {state["current_path"]: current})
            parsed = json.loads(current)
            require(parsed == state["proposed"] and set(parsed) == set(strategy.FIELDS)
                    and all(isinstance(v, str) and v.strip() for v in parsed.values()),
                    "reread fixture harvest is not its declared three-string proposal")
            proof["verification_after_write"] = True
            proof["effective_changed"] = parsed != state["initial"]
            action = "kept" if label.startswith("dom") else "revised"
            grounding = ("complete base plan/answers in context/rollouts/base1.md and context/deliverables/base1/answers.json.txt"
                if not label.startswith("agg") else "both complete candidate decisions, strategies and probe trajectories in context/pool and context/decisions")
            state["notes"] = ("<notes>\n" + action + " -> " + proof["decision"]
                + " -> " + grounding + "; synthetic consumption/compatibility test only, no effectiveness inference.\n</notes>")
            return self._tools([("c1_answer", "write", {"filePath": str(cwd / "output/answer.md"),
                "content": state["notes"]})]), "tool_use"
        if turn == verify_turn + 1:
            return self._tools([("c1_verify_notes", "read", {"filePath": str(cwd / "output/answer.md")})]), "tool_use"
        require(turn == verify_turn + 2 and proof["verification_after_write"], "fixture completion skipped verification")
        verify_delivery({"messages": body["messages"][-2:]}, {str(cwd / "output/answer.md"): state["notes"]})
        proof["notes_reread_model_visible"] = True
        proof["normal_final"] = True
        return [{"type": "text", "text": state["notes"]}], "end_turn"


class StudyMock(SDKMock):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.active_pilot: str | None = None
        self.pilot_proofs: dict[str, dict] = {}

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
            self._registered.clear()
            self._registered_system.clear()
            self._c1.clear()
            self.c1_sessions.clear()
        super().register_contract(label, prepared)

    def proofs(self) -> dict:
        result = copy.deepcopy(self.pilot_proofs)
        if self.active_pilot is not None:
            result[self.active_pilot] = copy.deepcopy(self.c1_sessions)
        return result
