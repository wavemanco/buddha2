"""One-shot trusted host attachment before transport construction or admission.

The host publisher is a trusted attestation seam, like the semantic reviews.
It cannot authenticate the orchestrator itself: its caller must obtain the actual
running-agent observation immediately before publication, never load old status.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import secrets
import subprocess  # nosec B404
import sys
import time
from pathlib import Path
from typing import Callable

from buddha2.artifacts import ContractError, digest, write_once

from .support import BASE, ROOT, read, require, safe

SECONDS = 1800
OBSERVATION_SECONDS = 30
BINDINGS = ("study_sha256", "source_sha256", "runtime_sha256", "policy_sha256", "launcher_sha256", "grant_sha256")
HASH = re.compile(r"[0-9a-f]{64}")
AGENT = re.compile(r"/root(?:/[a-z0-9_]+)+")


def profile() -> dict:
    return {"kind": "phase3b-s2-startup-supervision-profile-v2", "seconds": SECONDS,
        "observation_seconds": OBSERVATION_SECONDS, "renewable": False, "one_shot": True,
        "agent_source": "actual fresh collaboration.list_agents result via trusted host attestation",
        "exact_controller_owner_required": True, "before_transport_claim_binding_and_intent": True,
        "supervisor_started_before_key_window": "external orchestrator obligation verified in the actual rehearsal",
        "point_in_time_presence_only": True, "later_loss_uses_existing_review_and_export_timeouts": True,
        "quality_or_readiness_approval": False, "provider_calls": 0,
        "timing_reviews": {"policy_id": "phase3b-soft-timing-v1",
            "warning_glob": "timing-controls/*/warning.json",
            "pause_request_glob": "timing-controls/*/review-*.request.json",
            "operator_wait_seconds": SECONDS, "explicit_user_answer_required": True,
            "automatic_continuation": False,
            "decision_command": "python -B -m buddha2 experiment timing --request <host-request.json> --decision <continue|stop>",
            "supervisor_obligation": "Notify on warnings; promptly ask the user at a pause and publish only their actual answer.",
            "effective_after_controller_ack": True}}


def agent_name(value: str | None) -> str:
    if not isinstance(value, str) or AGENT.fullmatch(value) is None:
        raise ContractError("a dedicated supervisor agent is required")
    return value


def _utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _timestamp(value: str) -> dt.datetime:
    try:
        result = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(result.utcoffset() == dt.timedelta(0), "attachment time must be UTC")
        return result
    except (AttributeError, TypeError, ValueError) as error:
        raise ContractError("invalid attachment timestamp") from error


def _sealed(value: dict) -> dict:
    require(value.get("sha256") == digest({k: v for k, v in value.items() if k != "sha256"}), "attachment seal differs")
    return value


def _publish(target: Path, value: dict) -> dict:
    target = safe(target, roots=(ROOT, BASE))
    target.parent.mkdir(parents=True, exist_ok=True)
    sealed = {**value, "sha256": digest(value)}
    write_once(target, sealed)
    return sealed


def _directory(checked: dict) -> Path:
    study = checked.get("study_sha256")
    if not isinstance(study, str) or HASH.fullmatch(study) is None or type(checked.get("fixture")) is not bool:
        raise ContractError("invalid attachment study/mode")
    mode = "mock" if checked["fixture"] else "live"
    run = Path(checked["run"])
    require(run == BASE / "native" / study / mode, "attachment requires the canonical controller root")
    return safe(run / "supervision", roots=(ROOT, BASE))


def request(checked: dict, inspection: dict) -> dict:
    """Called exactly once after key entry, using the actually validated inspection."""
    directory = _directory(checked)
    bindings = {key: checked.get(key) for key in BINDINGS}
    require(all(isinstance(value, str) and HASH.fullmatch(value) is not None for value in bindings.values()),
            "invalid attachment release bindings")
    owner = inspection.get("container", {}).get("container_id")
    require(isinstance(owner, str) and HASH.fullmatch(owner) is not None
            and inspection.get("inspection_sha256") == digest({k: v for k, v in inspection.items() if k != "inspection_sha256"}),
            "attachment requires the exact sealed inspected owner")
    started = time.monotonic()
    created = _utc()
    value = {"kind": "phase3b-s2-supervision-request-v1", **bindings,
        "fixture": checked["fixture"], "supervisor_agent": agent_name(checked.get("supervisor_agent")),
        "inspection_sha256": inspection["inspection_sha256"], "launch_nonce": secrets.token_hex(16),
        "controller_owner": {"container_id": owner, "pid": os.getpid()}, "created_at_utc": created,
        "expires_at_utc": (_timestamp(created) + dt.timedelta(seconds=SECONDS)).isoformat(),
        "started_monotonic": started, "deadline_monotonic": started + SECONDS, "seconds": SECONDS,
        "renewable": False, "provider_calls": 0, "durable_intents": 0}
    target = directory / "request.json"
    require(not any((directory / name).exists() for name in ("request.json", "ack.json", "receipt.json", "failure.json")),
            "attachment is one-shot; do not restart an existing controller")
    return _publish(target, value)


def _validate_request(value: dict) -> None:
    _sealed(value)
    require(value.get("kind") == "phase3b-s2-supervision-request-v1" and type(value.get("fixture")) is bool
            and value.get("seconds") == SECONDS and value.get("renewable") is False
            and value.get("provider_calls") == value.get("durable_intents") == 0,
            "foreign or renewable attachment request")
    agent_name(value.get("supervisor_agent"))
    require(all(isinstance(value.get(k), str) and HASH.fullmatch(value[k]) is not None for k in (*BINDINGS, "inspection_sha256")),
            "invalid attachment bindings")
    require(isinstance(value.get("launch_nonce"), str) and re.fullmatch(r"[0-9a-f]{32}", value["launch_nonce"]) is not None,
            "invalid attachment nonce")
    owner = value.get("controller_owner")
    require(isinstance(owner, dict) and set(owner) == {"container_id", "pid"}
            and isinstance(owner["container_id"], str) and HASH.fullmatch(owner["container_id"]) is not None
            and type(owner["pid"]) is int and owner["pid"] > 0, "invalid attachment owner")
    require(all(type(value.get(k)) in (int, float) and math.isfinite(value[k]) for k in ("started_monotonic", "deadline_monotonic"))
            and value["deadline_monotonic"] == value["started_monotonic"] + SECONDS
            and _timestamp(value["expires_at_utc"]) == _timestamp(value["created_at_utc"]) + dt.timedelta(seconds=SECONDS),
            "attachment deadline was changed")


def _owner_running(container_id: str) -> dict:
    """Host-only sanitized metadata for the exact already-owned controller."""
    environment = {k: v for k, v in os.environ.items() if k.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATHEXT"}}
    result = subprocess.run(["docker", "inspect", "--format", '{{json .State.Running}}', container_id],
        env=environment, capture_output=True, text=True, timeout=10, check=False)  # nosec B603 B607
    require(result.returncode == 0 and result.stdout.strip() == "true", "exact controller is not running")
    return {"container_id": container_id, "running": True, "observed_at_utc": _utc()}


def publish_ack(target: Path, observation: dict, *, observe_owner: Callable[[str], dict] = _owner_running) -> dict:
    """Trusted host only: consume the immediately preceding actual agent-tool result.

    No status-file option exists. The observation is a direct caller attestation
    of collaboration.list_agents, not cryptographic proof of orchestrator state.
    """
    target = safe(target, roots=(ROOT, BASE))
    require(target.name == "request.json" and target.parent.name == "supervision", "unexpected attachment request path")
    value = read(target)
    _validate_request(value)
    require(not (target.parent / "ack.json").exists(), "attachment ACK has already been published")
    now = _timestamp(_utc())
    require(_timestamp(value["created_at_utc"]) <= now < _timestamp(value["expires_at_utc"]), "stale attachment request")
    require(isinstance(observation, dict) and set(observation) == {"kind", "tool", "request_sha256", "observed_at_utc", "agent"}
            and observation["kind"] == "phase3b-s2-supervisor-observation-v1"
            and observation["tool"] == "collaboration.list_agents" and observation["request_sha256"] == value["sha256"]
            and observation["agent"] == {"agent_name": value["supervisor_agent"], "agent_status": "running"},
            "fresh actual running-agent observation is required")
    observed = _timestamp(observation["observed_at_utc"])
    require(_timestamp(value["created_at_utc"]) <= observed <= now and (now - observed).total_seconds() <= OBSERVATION_SECONDS,
            "supervisor observation is stale or predates the request")
    owner = observe_owner(value["controller_owner"]["container_id"])
    require(owner.get("container_id") == value["controller_owner"]["container_id"] and owner.get("running") is True,
            "attachment controller owner is absent or foreign")
    published = _utc()
    require(_timestamp(published) < _timestamp(value["expires_at_utc"])
            and (_timestamp(published) - observed).total_seconds() <= OBSERVATION_SECONDS, "attachment expired during host inspection")
    require(read(target) == value and not (target.parent / "receipt.json").exists()
            and not (target.parent / "failure.json").exists(), "attachment changed or is already closed")
    return _publish(target.parent / "ack.json", {"kind": "phase3b-s2-supervision-ack-v1",
        "request": value, "request_sha256": value["sha256"], "supervisor_observation": observation,
        "controller_observation": owner, "published_at_utc": published, "trusted_host_attestation": True,
        "point_in_time_presence_only": True, "quality_or_readiness_approval": False, "provider_calls": 0})


def wait_for_attachment(checked: dict, inspection: dict) -> dict:
    """Production clock is never renewed; failures occur before any transport."""
    value = request(checked, inspection)
    directory = _directory(checked)
    try:
        while True:
            require(read(directory / "request.json") == value, "attachment request/deadline changed")
            require(time.monotonic() < value["deadline_monotonic"], "supervision attachment timed out")
            if (directory / "ack.json").exists():
                ack = _sealed(read(directory / "ack.json"))
                require(ack.get("kind") == "phase3b-s2-supervision-ack-v1" and ack.get("request") == value
                        and ack.get("request_sha256") == value["sha256"] and ack.get("trusted_host_attestation") is True
                        and ack.get("point_in_time_presence_only") is True and ack.get("quality_or_readiness_approval") is False
                        and ack.get("provider_calls") == 0, "foreign or invalid attachment ACK")
                observation = ack.get("supervisor_observation", {})
                require(observation.get("agent") == {"agent_name": value["supervisor_agent"], "agent_status": "running"}
                        and observation.get("request_sha256") == value["sha256"]
                        and observation.get("tool") == "collaboration.list_agents"
                        and ack.get("controller_observation", {}).get("container_id") == value["controller_owner"]["container_id"]
                        and ack.get("controller_observation", {}).get("running") is True,
                        "ACK lacks exact running supervisor/controller attestation")
                published, observed = _timestamp(ack["published_at_utc"]), _timestamp(observation["observed_at_utc"])
                require(_timestamp(value["created_at_utc"]) <= observed <= published < _timestamp(value["expires_at_utc"])
                        and (published - observed).total_seconds() <= OBSERVATION_SECONDS,
                        "ACK is stale or late")
                require(not (directory / "receipt.json").exists() and not (directory / "failure.json").exists(),
                        "attachment has already been consumed or closed")
                accepted = time.monotonic()
                accepted_utc = _utc()
                require(accepted < value["deadline_monotonic"] and _timestamp(accepted_utc) < _timestamp(value["expires_at_utc"]),
                        "attachment expired before consumption")
                return _publish(directory / "receipt.json", {"kind": "phase3b-s2-supervision-receipt-v1",
                    "request": value, "request_sha256": value["sha256"], "ack_sha256": ack["sha256"], "accepted_at_utc": accepted_utc,
                    "accepted_monotonic": accepted, "provider_calls": 0, "durable_intents": 0,
                    "scientific_complete": False, "point_in_time_presence_only": True})
            time.sleep(0.25)
    except BaseException:
        _publish(directory / "failure.json", {"kind": "phase3b-s2-supervision-stop-v1",
            "request_sha256": value["sha256"], "stopped_at_utc": _utc(), "provider_calls": 0,
            "durable_intents": 0, "resume_allowed": False, "raw_error_suppressed": True})
        raise


def require_transport_attachment(attachment: dict | None) -> dict:
    """Require this process's already-consumed real attachment before SDK creation."""
    if not isinstance(attachment, dict):
        raise ContractError("real transport requires a consumed supervisor attachment")
    _sealed(attachment)
    value = attachment.get("request")
    if not isinstance(value, dict):
        raise ContractError("attachment has no bound request")
    _validate_request(value)
    require(value["fixture"] is False and value["controller_owner"]["pid"] == os.getpid(),
            "real transport attachment belongs to another mode or controller")
    directory = BASE / "native" / value["study_sha256"] / "live" / "supervision"
    return _require_receipt(directory, attachment)


