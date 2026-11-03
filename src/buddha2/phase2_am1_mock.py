"""Credential-free, socket-blocked HTTP fixtures through the actual pinned SDKs.

These responses exercise serialization and accounting, not model behavior. The
helper cannot create a real transport: it supplies only in-memory MockTransport
objects, the literal fixture key and the reviewed AM-1 controls.
"""

from __future__ import annotations

import copy
import json
import re
from contextlib import ExitStack
from importlib.metadata import version
from typing import Any
from unittest.mock import patch

from .artifacts import ContractError
from .phase2_dispatch import FROZEN_PROFILES, DirectSDKTransport

_FAULT_ROLES = {"missing-write": "group", "unknown-usage": "group",
                "malformed-plan": "plan", "wrong-model": None,
                "unknown-tier": None, "over-input": None, "timeout": None}


def _no_socket(*args: Any, **kwargs: Any) -> Any:
    raise ContractError("external sockets are disabled during the SDK mock")


class SDKMock:
    """Select an accountable slot before each dispatch; inspect safe wire records.

    ``partition`` is ``distinct`` (ten heads) or ``pairs`` (five heads).
    ``fault`` optionally mutates the first matching response, restricted further
    by ``fault_slot`` when supplied. No authorization headers or keys are saved.
    """

    def __init__(self, *, partition: str = "distinct", fault: str | None = None,
                 fault_slot: str | None = None):
        if partition not in {"distinct", "pairs"} or fault not in {None, *_FAULT_ROLES}:
            raise ContractError("unknown SDK mock partition or fault")
        if fault_slot is not None and (fault is None or not isinstance(fault_slot, str)
                                       or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,180}", fault_slot)):
            raise ContractError("invalid SDK mock fault slot")
        self.partition, self.fault, self.fault_slot = partition, fault, fault_slot
        self.records: list[dict[str, Any]] = []
        self.transport: DirectSDKTransport
        self._stack: ExitStack | None = None
        self._selected: tuple[str, str] | None = None
        self.fault_triggered = False

    @property
    def http_calls(self) -> int:
        return len(self.records)

    def __enter__(self) -> SDKMock:
        if self._stack is not None:
            raise ContractError("SDK mock context is already active")
        # Import the real SDKs before patching socket construction: imported SSL
        # classes may inherit socket.socket, but importing performs no API call.
        import anthropic  # noqa: F401
        import httpx
        import httpx2
        import openai  # noqa: F401

        from .phase2_am1_controls import CONTROL_POLICY

        if version("anthropic") != "1.4.0" or version("openai") != "1.107.0":
            raise ContractError("SDK mock requires the exact retained SDK versions")
        stack = ExitStack()
        try:
            for target in ("socket.socket", "socket.create_connection", "socket.getaddrinfo"):
                stack.enter_context(patch(target, side_effect=_no_socket))
            self.transport = DirectSDKTransport(
                anthropic_api_key="fixture-not-a-secret", openai_api_key="fixture-not-a-secret",
                control_policy=CONTROL_POLICY,
                http_transports={
                    "anthropic": httpx2.MockTransport(lambda req: self._handle(req, http_module=httpx2)),
                    "openai": httpx.MockTransport(lambda req: self._handle(req, http_module=httpx))})
            setattr(self.transport, "select", self.select)
            stack.callback(self.transport._anthropic.close)
            stack.callback(self.transport._openai.close)
        except BaseException:
            stack.close()
            raise
        self._stack = stack
        return self

    def __exit__(self, *exc: Any) -> None:
        stack, self._stack = self._stack, None
        self._selected = None
        if stack is not None:
            stack.close()

    def select(self, role: str, slot_id: str) -> None:
        if (self._stack is None or role not in FROZEN_PROFILES or not isinstance(slot_id, str)
                or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,180}", slot_id)):
            raise ContractError("select a valid role/slot within the SDK mock context")
        self._selected = role, slot_id

    def _apply_fault(self, role: str, slot: str, response: dict) -> bool:
        if (self.fault is None or self.fault_triggered
                or self.fault_slot is not None and slot != self.fault_slot
                or _FAULT_ROLES[self.fault] not in {None, role}):
            return False
        self.fault_triggered = True
        if self.fault == "missing-write":
            del response["usage"]["prompt_tokens_details"]["cache_write_tokens"]
        elif self.fault == "unknown-usage":
            response["usage"]["unpriced_tokens"] = 7
        elif self.fault == "wrong-model":
            response["model"] = "unexpected-substitute-model"
        elif self.fault == "unknown-tier":
            target = response if role == "group" else response["usage"]
            target["service_tier"] = "unpriced-tier"
        elif self.fault == "over-input":
            response["usage"]["prompt_tokens" if role == "group" else "input_tokens"] = 2000000
            if role == "group":
                response["usage"]["total_tokens"] = 2000000 + response["usage"]["completion_tokens"]
        elif self.fault == "malformed-plan":
            response["content"][0]["text"] = '{"angles":[]}'
        return self.fault == "timeout"

    def _handle(self, request: Any, *, http_module: Any) -> Any:
        if self._selected is None:
            raise ContractError("SDK mock HTTP call has no declared role/slot")
        role, slot = self._selected
        body = json.loads(request.content.decode("utf-8"))
        endpoint = ("https://api.openai.com/v1/chat/completions" if role == "group"
                    else "https://api.anthropic.com/v1/messages")
        if str(request.url) != endpoint or request.method != "POST":
            raise ContractError("SDK mock refuses an undeclared endpoint")
        if body.get("model") != FROZEN_PROFILES[role]["model"]:
            raise ContractError("SDK mock received a changed model profile")
        if role == "plan":
            text = json.dumps({"angles": [{"id": f"angle-{i:02d}", "angle": f"mock direction {i}"}
                                         for i in range(1, 11)]})
        elif role == "rank":
            supplied = json.loads(body["messages"][0]["content"])
            text = json.dumps({"order": [row["id"] for row in reversed(supplied["responses"])]})
        elif role == "group":
            groups = ([[i] for i in range(10)] if self.partition == "distinct"
                      else [[i, i + 1] for i in range(0, 10, 2)])
            text = json.dumps({"groups": groups})
        elif role == "quality":
            text = '{"score":5}'
        else:
            text = "Synthetic SDK fixture answer for " + slot
        request_id = f"mock-request-{len(self.records) + 1:04d}"
        if role == "group":
            response = {"id": "chatcmpl-" + request_id, "object": "chat.completion", "created": 0,
                        "model": body["model"], "service_tier": "default",
                        "choices": [{"index": 0, "message": {"role": "assistant", "content": text,
                                     "refusal": None}, "finish_reason": "stop"}],
                        "usage": {"prompt_tokens": 120, "completion_tokens": 24, "total_tokens": 144,
                                  "prompt_tokens_details": {"cached_tokens": 16, "cache_write_tokens": 32},
                                  "completion_tokens_details": {"reasoning_tokens": 4}}}
        else:
            write, read = (0, 0) if role == "quality" else (16, 8)
            response = {"id": "msg-" + request_id, "type": "message", "role": "assistant",
                        "model": body["model"], "content": [{"type": "text", "text": text}],
                        "stop_reason": "end_turn", "stop_sequence": None,
                        "usage": {"input_tokens": 80, "output_tokens": 24,
                                  "cache_creation_input_tokens": write, "cache_read_input_tokens": read,
                                  "cache_creation": {"ephemeral_5m_input_tokens": write,
                                                     "ephemeral_1h_input_tokens": 0},
                                  "service_tier": "standard", "inference_geo": "global"}}
        previous_fault = self.fault_triggered
        timeout = self._apply_fault(role, slot, response)
        current_fault = self.fault_triggered and not previous_fault
        self.records.append({"role": role, "slot_id": slot, "url": str(request.url),
                             "method": request.method, "request": copy.deepcopy(body),
                             "model": body["model"], "request_id": request_id,
                             "http_status": None if timeout else 200,
                             "response": None if timeout else copy.deepcopy(response),
                             "fault": self.fault if current_fault else None})
        if timeout:
            raise http_module.ReadTimeout("scripted in-memory mock timeout", request=request)
        return http_module.Response(200, json=response, headers={"request-id": request_id,
                                                               "x-request-id": request_id})
