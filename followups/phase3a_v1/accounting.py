"""One durable, serialized Phase 3A request ledger and bounded resource broker.

Provider clients and credentials belong to the trusted host boundary. This module
accepts a transport, preserves native result identities and reuses AM-1 pricing.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import sys
import threading
from collections import Counter
from importlib.metadata import version
from pathlib import Path
from typing import Any, Callable

from buddha2 import phase2_am1_controls as am1
from buddha2.artifacts import ContractError, digest, read_json
from buddha2.phase2_dispatch import (
    DirectSDKTransport,
    _publish,
    _validate_auth,
    _validate_request,
    writer_lock,
)
from buddha2.phase2_release_journal import _append_event, _seal

from .transport import (
    TransportFailure,
    failure_from_exception,
    make_failure,
    provider_request_id,
    reject_final_assistant_prefill,
    retain_response,
    validate_failure,
)

PAIRS = tuple(f"p3a-{i:02}" for i in range(1, 5))
IMAGE_ID = "sha256:8792a096b4881d47ab19cc7cbf6a74a232f9ff7cedc978fe93f902a71522d4f2"
ROLES = frozenset({"answer", "plan", "rank", "editor", "fixed_selector", "group", "quality"})
EDITOR_ROLES = frozenset({"editor", "fixed_selector"})
CHECKS = frozenset({"source_profiles", "inference_dispositions", "sealed_before_judging",
                    "request_usage_identity", "isolation", "native_selector_classification"})
POLICY = {
    "id": "phase3a-r2-accounting-v1", "cell_micro_usd": 20_000_000, "cell_http": 96,
    "cell_input": 4_000_000, "cell_output": 786432, "assessment_micro_usd": 45_860_000,
    "first_assessment_micro_usd": 23_700_000, "phase_micro_usd": 205_860_000,
    "first_micro_usd": 50_860_000, "editor_payload_bytes": 1_048_576,
    "editor_turns": 8, "cost_basis": am1.CONTROL_POLICY["cost_basis"],
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


def runtime_guard() -> None:
    _require(sys.platform == "linux" and tuple(sys.version_info[:3]) == (3, 12, 15)
             and os.environ.get("BUDDHA2_IMAGE_ID") == IMAGE_ID
             and version("anthropic") == "1.4.0" and version("openai") == "1.107.0"
             and os.environ.get("BUDDHA2_OUTPUT_ROOT") == "/results"
             and os.environ.get("PHASE3A_OPENCODE") == "/opt/phase3a-opencode"
             and os.environ.get("PHASE3A_BUN") == "/usr/local/bin/bun"
             and Path(__file__).resolve().parents[2] == Path("/workspace"),
             "live Phase 3A requires its exact image, SDKs and fixed runtime mounts")


def _hash(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _wire(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def _aliased(role: str) -> str:
    return "quality" if role in EDITOR_ROLES else role


def _slot_scope(slots: Any) -> None:
    _require(isinstance(slots, dict) and len(slots) == 775, "the complete 775-slot worklist is required")
    counts: Counter = Counter()
    conversations: dict[str, set[int]] = {}
    for name, row in slots.items():
        _require(isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_.:/-]{1,240}", name) is not None
                 and isinstance(row, dict), "invalid frozen slot identity")
        role, cell, pair = row.get("role"), row.get("cell"), row.get("pair")
        _require(role in ROLES and pair in PAIRS and cell in (
            pair + ":fixed", pair + ":adaptive", "assessment"), "invalid slot role/cell/pair")
        extras = {"checkpoint"} if "checkpoint" in row else set()
        if extras:
            _require(row["checkpoint"] == ("canary" if pair == PAIRS[0] else "expansion"), "slot checkpoint differs from frozen pair")
        if role in {"group", "quality"}:
            _require(cell == "assessment", "native assessment cannot borrow an inference cell")
        else:
            _require(cell != "assessment", "inference cannot borrow the assessment pool")
        if role == "editor":
            _require(set(row) == {"role", "cell", "pair", "conversation", "turn"} | extras
                     and cell == pair + ":adaptive" and isinstance(row["conversation"], str)
                     and re.fullmatch(re.escape(cell) + r":(?:inv1|dom1|agg1)\.a[12]", row["conversation"])
                     and type(row["turn"]) is int and 1 <= row["turn"] <= POLICY["editor_turns"],
                     "editor must bind its exact stage/shape conversation and provider turn")
            conversations.setdefault(row["conversation"], set()).add(row["turn"])
        else:
            _require(set(row) == {"role", "cell", "pair"} | extras, "unexpected slot metadata")
        counts[cell, pair, role] += 1
    expected: Counter = Counter()
    for pair in PAIRS:
        for arm, population in (("adaptive", {"answer": 40, "plan": 4, "rank": 4, "editor": 48}),
                                ("fixed", {"answer": 60, "plan": 6, "rank": 6, "fixed_selector": 1})):
            for role, number in population.items():
                expected[pair + ":" + arm, pair, role] = number
        expected["assessment", pair, "group"] = 3 if pair == PAIRS[0] else 2
        expected["assessment", pair, "quality"] = 30 if pair == PAIRS[0] else 20
    _require(counts == expected and len(conversations) == 24 and
             all(turns == set(range(1, POLICY["editor_turns"] + 1)) for turns in conversations.values()), "frozen request scope differs")


def _path(path: Path) -> Path:
    path = Path(path)
    # This checks the contained fixture mount; it does not construct a temporary filename.
    _require(path.is_absolute() and (path.is_relative_to("/results") or path.is_relative_to("/tmp"))  # nosec B108
             and ".." not in path.parts and
             not any(p.is_symlink() for p in (path, *path.parents, *path.rglob("*"))),
             "journal must be an ordinary absolute path without links")
    return path


def _manifest(path: Path) -> dict:
    value = read_json(_path(path) / "manifest.json")
    _require(isinstance(value, dict) and set(value) == {"kind", "inputs", "run_id"} and value["kind"] == "phase3a-ledger-v1"
             and value["run_id"] == digest(value["inputs"]), "invalid phase ledger manifest")
    inputs = value["inputs"]
    _require(isinstance(inputs, dict) and set(inputs) == {"study_sha256", "slots", "authority", "fixture",
             "bindings", "policy", "editor_tools"} and _hash(inputs["study_sha256"]), "ledger inputs differ")
    _require(inputs["policy"] == POLICY and digest(inputs["policy"]) == digest(POLICY), "ledger policy differs")
    _slot_scope(inputs["slots"])
    validate_authority(inputs["study_sha256"], inputs["authority"], fixture=inputs["fixture"], bindings=inputs["bindings"])
    if not inputs["fixture"]:
        runtime_guard()
        _require(path == Path("/results/phase3a-r2-v1") / inputs["study_sha256"] / "live/journal",
                 "live work must use its single canonical journal")
    return value


def validate_authority(study_sha256: str, authority: dict, fixture: bool = False,
                       bindings: dict | None = None) -> None:
    """Pure pre-client validation; supplies no credential or dispatch permission."""
    _require(_hash(study_sha256) and type(fixture) is bool, "exact study/mode binding required")
    _validate_auth(authority, study_sha256, am1.CONTROL_POLICY)
    _require(authority["cap_micro_usd"] == POLICY["phase_micro_usd"] and
             authority["canary_cap_micro_usd"] == POLICY["first_micro_usd"] and
             authority["expansion_authorized"] is False and (fixture or authority["authorized"] is True),
             "phase authority differs")
    if bindings is not None:
        _require(isinstance(bindings, dict) and set(bindings) == {"source_sha256", "policy_sha256", "launcher_sha256"}
                 and all(_hash(v) for v in bindings.values()), "phase source bindings are incomplete")


def _cache_control(value: Any) -> bool:
    return value in ({"type": "ephemeral"}, {"type": "ephemeral", "ttl": "5m"})


def _text(value: Any) -> bool:
    if isinstance(value, str):
        return True
    return isinstance(value, list) and all(isinstance(b, dict) and b.get("type") == "text"
        and set(b).issubset({"type", "text", "cache_control"}) and isinstance(b.get("text"), str)
        and ("cache_control" not in b or _cache_control(b["cache_control"])) for b in value)


def _editor_request(role: str, request: Any, tools: dict) -> None:
    required = {"model": "claude-opus-5", "max_tokens": 16000, "thinking": {"type": "adaptive"},
                "output_config": {"effort": "high"}, "service_tier": "standard_only", "inference_geo": "global"}
    controls = copy.deepcopy(request) if isinstance(request, dict) else {}
    config = controls.get("output_config")
    if role == "fixed_selector" and isinstance(config, dict) and "format" in config:
        formatting = config["format"]
        _require(isinstance(formatting, dict) and set(formatting) == {"type", "schema"}
                 and formatting["type"] == "json_schema" and isinstance(formatting["schema"], dict),
                 "unsupported fixed selector structured schema")
        controls["output_config"] = {k: v for k, v in config.items() if k != "format"}
    _require(isinstance(request, dict) and set(request).issubset(set(required) | {
        "messages", "system", "tools", "tool_choice", "stream", "metadata"}) and
        all(type(controls.get(k)) is type(v) and controls.get(k) == v for k, v in required.items()),
        "editor/selector changed a frozen model/profile or added unsupported fields")
    _require("stream" not in request or type(request["stream"]) is bool, "invalid streaming control")
    if "metadata" in request:
        metadata = request["metadata"]
        _require(isinstance(metadata, dict) and set(metadata) == {"user_id"}
                 and isinstance(metadata["user_id"], str) and len(metadata["user_id"]) <= 256,
                 "unsupported editor request metadata")
    _require("system" not in request or _text(request["system"]), "unsupported editor system content")
    supplied = request.get("tools", [])
    _require(isinstance(supplied, list) and len(supplied) == len({t.get("name") for t in supplied if isinstance(t, dict)})
             and all(isinstance(t, dict) and t.get("name") in tools and t == tools[t["name"]] for t in supplied),
             "editor tool definitions differ from the frozen allowed client tools")
    names = {tool["name"] for tool in supplied}
    _require("tool_choice" not in request or request["tool_choice"] in ({"type": "auto"}, {"type": "none"}),
             "unsupported editor tool selection")
    messages = request.get("messages")
    _require(isinstance(messages, list) and messages, "editor requires explicit messages")
    tool_ids: set[str] = set()
    for message in messages:
        _require(isinstance(message, dict) and set(message) == {"role", "content"}
                 and message["role"] in {"user", "assistant"}, "unsupported editor message envelope")
        content = message["content"]
        if _text(content):
            continue
        _require(role == "editor" and isinstance(content, list), "selector supports only text, without tools")
        for block in content:
            _require(isinstance(block, dict), "invalid editor content block")
            kind = block.get("type")
            cache_keys = {"cache_control"} if "cache_control" in block else set()
            if cache_keys:
                _require(_cache_control(block["cache_control"]), "unsupported editor continuation cache policy")
            if kind == "text":
                _require(_text([block]), "invalid editor text block")
            elif kind == "tool_use":
                caller_keys = {"caller"} if "caller" in block else set()
                _require(not caller_keys or block["caller"] == {"type": "direct"},
                         "only direct client-tool caller metadata is supported")
                _require(set(block) == {"type", "id", "name", "input"} | cache_keys | caller_keys and block["name"] in names
                         and isinstance(block["id"], str) and block["id"] not in tool_ids and
                         message["role"] == "assistant" and isinstance(block["input"], dict), "invalid client tool call")
                tool_ids.add(block["id"])
            elif kind == "tool_result":
                _require(set(block).issubset({"type", "tool_use_id", "content", "is_error"} | cache_keys)
                         and block.get("tool_use_id") in tool_ids and message["role"] == "user" and _text(block.get("content"))
                         and ("is_error" not in block or type(block["is_error"]) is bool), "invalid client tool result")
            elif kind == "thinking":
                _require(set(block) == {"type", "thinking", "signature"} and
                         isinstance(block["thinking"], str) and isinstance(block["signature"], str), "invalid thinking continuation")
            elif kind == "redacted_thinking":
                _require(set(block) == {"type", "data"} and isinstance(block["data"], str), "invalid redacted continuation")
            else:
                raise ContractError("unsupported editor content or server tool")
    _require(role != "fixed_selector" or not supplied and "tool_choice" not in request, "fixed selector cannot use tools")
    _require(len(_wire(request)) <= POLICY["editor_payload_bytes"], "editor/selector exact request exceeds payload limit")


def validate_request(role: str, request: dict, *, editor_tools: dict | None = None) -> None:
    _require(role in ROLES, "unknown phase role")
    if role in EDITOR_ROLES:
        _editor_request(role, request, editor_tools or {})
    else:
        _validate_request(role, request)
        _require(role == "group" or type(request.get("max_tokens")) is int, "output token ceiling must be an integer")
        _require(am1.admitted(role, request), "strategy/native request exceeds preserved payload admission")
    reject_final_assistant_prefill(role, request)
    _wire(request)


def _reservation(role: str) -> dict:
    alias = _aliased(role)
    return {"micro_usd": am1.reservation(alias), "input": am1.CONTROL_POLICY["maximum_billable_input"][alias],
            "output": am1.CONTROL_POLICY["reserved_total_output"][alias]}


def _counter() -> dict:
    return dict.fromkeys(("attempts", "spent_micro_usd", "reserved_micro_usd", "input_tokens", "output_tokens",
                          "reserved_input_tokens", "reserved_output_tokens"), 0)


def _start(manifest: dict) -> dict:
    return {**_counter(), "run_id": manifest["run_id"], "fixture": manifest["inputs"]["fixture"],
        "study_sha256": manifest["inputs"]["study_sha256"], "status": "ready", "results": {}, "intents": {},
        "cells": {p + ":" + a: _counter() for p in PAIRS for a in ("fixed", "adaptive")},
        "assessment": _counter(), "first_pair": _counter(), "first_assessment": _counter(),
        "stopped_cells": [], "assessment_stopped": False, "checkpoint_stopped": False,
        "engineering_review": None, "first_assessments_closed": False, "provider_calls": 0, "retries": 0}


def _buckets(state: dict, meta: dict) -> list[dict]:
    values = [state, state["assessment"] if meta["cell"] == "assessment" else state["cells"][meta["cell"]]]
    if meta["pair"] == PAIRS[0]:
        values.append(state["first_pair"])
        if meta["cell"] == "assessment":
            values.append(state["first_assessment"])
    return values


def _admit(state: dict, meta: dict, reservation: dict) -> None:
    if state["status"] == "blocked-unknown":
        raise LiabilityStop("unresolved delivery/usage prohibits all later outbound calls")
    if state["status"] != "ready":
        raise IntegrityStop("the phase is durably halted")
    if not state["engineering_review"] and meta["pair"] != PAIRS[0]:
        raise AuthorityError("the first pair needs engineering review before remaining work")
    if meta["cell"] == "assessment" and meta["pair"] != PAIRS[0] and not state["first_assessments_closed"]:
        raise AuthorityError("finish/classify original first-pair assessment slots before later assessments")
    amount = reservation["micro_usd"]
    if state["spent_micro_usd"] + state["reserved_micro_usd"] + amount > POLICY["phase_micro_usd"]:
        raise PhaseBudgetStop("cumulative phase reservation ceiling reached")
    if not state["engineering_review"] and state["first_pair"]["spent_micro_usd"] + amount > POLICY["first_micro_usd"]:
        raise CheckpointStop("included first-pair reservation ceiling reached")
    if meta["cell"] == "assessment":
        bucket = state["assessment"]
        if state["assessment_stopped"] or bucket["spent_micro_usd"] + amount > POLICY["assessment_micro_usd"]:
            raise AssessmentBudgetStop("assessment reservation ceiling reached")
        if not state["engineering_review"] and (state["checkpoint_stopped"] or
                state["first_assessment"]["spent_micro_usd"] + amount > POLICY["first_assessment_micro_usd"]):
            raise CheckpointStop("included first-pair assessment checkpoint reached")
    else:
        bucket = state["cells"][meta["cell"]]
        if meta["cell"] in state["stopped_cells"] or bucket["spent_micro_usd"] + amount > POLICY["cell_micro_usd"] or (
            bucket["attempts"] + 1 > POLICY["cell_http"] or
            bucket["input_tokens"] + reservation["input"] > POLICY["cell_input"] or
            bucket["output_tokens"] + reservation["output"] > POLICY["cell_output"]):
            raise CellBudgetStop("inference cell dollar/request/input/output reservation ceiling reached")


def _intent(manifest: dict, slot: str, request: dict, index: int) -> dict:
    meta = manifest["inputs"]["slots"][slot]
    return {"slot_id": slot, "role": meta["role"], "cell": meta["cell"], "pair": meta["pair"],
        "study_sha256": manifest["inputs"]["study_sha256"], "fixture": manifest["inputs"]["fixture"],
        "dispatch_id": f"{manifest['run_id']}:{index:04}", "request": request,
        "request_sha256": digest(request), "reservation": _reservation(meta["role"])}


def _result(intent: dict, response: Any, *, failure: dict | None = None) -> dict:
    if failure is not None:
        validate_failure(failure)
        _require(response is None or response == retain_response(response), "unsafe retained failure response")
        if failure["stage"] in {"provider_call", "journal_replay"}:
            _require(response is None, "provider-call failure cannot contain an error body")
        available_id = provider_request_id(response.get("request_id")) if isinstance(response, dict) else None
        _require(available_id is None or failure["provider_request_id"] == available_id,
                 "failure does not bind its retained provider request identity")
    cost, known = (None, False) if failure is not None else am1.account(_aliased(intent["role"]), response)
    if not isinstance(response, dict) or not isinstance(response.get("text"), str):
        cost, known = None, False
    if intent["role"] == "editor" and isinstance(response, dict):
        payload = response.get("provider_response", {})
        content = response.get("content", payload.get("content") if isinstance(payload, dict) else None)
        if not isinstance(content, list) or any(not isinstance(block, dict) or block.get("type") not in {
                "text", "thinking", "redacted_thinking", "tool_use"} for block in content):
            cost, known = None, False
        if payload and (not isinstance(payload, dict) or payload.get("usage") != response.get("usage")
                        or payload.get("model") != response.get("model")):
            cost, known = None, False
    usage = response.get("usage", {}) if isinstance(response, dict) else {}
    if intent["role"] in EDITOR_ROLES and isinstance(usage, dict) and usage.get("inference_geo") not in (None, "global"):
        cost, known = None, False
    if not known and failure is None:
        failure = make_failure("accounting_unknown", "accounting", request_id=
            response.get("request_id") if isinstance(response, dict) else None)
        response = retain_response(response)
    return {k: intent[k] for k in ("slot_id", "role", "cell", "pair", "study_sha256", "fixture",
                                   "dispatch_id", "request_sha256")} | {
        "intent_sha256": digest(intent), "status": "response" if known else "unknown", "response": response,
        "spent_micro_usd": cost if known else None,
        "reserved_micro_usd": 0 if known else intent["reservation"]["micro_usd"],
        "input_tokens": sum(usage.get(k, 0) for k in (
            "input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")) if known else None,
        "output_tokens": usage.get("output_tokens") if known else None, "cost_basis": POLICY["cost_basis"],
        "failure": failure}


def _result_event_bytes(record: dict, events: list[dict]) -> bytes:
    # Exact encoding of the pinned parent _append_event, including seal and newline.
    event = _seal({"index": len(events) + 1, "kind": "result", "record": record,
                   "previous_event_sha256": events[-1]["event_sha256"] if events else None}, "event_sha256")
    return _wire(event) + b"\n"


def _bounded_failure_result(intent: dict, response: Any, failure: dict, events: list[dict]) -> dict:
    result = _result(intent, response, failure=failure)
    if len(_result_event_bytes(result, events)) > 2_000_000:
        failure = make_failure("processing_error", "serialization", request_id=failure["provider_request_id"])
        result = _result(intent, None, failure=failure)
    _require(len(_result_event_bytes(result, events)) <= 2_000_000, "bounded failure event exceeds artifact profile")
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
            event = json.loads(line.decode("utf-8"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except (ValueError, UnicodeError) as exc:
            raise IntegrityStop("invalid ledger JSON") from exc
        body = {k: v for k, v in event.items() if k != "event_sha256"}
        _require(set(event) == {"index", "kind", "record", "previous_event_sha256", "event_sha256"}
                 and line == _wire(event)
                 and type(event["index"]) is int and event["index"] == index and
                 event["previous_event_sha256"] == previous and event["event_sha256"] == digest(body)
                 and event["kind"] in {"intent", "result", "halt", "budget_stop", "review", "first_assessments_closed"}
                 and isinstance(event["record"], dict), "ledger event chain differs")
        events.append(event)
        previous = event["event_sha256"]
    _require(not tail or bool(events) and events[-1]["kind"] == "intent",
             "partial/unidentified intent tail; preserve without repair or dispatch")
    return events, tail


def _events(path: Path) -> list[dict]:
    return _read_events(path)[0]


def _review(state: dict, record: dict, *, closure: bool = False) -> None:
    fields = {"review_id", "study_sha256", "run_id", "state_sha256", "checks", "evidence", "first_assessments_closed"}
    _require(set(record) == fields and isinstance(record["review_id"], str) and
             record["study_sha256"] == state["study_sha256"] and record["run_id"] == state["run_id"] and
             record["state_sha256"] == digest(state) and record["checks"] == dict.fromkeys(CHECKS, True) and
             all(v is True for v in record["checks"].values()) and isinstance(record["evidence"], dict) and
             bool(record["evidence"]) and all(isinstance(k, str) and _hash(v) for k, v in record["evidence"].items()) and
             type(record["first_assessments_closed"]) is bool and state["status"] == "ready" and
             state["reserved_micro_usd"] == 0, "engineering review does not bind its exact reconciled prefix/evidence")
    _require(bool(state["engineering_review"]) is closure and
             (not closure or record["first_assessments_closed"] and not state["first_assessments_closed"]),
             "review transition is out of order")


def _replay(path: Path) -> tuple[dict, list[dict], dict]:
    manifest = _manifest(path)
    state, pending = _start(manifest), None
    events, tail = _read_events(path)
    for event in events:
        kind, record = event["kind"], event["record"]
        if kind == "intent":
            _require(pending is None and record.get("slot_id") in manifest["inputs"]["slots"]
                     and record["slot_id"] not in state["results"], "duplicate/out-of-order ledger intent")
            slot, request = record["slot_id"], record["request"]
            meta = manifest["inputs"]["slots"][slot]
            validate_request(meta["role"], request, editor_tools=manifest["inputs"]["editor_tools"])
            _require(record == _intent(manifest, slot, request, state["attempts"] + 1), "request intent differs")
            _admit(state, meta, record["reservation"])
            if meta["role"] == "editor" and meta["turn"] > 1:
                previous = next(name for name, row in manifest["inputs"]["slots"].items() if
                    row.get("conversation") == meta["conversation"] and row.get("turn") == meta["turn"] - 1)
                _require(previous in state["results"] and state["results"][previous]["status"] == "response",
                         "editor continuation lacks its preceding settled turn")
            for bucket in _buckets(state, meta):
                bucket["attempts"] += 1
                bucket["reserved_micro_usd"] += record["reservation"]["micro_usd"]
                bucket["reserved_input_tokens"] += record["reservation"]["input"]
                bucket["reserved_output_tokens"] += record["reservation"]["output"]
            state["intents"][slot] = record
            state["provider_calls"] = 0 if state["fixture"] else state["attempts"]
            pending = record
        elif kind == "result":
            if pending is None:
                raise IntegrityStop("result lacks its pending intent")
            _require(record == _result(pending, record.get("response"), failure=record.get("failure")),
                     "result differs from pending intent/accounting")
            meta = manifest["inputs"]["slots"][pending["slot_id"]]
            if record["status"] == "response":
                for bucket in _buckets(state, meta):
                    bucket["reserved_micro_usd"] -= pending["reservation"]["micro_usd"]
                    bucket["reserved_input_tokens"] -= pending["reservation"]["input"]
                    bucket["reserved_output_tokens"] -= pending["reservation"]["output"]
                    bucket["spent_micro_usd"] += record["spent_micro_usd"]
                    bucket["input_tokens"] += record["input_tokens"]
                    bucket["output_tokens"] += record["output_tokens"]
            else:
                state["status"] = "blocked-unknown"
            state["results"][record["slot_id"]] = record
            pending = None
        else:
            _require(pending is None and state["status"] == "ready", "control record follows pending/unknown/terminal halt")
            if kind in {"review", "first_assessments_closed"}:
                _review(state, record, closure=kind == "first_assessments_closed")
                if kind == "review":
                    state["engineering_review"] = digest(record)
                    state["checkpoint_stopped"] = False
                state["first_assessments_closed"] = record["first_assessments_closed"]
            elif kind == "halt":
                _require(record.get("state_sha256") == digest(state), "halt prefix differs")
                state["status"] = "halted-integrity"
            elif kind == "budget_stop":
                _require(record.get("state_sha256") == digest(state) and record.get("scope") in {
                    "cell", "assessment", "checkpoint", "phase"}, "budget-stop prefix differs")
                if record["scope"] == "cell":
                    _require(record.get("cell") in state["cells"] and record["cell"] not in state["stopped_cells"], "invalid stopped cell")
                    state["stopped_cells"].append(record["cell"])
                elif record["scope"] == "assessment":
                    state["assessment_stopped"] = True
                elif record["scope"] == "checkpoint":
                    state["checkpoint_stopped"] = True
                else:
                    state["status"] = "halted-budget"
    if pending is not None:
        state["results"][pending["slot_id"]] = _result(pending, None,
            failure=make_failure("unresolved_intent", "journal_replay"))
        state["status"] = "blocked-unknown"
    _require(not tail or pending is not None, "truncated result lacks its durable pending intent")
    if tail:
        state["stream_tail_sha256"] = hashlib.sha256(tail).hexdigest()
    state["provider_calls"] = 0 if state["fixture"] else state["attempts"]
    return state, events, manifest


def replay(journal: Path) -> dict:
    return _replay(_path(journal))[0]


def events(journal: Path) -> list[dict]:
    """Verified immutable event prefix for chronology and seal evidence."""
    return copy.deepcopy(_replay(_path(journal))[1])


def publish_review(journal: Path, record: dict, *, validate_evidence: Callable[[dict, dict], None]) -> dict:
    return _publish_review(journal, record, validate_evidence, closure=False)


def close_first_assessments(journal: Path, record: dict, *, validate_evidence: Callable[[dict, dict], None]) -> dict:
    return _publish_review(journal, record, validate_evidence, closure=True)


def journal_identity(*, study_sha256: str, slots: dict, authority: dict, fixture: bool,
                     bindings: dict, editor_tools: dict | None = None) -> str:
    validate_authority(study_sha256, authority, fixture=fixture, bindings=bindings)
    _slot_scope(slots)
    return digest({"study_sha256": study_sha256, "slots": slots, "authority": authority,
                   "fixture": fixture, "bindings": bindings, "policy": POLICY, "editor_tools": editor_tools or {}})


def _publish_review(journal: Path, record: dict, validate_evidence: Callable, *, closure: bool) -> dict:
    journal = _path(journal)
    with writer_lock(journal):
        state, events, _ = _replay(journal)
        kind = "first_assessments_closed" if closure else "review"
        existing = [e["record"] for e in events if e["kind"] == kind]
        if existing:
            _require(len(existing) == 1 and existing[0] == record, "conflicting/replayed-as-new engineering review")
            return state
        _review(state, record, closure=closure)
        _require(validate_evidence(copy.deepcopy(state), copy.deepcopy(record)) is None,
                 "engineering evidence validator must complete without a rejection")
        _append_event(journal, kind, record, events)
        return _replay(journal)[0]


class Ledger:
    """A shared instance queues threads; the file lock excludes other owners."""

    def __init__(self, journal: Path, *, study_sha256: str, slots: dict, authority: dict,
                 transport: Any, bindings: dict, editor_tools: dict | None = None):
        _require(_hash(study_sha256) and type(transport.fixture) is bool, "explicit exact study and transport mode required")
        validate_authority(study_sha256, authority, fixture=transport.fixture, bindings=bindings)
        if not transport.fixture:
            runtime_guard()
            _require(isinstance(transport, DirectSDKTransport) and transport.control_policy == am1.CONTROL_POLICY,
                     "live phase requires the pinned explicit-key direct SDK boundary")
        _slot_scope(slots)
        self.journal, self.transport, self._lock = _path(journal), transport, threading.RLock()
        inputs = {"study_sha256": study_sha256, "slots": copy.deepcopy(slots), "authority": copy.deepcopy(authority),
                  "fixture": transport.fixture, "bindings": copy.deepcopy(bindings), "policy": copy.deepcopy(POLICY),
                  "editor_tools": copy.deepcopy(editor_tools or {})}
        _require(isinstance(inputs["editor_tools"], dict) and set(inputs["editor_tools"]).issubset({"read", "write", "edit"})
                 and all(isinstance(k, str) and isinstance(v, dict) and v.get("name") == k
                         for k, v in inputs["editor_tools"].items()), "editor allowlist contains unbounded/invalid tools")
        self.manifest = {"kind": "phase3a-ledger-v1", "inputs": inputs, "run_id": journal_identity(
            study_sha256=study_sha256, slots=slots, authority=authority, fixture=transport.fixture,
            bindings=bindings, editor_tools=editor_tools)}
        with writer_lock(self.journal):
            if (self.journal / "manifest.json").exists():
                _require(read_json(self.journal / "manifest.json") == self.manifest, "another source/study/authority owns this journal")
            else:
                _require(not any(p.name != ".writer.lock" for p in self.journal.iterdir()), "unrecognized existing journal contents")
                _publish(self.journal / "manifest.json", self.manifest)
            _manifest(self.journal)
            _replay(self.journal)

    def state(self) -> dict:
        with self._lock:
            return replay(self.journal)

    def halt(self, reason: str, evidence_sha256: str | None = None) -> dict:
        """Persist an externally detected isolation/profile violation before more egress."""
        _require(isinstance(reason, str) and 0 < len(reason) <= 1000 and
                 (evidence_sha256 is None or _hash(evidence_sha256)), "invalid integrity-halt evidence")
        with self._lock, writer_lock(self.journal):
            state, events, _ = _replay(self.journal)
            if state["status"] == "ready":
                _append_event(self.journal, "halt", {"state_sha256": digest(state), "reason": reason,
                    "evidence_sha256": evidence_sha256}, events)
                return replay(self.journal)
            return state

    def dispatch(self, slot_id: str, role: str, request: dict, *, checkpoint: str | None = None) -> dict:
        request = copy.deepcopy(request)
        with self._lock, writer_lock(self.journal):
            state, events, manifest = _replay(self.journal)
            if state["status"] == "blocked-unknown":
                raise LiabilityStop("unknown request must never be resent")
            if state["status"] != "ready":
                raise IntegrityStop("phase is durably halted")
            try:
                meta = manifest["inputs"]["slots"].get(slot_id)
                _require(meta is not None and meta["role"] == role and (checkpoint is None or checkpoint == (
                    "canary" if meta["pair"] == PAIRS[0] else "expansion")), "undeclared request slot/role/checkpoint")
                validate_request(role, request, editor_tools=manifest["inputs"]["editor_tools"])
                if slot_id in state["results"]:
                    _require(state["results"][slot_id]["request_sha256"] == digest(request), "settled request changed on replay")
                    return state["results"][slot_id]
                if role == "editor" and meta["turn"] > 1:
                    previous = next(name for name, row in manifest["inputs"]["slots"].items() if
                        row.get("conversation") == meta["conversation"] and row.get("turn") == meta["turn"] - 1)
                    _require(previous in state["results"], "editor cannot skip or restart its provider-turn sequence")
            except (ValueError, TypeError, KeyError, StopIteration) as exc:
                _append_event(self.journal, "halt", {"state_sha256": digest(state), "reason": str(exc)}, events)
                raise IntegrityStop(str(exc)) from exc
            try:
                _admit(state, meta, _reservation(role))
            except (CellBudgetStop, AssessmentBudgetStop, CheckpointStop, PhaseBudgetStop) as exc:
                scope = ("cell" if isinstance(exc, CellBudgetStop) else "assessment" if isinstance(exc, AssessmentBudgetStop)
                         else "checkpoint" if isinstance(exc, CheckpointStop) else "phase")
                already = (meta["cell"] in state["stopped_cells"] if scope == "cell" else
                           state["assessment_stopped"] if scope == "assessment" else state["checkpoint_stopped"])
                if not already:
                    _append_event(self.journal, "budget_stop", {"state_sha256": digest(state), "scope": scope,
                        "cell": meta["cell"], "slot_id": slot_id, "reason": str(exc)}, events)
                raise
            intent = _intent(manifest, slot_id, request, state["attempts"] + 1)
            _append_event(self.journal, "intent", intent, events)
            returned = response = None
            stage = "transport_select"
            try:
                if hasattr(self.transport, "select"):
                    self.transport.select(role, slot_id)
                stage = "provider_call"
                returned = self.transport.create(role, request)
                stage = "response_copy"
                response = json.loads(_wire(returned))
                stage = "accounting"
                result = _result(intent, response)
                stage = "serialization"
                _wire(result)
                _require(len(_result_event_bytes(result, events)) <= 2_000_000,
                         "single result event exceeds the artifact profile")
            except TransportFailure as error:
                result = _bounded_failure_result(intent, error.response, error.failure, events)
            except Exception as error:
                candidate = response if response is not None else returned
                available_id = provider_request_id(candidate.get("request_id")) if isinstance(candidate, dict) else None
                kept = retain_response(candidate)
                result = _bounded_failure_result(intent, kept, failure_from_exception(error, stage,
                    request_id=available_id), events)
            _require(len(_result_event_bytes(result, events)) <= 2_000_000,
                     "single result event exceeds the artifact profile")
            _append_event(self.journal, "result", result, events)
            return result
