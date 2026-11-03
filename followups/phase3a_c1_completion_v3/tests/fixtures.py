"""Actual pinned SDK mocks for ledger tests; no production or live bypass."""
from __future__ import annotations

import copy
import json
import time
from typing import Any

from followups.phase3a_c1_completion_v3.transport import Transport as BoundedTransport


class Transport(BoundedTransport):
    """Keep the legacy test knobs while crossing the new real SDK/worker boundary."""

    def __init__(self, *, fault: str | None = None, input_tokens: int = 80,
                 output_tokens: int = 24, **kwargs: Any):
        import httpx
        import httpx2

        self.fault, self.input_tokens, self.output_tokens = fault, input_tokens, output_tokens
        self.calls: list[tuple[str, dict]] = []
        self.inflight = self.maximum_inflight = 0
        self._selected_role = ""

        def handle(request, module):
            body = json.loads(request.content)
            self.calls.append((self._selected_role, copy.deepcopy(body)))
            self.inflight += 1
            self.maximum_inflight = max(self.maximum_inflight, self.inflight)
            try:
                if fault == "slow":
                    time.sleep(.03)
                model = "different-model" if fault == "wrong-model" else body["model"]
                usage = {"input_tokens": input_tokens, "output_tokens": output_tokens,
                    "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
                    "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 0},
                    "service_tier": "standard", "inference_geo": "global"}
                if fault == "unknown":
                    usage["unsupported_usage"] = 1
                elif fault == "server_tool":
                    usage["server_tool_use"] = {"web_search_requests": 1}
                if body["model"] == "gpt-5.6-luna":
                    raw = {"id": "chatcmpl-fixture", "object": "chat.completion", "created": 0,
                        "model": model, "choices": [{"index": 0, "message": {
                            "role": "assistant", "content": "Synthetic response"}, "finish_reason": "stop"}],
                        "service_tier": "default", "usage": {"prompt_tokens": input_tokens,
                            "completion_tokens": output_tokens, "total_tokens": input_tokens + output_tokens}}
                else:
                    raw = {"id": "msg_fixture", "type": "message", "role": "assistant", "model": model,
                        "content": [{"type": "text", "text": "Synthetic response"}],
                        "stop_reason": "end_turn", "usage": usage}
                return module.Response(200, json=raw, headers={"request-id": "req_fixture"})
            finally:
                self.inflight -= 1

        mocks = {"anthropic": httpx2.MockTransport(lambda request: handle(request, httpx2)),
                 "openai": httpx.MockTransport(lambda request: handle(request, httpx))}
        if fault == "timeout":
            kwargs["fixture_behavior"] = {"failure": "read"}
        super().__init__(anthropic_api_key="fixture-not-a-secret", openai_api_key="fixture-not-a-secret",
                         http_transports=mocks, **kwargs)
        self.select = self._select

    def _select(self, role: str, slot: str) -> None:
        self._selected_role = role
