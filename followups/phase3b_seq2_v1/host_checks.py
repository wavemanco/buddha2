"""Actual keyless Windows launcher and isolated Inspect checks for the HI gate."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from buddha2.artifacts import digest
from followups.inspect_visibility_i1.paths import checked_path

from .snapshot import canonical, utc
from .supervision import agent_name
from .verify import (
    BINDINGS,
    IMAGE,
    OFFLINE_LIFECYCLE_TIMEOUT_SECONDS,
    ROOT,
    container_args,
    execute,
    expected_mounts,
    record,
    save,
)

PREFIX = "phase3b-seq2-v1"
WINDOWS_PS = Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")


def public_path(target: Path) -> Path:
    if any("stdout" in part.casefold() or "stderr" in part.casefold() for part in target.parts):
        raise ValueError("provider stream path rejected before metadata")
    return checked_path(target, ROOT)


def read(target: Path) -> dict:
    target = public_path(target)
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError("duplicate host proof JSON key")
            result[key] = item
        return result
    def constant(_):
        raise ValueError("nonfinite host proof JSON")
    value = json.loads(target.read_bytes(), object_pairs_hook=pairs, parse_constant=constant)
    if not isinstance(value, dict):
        raise ValueError("host proof must be an object")
    return value


def sha(target: Path) -> str:
    return hashlib.sha256(public_path(target).read_bytes()).hexdigest()


def sealed(target: Path) -> dict:
    value = read(target)
    if value.get("sha256") != digest({k: v for k, v in value.items() if k != "sha256"}):
        raise ValueError("host proof seal is invalid")
    return value


def inspections(directory: Path) -> set[str]:
    """Names only until the exact public inspection suffix is selected."""
    directory = checked_path(directory, ROOT, missing=True)
    if not directory.exists():
        return set()
    return {name for name in os.listdir(directory) if name.endswith(".inspection.json")}


def from_container(raw: str, *, missing: bool = False) -> Path:
    prefix = "/results/" + PREFIX + "/"
    if not isinstance(raw, str) or not raw.startswith(prefix):
        raise ValueError("matrix path escaped the fresh HI namespace")
    return checked_path(ROOT / "runs" / raw.removeprefix("/results/"), ROOT / "runs" / PREFIX, missing=missing)


def rehearsal_inputs(output: Path, study: dict, matrix: dict) -> tuple[dict, dict, Path]:
    """Require a fresh mock-only study, never resume the completed main matrix."""
    expected = "/results/" + output.relative_to(ROOT / "runs").as_posix() + "/release/"
    if any(matrix.get(key) != expected + name for key, name in (
            ("study_path", "study.json"), ("mock_grant_path", "mock-grant.json"),
            ("live_grant_path", "live-grant.json"))):
        raise ValueError("launcher inputs differ from this exact matrix release")
    prefix = "/results/" + (output / "operational-rehearsal").relative_to(ROOT / "runs").as_posix()
    prepared = read(output / "operational-rehearsal/prepared.json")
    fresh = read(output / "operational-rehearsal/release/study.json")
    def comparable(value):
        return {k: v for k, v in value.items() if k not in {"study_sha256", "fixture_supervision_rehearsal"}}
    expected_run = "/results/" + PREFIX + "/native/" + fresh["study_sha256"] + "/mock"
    if (study.get("fixture_supervision_rehearsal") is not False or fresh.get("fixture_supervision_rehearsal") is not True
            or any(value.get("study_sha256") != digest({k: v for k, v in value.items() if k != "study_sha256"}) for value in (study, fresh))
            or fresh["study_sha256"] == study["study_sha256"] or comparable(fresh) != comparable(study)
            or any(prepared.get(k) != fresh[k] for k in BINDINGS)
            or prepared.get("fixture") is not True or prepared.get("fixture_supervision_rehearsal") is not True
            or prepared.get("provider_calls") != 0 or prepared.get("provider_grant_permitted") is not False
            or prepared.get("study_path") != prefix + "/release/study.json"
            or prepared.get("mock_grant_path") != prefix + "/release/mock-grant.json"
            or prepared.get("run") != expected_run):
        raise ValueError("supervised rehearsal must be a fresh mock-only copy of the exact scientific profiles")
    run = from_container(expected_run, missing=True)
    journal = ROOT / "runs" / PREFIX / fresh["study_sha256"] / "mock/journal"
    for target in (run, journal):
        if checked_path(target, ROOT / "runs" / PREFIX, missing=True).exists():
            raise ValueError("supervised rehearsal execution roots already exist; do not resume")
    return fresh, prepared, run


def supervisor_handoff(output: Path, study: dict, prepared: dict, run: Path, supervisor_agent: str) -> dict:
    """Public instructions for the actual external agent; never a scripted ACK."""
    references = {"attachment": run / "supervision/receipt.json",
        "readiness": run / "inspection-readiness.json", "first": run / "inspection-first.json",
        **{name: run / "visibility" / name / "result.json" for name in ("first-pair", "closure")}}
    body = {"kind": "phase3b-s2-supervisor-handoff-v1", **{k: study[k] for k in BINDINGS},
        "supervisor_agent": agent_name(supervisor_agent), "fixture": True, "provider_calls": 0,
        "fixture_supervision_rehearsal": True, "parent_chat_ack_required": False,
        "study_path": prepared["study_path"], "mock_grant_path": prepared["mock_grant_path"],
        "request": str(run / "supervision/request.json"),
        "barriers": {name: str(run / ("barrier-" + name + ".json")) for name in ("readiness", "first")},
        "visibility_requests": {name: str(run / "visibility" / name / "request.json") for name in ("first-pair", "closure")},
        "export_outputs": {name: str(ROOT / "runs" / PREFIX / "visibility-exports" / study["study_sha256"] / "mock" / name / "supervised")
                           for name in ("first-pair", "closure")},
        "service_path": str(output / "operational-rehearsal/service.json"),
        "references": {name: target.relative_to(ROOT).as_posix() for name, target in references.items()}}
    value = {**body, "sha256": digest(body)}
    save(output / "operational-rehearsal/handoff.json", value)
    return value


def supervision_checks(output: Path, main: dict, study: dict, run: Path, handoff: dict, expected_mock_calls: int) -> dict:
    """Verify the externally serviced lifecycle without attributing fixture science."""
    service_path = output / "operational-rehearsal/service.json"
    deadline = time.monotonic() + 60
    while not service_path.exists() and time.monotonic() < deadline:
        time.sleep(0.25)
    service = read(service_path)
    expected_refs = {name: {"path": target, "sha256": sha(ROOT / target)} for name, target in handoff["references"].items()}
    if (service.get("kind") != "phase3b-s2-supervisor-service-v1" or service.get("fixture") is not True
            or service.get("provider_calls") != 0 or service.get("parent_chat_ack_required") is not False
            or service.get("supervisor_agent") != handoff["supervisor_agent"] or service.get("handoff_sha256") != handoff["sha256"]
            or any(service.get(k) != study[k] for k in BINDINGS) or service.get("references") != expected_refs):
        raise ValueError("actual supervisor service attestation is missing, foreign or incomplete")
    receipt = sealed(run / "supervision/receipt.json")
    request, ack = sealed(run / "supervision/request.json"), sealed(run / "supervision/ack.json")
    observation = ack.get("supervisor_observation", {})
    if (receipt.get("request") != request or receipt.get("request_sha256") != request.get("sha256")
            or receipt.get("ack_sha256") != ack.get("sha256") or ack.get("request") != request
            or request.get("fixture") is not True or request.get("supervisor_agent") != handoff["supervisor_agent"]
            or any(request.get(k) != study[k] for k in BINDINGS)
            or observation.get("tool") != "collaboration.list_agents" or observation.get("request_sha256") != request.get("sha256")
            or observation.get("agent") != {"agent_name": handoff["supervisor_agent"], "agent_status": "running"}
            or (run / "supervision/failure.json").exists()):
        raise ValueError("actual rehearsal lacks its exact consumed supervisor attachment")
    for name in ("readiness", "first"):
        barrier, inspection = sealed(run / ("barrier-" + name + ".json")), read(run / ("inspection-" + name + ".json"))
        review = sealed(run / ("readiness-review.json" if name == "readiness" else "first-review.json"))
        if (barrier.get("study_sha256") != study["study_sha256"] or barrier.get("fixture") is not True
                or inspection.get("study_sha256") != study["study_sha256"] or inspection.get("fixture") is not True
                or inspection.get("evidence_sha256") != barrier.get("evidence_sha256")
                or inspection.get("supervisor_agent") != handoff["supervisor_agent"]
                or inspection.get("no_quality_continuation_gate") is not True or not inspection.get("notes")
                or review.get("inspection") != inspection):
            raise ValueError("supervised review was skipped, auto-scripted or belongs to another actor")
    exports = []
    for name in ("first-pair", "closure"):
        target = Path(handoff["export_outputs"][name])
        status, ack = sealed(run / "visibility" / name / "status.json"), read(run / "visibility" / name / "result.json")
        result, proof = read(target / "visibility-result.json"), read(target / "export/result.json")
        actual, cleanup = read(target / "actual-container.json"), read(target / "cleanup.json")
        from .inspect_adapter import IMAGE as INSPECT_IMAGE
        if (status.get("visibility_status") != "complete" or status.get("canonical_status") != "complete"
                or status.get("worker_stopped") is not True or status.get("reports_published") is not True
                or status.get("fixture") is not True or any(status.get(k) != study[k] for k in BINDINGS)
                or ack != result or ack.get("study_sha256") != study["study_sha256"]
                or ack.get("checkpoint") != name or ack.get("provider_calls") != 0
                or ack.get("exporter_stopped") is not True or ack.get("cleanup_verified") is not True
                or proof.get("roundtrip_equal") is not True or proof.get("samples") != 12
                or proof.get("source_attachment_bytes_preserved") is not True or any(proof["model_network_attempts"].values())
                or actual.get("image") != INSPECT_IMAGE or actual.get("network_mode") != "none"
                or actual.get("read_only_root") is not True or cleanup.get("exit_code") != 0):
            raise ValueError("supervised timed Inspect handoff was not actually completed")
        exports.append({"checkpoint": name, "output": str(target), "result_sha256": sha(target / "visibility-result.json"),
                        "proof_sha256": sha(target / "export/result.json"), "cleanup_sha256": sha(target / "cleanup.json")})
    summary = read(run / "reports/final/summary.json")
    if (summary.get("study_sha256") != study["study_sha256"] or summary.get("fixture") is not True
            or summary.get("primary_scored") != 8 or summary.get("readiness_passed") is not True
            or type(expected_mock_calls) is not int or not 0 < expected_mock_calls <= 2344
            or summary.get("attempts") != expected_mock_calls or summary.get("scientific_complete") is not False
            or summary.get("authentic_live_path") is not False
            or any(summary.get(k) != 0 for k in ("reserved_micro_usd", "pending_intents", "durable_unknown_results"))):
        raise ValueError("fresh supervised fixture lifecycle is incomplete or claimed as science")
    proof = {"passed": True, "case": "S13", "fixture": True, "provider_calls": 0,
        "rehearsal_bindings": {k: study[k] for k in BINDINGS}, "supervisor_agent": handoff["supervisor_agent"],
        "parent_chat_ack_required": False, "trusted_host_attestation_not_orchestrator_authentication": True,
        "service_sha256": sha(service_path), "handoff_sha256": sha(output / "operational-rehearsal/handoff.json"),
        "fresh_mock_http_calls": summary["attempts"], "scientific_complete": False, "authentic_live_path": False,
        "references": expected_refs, "exports": exports}
    record(output, "supervision", main, proof)
    return proof


def launch_checks(output: Path, study: dict, matrix: dict, *, supervisor_agent: str) -> None:
    directory = ROOT / "runs" / PREFIX / "launcher"
    fresh, prepared, run = rehearsal_inputs(output, study, matrix)
    handoff = supervisor_handoff(output, fresh, prepared, run, supervisor_agent)
    rows = []
    for action, field in (("mock", "mock_grant_path"), ("config", "live_grant_path")):
        release, expected_study = (prepared, fresh) if action == "mock" else (matrix, study)
        before = inspections(directory)
        command = [str(WINDOWS_PS), "-NoProfile", "-File", str(ROOT / "phase3b-seq2.ps1"),
                   "-Action", action, "-Study", release["study_path"].removeprefix("/results/"),
                   "-Grant", release[field].removeprefix("/results/"), "-Stage", "all"]
        if action == "mock":
            command.extend(["-SupervisorAgent", agent_name(supervisor_agent)])
        environment = {name: value for name, value in os.environ.items()
                       if name.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "PATHEXT"}}
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = execute(command, environment=environment,
                         timeout=OFFLINE_LIFECYCLE_TIMEOUT_SECONDS if action == "mock" else 7200)
        save(output / ("launcher-" + action + "-execution.json"), result)
        if result["exit_code"]:
            raise ValueError("actual Windows bootstrap failed: " + action)
        names = inspections(directory) - before
        if len(names) != 1:
            raise ValueError("launcher did not publish one fresh actual inspection")
        inspection_path = checked_path(directory / names.pop(), ROOT)
        inspection = read(inspection_path)
        checked, container = inspection["preflight"], inspection["container"]
        fixture = action == "mock"
        if (any(checked.get(k) != expected_study[k] for k in BINDINGS)
                or checked["mode"] != ("mock" if fixture else "provider-config")
                or checked["fixture"] is not fixture or checked["provider_calls"] != 0
                or container["image"] != IMAGE
                or container["network_mode"] != ("none" if fixture else "bridge")
                or container["state_at_inspection"] != "created"
                or not container["read_only_rootfs"]):
            raise ValueError("actual launcher proof has foreign mode, source or runtime")
        if fixture and (checked.get("supervisor_agent") != supervisor_agent or checked.get("fixture_supervision_rehearsal") is not True):
            raise ValueError("actual mock launcher lacks its dedicated external supervisor")
        row = {"action": action, "inspection": str(inspection_path), "inspection_sha256": sha(inspection_path),
               "provider_calls": 0, "actual_credentials_used": False}
        if fixture:
            # Only this authenticated mock result is read; real-provider streams are never inspected.
            runtime_path = inspection_path.with_name(inspection_path.name.replace(".inspection.json", ".result.json"))
            runtime = read(runtime_path)
            if (runtime["action"] != "mock" or runtime["preflight"] != checked
                    or runtime["exit_code"] != 0 or runtime["state"] != "exited"
                    or runtime["actual_credentials_supplied"] is not False):
                raise ValueError("actual mock launcher did not settle successfully")
            row.update(runtime=str(runtime_path), runtime_sha256=sha(runtime_path))
            supervision_checks(output, study, fresh, run, handoff, matrix["mock_http_calls"])
        rows.append(row)
    record(output, "launcher", study, {"passed": True, "actions": rows,
            "Windows_PowerShell_5_bootstrap": str(WINDOWS_PS), "provider_configuration_started": False})


def replay_semantic_sha(target: Path, proof: dict) -> str:
    """Verify full replay semantics, excluding only the recorded export time."""
    semantic = read(target)
    evaluation = semantic.get("eval")
    if not isinstance(evaluation, dict) or not isinstance(evaluation.get("created"), str):
        raise ValueError("Inspect semantic export time is missing or invalid")
    created = evaluation.pop("created")
    utc(created)
    if created != proof.get("actual_exported_at_utc"):
        raise ValueError("Inspect semantic export time differs from its proof")
    result = hashlib.sha256(canonical(semantic)).hexdigest()
    if result != proof.get("semantic_sha256"):
        raise ValueError("Inspect semantic payload differs from its replay proof")
    return result


def inspect_checks(output: Path, study: dict, matrix: dict) -> None:
    from .inspect_adapter import IMAGE as INSPECT_IMAGE
    from .inspect_adapter import host_export

    run = from_container(matrix["run"])
    expected_run = ROOT / "runs" / PREFIX / "native" / study["study_sha256"] / "mock"
    if run != expected_run:
        raise ValueError("mock visibility source escaped its exact study")
    rows = []
    for checkpoint in ("first-pair", "closure"):
        snapshot = checked_path(run / "visibility" / checkpoint / "snapshot", ROOT)
        before = {name: sha(snapshot / name) for name in ("manifest.json", "payload.json")}
        semantics = []
        for repeat in (1, 2):
            target = ROOT / "runs" / PREFIX / "visibility-exports" / study["study_sha256"] / "mock" / checkpoint / ("replay-" + str(repeat))
            result = host_export(snapshot, target)
            proof = read(target / "export/result.json")
            actual = read(target / "actual-container.json")
            cleanup = read(target / "cleanup.json")
            if (result.get("visibility_status") != "complete" or result.get("provider_calls") != 0
                    or proof.get("roundtrip_equal") is not True or proof.get("samples") != 12
                    or proof.get("source_attachment_bytes_preserved") is not True
                    or any(proof["model_network_attempts"].values())
                    or actual["image"] != INSPECT_IMAGE or actual["network_mode"] != "none"
                    or not actual["read_only_root"] or cleanup["exit_code"] != 0):
                raise ValueError("actual isolated Inspect export failed")
            semantics.append(replay_semantic_sha(target / "export/semantic.json", proof))
            rows.append({"checkpoint": checkpoint, "repeat": repeat, "output": str(target),
                         "result_sha256": sha(target / "visibility-result.json"),
                         "actual_container_sha256": sha(target / "actual-container.json"),
                         "semantic_file_sha256": sha(target / "export/semantic.json"),
                         "actual_exported_at_utc": proof["actual_exported_at_utc"],
                         "semantic_sha256": semantics[-1]})
        if semantics[0] != semantics[1] or before != {name: sha(snapshot / name) for name in before}:
            raise ValueError("passive export changed source or replay semantics")
    record(output, "inspect", study, {"passed": True, "actual_image": INSPECT_IMAGE, "exports": rows,
        "provider_calls": 0, "credentials_used": False, "separate_host_launcher": True,
        "native_snapshot_inputs_unchanged": True, "replay_semantics_equal": True})


def native_fixture_checks(output: Path, study: dict) -> None:
    rows = []
    for mode in ("terminal-readiness", "terminal-later"):
        isolated = checked_path(output / "native-fixtures" / mode, ROOT, missing=True)
        isolated.mkdir(parents=True, exist_ok=False)
        args = container_args(output, mode="inside")
        original_mount = f"type=bind,source={ROOT / 'runs' / PREFIX},target=/results/{PREFIX}"
        args[args.index(original_mount)] = f"type=bind,source={isolated},target=/results/{PREFIX}"
        allowed_mounts = expected_mounts(output) - {(str(ROOT / "runs" / PREFIX), "/results/" + PREFIX, True)}
        allowed_mounts.add((str(isolated), "/results/" + PREFIX, True))
        args[args.index(IMAGE) + 1:] = ["-B", "-m", "followups.phase3b_seq2_v1.native_fixture",
            "--mode", mode, "--output", f"/results/{PREFIX}/fixture"]
        created = execute(args, timeout=60)
        owner = created["stdout"].strip()
        if created["exit_code"] or len(owner) != 64 or any(c not in "0123456789abcdef" for c in owner):
            save(isolated / "create.json", created)
            raise ValueError("native negative fixture has no exact owned container")
        try:
            save(isolated / "create.json", created)
            inspection = execute(["docker", "inspect", owner], timeout=60)
            save(isolated / "actual-container.json", inspection)
            actual = json.loads(inspection["stdout"])[0]
            mounts = {(m["Source"], m["Destination"], m["RW"]) for m in actual["Mounts"]}
            if (actual["Image"] != IMAGE or actual["HostConfig"]["NetworkMode"] != "none"
                    or not actual["HostConfig"]["ReadonlyRootfs"] or mounts != allowed_mounts):
                raise ValueError("actual native fixture isolation differs")
            execution = execute(["docker", "start", "--attach", owner])
            save(isolated / "execution.json", execution)
            proof_path = isolated / "fixture/native-fixture.json"
            proof = read(proof_path)
            if (execution["exit_code"] or proof.get("passed") is not True or proof.get("fixture") is not True
                    or proof.get("provider_calls") != 0 or proof.get("reserved_micro_usd") != 0
                    or proof.get("mode") != mode or any(proof.get(k) != study[k] for k in BINDINGS)):
                raise ValueError("actual native terminal fixture failed")
            rows.append({"mode": mode, "proof": str(proof_path), "proof_sha256": sha(proof_path),
                         "actual_container_sha256": sha(isolated / "actual-container.json")})
        finally:
            terminal = execute(["docker", "inspect", owner], timeout=60)
            save(isolated / "terminal.json", terminal)
            if terminal["exit_code"] or json.loads(terminal["stdout"])[0]["State"]["Running"]:
                save(isolated / "stop.json", execute(["docker", "stop", "--time", "10", owner], timeout=30))
            removed = execute(["docker", "rm", owner], timeout=30)
            save(isolated / "remove.json", removed)
            if removed["exit_code"]:
                raise ValueError("owned native fixture cleanup is unproved")
    record(output, "native-fixtures", study, {"passed": True, "fixtures": rows,
        "provider_calls": 0, "separate_canonical_fixture_mounts": True, "old_host_artifacts_writable": False})


def complete_host_checks(output: Path, *, supervisor_agent: str) -> None:
    from .regression import complete_regression

    study, matrix = read(output / "release/study.json"), read(output / "matrix.json")
    if not matrix.get("passed") or any(matrix.get(k) != study[k] for k in BINDINGS):
        raise ValueError("host coverage requires this exact complete offline matrix")
    launch_checks(output, study, matrix, supervisor_agent=agent_name(supervisor_agent))
    inspect_checks(output, study, matrix)
    native_fixture_checks(output, study)
    if complete_regression(output).get("passed") is not True:
        raise ValueError("affected frozen helper regression failed")
