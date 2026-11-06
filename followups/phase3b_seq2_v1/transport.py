"""Bounded owned-worker transport; only the coordinator can settle a journal slot."""
from __future__ import annotations

import base64
import copy
import json
import math
import multiprocessing
import os
import queue
import re
import threading
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any, Callable

from buddha2.artifacts import ContractError, digest
from buddha2.phase2_am1_controls import CONTROL_POLICY, normalize_group_usage
from buddha2.phase2_dispatch import DirectSDKTransport, _validate_request
from followups.phase3a_c1_completion_v3 import worker
from followups.phase3a_v1.transport import (
    TransportFailure,
    make_failure,
    provider_request_id,
    reject_final_assistant_prefill,
    retain_response,
)

from . import ledger_core as core
from .deadline import (
    NATIVE_TIMEOUT,
    POLICY,
    Budget,
    Clock,
    KnownDeadlineStop,
    Policy,
    TimingStop,
    budget,
    eligible,
    validate_clock,
    validate_gate,
)

_HASH = re.compile(r"[0-9a-f]{64}")


def normalize(role: str, raw: dict, request_id: str | None, elapsed: float) -> dict:
    """Frozen V1 normalization contract; no callable normalization seam existed there."""
    if not isinstance(raw, dict):
        raise ContractError("SDK response is not a JSON object")
    request_id = provider_request_id(request_id)
    if role == "group":
        usage = raw.get("usage") or {}
        choice = raw["choices"][0]
        return {"model": raw["model"], "text": choice["message"].get("content") or "",
            "stop_reason": choice["finish_reason"], "refusal": choice["message"].get("refusal"),
            "request_id": request_id, "message_id": raw["id"],
            "usage": normalize_group_usage(usage, raw.get("service_tier")),
            "provider_usage": usage, "latency_seconds": elapsed}
    response = {"model": raw["model"],
        "text": "".join(block["text"] for block in raw["content"] if block["type"] == "text"),
        "stop_reason": raw["stop_reason"], "request_id": request_id,
        "message_id": raw["id"], "usage": raw["usage"], "latency_seconds": elapsed}
    if role in {"editor", "native_selector", "fixed_selector"}:
        response["provider_response"] = raw
    return response


