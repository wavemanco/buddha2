"""Scripted C1 evidence-delivery fixture over the frozen real-SDK transport."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from buddha2.artifacts import ContractError, digest
from followups.phase3a_v1 import strategy
from followups.phase3a_v1.mocks import SDKMock as FrozenMock


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ContractError(reason)


def visible_read_lines(body: dict) -> dict[str, dict[int, str]]:
    """Recover exact numbered file content from genuine tool-result blocks only."""
    calls: dict[str, dict] = {}
    delivered: dict[str, dict[int, str]] = {}
    for message in body.get("messages", []):
        blocks = message.get("content", [])
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if message.get("role") == "assistant" and block.get("type") == "tool_use" and block.get("name") == "read":
                require(block.get("caller") == {"type": "direct"}, "fixture read caller/history metadata differs")
                calls[block["id"]] = block["input"]
            elif message.get("role") == "user" and block.get("type") == "tool_result":
                call = calls.get(block.get("tool_use_id"))
                if call is None or block.get("is_error"):
                    continue
                content = block.get("content", "")
                if isinstance(content, list):
                    content = "\n".join(part.get("text", "") for part in content if part.get("type") == "text")
                if not isinstance(content, str):
                    continue
                path_match = re.search(r"<path>([^\n]+)</path>", content)
                data_match = re.search(r"<content>\n(.*?)\n</content>", content, re.DOTALL)
                if path_match is None or data_match is None:
                    continue
                path = path_match.group(1)
                require(path == call["filePath"], "fixture read result names a different file")
                lines = delivered.setdefault(path, {})
                offset = call.get("offset", 1)
                limit = call.get("limit", 2000)
                for line in data_match.group(1).splitlines():
                    match = re.fullmatch(r"(\d+):(?: (.*))?", line)
                    if match:
                        number, text = int(match.group(1)), match.group(2) or ""
                        require(offset <= number < offset + limit, "fixture read returned undeclared line range")
                        require(number not in lines or lines[number] == text, "fixture read history conflicts")
                        lines[number] = text
    return delivered


def verify_delivery(body: dict, expected: dict[str, str]) -> dict:
    """Missing/truncated/mismatched data rejects; read issuance is insufficient."""
    delivered = visible_read_lines(body)
    proof = {}
    for path, text in expected.items():
        expected_lines = text.splitlines()
        actual = delivered.get(path, {})
        require(all(actual.get(i) == line for i, line in enumerate(expected_lines, 1)),
                "required complete evidence is absent or truncated in the model transcript: " + path)
        proof[path] = {"sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                       "source_lines": len(expected_lines), "all_lines_model_visible": True}
    return proof


class SDKMock(FrozenMock):
    """C1 composite: INV edits, DOM normally keeps base, AGG composes and edits."""
    def __init__(self, *, editor_mode: str = "c1", **kwargs: Any):
        self.c1_mode = editor_mode == "c1"
        self.c1_sessions: dict[str, dict] = {}
        self.c1_errors: list[dict] = []
        self._c1: dict[str, dict] = {}
        self._registered: dict[str, dict] = {}
        self._registered_system: dict[str, str] = {}
        super().__init__(editor_mode="standard" if self.c1_mode else editor_mode, **kwargs)

    def register_contract(self, label: str, prepared: dict) -> None:
        manifest = copy.deepcopy(prepared["manifest"])
        require(manifest.get("label") == label and manifest.get("sha256") ==
                digest({k: v for k, v in manifest.items() if k != "sha256"}),
                "fixture registration requires the frozen native stage contract")
        require(label not in self._registered or self._registered[label] == manifest,
                "fixture logical stage contract changed")
        system = prepared.get("authoring_system_text")
        if not isinstance(system, str) or not system.startswith("BUDDHA2-C1-OPEN-CODE-SYSTEM-V1\n"):
            raise ContractError("fixture requires the declared C1 system profile before OpenCode starts")
        require(label not in self._registered_system or self._registered_system[label] == system,
                "fixture logical stage system profile changed")
        self._registered[label] = manifest
        self._registered_system[label] = system

    @staticmethod
    def _context_file(cwd: Path, name: str) -> Path:
        path = cwd / "context" / name
        require(not Path(name).is_absolute() and ".." not in Path(name).parts,
                "fixture evidence path escaped context")
        require(not any(p.is_symlink() for p in (path, *path.parents)) and path.is_file(),
                "fixture evidence is not an ordinary file")
        return path

    def _start(self, cwd: Path, label: str) -> dict:
        manifest_path = self._context_file(cwd, "C1_MANIFEST.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        require(manifest.get("kind") == "phase3a-c1-evidence-v1"
                and manifest.get("sha256") == digest({k: v for k, v in manifest.items() if k != "sha256"}),
                "fixture requires the sealed C1 evidence manifest")
        require(self._registered.get(label) == manifest, "fixture manifest was not frozen before OpenCode execution")
        require(manifest.get("label") == label and manifest.get("role") == label[:3].upper(),
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
        initial = json.loads(self._context_file(cwd, "harness/systemprompt.md").read_text(encoding="utf-8"))
        require(set(initial) == set(strategy.FIELDS) and all(isinstance(v, str) and v.strip() for v in initial.values()),
                "fixture requires a valid initial three-string strategy")
        state = {"manifest": manifest, "expected": expected, "reads": reads, "initial": initial,
                 "current_path": str(cwd / "context/harness/systemprompt.md"), "cwd": cwd, "source_proof": source_proof}
        self._c1[label] = state
        self.c1_sessions[label] = {"fixture": True, "manifest_sha256": manifest["sha256"],
            "decision_after_complete_evidence": False, "verification_after_write": False,
            "decision": "KEEP_BASE" if label.startswith("dom") else "EDIT", "ordinary_rounds": 0,
            "terminal_note_used": False, "source_evidence": {},
            "mission_visible_before_evidence": False, "configured_system_visible_before_mission": False}
        return state

    @staticmethod
    def _tools(items: list[tuple[str, str, dict]]) -> list[dict]:
        return [{"type": "tool_use", "id": identity, "name": name, "input": payload,
                 "caller": {"type": "direct"}} for identity, name, payload in items]

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
        require(system.startswith("BUDDHA2-C1-OPEN-CODE-SYSTEM-V1\n") and configured in system,
                "actual OpenCode system profile differs from its frozen C1 contract/index")
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

    def _handle(self, request, *, http_module):
        if not self.c1_mode or self._selected is None or self._selected[0] != "editor":
            return super()._handle(request, http_module=http_module)
        role, slot = self._selected
        body = json.loads(request.content)
        require(str(request.url) == "https://api.anthropic.com/v1/messages" and body["model"] == "claude-opus-5",
                "fixture refuses a different editor endpoint/model")
        try:
            content, stop = self._editor_content(body, slot)
        except ContractError as exc:
            self.c1_errors.append({"slot_id": slot, "reason": str(exc)})
            raise
        request_id = f"phase3a-c1-mock-{len(self.records) + 1:04}"
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