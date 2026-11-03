"""Explicit-key transport. No environment credentials, retries or provider probes."""
from __future__ import annotations

import json
import os
import re
import time
from importlib.metadata import version

from buddha2.artifacts import ContractError
from buddha2.phase2_am1_controls import CONTROL_POLICY, normalize_group_usage
from buddha2.phase2_dispatch import DirectSDKTransport, _validate_request

_FAILURE_STAGES = {
    "timeout": {"provider_call"}, "connection": {"provider_call"},
    "provider_status": {"provider_call"}, "transport_error": {"provider_call"},
    "processing_error": {"transport_select", "response_conversion", "response_copy", "accounting", "serialization"},
    "accounting_unknown": {"accounting"}, "unresolved_intent": {"journal_replay"},
}
_RESPONSE_FIELDS = {"model", "text", "stop_reason", "request_id", "message_id", "usage",
                    "provider_usage", "refusal", "latency_seconds", "provider_response", "content"}
_PROVIDER_FIELDS = {"id", "type", "role", "model", "content", "stop_reason", "stop_sequence", "usage",
                    "object", "created", "choices", "service_tier", "system_fingerprint"}


def provider_request_id(value):
    return value if isinstance(value, str) and re.fullmatch(r"req_[A-Za-z0-9_-]{1,120}", value) else None


def validate_failure(value: dict) -> None:
    if type(value) is not dict or set(value) != {"category", "stage", "status_code", "provider_request_id"}:
        raise ContractError("invalid bounded failure evidence")
    category, stage, status = value["category"], value["stage"], value["status_code"]
    if (type(category) is not str or type(stage) is not str or category not in _FAILURE_STAGES
            or stage not in _FAILURE_STAGES[category]
            or value["provider_request_id"] is not None and provider_request_id(value["provider_request_id"]) is None
            or (type(status) is not int or not 400 <= status <= 599
                if category == "provider_status" else status is not None)):
        raise ContractError("invalid bounded failure evidence")


def make_failure(category: str, stage: str, *, status_code=None, request_id=None) -> dict:
    value = {"category": category, "stage": stage, "status_code": status_code,
             "provider_request_id": provider_request_id(request_id)}
    validate_failure(value)
    return value


def failure_from_exception(error: Exception, stage: str, *, request_id=None) -> dict:
    import anthropic
    import openai

    if stage != "provider_call":
        return make_failure("processing_error", stage, request_id=request_id)
    if isinstance(error, (anthropic.APITimeoutError, openai.APITimeoutError, TimeoutError)):
        return make_failure("timeout", stage)
    if isinstance(error, (anthropic.APIConnectionError, openai.APIConnectionError, ConnectionError)):
        return make_failure("connection", stage)
    if isinstance(error, (anthropic.APIStatusError, openai.APIStatusError)):
        status = getattr(error, "status_code", None)
        if type(status) is int and 400 <= status <= 599:
            return make_failure("provider_status", stage, status_code=status,
                request_id=getattr(error, "request_id", None))
    return make_failure("transport_error", stage)


