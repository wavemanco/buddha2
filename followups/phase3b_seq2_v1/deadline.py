"""Soft conversation reviews around the unchanged bounded provider requests."""
from __future__ import annotations

import copy
import math
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from buddha2.artifacts import ContractError, digest, write_once
from followups.phase3a_c1_completion_v3.deadline import (
    POLICY,
    Budget,
    KnownDeadlineStop,
    OwnerStopRequired,
    Policy,
    budget,
    eligible,
)

__all__ = ["POLICY", "Budget", "KnownDeadlineStop", "OwnerStopRequired", "Policy", "budget", "eligible",
    "CONVERSATION_POLICY", "NATIVE_TIMEOUT", "FETCH_TIMEOUT", "TimingStop", "clock_record", "validate_clock",
    "Clock", "validate_gate", "validate_stop", "decide"]

CONVERSATION_POLICY: dict[str, Any] = {
    "id": "phase3b-soft-timing-v1", "soft_seconds": 600, "warning_seconds": 480,
    "grace_seconds": 300, "extension_seconds": 600, "review_seconds": 1800, "max_requests": 24,
}
# These are outer ceilings, including operator waits; they grant no extra calls or money.
NATIVE_TIMEOUT = int(CONVERSATION_POLICY["soft_seconds"] + CONVERSATION_POLICY["grace_seconds"]
    + CONVERSATION_POLICY["max_requests"] * (CONVERSATION_POLICY["review_seconds"]
        + CONVERSATION_POLICY["extension_seconds"] + POLICY.completion + POLICY.cleanup))