class Transport(DirectSDKTransport):
    def __init__(self, *, anthropic_api_key: str, openai_api_key: str,
                 http_transports: dict[str, Any] | None = None,
                 fixture_policy: Policy | None = None, fixture_behavior: dict | None = None,
                 startup_attachment: dict | None = None):
        self.startup_attachment = None
        if http_transports is None:
            from .supervision import require_transport_attachment
            self.startup_attachment = require_transport_attachment(startup_attachment)
        import httpx
        import httpx2
        if any(n.startswith(("ANTHROPIC_", "OPENAI_")) or n.upper() in {
            "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR"} for n in os.environ):
            raise ContractError("ambient provider/transport overrides forbidden")
        if version("anthropic") != "1.4.0" or version("openai") != "1.107.0":
            raise ContractError("pinned SDK versions required")
        self._keys = {"anthropic_api_key": anthropic_api_key, "openai_api_key": openai_api_key}
        if any(not isinstance(v, str) or not v.strip() for v in self._keys.values()):
            raise ContractError("two explicit keys required")
        self.fixture = http_transports is not None
        if self.fixture:
            if (set(self._keys.values()) != {"fixture-not-a-secret"} or not isinstance(http_transports, dict)
                    or set(http_transports) != {"anthropic", "openai"}
                    or type(http_transports["anthropic"]) is not httpx2.MockTransport
                    or type(http_transports["openai"]) is not httpx.MockTransport):
                raise ContractError("fixture requires concrete SDK mocks and fixed fake keys")
        elif fixture_policy is not None or fixture_behavior:
            raise ContractError("fixture controls forbidden in live transport")
        behavior = dict(fixture_behavior or {})
        if (set(behavior) - {"ipc", "block_loop", "response_delay", "body_delay", "ignore_cancel", "cancel_delay", "cleanup_delay", "failure"}
                or behavior.get("ipc") not in (None, "never_read", "partial_frame")
                or behavior.get("failure") not in (None, "connect", "read", "write", "pool")
                or any(type(behavior[k]) not in (int, float) or not math.isfinite(behavior[k]) or behavior[k] < 0
                       for k in ("response_delay", "body_delay", "cancel_delay", "cleanup_delay") if k in behavior)
                or any(type(behavior[k]) is not bool for k in ("block_loop", "ignore_cancel") if k in behavior)):
            raise ContractError("invalid explicit fixture behavior")
        self.control_policy = copy.deepcopy(CONTROL_POLICY)
        if fixture_policy is not None and not isinstance(fixture_policy, Policy):
            raise ContractError("invalid fixture deadline policy")
        self._policy = fixture_policy or POLICY
        self._behavior, self._http = behavior, http_transports
        self._local = threading.local()
        self._conversations: dict[str, float] = {}
        self._soft_clocks: dict[str, Clock] = {}
        self._outcomes: dict[str, dict] = {}
        self._commits: dict[str, dict] = {}
        self._terminal = False
        self._closed = False
        self._active: dict | None = None
        self.select: Callable[[str, str], None] = lambda role, slot: None

    def register_conversation(self, conversation_id: str, absolute_deadline: float, *, clock: dict | None = None) -> None:
        limit = NATIVE_TIMEOUT if clock is not None else 600
        if (not isinstance(conversation_id, str) or not conversation_id or type(absolute_deadline) not in (int, float)
                or not math.isfinite(absolute_deadline) or absolute_deadline > time.monotonic() + limit + .1):
            raise ContractError("invalid conversation deadline registration")
        prior = self._conversations.get(conversation_id)
        if prior is not None and prior != absolute_deadline:
            raise ContractError("logical conversation deadline cannot be renewed")
        if clock is not None:
            validate_clock(clock)
            if (clock["conversation_id"] != conversation_id or clock["fixture"] is not self.fixture
                    or clock["deadline_monotonic"] != absolute_deadline):
                raise ContractError("conversation clock differs from its registration")
            if prior is not None:
                if conversation_id not in self._soft_clocks or self._soft_clocks[conversation_id].record != clock:
                    raise ContractError("conversation timing profile cannot change")
                return
            owner = self.startup_attachment["request"]["controller_owner"] if self.startup_attachment else None
            self._soft_clocks[conversation_id] = Clock(clock, owner=owner)
        elif conversation_id in self._soft_clocks:
            raise ContractError("soft conversation cannot revert to a legacy clock")
        self._conversations[conversation_id] = absolute_deadline

    def review_before_intent(self, slot_id: str, role: str, meta: dict, bindings: dict, financial: dict) -> None:
        """Wait only before an intent; the caller reruns source/readiness guards afterward."""
        self._local.timing_gate = None
        if self._closed or self._terminal:
            raise KnownDeadlineStop("closed or terminal transport cannot review continuation")
        conversation = meta.get("conversation")
        clock = self._soft_clocks.get(conversation) if role in {"editor", "native_selector"} and isinstance(conversation, str) else None
        if clock is not None:
            self._local.timing_gate = {"clock": copy.deepcopy(clock.record),
                "gate": clock.before_request(slot_id, bindings, financial)}

    def prepare(self, slot_id: str, role: str, meta: dict, bindings: dict) -> Budget:
        if self._closed:
            raise ContractError("closed transport cannot admit an intent")
        if self._terminal:
            raise KnownDeadlineStop("transport is terminal; no further admission")
        if (not isinstance(slot_id, str) or role != meta.get("role")
                or not isinstance(bindings, dict) or not {"source_sha256", "policy_sha256", "launcher_sha256"} <= set(bindings)
                or set(bindings) - {"study_sha256", "source_sha256", "policy_sha256", "launcher_sha256", "runtime_sha256"}
                or any(not isinstance(v, str) or _HASH.fullmatch(v) is None for v in bindings.values())):
            raise ContractError("deadline admission bindings differ")
        deadline = None
        timing = None
        if role in {"editor", "native_selector"}:
            name = meta.get("conversation")
            if name not in self._conversations:
                raise ContractError("editor lacks its absolute native conversation deadline")
            deadline = self._conversations[name]
            if name in self._soft_clocks:
                timing = getattr(self._local, "timing_gate", None)
                if not timing or timing["clock"] != self._soft_clocks[name].record:
                    raise ContractError("soft conversation lacks its pre-intent review gate")
                validate_gate(timing["clock"], timing["gate"], slot_id=slot_id, bindings=bindings, fixture=self.fixture)
                if time.monotonic() + self._policy.completion + self._policy.cleanup >= deadline:
                    raise TimingStop("hard_lifetime", {"clock": timing["clock"], "observed_monotonic": time.monotonic()})
                deadline = None
        allocation = budget(deadline, policy=self._policy)
        self._local.context = {"slot_id": slot_id, "role": role, "meta": copy.deepcopy(meta),
            "bindings": copy.deepcopy(bindings), "budget": allocation, "intent": None, "attempted": False,
            "conversation_timing": copy.deepcopy(timing)}
        return allocation

    def bind_intent(self, intent: dict, allocation: Budget) -> None:
        ctx = self._local.context
        if (ctx["budget"] != allocation or intent.get("slot_id") != ctx["slot_id"]
                or intent.get("role") != ctx["role"] or intent.get("fixture") is not self.fixture
                or ctx["bindings"].get("study_sha256", intent.get("study_sha256")) != intent.get("study_sha256")):
            raise ContractError("durable intent differs from deadline admission")
        ctx["intent"] = copy.deepcopy(intent)

    def disposition(self, slot_id: str) -> dict:
        return copy.deepcopy(self._outcomes.get(slot_id, {}))

    def commit(self, slot_id: str, result: dict) -> dict:
        if slot_id not in self._outcomes or result.get("slot_id") != slot_id:
            raise ContractError("transport commit lacks its exact outcome")
        record = self.disposition(slot_id) | {"terminal_result_sha256": digest(result),
            "terminal_status": result["status"], "terminal_reserved_micro_usd": result["reserved_micro_usd"]}
        record["sha256"] = digest(record)
        if slot_id in self._commits and self._commits[slot_id] != record:
            raise ContractError("transport result commitment cannot change")
        self._commits[slot_id] = record
        return copy.deepcopy(record)

    def create(self, role: str, request: dict) -> dict:
        ctx = getattr(self._local, "context", None)
        if (not ctx or ctx["intent"] is None or ctx["attempted"] or ctx["role"] != role
                or digest(request) != ctx["intent"]["request_sha256"]):
            raise ContractError("provider operation lacks its single durable intent")
        reject_final_assistant_prefill(role, request)
        if role in {"editor", "native_selector", "fixed_selector"}:
            config = request.get("output_config", {})
            config = {k: v for k, v in config.items() if k != "format"} if role == "fixed_selector" else config
            if (request.get("model") != "claude-opus-5" or request.get("max_tokens") != 16000
                    or request.get("thinking") != {"type": "adaptive"} or config != {"effort": "high"}
                    or request.get("service_tier") != "standard_only" or request.get("inference_geo") != "global"):
                raise ContractError("frozen editor/selector profile differs")
        else:
            _validate_request(role, request)
        ctx["attempted"] = True
        return self._coordinate(ctx, request)

    def _coordinate(self, ctx: dict, request: dict) -> dict:
        allocation: Budget = ctx["budget"]
        started = allocation.started_monotonic
        incoming: queue.Queue = queue.Queue()
        outgoing: queue.Queue = queue.Queue()
        stop = threading.Event()
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe(duplex=True)
        process = context.Process(target=worker.main, args=(child, self._behavior if self.fixture else None), daemon=True)
        helpers: list[threading.Thread] = []
        state: dict[str, Any] = {"process": process, "parent": parent, "child": child, "helpers": helpers,
                 "stop": stop, "outgoing": outgoing, "cleanup_deadline": allocation.cleanup_deadline}
        self._active = state
        def send(value: dict) -> None:
            outgoing.put(value)
        def starter() -> None:
            try:
                process.start()
                child.close()
                incoming.put({"type": "started"})
            except BaseException:
                incoming.put({"type": "ipc_failure"})
        def writer() -> None:
            try:
                while not stop.is_set():
                    value = outgoing.get()
                    if value is None:
                        return
                    parent.send_bytes(json.dumps(value, ensure_ascii=False, allow_nan=False,
                                                 separators=(",", ":")).encode())
            except BaseException:
                incoming.put({"type": "ipc_failure"})
        def reader() -> None:
            try:
                while not stop.is_set():
                    incoming.put(json.loads(parent.recv_bytes(worker.MAX_FRAME).decode("utf-8")))
            except BaseException:
                incoming.put({"type": "ipc_closed"})
        for target in (starter, writer, reader):
            thread = threading.Thread(target=target, daemon=True)
            helpers.append(thread)
            thread.start()
        receipt = failure = failure_response = None
        captured = None
        sdk_invoked: bool | None = False
        go_sent = cancelled = done = False
        subtype = None
        end = allocation.cleanup_deadline
        cleanup_started = None
        owner_stop = False
        def fixture_reply(message: dict) -> None:
            try:
                import httpx
                import httpx2
                if not self.fixture or self._http is None or message["provider"] not in self._http:
                    raise ContractError("unexpected live mock RPC")
                self.select(ctx["role"], ctx["slot_id"])
                module = httpx if message["provider"] == "openai" else httpx2
                io = {key: getattr(allocation.policy, key) for key in ("connect", "pool", "write", "read")}
                if message.get("timeouts") != io:
                    raise ContractError("actual async SDK I/O timeout extensions differ")
                wire = module.Request(message["method"], message["url"],
                    content=base64.b64decode(message["body"], validate=True), extensions={"timeout": io})
                response = self._http[message["provider"]].handle_request(wire)
                body = response.read()
                incoming.put({"type": "fixture_result", "value": {"type": "http_result", "id": message["id"],
                    "status": response.status_code, "headers": dict(response.headers),
                    "body": base64.b64encode(body).decode("ascii")}})
            except BaseException:
                incoming.put({"type": "ipc_failure"})
        try:
            stop_margin = min(.2, allocation.policy.cleanup / 3)
            while time.monotonic() < end - stop_margin:
                now = time.monotonic()
                if now >= allocation.deadline_monotonic and not cancelled and not done and receipt is None:
                    cancelled = True
                    cleanup_started = now if cleanup_started is None else cleanup_started
                    send({"type": "cancel"})
                try:
                    msg = incoming.get(timeout=max(.001, min(.02, end - now)))
                except queue.Empty:
                    continue
                kind = msg.get("type") if isinstance(msg, dict) else "ipc_failure"
                if kind == "started":
                    if time.monotonic() < allocation.deadline_monotonic:
                        send({"type": "init", "fixture": self.fixture, "keys": dict(self._keys),
                              "role": ctx["role"], "request": request,
                              "io": {k: getattr(allocation.policy, k) for k in ("connect", "pool", "write", "read")}})
                    else:
                        cancelled = True
                        cleanup_started = time.monotonic() if cleanup_started is None else cleanup_started
                elif kind == "ready":
                    if not cancelled and time.monotonic() < allocation.deadline_monotonic:
                        go_sent, sdk_invoked = True, None
                        send({"type": "go"})
                    else:
                        send({"type": "cancel"})
                elif kind == "invoked":
                    sdk_invoked = True
                elif kind == "http":
                    t = threading.Thread(target=fixture_reply, args=(msg,), daemon=True)
                    helpers.append(t)
                    t.start()
                elif kind == "fixture_result":
                    send(msg["value"])
                elif kind == "receipt":
                    try:
                        converted = normalize(ctx["role"], msg["raw"], msg.get("request_id"), time.monotonic() - started)
                        validated = core._result(ctx["intent"], converted)
                        receipt = converted
                        captured = time.monotonic() if validated["status"] == "response" else None
                        if captured is None:
                            failure = validated["failure"]
                    except Exception:
                        request_id = provider_request_id(msg.get("request_id"))
                        failure = make_failure("processing_error", "response_conversion", request_id=request_id)
                        failure_response = retain_response({"provider_response": msg.get("raw"), "request_id": request_id})
                    cleanup_started = time.monotonic() if cleanup_started is None else cleanup_started
                    end = min(end, cleanup_started + allocation.policy.cleanup)
                elif kind == "failure":
                    category = msg.get("category")
                    failure = make_failure(category if category in {"timeout", "connection", "provider_status", "transport_error"}
                        else "transport_error", "provider_call", status_code=msg.get("status_code"), request_id=msg.get("request_id"))
                    subtype = msg.get("timeout_subtype") if msg.get("timeout_subtype") in {
                        "ConnectTimeout", "ReadTimeout", "WriteTimeout", "PoolTimeout"} else None
                    cleanup_started = time.monotonic() if cleanup_started is None else cleanup_started
                    end = min(end, cleanup_started + allocation.policy.cleanup)
                elif kind == "done":
                    done = True
                    break
                elif kind in {"ipc_closed", "ipc_failure"}:
                    if receipt is not None or failure is not None:
                        break
                    failure = make_failure("timeout" if cancelled else "transport_error", "provider_call")
                    cleanup_started = time.monotonic() if cleanup_started is None else cleanup_started
                    end = min(end, cleanup_started + allocation.policy.cleanup)
                    break
        finally:
            state["cleanup_deadline"] = end
            state["done"] = done
            stopped = self._stop(state, end)
            owner_stop = not stopped
            self._active = None if stopped else state
        finished = time.monotonic()
        late = captured is not None and not eligible(captured, allocation)
        unknown = receipt is None or captured is None
        deadline_expired = cancelled or late or finished > end and not stopped
        cleanup_failed = not done or bool(state.get("forced_worker_stop", False))
        self._terminal = self._terminal or unknown or late or owner_stop or cleanup_failed
        audit = {"kind": "phase3b-s2-transport-audit-v1", "slot_id": ctx["slot_id"], "role": ctx["role"],
            "intent_sha256": digest(ctx["intent"]), "request_sha256": ctx["intent"]["request_sha256"],
            "study_sha256": ctx["intent"]["study_sha256"], **ctx["bindings"], "fixture": self.fixture,
            "budget": allocation.record(), "parent_capture_monotonic": captured,
            "capture_point": "parent after complete receipt normalization and frozen core model/usage validation",
            "finished_utc": datetime.now(timezone.utc).isoformat(), "elapsed_seconds": finished - started,
            "cleanup_elapsed_seconds": max(0.0, finished - cleanup_started) if cleanup_started is not None else 0.0,
            "sdk_invoked": sdk_invoked if go_sent else False, "wire_egress": "not-started" if not go_sent else "unknown",
            "timeout_subtype": subtype, "completion_category": "late-known" if late else "known" if not unknown else "unknown",
            "late_known": late, "deadline_expired": deadline_expired, "cleanup_failed": cleanup_failed, "worker_stopped": stopped,
            "owner_stop_required": owner_stop, "worker_pid": process.pid}
        if ctx.get("conversation_timing") is not None:
            audit.update(kind="phase3b-s2-transport-audit-v2", conversation_timing=ctx["conversation_timing"])
        self._outcomes[ctx["slot_id"]] = audit
        if stopped:
            process.close()
        if receipt is not None:
            # Core accounting remains authoritative even when validation classified its usage unknown.
            return receipt
        raise TransportFailure(failure or make_failure("timeout" if cancelled else "transport_error", "provider_call"), failure_response)

    @staticmethod
    def _stop(state: dict, deadline: float) -> bool:
        process = state["process"]
        state["stop"].set()
        state["outgoing"].put(None)
        try:
            if process.pid is not None:
                remaining = max(0.0, deadline - time.monotonic())
                # A completed worker may need normal interpreter teardown; reserve
                # headroom for termination and helpers within this same deadline.
                grace = remaining - min(1.0, remaining / 2) if state.get("done") else min(.02, remaining)
                process.join(timeout=grace)
                if process.is_alive():
                    state["forced_worker_stop"] = True
                    process.terminate()
                    process.join(timeout=min(.05, max(0.0, deadline - time.monotonic())))
                if process.is_alive():
                    process.kill()
                    process.join(timeout=max(0.0, min(.1, deadline - time.monotonic())))
        except (AssertionError, OSError, ValueError):
            state["stop_error"] = True
        for name in ("parent", "child"):
            try:
                state[name].close()
            except OSError:
                state["stop_error"] = True
        for helper in state["helpers"]:
            helper.join(timeout=max(0.0, min(.05, deadline - time.monotonic())))
        try:
            dead = process.pid is not None and not process.is_alive()
        except (AssertionError, ValueError):
            dead = False
        return dead and not any(t.is_alive() for t in state["helpers"])

    def close(self) -> None:
        self._closed = True
        if self._active is not None:
            self._stop(self._active, self._active["cleanup_deadline"])
        for name in self._keys:
            self._keys[name] = ""


