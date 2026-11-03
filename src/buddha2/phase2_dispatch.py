"""Phase 2's single-attempt dispatch journal, with fail-closed live admission.

The offline byte estimate is deliberately *not* certified as a provider token
bound. Current live dispatch is blocked even with a spending grant. A later
reviewed admission implementation is needed before this kit can spend money.
"""

from __future__ import annotations

import copy
import json
import os
import re
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Protocol

from . import phase2_am1_controls as am1
from .artifacts import ContractError, digest, read_json, write_once

_SONNET = {"provider": "anthropic", "model": "claude-sonnet-5-5", "max_tokens": 4096,
           "thinking": {"type": "adaptive"}, "output_config": {"effort": "low"},
           "service_tier": "standard_only", "inference_geo": "global",
           "input_limit": 8000, "reserved_output": 4096}
FROZEN_PROFILES: dict[str, dict[str, Any]] = {
    "answer": copy.deepcopy(_SONNET), "plan": copy.deepcopy(_SONNET),
    "rank": _SONNET | {"input_limit": 64000},
    "group": {"provider": "openai", "model": "gpt-5.6-luna", "input_limit": 64000,
              "reserved_output": 128000},
    "quality": {"provider": "anthropic", "model": "claude-opus-5", "max_tokens": 16000,
                "thinking": {"type": "adaptive"}, "output_config": {"effort": "high"},
                "input_limit": 8000, "reserved_output": 16000},
}
# Exact rates in hundredths of a micro-dollar per token, avoiding binary floats.
_RATES = {"sonnet": (200, 250, 10, 1000), "group": (20, 0, 2, 120),
          "quality": (500, 0, 50, 2500)}
ADMISSION_POLICY: dict[str, Any] = {"revision": "phase2-json-byte-candidate-v1", "framing_allowance": 2048,
                    "provider_verified": False,
                    "limitation": "Private provider framing/schema tokenization has no verified bound."}
_AUTH_FIELDS = {"study_sha256", "authorization_id", "authorized", "cap_micro_usd",
                "canary_cap_micro_usd", "expansion_authorized"}


class Transport(Protocol):
    fixture: bool

    def create(self, role: str, request: dict) -> dict: ...


def _role(role: str) -> dict:
    if role not in FROZEN_PROFILES:
        raise ContractError("unknown Phase 2 dispatch role")
    return FROZEN_PROFILES[role]


def build_request(role: str, *, messages: list, system: Any = None,
                  response_format: dict | None = None) -> dict:
    """Construct only declared role controls; native callers retain their templates."""
    profile = _role(role)
    request = {key: copy.deepcopy(value) for key, value in profile.items()
               if key not in {"provider", "input_limit", "reserved_output"}}
    request["messages"] = copy.deepcopy(messages)
    if system is not None:
        request["system"] = copy.deepcopy(system)
    if response_format is not None:
        request["response_format"] = copy.deepcopy(response_format)
    _validate_request(role, request)
    return request


