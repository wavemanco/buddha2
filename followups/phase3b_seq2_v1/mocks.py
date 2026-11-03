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

from . import contract, rank_io, strategy


def _keep(label: str) -> bool:
    stage = label.split(".", 1)[0]
    return stage.startswith("dom") or stage in {"inv2", "c2"}


def _metadata_reads(cwd: Path, name: str, prefix: str) -> list[tuple[str, str, dict]]:
    """Read every unchanged metadata line within the real tool's page/byte limits."""
    target = SDKMock._context_file(cwd, name)
    lines = target.read_text(encoding="utf-8").splitlines()
    require(max(map(len, lines), default=0) < 2000, "metadata line exceeds actual Read tool limits")
    reads = []
    for offset in range(0, len(lines), 128):
        page = lines[offset:offset + 128]
        require(len("\n".join(page).encode()) < 40 * 1024, "metadata page exceeds actual Read byte budget")
        reads.append((f"{prefix}_{offset:05}", "read", {"filePath": str(target), "offset": offset + 1, "limit": len(page)}))
    return reads


class SDKMock(frozen.SDKMock):
    def select(self, role: str, slot: str):
        from .accounting import ROLES
        require(role in ROLES and isinstance(slot, str), "mock requires exact S2 role/slot")
        self._selected = role, slot

    def _handle(self, request, *, http_module):
        if self._selected is not None and self._selected[0] == "rank":
            body = json.loads(request.content)
            supplied = json.loads(body["messages"][0]["content"])
            require([row["id"] for row in supplied["responses"]] == list(rank_io.LABELS),
                    "actual SDK rank wire requires RC1 labels")
        if self._selected is None or self._selected[0] not in {"editor", "native_selector"}:
            return super()._handle(request, http_module=http_module)
        role, slot = self._selected
        body = json.loads(request.content)
        require(str(request.url) == "https://api.anthropic.com/v1/messages" and body["model"] == "claude-opus-5",
                "fixture refuses another native endpoint/model")
        try:
            content, stop = self._editor_content(body, slot)
        except ContractError as exc:
            self.c1_errors.append({"slot_id": slot, "reason": str(exc)})
            raise
        request_id = f"phase3b-s2-mock-{len(self.records) + 1:04}"
        response = {"id": "msg_" + request_id, "type": "message", "role": "assistant",
            "model": body["model"], "content": content, "stop_reason": stop, "stop_sequence": None,
            "usage": {"input_tokens": 80, "output_tokens": 24, "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0, "cache_creation": {
                    "ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 0},
                "service_tier": "standard", "inference_geo": "global"}}
        self.records.append({"role": role, "slot_id": slot, "url": str(request.url), "method": request.method,
            "request": copy.deepcopy(body), "model": body["model"], "request_id": request_id,
            "http_status": 200, "response": copy.deepcopy(response), "fault": None})
        return http_module.Response(200, json=response, headers={"request-id": request_id})

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
                and (manifest.get("role") == "SELECT" or system == contract.authoring_system(prepared["effective_mission"], prepared["index_text"])),
                "HI fixture requires its exact declared authoring profile")
        if not isinstance(system, str):
            raise ContractError("missing HI authoring profile")
        require(label not in self._registered or self._registered[label] == manifest,
                "HI fixture logical contract changed")
        require(label not in self._registered_system or self._registered_system[label] == system,
                "HI fixture logical authoring profile changed")
        self._registered[label], self._registered_system[label] = manifest, system

    def _start(self, cwd: Path, label: str) -> dict:
        manifest_path = self._context_file(cwd, "C1_MANIFEST.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        require(manifest.get("kind") == "phase3a-c1-evidence-v1"
                and manifest.get("sha256") == digest({k: v for k, v in manifest.items() if k != "sha256"}),
                "fixture requires the sealed C1 evidence manifest")
        require(self._registered.get(label) == manifest, "fixture manifest was not frozen before OpenCode execution")
        require(manifest.get("label") == label and manifest.get("role") == ("SELECT" if label == "select.seq2" else "AGG" if label.startswith("c") else label[:3].upper()),
                "fixture manifest belongs to another role/stage")
        expected, reads, source_proof = {}, [], {}
        for entry in manifest["required_evidence"]:
            path = self._context_file(cwd, entry["path"])
            data = path.read_bytes()
            require(len(data) == entry["bytes"] and hashlib.sha256(data).hexdigest() == entry["sha256"],
                    "fixture evidence changed after contract freezing")
            original, joined, cursor, views = data.decode("utf-8"), [], 0, []
            require(bool(entry.get("chunks")), "fixture evidence has no lossless read views")
            for chunk in entry["chunks"]:
                view_path = self._context_file(cwd, chunk["path"])
                view_bytes = view_path.read_bytes()
                require(len(view_bytes) == chunk["bytes"]
                        and hashlib.sha256(view_bytes).hexdigest() == chunk["sha256"],
                        "fixture lossless view changed after contract freezing")
                view_text = view_bytes.decode("utf-8")
                view = json.loads(view_text)
                require(view["source_path"] == entry["path"] and view["source_sha256"] == entry["sha256"]
                        and view["char_start"] == chunk["char_start"] == cursor
                        and view["char_end"] == chunk["char_end"]
                        and isinstance(view["text"], list)
                        and all(isinstance(segment, str) for segment in view["text"]),
                        "fixture lossless view source/range differs")
                fragment = "".join(view["text"])
                require(fragment == original[cursor:view["char_end"]], "fixture view rewrites original evidence")
                joined.append(fragment)
                cursor = view["char_end"]
                expected[str(view_path)] = view_text
                views.append({"path": str(view_path), "sha256": chunk["sha256"],
                              "char_start": chunk["char_start"], "char_end": chunk["char_end"]})
                reads.append({"filePath": str(view_path), "offset": chunk["offset"], "limit": chunk["limit"]})
            require(cursor == len(original) and "".join(joined) == original,
                    "fixture views omit or duplicate original evidence")
            source_proof[str(path)] = {"sha256": entry["sha256"], "bytes": entry["bytes"],
                                      "views": views, "lossless_reconstruction": True}
        initial = (None if label == "select.seq2" else json.loads(
            self._context_file(cwd, "harness/systemprompt.md").read_text(encoding="utf-8")))
        require(initial is None or set(initial) == set(strategy.FIELDS)
                and all(isinstance(value, str) and value.strip() for value in initial.values()),
                "fixture requires the exact valid strategy")
        state = {"manifest": manifest, "expected": expected, "reads": reads, "initial": initial,
                 "current_path": str(cwd / "context/harness/systemprompt.md"), "cwd": cwd, "source_proof": source_proof}
        self._c1[label] = state
        self.c1_sessions[label] = {"fixture": True, "manifest_sha256": manifest["sha256"],
            "decision_after_complete_evidence": False, "verification_after_write": False,
            "decision": "SELECT" if label == "select.seq2" else "KEEP_BASE" if _keep(label) else "EDIT", "ordinary_rounds": 0,
            "terminal_note_used": False, "source_evidence": {},
            "mission_visible_before_evidence": False, "configured_system_visible_before_mission": False}
        return state

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
        match = re.search(r"\.editor\.((?:(?:inv[12]|dom[12]|c[12])\.a[12]|select\.seq2))\.t(\d+)$", slot)
        require(match is not None, "fixture requires a declared HI editor slot")
        if match is None:
            raise ContractError("missing HI editor slot")
        label, turn = match.group(1), int(match.group(2))
        require(1 <= turn <= 23, "terminal24 must be refused before readiness SDK dispatch")
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
                and (label == "select.seq2" or configured.endswith(contract.FINAL_RULE)), "actual HI SYSTEM profile differs")
        proof = self.c1_sessions[label]
        proof.update(ordinary_rounds=turn, configured_system_visible_before_mission=True,
            authoring_system_sha256=hashlib.sha256(configured.encode()).hexdigest(),
            actual_system_sha256=hashlib.sha256(system.encode()).hexdigest(),
            R1_final_verbatim_rule_visible=True, HI_deliberately_inefficient_evidence_reading=True)
        if label == "select.seq2":
            return self._selector_content(body, label, turn, state, proof)
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
            return self._tools([*_metadata_reads(cwd, "C1_MANIFEST.json", "s2_manifest"),
                *_metadata_reads(cwd, "C1_INDEX.md", "s2_index"),
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
            if _keep(label):
                state["proposed"] = proposed
                return [{"type": "text", "text": "KEEP_BASE: complete delivered evidence; synthetic unchanged decision."},
                    *self._tools([("r3_verify", "read", {"filePath": state["current_path"]})])], "tool_use"
            if label.startswith("c"):
                proposed = json.loads(self._context_file(cwd, "pool/inv1/harness/systemprompt.md").read_text(encoding="utf-8"))
                proposed["rank_system"] += "\nSynthetic C1 composition fixture instruction."
            else:
                proposed["answer_system"] += "\nSynthetic C1 procedure fixture instruction."
            state["proposed"] = proposed
            return [{"type": "text", "text": "EDIT: complete delivered evidence; synthetic test only."},
                *self._tools([("r3_write", "write", {"filePath": state["current_path"],
                    "content": json.dumps(proposed, sort_keys=True, ensure_ascii=False, indent=2) + "\n"})])], "tool_use"
        verify_turn = 8 if _keep(label) else 9
        if turn == 8 and not _keep(label):
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
                         if not label.startswith("c") else "both candidates in context/pool and context/decisions")
            state["notes"] = ("<notes>\n" + ("kept" if _keep(label) else "revised")
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

    def _selector_content(self, body: dict, label: str, turn: int, state: dict, proof: dict):
        cwd = state["cwd"]
        if turn == 1:
            return self._tools([("s2_select_mission", "read", {"filePath": str(cwd / "MISSION.md")})]), "tool_use"
        mission = (cwd / "MISSION.md").read_text(encoding="utf-8")
        if self.fixture_mode == "terminal":
            return self._tools([(f"s2_select_wait_{turn}", "read", {"filePath": str(cwd / "MISSION.md")})]), "tool_use"
        if turn == 2:
            proof["mission_delivery"] = verify_delivery(body, {str(cwd / "MISSION.md"): mission})
            proof["mission_visible_before_evidence"] = True
            reads = [*_metadata_reads(cwd, "C1_MANIFEST.json", "s2_select_manifest"),
                     *_metadata_reads(cwd, "C1_INDEX.md", "s2_select_index")]
            reads.extend((f"s2_select_evidence_{i}", "read", item) for i, item in enumerate(state["reads"]))
            return self._tools(reads), "tool_use"
        if turn == 3:
            common = {str(cwd / "context" / name): (cwd / "context" / name).read_text(encoding="utf-8")
                      for name in ("C1_MANIFEST.json", "C1_INDEX.md")}
            proof["delivered_views"] = verify_delivery(body, state["expected"] | common)
            proof["source_evidence"] = copy.deepcopy(state["source_proof"])
            proof["decision_after_complete_evidence"] = True
            candidates = [entry["path"] for entry in state["manifest"]["required_evidence"]
                          if entry["kind"] == "selection_candidate"]
            # Alternate anonymous IDs across tasks for both native-choice code paths; not a quality claim.
            index = 1 if len(candidates) > 1 and getattr(self, "active_pilot", "").endswith("02") else 0
            chosen = Path(candidates[index]).stem
            state["notes"] = ("<why>\nSynthetic full-candidate inspection only; no quality inference.\n</why>\n\n"
                              + "```choice\n" + chosen + "\n```")
            return self._tools([("s2_select_save", "write", {"filePath": str(cwd / "output/answer.md"),
                                                            "content": state["notes"]})]), "tool_use"
        if turn == 4:
            return self._tools([("s2_select_reread", "read", {"filePath": str(cwd / "output/answer.md")})]), "tool_use"
        require(turn == 5, "unexpected selector mock round")
        verify_delivery({"messages": body["messages"][-2:]}, {str(cwd / "output/answer.md"): state["notes"]})
        proof.update(normal_final=True, notes_reread_model_visible=True)
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