def audit_path(study_sha256: str, fixture: bool, slot_id: str) -> Path:
    if (not isinstance(study_sha256, str) or _HASH.fullmatch(study_sha256) is None
            or type(fixture) is not bool or not isinstance(slot_id, str)
            or re.fullmatch(r"[A-Za-z0-9_.:/-]{1,240}", slot_id) is None):
        raise ContractError("invalid transport audit scope")
    return Path("/results/phase3b-seq2-v1") / study_sha256 / (
        "mock" if fixture else "live") / "transport-audit" / (digest({"slot_id": slot_id}) + ".json")


def validate_audit(record: dict, *, intent: dict, result: dict, bindings: dict) -> dict:
    """Read-only exact receipt binding, usable during replay without any client."""
    if not isinstance(record, dict):
        raise ContractError("transport audit must be an object")
    expected = {"kind", "slot_id", "role", "intent_sha256", "request_sha256", "study_sha256", "fixture",
        "budget", "parent_capture_monotonic", "capture_point", "finished_utc", "elapsed_seconds",
        "cleanup_elapsed_seconds", "sdk_invoked", "wire_egress", "timeout_subtype", "completion_category",
        "late_known", "deadline_expired", "cleanup_failed", "worker_stopped", "owner_stop_required", "worker_pid",
        "terminal_result_sha256", "terminal_status", "terminal_reserved_micro_usd", "sha256"} | set(bindings)
    soft = record.get("kind") == "phase3b-s2-transport-audit-v2"
    if soft:
        expected.add("conversation_timing")
    if (set(record) != expected or record.get("kind") not in {"phase3b-s2-transport-audit-v1", "phase3b-s2-transport-audit-v2"}
            or record.get("sha256") != digest({k: v for k, v in record.items() if k != "sha256"})
            or record["slot_id"] != intent["slot_id"] or record["role"] != intent["role"]
            or record["study_sha256"] != intent["study_sha256"] or record["fixture"] is not intent["fixture"]
            or record["intent_sha256"] != digest(intent) or record["request_sha256"] != intent["request_sha256"]
            or record["terminal_result_sha256"] != digest(result) or record["terminal_status"] != result["status"]
            or record["terminal_reserved_micro_usd"] != result["reserved_micro_usd"]
            or any(record.get(k) != v for k, v in bindings.items())):
        raise ContractError("transport audit differs from authoritative slot/result/source")
    value = record["budget"]
    try:
        policy = Policy(**value["policy"])
        allocation = Budget(**{k: value[k] for k in ("started_monotonic", "deadline_monotonic",
            "effective_seconds", "conversation_deadline", "started_utc")}, policy=policy)
        numbers = (allocation.started_monotonic, allocation.deadline_monotonic, allocation.effective_seconds,
                   record["elapsed_seconds"], record["cleanup_elapsed_seconds"])
        valid = (all(type(n) in (int, float) and math.isfinite(n) for n in numbers)
            and allocation.effective_seconds > 0 and allocation.effective_seconds <= policy.completion
            and math.isclose(allocation.deadline_monotonic - allocation.started_monotonic,
                             allocation.effective_seconds, abs_tol=1e-6)
            and value["cleanup_deadline_monotonic"] == allocation.cleanup_deadline
            and (intent["fixture"] or policy == POLICY)
            and all(type(record[k]) is bool for k in ("late_known", "deadline_expired", "cleanup_failed", "worker_stopped", "owner_stop_required"))
            and record["owner_stop_required"] is not record["worker_stopped"]
            and (record["sdk_invoked"] is None or type(record["sdk_invoked"]) is bool)
            and record["wire_egress"] in {"not-started", "unknown"}
            and (record["wire_egress"] != "not-started" or record["sdk_invoked"] is False)
            and record["timeout_subtype"] in {None, "ConnectTimeout", "ReadTimeout", "WriteTimeout", "PoolTimeout"})
        if intent["role"] in {"editor", "native_selector"}:
            if soft:
                timing = record["conversation_timing"]
                if not isinstance(timing, dict) or set(timing) != {"clock", "gate"}:
                    raise ValueError("invalid conversation timing evidence")
                validate_gate(timing["clock"], timing["gate"], slot_id=intent["slot_id"], bindings=bindings, fixture=intent["fixture"])
                valid = valid and allocation.conversation_deadline is None and allocation.effective_seconds == policy.completion
                valid = valid and timing["gate"]["checked_monotonic"] <= allocation.started_monotonic
                valid = valid and allocation.cleanup_deadline < timing["clock"]["deadline_monotonic"]
            elif allocation.conversation_deadline is not None:
                available = min(policy.completion, allocation.conversation_deadline
                                - allocation.started_monotonic - policy.editor_margin)
                valid = valid and available >= policy.editor_minimum and math.isclose(
                    allocation.effective_seconds, available, abs_tol=1e-6)
            else:
                valid = False
        else:
            valid = valid and not soft and allocation.conversation_deadline is None
        valid = valid and record["completion_category"] in {"known", "late-known", "unknown"}
        valid = valid and record["capture_point"] == "parent after complete receipt normalization and frozen core model/usage validation"
        captured = record["parent_capture_monotonic"]
        if captured is not None:
            valid = valid and type(captured) in (int, float) and math.isfinite(captured)
            valid = valid and record["late_known"] is (not eligible(captured, allocation)) and result["status"] == "response"
        else:
            valid = valid and record["late_known"] is False and result["status"] == "unknown"
        if not valid:
            raise ValueError
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ContractError("invalid bounded transport timing/audit disposition") from exc
    return copy.deepcopy(record)


def read_audit(study_sha256: str, fixture: bool, slot_id: str, *, intent: dict, result: dict, bindings: dict) -> dict:
    path = audit_path(study_sha256, fixture, slot_id)
    if (any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file()
            or path.stat().st_size > 2_000_000):
        raise ContractError("missing/linked/oversized authoritative transport audit")
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ContractError("duplicate transport audit JSON key")
            value[key] = item
        return value
    def nonfinite(_):
        raise ContractError("nonfinite transport audit JSON")
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=nonfinite)
    return validate_audit(value, intent=intent, result=result, bindings=bindings)