def input_bound(request: dict, *, control_policy: dict | None = None,
                role: str | None = None) -> dict:
    """An auditable candidate estimate, not proof of real-provider admission.

    Counting the entire wire JSON includes text, UTF-8 expansion, role names and
    structured schema. The allowance is explicit; no claim is made that it
    bounds private control/schema expansion. Fixtures may use this exact
    synthetic byte policy. Live execution remains disabled.
    """
    if control_policy is not None:
        am1.validate_policy(control_policy)
        if role is None:
            raise ContractError("AM-1 admission requires its role")
        return am1.admission(role, request)
    try:
        raw = json.dumps(request, sort_keys=True, ensure_ascii=False,
                         allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ContractError("request is not canonical UTF-8 JSON") from exc
    return {**ADMISSION_POLICY, "serialized_utf8_bytes": len(raw),
            "candidate_tokens": len(raw) + ADMISSION_POLICY["framing_allowance"],
            "request_sha256": digest(request)}


def reservation(role: str, *, control_policy: dict | None = None) -> int:
    if control_policy is not None:
        am1.validate_policy(control_policy)
        return am1.reservation(role)
    profile = _role(role)
    rate = _RATES["group" if role == "group" else "quality" if role == "quality" else "sonnet"]
    input_rate = max(rate[0], rate[1])
    return (profile["input_limit"] * input_rate + profile["reserved_output"] * rate[3] + 99) // 100


def _text_content(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value)
    return isinstance(value, list) and bool(value) and all(
        isinstance(block, dict) and set(block).issubset({"type", "text", "cache_control"})
        and block.get("type") == "text" and isinstance(block.get("text"), str)
        and ("cache_control" not in block or block["cache_control"] in (
            {"type": "ephemeral"}, {"type": "ephemeral", "ttl": "5m"}))
        for block in value)


def _validate_request(role: str, request: Any) -> None:
    profile = _role(role)
    controls = {key: value for key, value in profile.items()
                if key not in {"provider", "input_limit", "reserved_output"}}
    if not isinstance(request, dict) or not set(request).issubset(
        set(controls) | {"messages", "system", "response_format"}
    ):
        raise ContractError("request overrides frozen profile or adds unsupported controls")
    actual_controls = {key: request.get(key) for key in controls}
    if role == "quality" and isinstance(actual_controls.get("output_config"), dict):
        config: Any = actual_controls["output_config"]
        if "format" in config:
            formatting = config["format"]
            if (not isinstance(formatting, dict) or set(formatting) != {"type", "schema"}
                    or formatting["type"] != "json_schema" or not isinstance(formatting["schema"], dict)):
                raise ContractError("native quality requires its declared structured JSON schema")
            actual_controls["output_config"] = {key: value for key, value in config.items() if key != "format"}
    if actual_controls != controls:
        raise ContractError("request overrides frozen profile or adds unsupported controls")
    messages = request.get("messages")
    if not isinstance(messages, list) or not messages or any(
        not isinstance(message, dict) or set(message) != {"role", "content"}
        or message["role"] not in {"system", "user", "assistant"}
        or not _text_content(message["content"]) for message in messages
    ):
        raise ContractError("only declared text messages are supported")
    if "system" in request and (profile["provider"] != "anthropic" or not _text_content(request["system"])):
        raise ContractError("unsupported system instruction")
    if profile["provider"] == "anthropic" and any(row["role"] == "system" for row in messages):
        raise ContractError("Anthropic system messages require the explicit system field")
    if "response_format" in request:
        value = request["response_format"]
        if role != "group" or not isinstance(value, dict) or value.get("type") != "json_schema":
            raise ContractError("only the native grouping structured schema is supported")
    if profile["provider"] != "anthropic" and any(
        isinstance(row["content"], list) for row in messages
    ):
        raise ContractError("native grouping uses plain text messages")
    input_bound(request)


@contextmanager
def writer_lock(run: Path) -> Iterator[None]:
    """One phase journal owner, including the complete provider request lifetime."""
    import fcntl

    if any(path.is_symlink() for path in (run, *run.parents)):
        raise ContractError("journal paths may not contain symlinks")
    run.mkdir(parents=True, exist_ok=True)
    if any(path.is_symlink() for path in run.rglob("*")):
        raise ContractError("journal paths may not contain symlinks")
    with (run / ".writer.lock").open("a+b") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ContractError("another concurrent writer owns the phase journal") from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def _validate_auth(value: Any, study: str, control_policy: dict | None = None) -> None:
    fields = _AUTH_FIELDS if control_policy is None else _AUTH_FIELDS | {
        "control_policy_sha256", "billing_profile"}
    if not isinstance(value, dict) or set(value) != fields or value["study_sha256"] != study:
        raise ContractError("authorization does not bind this exact study")
    if control_policy is not None:
        am1.validate_policy(control_policy)
        if (value["control_policy_sha256"] != am1.CONTROL_SHA256
                or value["billing_profile"] != am1.BILLING_PROFILE):
            raise ContractError("authorization lacks the exact AM-1 control/public-PAYG profile")
    if not isinstance(value["authorization_id"], str) or not 1 <= len(value["authorization_id"]) <= 200:
        raise ContractError("authorization evidence reference required")
    limits = (("cap_micro_usd", 125_000_000), ("canary_cap_micro_usd", 5_000_000)) if control_policy is None else (
        ("cap_micro_usd", am1.FULL_STUDY_MAX_MICRO_USD),
        ("canary_cap_micro_usd", am1.FIRST_BLOCK_MAX_MICRO_USD))
    if any(type(value[key]) is not bool for key in ("authorized", "expansion_authorized")) or any(
        type(value[key]) is not int or not 0 < value[key] <= limit
        for key, limit in limits
    ) or value["canary_cap_micro_usd"] > value["cap_micro_usd"]:
        raise ContractError("authorization exceeds the declared total/canary ceiling")


def _publish(path: Path, value: dict) -> None:
    """Publish atomically, then persist its directory entry before dispatch."""
    write_once(path, value)
    for parent in (path.parent, path.parent.parent):
        descriptor = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _model_matches(requested: str, returned: Any) -> bool:
    return isinstance(returned, str) and bool(re.fullmatch(re.escape(requested) + r"(?:-\d{8})?", returned))


def _zero(value: Any) -> bool:
    return value is None or type(value) is int and value == 0 or isinstance(value, dict) and all(
        _zero(item) for item in value.values())


def _account(role: str, response: Any, *, control_policy: dict | None = None) -> tuple[int | None, bool]:
    """Settle exact known token categories; unknowns never become free calls."""
    if control_policy is not None:
        am1.validate_policy(control_policy)
        return am1.account(role, response)
    profile = _role(role)
    if not isinstance(response, dict) or not _model_matches(profile["model"], response.get("model")):
        return None, False
    usage = response.get("usage")
    allowed = {"input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens",
               "cache_creation", "service_tier", "inference_geo", "speed", "output_tokens_details",
               "input_tokens_details", "server_tool_use"}
    if not isinstance(usage, dict) or set(usage).difference(allowed):
        return None, False
    categories = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    if any(type(usage.get(key, 0)) is not int or usage.get(key, 0) < 0 for key in categories) or any(
        key not in usage for key in ("input_tokens", "output_tokens")
    ):
        return None, False
    base, output, write, read = (usage.get(key, 0) for key in categories)
    cache = usage.get("cache_creation")
    if cache is not None and (not isinstance(cache, dict) or set(cache).difference({
        "ephemeral_5m_input_tokens", "ephemeral_1h_input_tokens"
    }) or type(cache.get("ephemeral_5m_input_tokens", 0)) is not int
        or cache.get("ephemeral_5m_input_tokens", 0) != write
        or not _zero(cache.get("ephemeral_1h_input_tokens"))):
        return None, False
    if (role in {"quality", "group"} and write) or not _zero(usage.get("server_tool_use")):
        return None, False
    if (usage.get("service_tier") not in (("default", "standard") if role == "group" else ("standard",))
            or usage.get("inference_geo") not in (None, "global")
            or usage.get("speed") not in (None, "standard")):
        return None, False
    rate = _RATES["group" if role == "group" else "quality" if role == "quality" else "sonnet"]
    cost = (base * rate[0] + write * rate[1] + read * rate[2] + output * rate[3] + 99) // 100
    valid = (base + write + read <= profile["input_limit"] and output <= profile["reserved_output"]
             and cost <= reservation(role))
    # Details are a breakdown of already billed input/output, not extra charges.
    thinking_detail = "reasoning_tokens" if role == "group" else "thinking_tokens"
    for name, permitted, total in (("output_tokens_details", {thinking_detail}, output),
                                   ("input_tokens_details", {"cached_tokens"}, base + read)):
        details = usage.get(name)
        if details is not None and (not isinstance(details, dict) or set(details).difference(permitted)
                                   or any(type(v) is not int or not 0 <= v <= total for v in details.values())):
            return None, False
    return cost, valid


def _result(intent: dict, response: Any, *, unknown: bool = False,
            control_policy: dict | None = None) -> dict:
    cost, valid = _account(intent["role"], response, control_policy=control_policy) if not unknown else (None, False)
    value = {"slot_id": intent["slot_id"], "role": intent["role"],
            "fixture": intent["fixture"], "study_sha256": intent["study_sha256"],
            "status": "response" if valid else "unknown", "response": response,
            "spent_micro_usd": cost,
            "reserved_micro_usd": 0 if valid else intent["reservation_micro_usd"],
            "request_sha256": intent["request_sha256"], "dispatch_id": intent["dispatch_id"],
            "intent_sha256": digest(intent)}
    if control_policy is not None:
        value["cost_basis"] = am1.CONTROL_POLICY["cost_basis"]
    return value


def replay_dispatch(run: Path) -> dict:
    """Reconcile immutable intents/results; an interrupted intent remains owed."""
    if any(path.is_symlink() for path in (run, *run.parents, *run.rglob("*"))):
        raise ContractError("journal paths may not contain symlinks")
    manifest = read_json(run / "manifest.json")
    if not isinstance(manifest, dict) or manifest.get("run_id") != digest(manifest.get("inputs")):
        raise ContractError("invalid dispatch manifest identity")
    inputs = manifest["inputs"]
    control_policy = inputs.get("control_policy")
    if control_policy is not None:
        am1.validate_policy(control_policy)
    expected_admission = ADMISSION_POLICY if control_policy is None else control_policy
    rates_valid = (inputs.get("rates_hundredths_micro_usd") == {key: list(value) for key, value in _RATES.items()}
                   if control_policy is None else inputs.get("rates_thousandths_micro_usd") ==
                   control_policy["maximum_rates_thousandths_micro_usd"])
    if (inputs.get("profiles") != FROZEN_PROFILES or inputs.get("admission") != expected_admission
            or not rates_valid):
        raise ContractError("stale dispatch profiles/admission")
    if control_policy is not None:
        _validate_auth(inputs.get("authorization", {}) | {"expansion_authorized": False},
                       inputs["study_sha256"], control_policy)
    spent = reserved = canary_spent = canary_reserved = 0
    results, seen = {}, set()
    blocked = False
    paths = sorted((run / "attempts").glob("*.intent.json"))
    for index, path in enumerate(paths, start=1):
        if blocked or path.name != f"{index:04}.intent.json":
            raise ContractError("dispatch continued after a liability or has a sequence gap")
        intent = read_json(path)
        slot = intent.get("slot_id")
        if slot not in inputs["slots"] or slot in seen or intent.get("role") != inputs["slots"][slot]["role"]:
            raise ContractError("unknown, repeated or mismatched dispatch slot")
        role = intent["role"]
        _validate_request(role, intent.get("request"))
        if not _admitted(role, intent["request"], control_policy):
            raise ContractError("saved dispatch exceeded the offline candidate admission limit")
        expected = _intent(manifest, slot, role, intent["request"], index)
        if intent != expected:
            raise ContractError("dispatch request/profile identity changed")
        seen.add(slot)
        result_path = path.with_name(f"{index:04}.result.json")
        amount = intent["reservation_micro_usd"]
        cap = inputs["authorization"]["cap_micro_usd"]
        is_canary = intent["checkpoint"] == "canary"
        if spent + reserved + amount > cap or (is_canary and canary_spent + canary_reserved + amount
                                               > inputs["authorization"]["canary_cap_micro_usd"]):
            raise ContractError("saved dispatch exceeded an admitted budget reservation")
        if not is_canary:
            permit = read_json(run / "authorization" / "expansion.json")
            if permit != {"run_id": manifest["run_id"], "expansion_authorized": True}:
                raise ContractError("expansion dispatch lacks its recorded review")
        if not result_path.exists():
            results[slot] = _result(intent, None, unknown=True, control_policy=control_policy)
            reserved += amount
            canary_reserved += amount if is_canary else 0
            blocked = True
            continue
        result = read_json(result_path)
        expected_result = _result(intent, result.get("response"), unknown=result.get("response") is None,
                                  control_policy=control_policy)
        if result != expected_result:
            raise ContractError("dispatch usage/result identity changed")
        results[slot] = result
        spent += result["spent_micro_usd"] or 0
        reserved += result["reserved_micro_usd"]
        if is_canary:
            canary_spent += result["spent_micro_usd"] or 0
            canary_reserved += result["reserved_micro_usd"]
        blocked = result["status"] == "unknown"
    for path in (run / "attempts").glob("*.result.json"):
        if not path.with_name(path.name.replace(".result.", ".intent.")).exists():
            raise ContractError("dispatch result has no durable intent")
    return {"run_id": manifest["run_id"], "fixture": inputs["fixture"],
            "status": "blocked-unknown" if blocked else "ready", "attempts": len(paths),
            "spent_micro_usd": spent, "reserved_micro_usd": reserved,
            "canary_spent_micro_usd": canary_spent, "canary_reserved_micro_usd": canary_reserved,
            "provider_calls": 0 if inputs["fixture"] else len(paths), "retries": 0, "results": results}


def _intent(manifest: dict, slot: str, role: str, request: dict, index: int) -> dict:
    policy = manifest["inputs"].get("control_policy")
    return {"run_id": manifest["run_id"], "dispatch_id": f"{manifest['run_id']}:{index:04}",
            "fixture": manifest["inputs"]["fixture"], "study_sha256": manifest["inputs"]["study_sha256"],
            "slot_id": slot, "role": role, "checkpoint": manifest["inputs"]["slots"][slot]["checkpoint"],
            "request": request, "request_sha256": digest(request), "profile_sha256": digest(_role(role)),
            "admission": input_bound(request, control_policy=policy, role=role),
            "reservation_micro_usd": reservation(role, control_policy=policy)}


def _admitted(role: str, request: dict, policy: dict | None) -> bool:
    if policy is not None:
        return am1.admitted(role, request)
    return input_bound(request)["candidate_tokens"] <= _role(role)["input_limit"]


class Dispatcher:
    """Sole request boundary for a frozen phase-wide worklist and budget."""

    def __init__(self, run: Path, *, study_sha256: str, slots: dict[str, dict],
                 authorization: dict, transport: Transport, control_policy: dict | None = None):
        if not re.fullmatch(r"[0-9a-f]{64}", study_sha256):
            raise ContractError("study must have a canonical SHA-256 identity")
        _validate_auth(authorization, study_sha256, control_policy)
        if control_policy is not None and transport.fixture is False:
            if run != am1.canonical_live_journal(study_sha256):
                raise ContractError("AM-1 live work requires its single canonical study journal")
        if not isinstance(slots, dict) or not slots or len(slots) > 1320 or any(
            not isinstance(slot, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,180}", slot)
            or not isinstance(value, dict) or set(value) != {"role", "checkpoint"}
            or value["role"] not in FROZEN_PROFILES or value["checkpoint"] not in {"canary", "expansion"}
            for slot, value in slots.items()
        ) or type(transport.fixture) is not bool:
            raise ContractError("invalid bounded role/slot/transport worklist")
        inputs: dict[str, Any] = {"study_sha256": study_sha256, "slots": copy.deepcopy(slots),
                  "profiles": copy.deepcopy(FROZEN_PROFILES), "admission": copy.deepcopy(
                      ADMISSION_POLICY if control_policy is None else control_policy),
                  "authorization": {key: value for key, value in authorization.items()
                                    if key != "expansion_authorized"}, "fixture": transport.fixture}
        if control_policy is None:
            inputs["rates_hundredths_micro_usd"] = {key: list(value) for key, value in _RATES.items()}
        else:
            inputs["control_policy"] = copy.deepcopy(control_policy)
            inputs["rates_thousandths_micro_usd"] = copy.deepcopy(control_policy["maximum_rates_thousandths_micro_usd"])
        self.manifest: dict[str, Any] = {"schema_version": 2, "run_id": digest(inputs), "inputs": inputs}
        self.run, self.transport, self.authorization = run, transport, copy.deepcopy(authorization)
        self.control_policy = copy.deepcopy(control_policy)
        with writer_lock(run):
            _publish(run / "manifest.json", self.manifest)
            if authorization["expansion_authorized"]:
                _publish(run / "authorization" / "expansion.json",
                         {"run_id": self.manifest["run_id"], "expansion_authorized": True})

    def dispatch(self, slot_id: str, role: str, request: dict, *, checkpoint: str = "canary") -> dict:
        request = copy.deepcopy(request)
        slots = self.manifest["inputs"]["slots"]
        if slot_id not in slots or slots[slot_id] != {"role": role, "checkpoint": checkpoint}:
            raise ContractError("request is not a declared role/checkpoint slot")
        _validate_request(role, request)
        if not _admitted(role, request, self.control_policy):
            raise ContractError("request exceeds the offline candidate admission limit")
        if not self.transport.fixture:
            if not self.authorization["authorized"]:
                raise ContractError("no applicable live spending authorization")
            if self.control_policy is None:
                raise ContractError("live dispatch blocked: provider input token bound is unverified")
            if (not isinstance(self.transport, DirectSDKTransport)
                    or self.transport.control_policy != self.control_policy):
                raise ContractError("AM-1 live dispatch requires its exact pinned direct SDK transport")
        if checkpoint == "expansion" and not self.authorization["expansion_authorized"]:
            raise ContractError("post-canary expansion requires its own recorded review")
        with writer_lock(self.run):
            state = replay_dispatch(self.run)
            if state["status"] != "ready":
                raise ContractError("unresolved delivery/usage liability; do not redispatch")
            if slot_id in state["results"]:
                result = state["results"][slot_id]
                if result["request_sha256"] != digest(request):
                    raise ContractError("saved slot request identity changed")
                return result
            amount = reservation(role, control_policy=self.control_policy)
            if state["spent_micro_usd"] + state["reserved_micro_usd"] + amount > self.authorization["cap_micro_usd"]:
                raise ContractError("phase total reservation ceiling reached")
            if checkpoint == "canary" and state["canary_spent_micro_usd"] + state["canary_reserved_micro_usd"] + amount > self.authorization["canary_cap_micro_usd"]:
                raise ContractError("canary reservation ceiling reached")
            index = state["attempts"] + 1
            intent = _intent(self.manifest, slot_id, role, request, index)
            path = self.run / "attempts" / f"{index:04}.intent.json"
            _publish(path, intent)
            try:
                response = copy.deepcopy(self.transport.create(role, copy.deepcopy(request)))
                result = _result(intent, response, control_policy=self.control_policy)
                # Reject non-JSON/nonfinite provider data as ambiguous, not a zero charge.
                digest(result)
            except Exception:
                result = _result(intent, None, unknown=True, control_policy=self.control_policy)
            _publish(path.with_name(f"{index:04}.result.json"), result)
            return result


class DirectSDKTransport:
    """Explicit-key SDK seam; constructors never count tokens or create outputs.

    Not constructed in Phase 2A. Dispatcher currently refuses all live calls.
    Keys are never stored in the journal, forwarded implicitly or read here.
    """

    fixture = False

    def __init__(self, *, anthropic_api_key: str, openai_api_key: str,
                 control_policy: dict | None = None, http_transports: dict[str, Any] | None = None):
        if any(not isinstance(key, str) or not key.strip() for key in (anthropic_api_key, openai_api_key)):
            raise ContractError("explicit keys for both providers are required")
        if any(value and (key.startswith(("ANTHROPIC_", "OPENAI_")) and key not in {
            "ANTHROPIC_API_KEY", "OPENAI_API_KEY"} or key.upper() in {
                "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR"})
               for key, value in os.environ.items()):
            raise ContractError("ambient provider/transport overrides are not permitted")
        import anthropic
        import openai

        if control_policy is not None:
            am1.validate_policy(control_policy)
            am1.runtime_guard()
        self.control_policy = copy.deepcopy(control_policy)
        clients: dict[str, dict] = {"anthropic": {}, "openai": {}}
        if http_transports is not None:
            import httpx
            import httpx2

            if (control_policy is None or not isinstance(http_transports, dict) or set(http_transports) != set(clients)
                    or type(http_transports["anthropic"]) is not httpx2.MockTransport
                    or type(http_transports["openai"]) is not httpx.MockTransport
                    or anthropic_api_key != "fixture-not-a-secret" or openai_api_key != "fixture-not-a-secret"):
                raise ContractError("SDK mocks require AM-1, concrete MockTransports and fixed fake keys")
            clients = {name: {"transport": value} for name, value in http_transports.items()}
            self.fixture = True
        self._anthropic = anthropic.Anthropic(
            api_key=anthropic_api_key, base_url="https://api.anthropic.com", max_retries=0,
            timeout=90.0, http_client=anthropic.DefaultHttpxClient(
                trust_env=False, follow_redirects=False, timeout=90.0, **clients["anthropic"]))
        self._openai = openai.OpenAI(
            api_key=openai_api_key, base_url="https://api.openai.com/v1", max_retries=0,
            timeout=90.0, http_client=openai.DefaultHttpxClient(
                trust_env=False, follow_redirects=False, timeout=90.0, **clients["openai"]))

    def create(self, role: str, request: dict) -> dict:
        _validate_request(role, request)
        started = time.monotonic()
        if role == "group":
            result = self._openai.chat.completions.create(**request)
            latency = time.monotonic() - started
            usage = result.usage.model_dump(mode="json", exclude_none=True) if result.usage else {}
            if self.control_policy is not None:
                canonical = am1.normalize_group_usage(usage, result.service_tier)
            else:
                details = usage.get("prompt_tokens_details") or {}
                output_details = usage.get("completion_tokens_details") or {}
                cached = details.get("cached_tokens", 0)
                canonical = {"input_tokens": usage.get("prompt_tokens", 0) - cached,
                             "output_tokens": usage.get("completion_tokens"),
                             "cache_read_input_tokens": cached,
                             "input_tokens_details": {"cached_tokens": cached},
                             "output_tokens_details": {"reasoning_tokens": output_details.get("reasoning_tokens", 0)},
                             "service_tier": result.service_tier}
                if set(usage).difference({"prompt_tokens", "completion_tokens", "total_tokens",
                                         "prompt_tokens_details", "completion_tokens_details"}) or any(
                    not _zero(value) for key, value in details.items() if key != "cached_tokens"
                ) or any(not _zero(value) for key, value in output_details.items() if key != "reasoning_tokens"):
                    canonical["unsupported_usage"] = True
            choice = result.choices[0]
            return {"model": result.model, "text": choice.message.content or "",
                    "stop_reason": choice.finish_reason, "refusal": choice.message.refusal,
                    "request_id": getattr(result, "_request_id", None), "message_id": result.id,
                    "usage": canonical, "provider_usage": usage, "latency_seconds": latency}
        result = self._anthropic.messages.create(**request)
        latency = time.monotonic() - started
        return {"model": result.model, "text": "".join(block.text for block in result.content if block.type == "text"),
                "stop_reason": result.stop_reason, "request_id": getattr(result, "_request_id", None),
                "message_id": result.id, "usage": result.usage.model_dump(mode="json", exclude_none=True),
                "latency_seconds": latency}
