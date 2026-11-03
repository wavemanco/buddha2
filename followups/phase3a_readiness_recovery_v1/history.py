"""HI ordinary history invariant plus the sole pinned terminal16 continuation."""

from __future__ import annotations

import copy
import re
from collections import Counter
from collections.abc import Callable

from buddha2.artifacts import ContractError, digest
from followups.phase3a_c1_completion_v3.evidence import _body, _without_cache
from followups.phase3a_v1.editor import _terminal_shape


class HistoryGuard:
    """Owned ordinary1-15 history plus an explicit exact terminal16 branch."""

    def __init__(self, delegate: Callable, prefix: str):
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,140}", prefix):
            raise ContractError("invalid history conversation identity")
        self.delegate, self.prefix = delegate, prefix
        self.responses: list[list[dict]] = []
        self.previous_messages: list[dict] | None = None
        self.audits: list[dict] = []
        self.controls: dict | None = None
        self.stopped = False

    def __call__(self, slot: str, role: str, request: dict) -> dict:
        if self.stopped:
            raise ContractError("history conversation is stopped")
        try:
            return self._call(slot, role, request)
        except Exception:
            self.stopped = True
            raise

    def _call(self, slot: str, role: str, request: dict) -> dict:
        if (
            role != "editor"
            or slot != f"{self.prefix}.t{len(self.responses) + 1:02}"
            or len(self.responses) >= 16
        ):
            raise ContractError("history belongs to another conversation or turn")
        body = _body(request, set())
        controls = _without_cache({key: value for key, value in body.items() if key != "messages"})
        if self.controls is not None and controls != self.controls:
            raise ContractError(
                "history changed its effective instructions, tools or model controls"
            )
        messages = _without_cache(body["messages"])
        terminal = len(self.responses) == 15
        # OpenCode's only terminal delta is an extra pinned maximum-steps message.
        # The relay has already bound its exact assistant→user role translation.
        if terminal:
            if not messages or messages[-1].get("role") != "user" or not _terminal_shape(messages[-1]):
                raise ContractError("terminal16 lacks its sole pinned control")
            continuing = messages[:-1]
        else:
            continuing = messages
            if messages and _terminal_shape(messages[-1]):
                raise ContractError("terminal control appeared before terminal16")
        if not isinstance(continuing, list) or not continuing or continuing[-1].get("role") != "user":
            raise ContractError("history requires a continuing user/tool message")
        if self.previous_messages is not None:
            prefix = self.previous_messages
            # Native tool turns add exactly the previous assistant and its user tool results.
            if len(continuing) != len(prefix) + 2 or continuing[: len(prefix)] != prefix:
                raise ContractError("history changed its complete prior message prefix")
            assistant, user = continuing[-2:]
            if assistant != {
                "role": "assistant",
                "content": _without_cache(self.responses[-1]),
            }:
                raise ContractError("history omitted or changed provider-returned assistant blocks")
            expected = [b["id"] for b in self.responses[-1] if b.get("type") == "tool_use"]
            blocks = user.get("content")
            if (
                not expected
                or not isinstance(blocks, list)
                or any(b.get("type") != "tool_result" for b in blocks)
                or Counter(b.get("tool_use_id") for b in blocks) != Counter(expected)
            ):
                raise ContractError("history lacks exactly the previous tool results")
        elif len(continuing) != 1 or continuing[0].get("role") != "user":
            raise ContractError("history started with unowned provider state")
        # Delegate validates controls/payload/reservations after this invariant, before dispatch.
        result = self.delegate(slot, role, request)
        if result.get("status") != "response":
            raise ContractError("history cannot advance after an unresolved provider result")
        response = result["response"]["provider_response"]
        if response.get("stop_reason") not in {"tool_use", "end_turn"}:
            raise ContractError("history cannot advance after an incomplete provider response")
        content = response["content"]
        if not isinstance(content, list) or not content:
            raise ContractError("provider returned missing history blocks")
        for block in content:
            if not isinstance(block, dict) or block.get("type") not in {
                "text",
                "thinking",
                "redacted_thinking",
                "tool_use",
            }:
                raise ContractError("provider returned an unsupported history block")
            if block["type"] == "thinking" and (
                set(block) != {"type", "thinking", "signature"}
                or not isinstance(block["thinking"], str)
                or not isinstance(block["signature"], str)
                or not block["signature"]
            ):
                raise ContractError("thinking requires exact text and opaque nonempty signature")
            if block["type"] == "redacted_thinking" and (
                set(block) != {"type", "data"}
                or not isinstance(block["data"], str)
                or not block["data"]
            ):
                raise ContractError("redacted thinking requires opaque nonempty data")
        ids = [b["id"] for b in content if b.get("type") == "tool_use"]
        if len(ids) != len(set(ids)):
            raise ContractError("provider returned duplicate tool identities")
        if bool(ids) != (response["stop_reason"] == "tool_use"):
            raise ContractError("provider completion reason differs from its tool blocks")
        if ids and content[-1]["type"] in {"thinking", "redacted_thinking"}:
            raise ContractError("tool-use response cannot end with a thinking block")
        self.previous_messages = copy.deepcopy(messages)
        self.controls = copy.deepcopy(controls)
        self.responses.append(copy.deepcopy(content))
        self.audits.append(
            {
                "slot_id": slot,
                "request_sha256": digest(request),
                "response_content_sha256": digest(content),
                "history_preserved": True,
                "history_restored": False,
                "terminal_control": terminal,
                "terminal_control_sha256": digest(messages[-1]) if terminal else None,
            }
        )
        return result