FETCH_TIMEOUT = NATIVE_TIMEOUT - 10
_HASH = re.compile(r"[a-f0-9]{64}\Z")
_PAIR = r"(?:p3b-0[1-4]|p4-(?:0[1-9]|1[0-9]|2[0-4]))"
_SLOT = re.compile(_PAIR + r"\.adaptive\.editor\.(?:inv[12]\.a[12]|dom[12]\.a[12]|c[12]\.a[12]|select\.seq2)\.t(?:0[1-9]|1[0-9]|2[0-4])\Z")


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _number(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _seal(value: dict) -> dict:
    return {**value, "sha256": digest(value)}


def _checked(value: Any) -> dict:
    _require(isinstance(value, dict) and value.get("sha256") == digest(
        {k: v for k, v in value.items() if k != "sha256"}), "timing record seal differs")
    return value


def clock_record(*, study_sha256: str, source_sha256: str, pilot: str, label: str,
                 fixture: bool, editor_profile_sha256: str, started: float | None = None) -> dict:
    started = time.monotonic() if started is None else started
    _require(_number(started), "invalid conversation start")
    value = {"kind": "phase3b-conversation-clock-v2", "study_sha256": study_sha256,
        "source_sha256": source_sha256, "pilot": pilot, "label": label,
        "conversation_id": pilot + ":adaptive:" + label, "fixture": fixture,
        "started_monotonic": started, "deadline_monotonic": started + NATIVE_TIMEOUT,
        "soft_deadline_monotonic": started + CONVERSATION_POLICY["soft_seconds"],
        "grace_deadline_monotonic": started + (CONVERSATION_POLICY["soft_seconds"] + CONVERSATION_POLICY["grace_seconds"]),
        "seconds": CONVERSATION_POLICY["soft_seconds"], "timing_policy": copy.deepcopy(CONVERSATION_POLICY),
        "native_subprocess_cap_seconds": NATIVE_TIMEOUT, "OpenCode_fetch_cap_seconds": FETCH_TIMEOUT,
        "renewable": False, "editor_profile_sha256": editor_profile_sha256,
        "anchor": "inside editor._SERIAL before boundary setup and native CLI invocation"}
    return validate_clock(_seal(value))


def validate_clock(value: Any) -> dict:
    _checked(value)
    _require(value.get("kind") == "phase3b-conversation-clock-v2"
        and all(isinstance(value.get(k), str) and _HASH.fullmatch(value[k]) for k in
                ("study_sha256", "source_sha256", "editor_profile_sha256"))
        and type(value.get("fixture")) is bool and _number(value.get("started_monotonic"))
        and isinstance(value.get("pilot"), str) and re.fullmatch(_PAIR, value["pilot"])
        and isinstance(value.get("label"), str)
        and _SLOT.fullmatch(value["pilot"] + ".adaptive.editor." + value.get("label", "") + ".t01")
        and value.get("conversation_id") == value["pilot"] + ":adaptive:" + value["label"]
        and value.get("timing_policy") == CONVERSATION_POLICY and value.get("renewable") is False
        and value.get("seconds") == CONVERSATION_POLICY["soft_seconds"]
        and value.get("deadline_monotonic") == value["started_monotonic"] + NATIVE_TIMEOUT
        and value.get("soft_deadline_monotonic") == value["started_monotonic"] + 600
        and value.get("grace_deadline_monotonic") == value["started_monotonic"] + 900
        and value.get("native_subprocess_cap_seconds") == NATIVE_TIMEOUT
        and value.get("OpenCode_fetch_cap_seconds") == FETCH_TIMEOUT, "invalid conversation timing profile")
    return value


class TimingStop(KnownDeadlineStop):
    def __init__(self, reason: str, evidence: dict):
        self.reason, self.evidence = reason, copy.deepcopy(evidence)
        super().__init__("conversation timing stopped before admission: " + reason)


def _validate_request(value: Any) -> dict:
    _checked(value)
    clock = validate_clock(value.get("clock"))
    bindings = value.get("bindings")
    _require(set(value) == {"kind", "clock", "bindings", "slot_id", "sequence", "fixture", "controller_owner",
        "controller_paused", "created_monotonic", "deadline_monotonic", "soft_deadline_monotonic",
        "created_at_utc", "expires_at_utc", "financial", "sha256"}
        and value.get("kind") == "phase3b-time-review-request-v1"
        and isinstance(bindings, dict) and {"study_sha256", "source_sha256", "policy_sha256", "launcher_sha256"} <= set(bindings)
        and set(bindings) <= {"study_sha256", "source_sha256", "policy_sha256", "launcher_sha256", "runtime_sha256"}
        and all(isinstance(v, str) and _HASH.fullmatch(v) for v in bindings.values())
        and all(bindings[k] == clock[k] for k in ("study_sha256", "source_sha256"))
        and isinstance(value.get("slot_id"), str) and _SLOT.fullmatch(value["slot_id"])
        and value["slot_id"].startswith(clock["pilot"] + ".adaptive.editor." + clock["label"] + ".t")
        and type(value.get("sequence")) is int and 1 <= value["sequence"] <= 24
        and value.get("fixture") is clock["fixture"] and value.get("controller_paused") is True
        and all(_number(value.get(k)) for k in ("created_monotonic", "deadline_monotonic", "soft_deadline_monotonic"))
        and value["created_monotonic"] >= value["soft_deadline_monotonic"]
        and 0 < value["deadline_monotonic"] - value["created_monotonic"] <= 1800
        and value["deadline_monotonic"] <= clock["deadline_monotonic"] - POLICY.completion - POLICY.cleanup
        and isinstance(value.get("financial"), dict), "invalid timing review request")
    owner = value.get("controller_owner")
    _require(clock["fixture"] and owner is None or isinstance(owner, dict) and set(owner) == {"container_id", "pid"}
        and isinstance(owner["container_id"], str) and _HASH.fullmatch(owner["container_id"])
        and type(owner["pid"]) is int and owner["pid"] == 1,
        "timing review lacks its exact controller owner")
    created = datetime.fromisoformat(value["created_at_utc"])
    expires = datetime.fromisoformat(value["expires_at_utc"])
    _require(created.tzinfo is not None and expires.tzinfo is not None and math.isclose(
        (expires - created).total_seconds(), value["deadline_monotonic"] - value["created_monotonic"], abs_tol=.001),
        "timing review wall and monotonic windows differ")
    return value


def _validate_decision(value: Any, request: dict) -> dict:
    _checked(value)
    _require(set(value) == {"kind", "request_sha256", "decision", "created_at_utc", "sha256"}
        and value["kind"] == "phase3b-time-review-decision-v1" and value["request_sha256"] == request["sha256"]
        and value["decision"] in {"continue", "stop"}, "timing decision belongs to another request")
    decided = datetime.fromisoformat(value["created_at_utc"])
    _require(decided.tzinfo is not None
        and datetime.fromisoformat(request["created_at_utc"]) <= decided < datetime.fromisoformat(request["expires_at_utc"]),
        "timing decision is outside its original review window")
    return value


class Clock:
    def __init__(self, record: dict, directory: Path | None = None, *, owner: dict | None = None):
        from .support import NATIVE, safe
        self.record = copy.deepcopy(validate_clock(record))
        expected = NATIVE / record["study_sha256"] / ("mock" if record["fixture"] else "live") / "timing-controls" / digest({"conversation_id": record["conversation_id"]})
        _require(directory is None or record["fixture"] or Path(directory) == expected, "foreign timing control directory")
        self.directory = safe(Path(directory) if directory is not None else expected)
        self.owner = copy.deepcopy(owner)
        self.deadline = record["grace_deadline_monotonic"]
        self.reviews: list[dict] = []
        self.warned = self.grace_recorded = False
        write_once(self.directory / "clock.json", self.record)

    def before_request(self, slot: str, bindings: dict, financial: dict) -> dict:
        from .support import read
        _require(isinstance(slot, str) and _SLOT.fullmatch(slot) and isinstance(bindings, dict)
            and isinstance(financial, dict), "invalid timing admission metadata")
        now = time.monotonic()
        hard = self.record["deadline_monotonic"] - POLICY.completion - POLICY.cleanup
        if now >= hard:
            raise TimingStop("hard_lifetime", {"clock": self.record, "observed_monotonic": now})
        for name, elapsed, flag in (("warning", 480, "warned"), ("grace", 600, "grace_recorded")):
            if now >= self.record["started_monotonic"] + elapsed and not getattr(self, flag):
                write_once(self.directory / (name + ".json"), _seal({"kind": "phase3b-time-" + name + "-v1",
                    "clock_sha256": self.record["sha256"], "observed_monotonic": now, "slot_id": slot,
                    "automatic_provider_call": False}))
                setattr(self, flag, True)
        # File work may cross a soft or hard boundary; decide with the current clock.
        now = time.monotonic()
        if now >= hard:
            raise TimingStop("hard_lifetime", {"clock": self.record, "observed_monotonic": now})
        permission_time = now
        if now >= self.deadline:
            sequence = len(self.reviews) + 1
            _require(sequence <= 24, "too many timing decisions for the declared request limit")
            expires = min(now + 1800, hard)
            utc = datetime.now(timezone.utc)
            request = _validate_request(_seal({"kind": "phase3b-time-review-request-v1", "clock": self.record,
                "bindings": copy.deepcopy(bindings), "slot_id": slot, "sequence": sequence,
                "fixture": self.record["fixture"], "controller_owner": self.owner, "controller_paused": True,
                "created_monotonic": now, "deadline_monotonic": expires, "soft_deadline_monotonic": self.deadline,
                "created_at_utc": utc.isoformat(), "expires_at_utc": (utc + timedelta(seconds=expires - now)).isoformat(),
                "financial": copy.deepcopy(financial)}))
            prefix = self.directory / f"review-{sequence:02}"
            write_once(Path(str(prefix) + ".request.json"), request)
            decision = None
            outcome = "review_timeout"
            while time.monotonic() < expires:
                target = Path(str(prefix) + ".decision.json")
                if target.exists():
                    decision = _validate_decision(read(target), request)
                    outcome = "continued" if decision["decision"] == "continue" else "operator_stop"
                    break
                time.sleep(min(1.0, max(0.0, expires - time.monotonic())))
            finished = time.monotonic()
            permission_time = finished
            if finished >= expires:
                outcome = "review_timeout"
            waited = finished - now
            if outcome == "continued":
                # An overrunning setup step must not consume the user's new allowance.
                self.deadline = finished + CONVERSATION_POLICY["extension_seconds"]
            ack = _seal({"kind": "phase3b-time-review-ack-v1", "request": request, "decision": decision,
                "outcome": outcome, "acknowledged_monotonic": finished, "paused_seconds": waited,
                "soft_deadline_monotonic": self.deadline})
            write_once(Path(str(prefix) + ".ack.json"), ack)
            if outcome != "continued":
                raise TimingStop(outcome, ack)
            self.reviews.append(ack)
        gate = _seal({"kind": "phase3b-soft-time-gate-v1", "clock_sha256": self.record["sha256"],
            "slot_id": slot, "bindings": copy.deepcopy(bindings),
            "checked_monotonic": permission_time, "soft_deadline_monotonic": self.deadline,
            "reviews": copy.deepcopy(self.reviews)})
        validate_gate(self.record, gate, slot_id=slot, bindings=bindings, fixture=self.record["fixture"])
        return gate


def validate_gate(clock: dict, gate: dict, *, slot_id: str, bindings: dict, fixture: bool) -> dict:
    validate_clock(clock)
    _checked(gate)
    _require(set(gate) == {"kind", "clock_sha256", "slot_id", "bindings", "checked_monotonic", "soft_deadline_monotonic", "reviews", "sha256"}
        and gate.get("kind") == "phase3b-soft-time-gate-v1" and gate.get("clock_sha256") == clock["sha256"]
        and gate.get("slot_id") == slot_id and gate.get("bindings") == bindings
        and clock["fixture"] is fixture and all(clock[k] == bindings[k] for k in ("study_sha256", "source_sha256"))
        and isinstance(slot_id, str) and _SLOT.fullmatch(slot_id)
        and slot_id.startswith(clock["pilot"] + ".adaptive.editor." + clock["label"] + ".t")
        and isinstance(gate.get("reviews"), list) and len(gate["reviews"]) <= 24, "soft timing gate identity differs")
    deadline = clock["grace_deadline_monotonic"]
    latest = clock["started_monotonic"]
    for sequence, ack in enumerate(gate["reviews"], 1):
        _checked(ack)
        request = _validate_request(ack.get("request"))
        _validate_decision(ack.get("decision"), request)
        waited, finished = ack.get("paused_seconds"), ack.get("acknowledged_monotonic")
        _require(request["clock"] == clock and request["bindings"] == bindings and request["sequence"] == sequence
            and set(ack) == {"kind", "request", "decision", "outcome", "acknowledged_monotonic", "paused_seconds", "soft_deadline_monotonic", "sha256"}
            and ack.get("kind") == "phase3b-time-review-ack-v1"
            and request["soft_deadline_monotonic"] == deadline and ack.get("outcome") == "continued"
            and ack["decision"]["decision"] == "continue" and _number(waited) and waited >= 0 and _number(finished)
            and math.isclose(finished - request["created_monotonic"], waited, abs_tol=1e-6)
            and request["created_monotonic"] >= latest and finished < request["deadline_monotonic"]
            and int(request["slot_id"].rsplit(".t", 1)[1]) <= int(slot_id.rsplit(".t", 1)[1]),
            "invalid continued timing review")
        latest = finished
        deadline = finished + CONVERSATION_POLICY["extension_seconds"]
        _require(ack.get("soft_deadline_monotonic") == deadline, "timing allowance changed without a decision")
    checked = gate.get("checked_monotonic")
    _require(_number(checked) and latest <= checked < deadline
        and checked < clock["deadline_monotonic"] - POLICY.completion - POLICY.cleanup
        and gate.get("soft_deadline_monotonic") == deadline, "soft timing gate exceeded its reviewed allowance")
    return gate


def validate_stop(evidence: Any, reason: Any, *, slot_id: str, bindings: dict, fixture: bool) -> dict:
    _require(isinstance(evidence, dict), "missing timing stop evidence")
    if reason == "hard_lifetime":
        clock = validate_clock(evidence.get("clock"))
        _require(_number(evidence.get("observed_monotonic")) and evidence["observed_monotonic"] >=
            clock["deadline_monotonic"] - POLICY.completion - POLICY.cleanup, "hard lifetime has not elapsed")
    else:
        _checked(evidence)
        request = _validate_request(evidence.get("request"))
        clock = request["clock"]
        _require(request["slot_id"] == slot_id and request["bindings"] == bindings
            and evidence.get("kind") == "phase3b-time-review-ack-v1" and evidence.get("outcome") == reason
            and _number(evidence.get("acknowledged_monotonic"))
            and evidence["acknowledged_monotonic"] >= request["created_monotonic"], "timing stop identity differs")
        if reason == "operator_stop":
            _validate_decision(evidence.get("decision"), request)
            _require(evidence["decision"]["decision"] == "stop"
                and evidence["acknowledged_monotonic"] < request["deadline_monotonic"], "invalid operator stop")
        elif reason == "review_timeout":
            _require(evidence["acknowledged_monotonic"] >= request["deadline_monotonic"], "review did not expire")
        else:
            raise ContractError("unknown timing stop")
    _require(clock["fixture"] is fixture and all(clock[k] == bindings[k] for k in ("study_sha256", "source_sha256"))
        and isinstance(slot_id, str) and _SLOT.fullmatch(slot_id)
        and slot_id.startswith(clock["pilot"] + ".adaptive.editor." + clock["label"] + ".t"),
        "timing stop belongs to another conversation")
    return evidence


def decide(request_path: Path, decision: str) -> dict:
    """Trusted host operation, invoked only after the user's continue/stop answer."""
    from .support import BASE, ROOT, read, safe, source_identity
    target = safe(Path(request_path).absolute(), roots=(ROOT / "runs/phase3b-seq2-v1", BASE))
    request = _validate_request(read(target))
    _require(target.name == f"review-{request['sequence']:02}.request.json"
        and target.parent.name == digest({"conversation_id": request["clock"]["conversation_id"]})
        and target.parent.parent.name == "timing-controls" and decision in {"continue", "stop"},
        "unexpected timing decision path/action")
    prefix = target.name.removesuffix(".request.json")
    _require(not (target.parent / (prefix + ".ack.json")).exists(), "timing review is already closed")
    _require(datetime.now(timezone.utc) < datetime.fromisoformat(request["expires_at_utc"]), "timing review expired")
    if not request["fixture"]:
        from .supervision import _owner_running
        _owner_running(request["controller_owner"]["container_id"])
        _require(source_identity()["sha256"] == request["bindings"]["source_sha256"], "timing review source changed")
    value = _validate_decision(_seal({"kind": "phase3b-time-review-decision-v1", "request_sha256": request["sha256"],
        "decision": decision, "created_at_utc": datetime.now(timezone.utc).isoformat()}), request)
    write_once(target.parent / (prefix + ".decision.json"), value)
    return {"decision": decision, "request_sha256": request["sha256"], "provider_calls": 0,
            "financial_authority_changed": False, "effective_only_after_controller_ack": True}
