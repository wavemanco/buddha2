"""Actual-SDK fixtures; the real OpenCode tool loop runs on a network-none host."""
from __future__ import annotations

import copy
import json
import re
import threading
from pathlib import Path

from buddha2.artifacts import ContractError
from buddha2.phase2_am1_mock import SDKMock as ParentMock

from . import strategy
from .accounting import ROLES
from .transport import Transport


class SDKMock(ParentMock):
    def __init__(self, *, editor_invalid_first=False, editor_mode="standard", **kwargs):
        if editor_mode not in {"standard", "seven_turn", "terminal_unchanged", "terminal_changed", "ninth_tool"}:
            raise ContractError("unknown editor fixture mode")
        self._context = threading.local()
        self.editor_invalid_first = editor_invalid_first
        self.editor_mode = editor_mode
        super().__init__(**kwargs)

    @property
    def _selected(self):
        return getattr(self._context, "selected", None)

    @_selected.setter
    def _selected(self, value):
        self._context.selected = value

    def __enter__(self):
        import httpx
        import httpx2
        self.transport = Transport(anthropic_api_key="fixture-not-a-secret", openai_api_key="fixture-not-a-secret",
            http_transports={"anthropic": httpx2.MockTransport(lambda req: self._handle(req, http_module=httpx2)),
                             "openai": httpx.MockTransport(lambda req: self._handle(req, http_module=httpx))})
        self.transport.select = self.select
        return self

    def __exit__(self, *exc):
        self.transport._anthropic.close()
        self.transport._openai.close()

    def select(self, role: str, slot: str):
        if role not in ROLES or not isinstance(slot, str):
            raise ContractError("mock requires an exact phase role/slot")
        self._selected = role, slot

    def _handle(self, request, *, http_module):
        if self._selected is None:
            raise ContractError("mock dispatch has no frozen slot")
        role, slot = self._selected
        if role not in {"editor", "fixed_selector"}:
            return super()._handle(request, http_module=http_module)
        body = json.loads(request.content)
        if str(request.url) != "https://api.anthropic.com/v1/messages" or body["model"] != "claude-opus-5":
            raise ContractError("mock refuses a different editor endpoint/model")
        content: list[dict] = []
        stop = "end_turn"
        if role == "fixed_selector":
            supplied = json.loads(body["messages"][0]["content"])
            content = [{"type": "text", "text": json.dumps({"candidate_id": supplied["candidates"][0]["id"]})}]
        else:
            system = "\n".join(part["text"] for part in body["system"])
            match = re.search(r"Working directory: ([^\r\n]+)", system)
            if not match:
                raise ContractError("actual OpenCode working-directory evidence is missing")
            cwd = match.group(1).strip()
            turn = int(slot.rsplit(".t", 1)[1])
            if turn == 1:
                content = [{"type": "tool_use", "id": "read_mission", "name": "read",
                            "input": {"filePath": cwd + "/MISSION.md"}},
                           {"type": "tool_use", "id": "read_strategy", "name": "read",
                            "input": {"filePath": cwd + "/context/harness/systemprompt.md"}}]
                evidence = ["rollouts/base1.md"]
                if ".agg1." in slot:
                    evidence += [f"pool/{stage}/{name}" for stage in ("inv1", "dom1")
                                 for name in ("rollout.md", "harness/systemprompt.md")]
                for index, name in enumerate(evidence):
                    path = Path(cwd) / "context" / name
                    if path.is_file():
                        content.append({"type": "tool_use", "id": f"read_evidence_{index}", "name": "read",
                                        "input": {"filePath": str(path)}})
                stop = "tool_use"
            elif (self.editor_mode == "standard" and turn == 2 or
                  self.editor_mode in {"seven_turn", "terminal_changed"} and turn == 6):
                payload = strategy.seed_templates()
                # Deliberate synthetic changes test consumption and lineage, not research effectiveness.
                field = "answer_system" if ".inv1." in slot else "plan_system" if ".dom1." in slot else "rank_system"
                payload[field] += "\nOffline fixture instruction for " + slot.split(".editor.", 1)[1].split(".t", 1)[0]
                payload = {key: payload[key] for key in strategy.FIELDS}
                proposed_text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
                if self.editor_invalid_first and ".inv1.a1." in slot:
                    proposed_text = "{}"
                content = [{"type": "tool_use", "id": "write_strategy", "name": "write", "input": {
                    "filePath": cwd + "/context/harness/systemprompt.md",
                    "content": proposed_text}},
                    {"type": "tool_use", "id": "write_answer", "name": "write", "input": {
                    "filePath": cwd + "/output/answer.md", "content": "Offline fixture edited the declared strategy."}}]
                stop = "tool_use"
            elif (self.editor_mode == "seven_turn" and 2 <= turn <= 5
                    or self.editor_mode == "terminal_changed" and turn in {2, 3, 4, 5, 7}
                    or self.editor_mode == "terminal_unchanged" and 2 <= turn <= 7
                    or self.editor_mode == "ninth_tool" and 2 <= turn <= 8):
                content = [{"type": "tool_use", "id": f"read_round_{turn}", "name": "read",
                            "input": {"filePath": cwd + "/MISSION.md"}}]
                stop = "tool_use"
            else:
                content = [{"type": "text", "text": "Offline fixture edited the declared strategy."}]
                if self.editor_mode == "terminal_unchanged":
                    content[0]["text"] = "Offline fixture reached the step limit without changing the strategy."
        # Real client-tool responses retain this metadata through OpenCode's next history.
        for block in content:
            if block["type"] == "tool_use":
                block["caller"] = {"type": "direct"}
        request_id = f"phase3a-mock-{len(self.records) + 1:04}"
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