def retain_response(value) -> dict | None:
    """Keep only a bounded JSON response, never an exception or HTTP error body."""
    if not isinstance(value, dict):
        return None
    kept = {key: item for key, item in value.items() if key in _RESPONSE_FIELDS}
    if "request_id" in kept:
        kept["request_id"] = provider_request_id(kept["request_id"])
    if "provider_response" in kept:
        payload = kept["provider_response"]
        kept["provider_response"] = {key: item for key, item in payload.items() if key in _PROVIDER_FIELDS} if isinstance(payload, dict) else None
    try:
        encoded = json.dumps(kept, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
        return json.loads(encoded) if len(encoded) <= 8_388_608 else None
    except (TypeError, ValueError, OverflowError):
        return None


class TransportFailure(Exception):
    """Only allowlisted facts and a JSON response cross the trusted boundary."""

    def __init__(self, failure: dict, response=None):
        validate_failure(failure)
        self.failure = dict(failure)
        self.response = retain_response(response)
        super().__init__("bounded provider boundary failure")


def reject_final_assistant_prefill(role: str, request: dict) -> None:
    messages = request.get("messages")
    if (role != "group" and isinstance(messages, list) and messages
            and isinstance(messages[-1], dict) and messages[-1].get("role") == "assistant"):
        raise ContractError("unsupported final assistant prefill")


class Transport(DirectSDKTransport):
    def __init__(self, *, anthropic_api_key: str, openai_api_key: str, http_transports=None):
        import anthropic
        import openai
        if any(name.startswith(("ANTHROPIC_", "OPENAI_")) or name.upper() in {
                "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR"}
               for name in os.environ):
            raise ContractError("ambient provider or transport overrides are not permitted")
        if version("anthropic") != "1.4.0" or version("openai") != "1.107.0":
            raise ContractError("Phase 3A requires its pinned SDK versions")
        if any(not isinstance(key, str) or not key.strip() for key in (anthropic_api_key, openai_api_key)):
            raise ContractError("two explicit keys are required")
        clients: dict[str, dict] = {"anthropic": {}, "openai": {}}
        self.fixture = False
        if http_transports is not None:
            import httpx
            import httpx2
            if (anthropic_api_key != "fixture-not-a-secret" or openai_api_key != "fixture-not-a-secret"
                    or not isinstance(http_transports, dict) or set(http_transports) != set(clients)
                    or type(http_transports["anthropic"]) is not httpx2.MockTransport
                    or type(http_transports["openai"]) is not httpx.MockTransport):
                raise ContractError("offline transports require concrete SDK mocks and fixed fake keys")
            clients = {name: {"transport": value} for name, value in http_transports.items()}
            self.fixture = True
        self.control_policy = CONTROL_POLICY
        self._anthropic = anthropic.Anthropic(
            api_key=anthropic_api_key, base_url="https://api.anthropic.com", max_retries=0, timeout=90.0,
            http_client=anthropic.DefaultHttpxClient(trust_env=False, follow_redirects=False,
                timeout=90.0, **clients["anthropic"]))
        self._openai = openai.OpenAI(
            api_key=openai_api_key, base_url="https://api.openai.com/v1", max_retries=0, timeout=90.0,
            http_client=openai.DefaultHttpxClient(trust_env=False, follow_redirects=False,
                timeout=90.0, **clients["openai"]))

    def create(self, role: str, request: dict) -> dict:
        reject_final_assistant_prefill(role, request)
        if role in {"editor", "fixed_selector"}:
            output_config = request.get("output_config", {})
            if role == "fixed_selector" and isinstance(output_config, dict):
                output_config = {k: v for k, v in output_config.items() if k != "format"}
            if (request.get("model") != "claude-opus-5"
                or request.get("max_tokens") != 16000
                or request.get("thinking") != {"type": "adaptive"}
                or output_config != {"effort": "high"}
                or request.get("service_tier") != "standard_only"
                    or request.get("inference_geo") != "global"):
                raise ContractError("editor/selector controls differ from the frozen profile")
        else:
            _validate_request(role, request)
        started = time.monotonic()
        try:
            result = (self._openai.chat.completions.create(**request) if role == "group"
                      else self._anthropic.messages.create(**request))
        except Exception as error:
            raise TransportFailure(failure_from_exception(error, "provider_call")) from None
        raw = None
        request_id = provider_request_id(getattr(result, "_request_id", None))
        try:
            raw = result.model_dump(mode="json", exclude_none=True)
            if not isinstance(raw, dict):
                raise TypeError
            if role == "group":
                usage = raw.get("usage") or {}
                choice = raw["choices"][0]
                return {"model": raw["model"], "text": choice["message"].get("content") or "",
                    "stop_reason": choice["finish_reason"], "refusal": choice["message"].get("refusal"),
                    "request_id": request_id, "message_id": raw["id"],
                    "usage": normalize_group_usage(usage, raw.get("service_tier")),
                    "provider_usage": usage, "latency_seconds": time.monotonic() - started}
            response = {"model": raw["model"],
                "text": "".join(block["text"] for block in raw["content"] if block["type"] == "text"),
                "stop_reason": raw["stop_reason"], "request_id": request_id,
                "message_id": raw["id"], "usage": raw["usage"],
                "latency_seconds": time.monotonic() - started}
            if role in {"editor", "fixed_selector"}:
                response["provider_response"] = raw
            return response
        except Exception as error:
            kept = {"provider_response": raw, "request_id": request_id} if isinstance(raw, dict) else None
            raise TransportFailure(failure_from_exception(error, "response_conversion", request_id=request_id), kept) from None
