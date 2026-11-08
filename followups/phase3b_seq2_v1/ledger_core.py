"""Versioned S2 ledger kernel; no mutation of historical module globals.

The transaction/usage/event rules are retained from our accepted ledger. Only
explicit S2 role, payload, cell, and checkpoint parameters change here.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from buddha2 import phase2_am1_controls as am1
from buddha2.artifacts import ContractError, digest
from buddha2.artifacts import read_json as read_json
from buddha2.phase2_dispatch import DirectSDKTransport as DirectSDKTransport
from buddha2.phase2_dispatch import _publish as _publish
from buddha2.phase2_dispatch import _validate_auth as _validate_auth
from buddha2.phase2_dispatch import (
    _validate_request,
)
from buddha2.phase2_dispatch import writer_lock as writer_lock
from buddha2.phase2_release_journal import _append_event as _append_event
from buddha2.phase2_release_journal import _seal
from followups.phase3a_v1.transport import TransportFailure as TransportFailure
from followups.phase3a_v1.transport import failure_from_exception as failure_from_exception
from followups.phase3a_v1.transport import (
    make_failure,
    provider_request_id,
    reject_final_assistant_prefill,
    retain_response,
    validate_failure,
)

PAIRS = tuple(f"p3b-{i:02}" for i in range(1, 5))
ROLES = frozenset(
    {"answer", "plan", "rank", "editor", "native_selector", "fixed_selector", "group", "quality"}
)
EDITOR_ROLES = frozenset({"editor", "native_selector", "fixed_selector"})
CHECKS = frozenset(
    {
        "source_profiles",
        "inference_dispositions",
        "sealed_before_judging",
        "request_usage_identity",
        "isolation",
        "native_selector_classification",
    }
)
POLICY = {
    "id": "phase3b-seq2-accounting-v1",
    "cell_micro_usd": 35_000_000,
    "cell_http": 448,
    "cell_input": 12_000_000,
    "cell_output": 6_291_456,
    "assessment_micro_usd": 70_000_000,
    "first_assessment_micro_usd": 25_000_000,
    "phase_micro_usd": 180_000_000,
    "first_micro_usd": 55_000_000,
    "editor_payload_bytes": 2_097_152,
    # Ten 100k-character answers plus a 100k prompt; JSON needs at most six bytes/character.
    # Native grouping/scoring add fixed framing, not another layer of JSON escaping.
    "evaluator_payload_bytes": {"group": 8_388_608, "quality": 2_097_152},
    "editor_turns": 24,
    "cost_basis": am1.CONTROL_POLICY["cost_basis"],
    "am1_sha256": am1.CONTROL_SHA256,
}


class AuthorityError(ContractError):
    """The frozen phase/review authority does not permit this operation."""


class IntegrityStop(ContractError):
    """An integrity violation permanently blocks further outbound requests."""


class LiabilityStop(ContractError):
    """Unknown delivery or accounting retains its reservation globally."""


class CellBudgetStop(ContractError):
    """This inference cell cannot admit another request; other cells may proceed."""


class CheckpointStop(ContractError):
    """The initial included checkpoint requires its engineering review."""


class AssessmentBudgetStop(ContractError):
    """The assessment pool cannot admit another request."""


class PhaseBudgetStop(ContractError):
    """The phase-wide resource ceiling prevents further outbound requests."""


def _require(condition: Any, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _hash(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _wire(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")


def _aliased(role: str) -> str:
    return "quality" if role in EDITOR_ROLES else role


def _cache_control(value: Any) -> bool:
    return value in ({"type": "ephemeral"}, {"type": "ephemeral", "ttl": "5m"})


def _text(value: Any) -> bool:
    if isinstance(value, str):
        return True
    return isinstance(value, list) and all(
        isinstance(b, dict)
        and b.get("type") == "text"
        and set(b).issubset({"type", "text", "cache_control"})
        and isinstance(b.get("text"), str)
        and ("cache_control" not in b or _cache_control(b["cache_control"]))
        for b in value
    )


def _editor_request(role: str, request: Any, tools: dict, *, payload_limit: int | None = None) -> None:
    required = {
        "model": "claude-opus-5",
        "max_tokens": 16000,
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": "high"},
        "service_tier": "standard_only",
        "inference_geo": "global",
    }
    controls = copy.deepcopy(request) if isinstance(request, dict) else {}
    config = controls.get("output_config")
    if role == "fixed_selector" and isinstance(config, dict) and "format" in config:
        formatting = config["format"]
        _require(
            isinstance(formatting, dict)
            and set(formatting) == {"type", "schema"}
            and formatting["type"] == "json_schema"
            and isinstance(formatting["schema"], dict),
            "unsupported fixed selector structured schema",
        )
        controls["output_config"] = {k: v for k, v in config.items() if k != "format"}
    _require(
        isinstance(request, dict)
        and set(request).issubset(
            set(required) | {"messages", "system", "tools", "tool_choice", "stream", "metadata"}
        )
        and all(
            type(controls.get(k)) is type(v) and controls.get(k) == v for k, v in required.items()
        ),
        "editor/selector changed a frozen model/profile or added unsupported fields",
    )
    _require(
        "stream" not in request or type(request["stream"]) is bool, "invalid streaming control"
    )
    if "metadata" in request:
        metadata = request["metadata"]
        _require(
            isinstance(metadata, dict)
            and set(metadata) == {"user_id"}
            and isinstance(metadata["user_id"], str)
            and len(metadata["user_id"]) <= 256,
            "unsupported editor request metadata",
        )
    _require(
        "system" not in request or _text(request["system"]), "unsupported editor system content"
    )
    supplied = request.get("tools", [])
    _require(
        isinstance(supplied, list)
        and len(supplied) == len({t.get("name") for t in supplied if isinstance(t, dict)})
        and all(
            isinstance(t, dict) and t.get("name") in tools and t == tools[t["name"]]
            for t in supplied
        ),
        "editor tool definitions differ from the frozen allowed client tools",
    )
    names = {tool["name"] for tool in supplied}
    _require(
        "tool_choice" not in request
        or request["tool_choice"] in ({"type": "auto"}, {"type": "none"}),
        "unsupported editor tool selection",
    )
    messages = request.get("messages")
    _require(isinstance(messages, list) and messages, "editor requires explicit messages")
    tool_ids: set[str] = set()
    for message in messages:
        _require(
            isinstance(message, dict)
            and set(message) == {"role", "content"}
            and message["role"] in {"user", "assistant"},
            "unsupported editor message envelope",
        )
        content = message["content"]
        if _text(content):
            continue
        _require(
            role in {"editor", "native_selector"} and isinstance(content, list),
            "selector supports only text, without tools",
        )
        for block in content:
            _require(isinstance(block, dict), "invalid editor content block")
            kind = block.get("type")
            cache_keys = {"cache_control"} if "cache_control" in block else set()
            if cache_keys:
                _require(
                    _cache_control(block["cache_control"]),
                    "unsupported editor continuation cache policy",
                )
            if kind == "text":
                _require(_text([block]), "invalid editor text block")
            elif kind == "tool_use":
                caller_keys = {"caller"} if "caller" in block else set()
                _require(
                    not caller_keys or block["caller"] == {"type": "direct"},
                    "only direct client-tool caller metadata is supported",
                )
                _require(
                    set(block) == {"type", "id", "name", "input"} | cache_keys | caller_keys
                    and block["name"] in names
                    and isinstance(block["id"], str)
                    and block["id"] not in tool_ids
                    and message["role"] == "assistant"
                    and isinstance(block["input"], dict),
                    "invalid client tool call",
                )
                tool_ids.add(block["id"])
            elif kind == "tool_result":
                _require(
                    set(block).issubset({"type", "tool_use_id", "content", "is_error"} | cache_keys)
                    and block.get("tool_use_id") in tool_ids
                    and message["role"] == "user"
                    and _text(block.get("content"))
                    and ("is_error" not in block or type(block["is_error"]) is bool),
                    "invalid client tool result",
                )
            elif kind == "thinking":
                _require(
                    set(block) == {"type", "thinking", "signature"}
                    and isinstance(block["thinking"], str)
                    and isinstance(block["signature"], str),
                    "invalid thinking continuation",
                )
            elif kind == "redacted_thinking":
                _require(
                    set(block) == {"type", "data"} and isinstance(block["data"], str),
                    "invalid redacted continuation",
                )
            else:
                raise ContractError("unsupported editor content or server tool")
    _require(
        role != "fixed_selector" or not supplied and "tool_choice" not in request,
        "fixed selector cannot use tools",
    )
    _require(
        len(_wire(request)) <= (POLICY["editor_payload_bytes"] if payload_limit is None else payload_limit),
        "editor/selector exact request exceeds payload limit",
    )


def validate_request(role: str, request: dict, *, editor_tools: dict | None = None,
                     policy: dict | None = None) -> None:
    _require(role in ROLES, "unknown phase role")
    overrides = {}
    if policy is not None:
        from followups.phase4_cm1_v1.policy import request_limits

        overrides = request_limits(policy)
    if role in EDITOR_ROLES:
        _editor_request(role, request, editor_tools or {}, payload_limit=overrides.get(role))
    else:
        _validate_request(role, request)
        _require(
            role == "group" or type(request.get("max_tokens")) is int,
            "output token ceiling must be an integer",
        )
        evaluator_limit = POLICY["evaluator_payload_bytes"].get(role)
        _require(
            len(_wire(request)) <= overrides[role] if role in overrides else
            am1.admitted(role, request) if evaluator_limit is None
            else len(_wire(request)) <= evaluator_limit,
            "strategy/native request exceeds phase payload admission",
        )
    reject_final_assistant_prefill("editor" if role == "native_selector" else role, request)
    _wire(request)


def _reservation(role: str) -> dict:
    alias = _aliased(role)
    return {
        "micro_usd": am1.reservation(alias),
        "input": am1.CONTROL_POLICY["maximum_billable_input"][alias],
        "output": am1.CONTROL_POLICY["reserved_total_output"][alias],
    }


def _counter() -> dict:
    return dict.fromkeys(
        (
            "attempts",
            "spent_micro_usd",
            "reserved_micro_usd",
            "input_tokens",
            "output_tokens",
            "reserved_input_tokens",
            "reserved_output_tokens",
        ),
        0,
    )


def _start(manifest: dict) -> dict:
    return {
        **({"execution_pairs": list(manifest["inputs"]["policy"]["execution_pairs"])} if "execution_pairs" in manifest["inputs"].get("policy", {}) else {}),
        **_counter(),
        "run_id": manifest["run_id"],
        "fixture": manifest["inputs"]["fixture"],
        "study_sha256": manifest["inputs"]["study_sha256"],
        "status": "ready",
        "results": {},
        "intents": {},
        "cells": {p + ":" + a: _counter() for p in manifest["inputs"].get("policy", {}).get("execution_pairs", PAIRS) for a in ("fixed", "adaptive")},
        "assessment": _counter(),
        "first_pair": _counter(),
        "first_assessment": _counter(),
        "stopped_cells": [],
        "assessment_stopped": False,
        "checkpoint_stopped": False,
        "engineering_review": None,
        "first_assessments_closed": False,
        "provider_calls": 0,
        "retries": 0,
    }


def _buckets(state: dict, meta: dict) -> list[dict]:
    values = [
        state,
        state["assessment"] if meta["cell"] == "assessment" else state["cells"][meta["cell"]],
    ]
    if meta["pair"] == state.get("execution_pairs", PAIRS)[0]:
        values.append(state["first_pair"])
        if meta["cell"] == "assessment":
            values.append(state["first_assessment"])
    return values


def _admit(state: dict, meta: dict, reservation: dict, *, policy: dict | None = None) -> None:
    policy = POLICY if policy is None else policy
    first = state.get("execution_pairs", PAIRS)[0]
    if state["status"] == "blocked-unknown":
        raise LiabilityStop("unresolved delivery/usage prohibits all later outbound calls")
    if state["status"] != "ready":
        raise IntegrityStop("the phase is durably halted")
    if not state["engineering_review"] and meta["pair"] != first:
        raise AuthorityError("the first pair needs engineering review before remaining work")
    if (
        meta["cell"] == "assessment"
        and meta["pair"] != first
        and not state["first_assessments_closed"]
    ):
        raise AuthorityError(
            "finish/classify original first-pair assessment slots before later assessments"
        )
    amount = reservation["micro_usd"]
    if state["spent_micro_usd"] + state["reserved_micro_usd"] + amount > policy["phase_micro_usd"]:
        raise PhaseBudgetStop("cumulative phase reservation ceiling reached")
    if (
        meta["pair"] == first
        and state["first_pair"]["spent_micro_usd"] + amount > policy["first_micro_usd"]
    ):
        raise CheckpointStop("included first-pair reservation ceiling reached")
    if meta["cell"] == "assessment":
        bucket = state["assessment"]
        if (
            state["assessment_stopped"]
            or bucket["spent_micro_usd"] + amount > policy["assessment_micro_usd"]
        ):
            raise AssessmentBudgetStop("assessment reservation ceiling reached")
        if meta["pair"] == first and (
            state["checkpoint_stopped"]
            or state["first_assessment"]["spent_micro_usd"] + amount
            > policy["first_assessment_micro_usd"]
        ):
            raise CheckpointStop("included first-pair assessment checkpoint reached")
    else:
        bucket = state["cells"][meta["cell"]]
        limits = policy.get("cell_bounds", {}).get(meta["cell"].split(":")[1], {})
        if (
            meta["cell"] in state["stopped_cells"]
            or bucket["spent_micro_usd"] + amount > policy["cell_micro_usd"]
            or (
                bucket["attempts"] + 1 > limits.get("http", policy["cell_http"])
                or bucket["input_tokens"] + reservation["input"] > limits.get("input", policy["cell_input"])
                or bucket["output_tokens"] + reservation["output"] > limits.get("output", policy["cell_output"])
            )
        ):
            raise CellBudgetStop(
                "inference cell dollar/request/input/output reservation ceiling reached"
            )


def _intent(manifest: dict, slot: str, request: dict, index: int) -> dict:
    meta = manifest["inputs"]["slots"][slot]
    study = manifest["inputs"]["study_sha256"]
    policy = manifest["inputs"].get("policy", {})
    if policy.get("id") == "phase4-cm1-child-accounting-v1" and policy["phase4_child"]["kind"] == "assessment":
        study = policy["phase4_child"]["generation_study_sha256"]
        _require(_hash(study), "P4 assessment lacks its original generation identity")
    return {
        "slot_id": slot,
        "role": meta["role"],
        "cell": meta["cell"],
        "pair": meta["pair"],
        "study_sha256": study,
        "fixture": manifest["inputs"]["fixture"],
        "dispatch_id": f"{manifest['run_id']}:{index:04}",
        "request": request,
        "request_sha256": digest(request),
        "reservation": _reservation(meta["role"]),
    }


def _result(intent: dict, response: Any, *, failure: dict | None = None) -> dict:
    if failure is not None:
        validate_failure(failure)
        _require(
            response is None or response == retain_response(response),
            "unsafe retained failure response",
        )
        if failure["stage"] in {"provider_call", "journal_replay"}:
            _require(response is None, "provider-call failure cannot contain an error body")
        available_id = (
            provider_request_id(response.get("request_id")) if isinstance(response, dict) else None
        )
        _require(
            available_id is None or failure["provider_request_id"] == available_id,
            "failure does not bind its retained provider request identity",
        )
    cost, known = (
        (None, False) if failure is not None else am1.account(_aliased(intent["role"]), response)
    )
    if not isinstance(response, dict) or not isinstance(response.get("text"), str):
        cost, known = None, False
    if intent["role"] in {"editor", "native_selector"} and isinstance(response, dict):
        payload = response.get("provider_response", {})
        content = response.get(
            "content", payload.get("content") if isinstance(payload, dict) else None
        )
        if not isinstance(content, list) or any(
            not isinstance(block, dict)
            or block.get("type") not in {"text", "thinking", "redacted_thinking", "tool_use"}
            for block in content
        ):
            cost, known = None, False
        if payload and (
            not isinstance(payload, dict)
            or payload.get("usage") != response.get("usage")
            or payload.get("model") != response.get("model")
        ):
            cost, known = None, False
    usage = response.get("usage", {}) if isinstance(response, dict) else {}
    if (
        intent["role"] in EDITOR_ROLES
        and isinstance(usage, dict)
        and usage.get("inference_geo") not in (None, "global")
    ):
        cost, known = None, False
    if not known and failure is None:
        failure = make_failure(
            "accounting_unknown",
            "accounting",
            request_id=response.get("request_id") if isinstance(response, dict) else None,
        )
        response = retain_response(response)
    return {
        k: intent[k]
        for k in (
            "slot_id",
            "role",
            "cell",
            "pair",
            "study_sha256",
            "fixture",
            "dispatch_id",
            "request_sha256",
        )
    } | {
        "intent_sha256": digest(intent),
        "status": "response" if known else "unknown",
        "response": response,
        "spent_micro_usd": cost if known else None,
        "reserved_micro_usd": 0 if known else intent["reservation"]["micro_usd"],
        "input_tokens": sum(
            usage.get(k, 0)
            for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
        )
        if known
        else None,
        "output_tokens": usage.get("output_tokens") if known else None,
        "cost_basis": POLICY["cost_basis"],
        "failure": failure,
    }


def _result_event_bytes(record: dict, events: list[dict]) -> bytes:
    # Exact encoding of the pinned parent _append_event, including seal and newline.
    event = _seal(
        {
            "index": len(events) + 1,
            "kind": "result",
            "record": record,
            "previous_event_sha256": events[-1]["event_sha256"] if events else None,
        },
        "event_sha256",
    )
    return _wire(event) + b"\n"


def _bounded_failure_result(intent: dict, response: Any, failure: dict, events: list[dict]) -> dict:
    result = _result(intent, response, failure=failure)
    if len(_result_event_bytes(result, events)) > 2_000_000:
        failure = make_failure(
            "processing_error", "serialization", request_id=failure["provider_request_id"]
        )
        result = _result(intent, None, failure=failure)
    _require(
        len(_result_event_bytes(result, events)) <= 2_000_000,
        "bounded failure event exceeds artifact profile",
    )
    return result


def _read_events(path: Path) -> tuple[list[dict], bytes]:
    target = path / "events.jsonl"
    if not target.exists():
        return [], b""
    raw = target.read_bytes()
    _require(len(raw) <= 1_500_000_000, "oversized event stream")
    lines = raw.splitlines(keepends=True)
    tail = lines.pop() if lines and not lines[-1].endswith(b"\n") else b""
    events, previous = [], None
    for index, raw_line in enumerate(lines, 1):
        line = raw_line.removesuffix(b"\n")
        try:
            event = json.loads(
                line.decode("utf-8"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError())
            )
        except (ValueError, UnicodeError) as exc:
            raise IntegrityStop("invalid ledger JSON") from exc
        body = {k: v for k, v in event.items() if k != "event_sha256"}
        _require(
            set(event) == {"index", "kind", "record", "previous_event_sha256", "event_sha256"}
            and line == _wire(event)
            and type(event["index"]) is int
            and event["index"] == index
            and event["previous_event_sha256"] == previous
            and event["event_sha256"] == digest(body)
            and event["kind"]
            in {"intent", "result", "halt", "budget_stop", "review", "first_assessments_closed"}
            and isinstance(event["record"], dict),
            "ledger event chain differs",
        )
        events.append(event)
        previous = event["event_sha256"]
    _require(
        not tail or bool(events) and events[-1]["kind"] == "intent",
        "partial/unidentified intent tail; preserve without repair or dispatch",
    )
    return events, tail


def _review(state: dict, record: dict, *, closure: bool = False) -> None:
    fields = {
        "review_id",
        "study_sha256",
        "run_id",
        "state_sha256",
        "checks",
        "evidence",
        "first_assessments_closed",
    }
    _require(
        set(record) == fields
        and isinstance(record["review_id"], str)
        and record["study_sha256"] == state["study_sha256"]
        and record["run_id"] == state["run_id"]
        and record["state_sha256"] == digest(state)
        and record["checks"] == dict.fromkeys(CHECKS, True)
        and all(v is True for v in record["checks"].values())
        and isinstance(record["evidence"], dict)
        and bool(record["evidence"])
        and all(isinstance(k, str) and _hash(v) for k, v in record["evidence"].items())
        and type(record["first_assessments_closed"]) is bool
        and state["status"] == "ready"
        and state["reserved_micro_usd"] == 0,
        "engineering review does not bind its exact reconciled prefix/evidence",
    )
    _require(
        bool(state["engineering_review"]) is closure
        and (
            not closure
            or record["first_assessments_closed"]
            and not state["first_assessments_closed"]
        ),
        "review transition is out of order",
    )
