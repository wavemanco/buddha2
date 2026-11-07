"""Execute only the eight missing judgments, in a new packet-bound journal."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from buddha2.artifacts import digest, write_once

from . import assessment_reuse as reuse
from . import ledger_core as core
from . import native, supervision, support
from . import transport as bounded
from .support import BASE, NATIVE, ROOT, checked, file_hash, read, require, safe, seal

KIND = "buddha2-assessment-only-execution-v1"
PACKET_SHA = "2611139c34dc5c1c73b540631dabe4fc0b85611728ae9e5cbc661561c0d1e217"
POLICY = {
    "id": "phase3b-eight-saved-judgments-v1", "maximum_attempts": 8,
    "cap_micro_usd": 15_011_727, "remaining_phase_micro_usd": 135_352_892,
    "historical_known_micro_usd": 90_691_473, "historical_reserved_micro_usd": 22_880_000,
    "historical_attempts": 3181, "prior_closed_spent_micro_usd": 11_082_350,
    "control_policy_sha256": core.am1.CONTROL_SHA256,
    "request_policy_sha256": digest(core.POLICY),
    "cost_basis": core.POLICY["cost_basis"], "generation_calls": 0, "retries": 0,
}
AUTHORITY = {
    "kind": "phase3b-eight-judgments-direct-authority-v1", "authorized": True,
    "user_answer": "proceed", "annotation_selected_text":
        "Next is controlled execution/accounting for the eight missing judgments, without regenerating answers.",
    "annotation_source_assistant_message_id": "msg_06164bcbf959a5c0016aedbddd9d8887d0a8c9d203f1792207",
    "approval_timestamp_provided": False, "policy_sha256": digest(POLICY),
    "new_generation_or_repetition_authorized": False,
}


def _packet(path: Path) -> dict:
    packet = checked(read(reuse._ordinary(path)))
    require(packet.get("sha256") == PACKET_SHA, "only the accepted saved-generation packet is reusable")
    rebuilt = reuse._build(reuse._ordinary(Path(packet["parent_study_path"])))
    # Keep the prepared packet immutable; this execution records its own current source.
    rebuilt["source_sha256"] = packet["source_sha256"]
    require(seal(rebuilt) == packet, "saved-generation compatibility changed")
    return packet


def _body(packet_path: Path) -> dict:
    packet_path = reuse._ordinary(packet_path)
    packet = _packet(packet_path)
    source = support.source_identity()
    return {"kind": KIND, "packet_path": packet_path.relative_to(ROOT).as_posix(),
        "assessment_packet_sha256": packet["sha256"], "generation_study_sha256": reuse.PARENT_STUDY,
        "source_sha256": source["sha256"], "runtime_sha256": digest(support.runtime_identity()),
        "policy_sha256": digest(POLICY), "launcher_sha256": file_hash(support.LAUNCHER),
        "authority_sha256": digest(AUTHORITY),
        "pending": [row for row in packet["worklist"] if row["disposition"] == "pending"]}


def prepare(packet_path: Path, output: Path) -> dict:
    support.runtime_guard()
    output = reuse._ordinary(output)
    require(output.parent == BASE / "assessment-execution" and not output.exists(),
            "assessment execution requires a fresh preparation namespace")
    body = _body(packet_path)
    study = {**body, "study_sha256": digest(body)}
    output.mkdir(parents=True, exist_ok=False)
    write_once(output / "study.json", study)
    for fixture in (True, False):
        write_once(output / ("mock-grant.json" if fixture else "grant.json"),
                   seal({"kind": KIND + "-grant", "study_sha256": study["study_sha256"],
                         "fixture": fixture, "authority": AUTHORITY}))
    return {"study_sha256": study["study_sha256"], "study_path": str(output / "study.json"),
            "pending_requests": 8, "provider_calls": 0, "acceptance_required": True}


def _load(study_path: Path, grant_path: Path) -> tuple[dict, dict]:
    support.runtime_guard()
    study = read(reuse._ordinary(study_path))
    body = _body(ROOT / study["packet_path"])
    require(study == {**body, "study_sha256": digest(body)}, "execution source or saved requests changed")
    grant = checked(read(reuse._ordinary(grant_path)))
    require(type(grant.get("fixture")) is bool and grant == seal({"kind": KIND + "-grant",
        "study_sha256": study["study_sha256"], "fixture": grant["fixture"], "authority": AUTHORITY}),
        "eight-judgment authority or mode differs")
    return study, grant


def _paths(study: dict, fixture: bool) -> tuple[Path, Path]:
    mode = "mock" if fixture else "live"
    identity = study["study_sha256"]
    return safe(NATIVE / identity / mode), safe(BASE / identity / mode / "journal")


def _bindings(study: dict) -> dict:
    return {key: study[key] for key in ("source_sha256", "policy_sha256", "launcher_sha256")}


def _manifest(study: dict, grant: dict) -> dict:
    # Native result.study_sha256 identifies generation; run_id identifies this new execution.
    inputs = {"study_sha256": reuse.PARENT_STUDY, "generation_study_sha256": reuse.PARENT_STUDY,
        "assessment_execution_sha256": study["study_sha256"], "assessment_packet_sha256": PACKET_SHA,
        "fixture": grant["fixture"], "bindings": _bindings(study), "grant_sha256": grant["sha256"],
        "policy": POLICY, "slots": {row["slot_id"]: {"role": "quality", "cell": "assessment",
            "pair": "p3b-01"} for row in study["pending"]}}
    return {"kind": KIND + "-journal", "inputs": inputs, "run_id": digest(inputs)}


def preflight(study_path: Path, grant_path: Path, stage: str, mode: str,
              *, supervisor_agent: str | None = None) -> dict:
    require(stage == "all" and mode in {"preflight", "provider-config", "mock", "provider"},
            "assessment-only execution has one eight-request stage")
    study, grant = _load(study_path, grant_path)
    fixture = grant["fixture"]
    require(mode not in {"mock", "provider"} or fixture is (mode == "mock"), "execution mode differs")
    if mode in {"mock", "provider"}:
        supervisor_agent = supervision.agent_name(supervisor_agent)
    acceptance = None
    if mode == "provider":
        acceptance = support.offline_readiness(study_path,
            {key: study[key] for key in support.READINESS_BINDINGS})
    run, journal = _paths(study, fixture)
    manifest = _manifest(study, grant)
    if (journal / "manifest.json").exists():
        state, _, _ = _replay(study, grant)
        require(state["status"] == "ready" and state["reserved_micro_usd"] == 0,
                "assessment journal is closed, blocked or has unresolved liability")
    return {"kind": "phase3b-s2-launch-preflight-v1", "assessment_only": True,
        **{key: study[key] for key in ("study_sha256", "source_sha256", "runtime_sha256",
                                      "policy_sha256", "launcher_sha256")},
        "grant_sha256": grant["sha256"], "fixture": fixture, "mode": mode, "stage": stage,
        "study_path": str(study_path), "grant_path": str(grant_path), "run": str(run),
        "journal": str(journal), "journal_id": manifest["run_id"], "provider_calls": 0,
        "credentials_read": False, "credential_access": False, "provider_requests": 0,
        "configuration_only": mode == "provider-config", "supervisor_agent": supervisor_agent,
        "cap_micro_usd": POLICY["cap_micro_usd"], "first_pair_cap_micro_usd": POLICY["cap_micro_usd"],
        "readiness_included_micro_usd": 0,
        "maximum_admitted_attempts": 8, "slot_count": 8, "offline_readiness": acceptance,
        "billing_profile": core.am1.BILLING_PROFILE, "control_policy_sha256": core.am1.CONTROL_SHA256}


def claim(prepared: dict) -> None:
    require(prepared.get("assessment_only") is True and prepared["mode"] == "provider",
            "only inspected provider execution can claim these eight judgments")
    write_once(safe(BASE / ("assessment-only-claim-" + PACKET_SHA + ".json")),
               {key: prepared[key] for key in ("study_sha256", "source_sha256", "grant_sha256", "journal_id")})


def _audit_path(run: Path, slot: str) -> Path:
    return safe(run / "transport-audit" / (digest({"slot_id": slot}) + ".json"))


def _replay(study: dict, grant: dict) -> tuple[dict, list, dict]:
    run, journal = _paths(study, grant["fixture"])
    manifest = _manifest(study, grant)
    require(read(journal / "manifest.json") == manifest, "another execution owns this assessment journal")
    events, tail = core._read_events(journal)
    state: dict[str, Any] = {"status": "ready", "attempts": 0, "spent_micro_usd": 0, "reserved_micro_usd": 0,
             "results": {}, "intents": {}}
    pending = {row["slot_id"]: row for row in study["pending"]}
    active = None
    for event in events:
        row = event["record"]
        require(state["status"] == "ready", "events follow a terminal assessment disposition")
        if event["kind"] == "intent":
            slot = row["slot_id"]
            require(active is None and slot in pending and slot not in state["intents"]
                and row == core._intent(manifest, slot, pending[slot]["request"], state["attempts"] + 1),
                "foreign, repeated or changed assessment intent")
            require(state["spent_micro_usd"] + row["reservation"]["micro_usd"] <= POLICY["cap_micro_usd"],
                    "assessment reservation exceeds the remaining included first-prompt cap")
            state["intents"][slot] = active = row
            state["attempts"] += 1
            state["reserved_micro_usd"] = row["reservation"]["micro_usd"]
        elif event["kind"] == "result":
            if active is None:
                raise core.ContractError("assessment result has no preceding intent")
            require(row == core._result(active, row["response"], failure=row["failure"]),
                    "assessment result accounting changed")
            state["results"][row["slot_id"]] = row
            state["spent_micro_usd"] += row["spent_micro_usd"] or 0
            state["reserved_micro_usd"] = row["reserved_micro_usd"]
            try:
                audit = bounded.validate_audit(read(_audit_path(run, row["slot_id"])), intent=active,
                                              result=row, bindings=_bindings(study))
            except (OSError, ValueError):
                state["status"] = "blocked"
                active = None
                continue
            active = None
            if row["status"] != "response" or audit["late_known"] or audit["cleanup_failed"] or audit["owner_stop_required"]:
                state["status"] = "blocked"
        else:
            require(event["kind"] == "halt" and active is None, "unknown assessment journal event")
            state["status"] = "halted"
    if active is not None or tail:
        state["status"] = "blocked"
    return state, events, manifest


def _saved(study: dict) -> tuple[dict, dict, native.Phase3NativeAssessment]:
    parent = ROOT / "runs/phase3b-seq2-v1"
    events, _ = core._read_events(parent / reuse.PARENT_STUDY / "live/journal")
    results = {e["record"]["slot_id"]: e["record"] for e in events if e["kind"] == "result"}
    root = parent / "native" / reuse.PARENT_STUDY / "live"
    branches = {arm: checked(read(root / f"branches/p3b-01-{arm}.json"))["result"]
                for arm in ("fixed", "adaptive")}
    portfolios = {"fixed": branches["fixed"]["portfolio"], **branches["adaptive"]["checkpoints"]}
    return results, portfolios, native.Phase3NativeAssessment(ROOT / ".upstream/novelty-bench")


def _quality(evaluator, portfolio: dict, result: dict, request: dict) -> None:
    # Fixture responses check the native syntax only; they never enter live native assessments.
    response = result["response"] if result["fixture"] else evaluator._response(
        result, result["slot_id"], "quality", request, portfolio)
    message = SimpleNamespace(stop_reason=response.get("stop_reason"),
                              content=[SimpleNamespace(type="text", text=response["text"])])
    schema = evaluator.modules["score"].Score
    evaluator.modules["judge"].parse_message(message, schema)
    require(1 <= evaluator._strict_object(response["text"], schema).score <= 10, "quality score out of range")


def report(study_path: Path, grant_path: Path) -> dict:
    study, grant = _load(study_path, grant_path)
    state, _, _ = _replay(study, grant)
    packet = _packet(ROOT / study["packet_path"])
    assessments = {}
    if not grant["fixture"] and state["status"] == "ready" and len(state["results"]) == 8:
        saved, portfolios, evaluator = _saved(study)
        require(not set(saved).intersection(state["results"]), "new judgments replace saved results")
        combined = saved | state["results"]
        for target in packet["targets"]:
            prefix = evaluator.slot_prefix(target["assessment_id"])
            quality = [combined[row["slot_id"]] for row in packet["worklist"]
                       if row["target"] == target["target"] and row["role"] == "quality"]
            assessments[target["target"]] = evaluator.finalize(portfolios[target["target"]],
                combined[prefix + ".group"], quality, assessment_id=target["assessment_id"])
        require(all(digest(assessments[key]) == value
                    for key, value in packet["complete_cached_assessments"].items()),
                "supplement changed a complete cached assessment")
    return seal({"kind": KIND + "-outcome", "assessment_execution_sha256": study["study_sha256"],
        "generation_study_sha256": reuse.PARENT_STUDY, "assessment_packet_sha256": PACKET_SHA,
        "fixture": grant["fixture"], "source_sha256": study["source_sha256"],
        "status": "mock-completed" if grant["fixture"] and state["status"] == "ready" and len(state["results"]) == 8
                  else "assessed" if len(assessments) == 3 and all(a["status"] == "scored" for a in assessments.values())
                  else "incomplete", "journal_status": state["status"], "new_attempts": state["attempts"],
        "spent_micro_usd": state["spent_micro_usd"], "reserved_micro_usd": state["reserved_micro_usd"],
        "provider_calls": 0 if grant["fixture"] else state["attempts"], "reused_judgments": 25,
        "assessments": assessments, "selected_checkpoint": "c1", "closed_parent_changed": False,
        "four_prompt_comparison_complete": False, "generation_calls": 0})


def run(study_path: Path, grant_path: Path, stage: str, transport) -> dict:
    study, grant = _load(study_path, grant_path)
    require(stage == "all" and isinstance(transport, bounded.Transport) and transport.fixture is grant["fixture"],
            "assessment-only execution requires its existing bounded transport")
    run_root, journal = _paths(study, grant["fixture"])
    manifest = _manifest(study, grant)
    if not grant["fixture"]:
        support.offline_readiness(study_path, {key: study[key] for key in support.READINESS_BINDINGS})
        attachment = transport.startup_attachment or {}
        require(all(attachment.get("request", {}).get(key) == value for key, value in {
            **{key: study[key] for key in support.READINESS_BINDINGS}, "grant_sha256": grant["sha256"]}.items()),
            "transport belongs to another assessment execution or grant")
        require(read(safe(BASE / ("assessment-only-claim-" + PACKET_SHA + ".json"))) == {
            "study_sha256": study["study_sha256"], "source_sha256": study["source_sha256"],
            "grant_sha256": grant["sha256"], "journal_id": manifest["run_id"]},
            "the eight-judgment allowance is not claimed by this execution")
    _, portfolios, evaluator = _saved(study)
    with core.writer_lock(run_root / "assessment-owner"), core.writer_lock(journal):
        core._publish(journal / "manifest.json", manifest)
        for row in study["pending"]:
            state, events, _ = _replay(study, grant)
            if state["status"] != "ready":
                break
            slot, request = row["slot_id"], row["request"]
            if slot in state["results"]:
                try:
                    _quality(evaluator, portfolios["c2"], state["results"][slot], request)
                except (ValueError, TypeError, KeyError, evaluator.modules["judge"].JudgeRefusal):
                    core._append_event(journal, "halt", {"reason": "invalid_or_refused_quality"}, events)
                    break
                continue
            # Recheck current source and parent before every new financial admission.
            _load(study_path, grant_path)
            core.validate_request("quality", request)
            if state["spent_micro_usd"] + core._reservation("quality")["micro_usd"] > POLICY["cap_micro_usd"]:
                core._append_event(journal, "halt", {"reason": "remaining_first_prompt_cap"}, events)
                break
            meta = manifest["inputs"]["slots"][slot]
            allocation = transport.prepare(slot, "quality", meta, _bindings(study))
            intent = core._intent(manifest, slot, request, state["attempts"] + 1)
            core._append_event(journal, "intent", intent, events)
            returned = response = None
            stage_name = "transport_select"
            try:
                transport.bind_intent(intent, allocation)
                transport.select("quality", slot)
                stage_name = "provider_call"
                returned = transport.create("quality", copy.deepcopy(request))
                stage_name = "response_copy"
                response = json.loads(core._wire(returned))
                stage_name = "accounting"
                result = core._result(intent, response)
                stage_name = "serialization"
                core._wire(result)
                require(len(core._result_event_bytes(result, events)) <= 2_000_000,
                        "assessment result exceeds the preserved artifact profile")
            except core.TransportFailure as error:
                result = core._bounded_failure_result(intent, error.response, error.failure, events)
            except Exception as error:
                candidate = response if response is not None else returned
                request_id = core.provider_request_id(candidate.get("request_id")) if isinstance(candidate, dict) else None
                result = core._bounded_failure_result(intent, core.retain_response(candidate),
                    core.failure_from_exception(error, stage_name, request_id=request_id), events)
            core._append_event(journal, "result", result, events)
            audit = transport.commit(slot, result)
            bounded.validate_audit(audit, intent=intent, result=result, bindings=_bindings(study))
            core._publish(_audit_path(run_root, slot), audit)
            state, events, _ = _replay(study, grant)
            if state["status"] != "ready":
                break
            try:
                _quality(evaluator, portfolios["c2"], result, request)
            except (ValueError, TypeError, KeyError, evaluator.modules["judge"].JudgeRefusal):
                core._append_event(journal, "halt", {"reason": "invalid_or_refused_quality"}, events)
                break
        outcome = report(study_path, grant_path)
        core._publish(run_root / "outcome.json", outcome)
        return {key: outcome[key] for key in ("status", "new_attempts", "spent_micro_usd",
                "reserved_micro_usd", "provider_calls", "generation_calls", "sha256")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_command = commands.add_parser("prepare")
    prepare_command.add_argument("--packet", type=Path, required=True)
    prepare_command.add_argument("--output", type=Path, required=True)
    replay_command = commands.add_parser("report")
    replay_command.add_argument("--study", type=Path, required=True)
    replay_command.add_argument("--grant", type=Path, required=True)
    args = parser.parse_args(argv)
    result = prepare(args.packet, args.output) if args.command == "prepare" else report(args.study, args.grant)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0