def _require_receipt(directory: Path, receipt: dict) -> dict:
    _sealed(receipt)
    value = receipt.get("request")
    if not isinstance(value, dict):
        raise ContractError("receipt has no bound attachment request")
    _validate_request(value)
    ack = _sealed(read(directory / "ack.json"))
    observation = ack.get("supervisor_observation", {})
    require(read(directory / "request.json") == value and read(directory / "receipt.json") == receipt
            and not (directory / "failure.json").exists()
            and receipt.get("kind") == "phase3b-s2-supervision-receipt-v1"
            and receipt.get("request_sha256") == value["sha256"] and receipt.get("ack_sha256") == ack["sha256"]
            and ack.get("request") == value and ack.get("request_sha256") == value["sha256"]
            and ack.get("kind") == "phase3b-s2-supervision-ack-v1"
            and ack.get("trusted_host_attestation") is True and ack.get("point_in_time_presence_only") is True
            and ack.get("quality_or_readiness_approval") is False and ack.get("provider_calls") == 0
            and observation.get("agent") == {"agent_name": value["supervisor_agent"], "agent_status": "running"}
            and observation.get("request_sha256") == value["sha256"] and observation.get("tool") == "collaboration.list_agents"
            and ack.get("controller_observation", {}).get("container_id") == value["controller_owner"]["container_id"]
            and ack.get("controller_observation", {}).get("running") is True
            and _timestamp(value["created_at_utc"]) <= _timestamp(observation["observed_at_utc"]) <= _timestamp(ack["published_at_utc"])
            <= _timestamp(receipt["accepted_at_utc"]) < _timestamp(value["expires_at_utc"])
            and (_timestamp(ack["published_at_utc"]) - _timestamp(observation["observed_at_utc"])).total_seconds() <= OBSERVATION_SECONDS
            and receipt.get("provider_calls") == receipt.get("durable_intents") == 0
            and receipt.get("scientific_complete") is False and receipt.get("point_in_time_presence_only") is True
            and type(receipt.get("accepted_monotonic")) in (int, float)
            and value["started_monotonic"] <= receipt["accepted_monotonic"] < value["deadline_monotonic"]
            and _timestamp(value["created_at_utc"]) <= _timestamp(receipt["accepted_at_utc"]) < _timestamp(value["expires_at_utc"]),
            "attachment receipt is absent, closed or belongs to another owner")
    return receipt


def require_attached(study: dict, grant: dict, fixture: bool) -> dict:
    """Pre-admission workflow guard; old availability deadlines are not renewed."""
    require(type(fixture) is bool, "attachment workflow mode is invalid")
    directory = BASE / "native" / study["study_sha256"] / ("mock" if fixture else "live") / "supervision"
    receipt = _require_receipt(directory, read(directory / "receipt.json"))
    value = receipt["request"]
    require(value["fixture"] is fixture and value["controller_owner"]["pid"] == os.getpid()
            and all(value[k] == (grant[k] if k == "grant_sha256" else study[k]) for k in BINDINGS),
            "workflow attachment belongs to another release/grant/controller")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        raw = sys.stdin.buffer.read(65537)
        require(len(raw) <= 65536, "oversized supervisor observation")
        result = publish_ack(args.request, json.loads(raw))
        print(json.dumps({"passed": True, "ack_sha256": result["sha256"], "provider_calls": 0}))
        return 0
    except Exception:
        print(json.dumps({"passed": False, "raw_error_suppressed": True, "provider_calls": 0}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
