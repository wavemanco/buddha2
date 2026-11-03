"""Actual keyless Windows launcher and isolated Inspect checks for the HI gate."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from followups.inspect_visibility_i1.paths import checked_path

from .verify import BINDINGS, IMAGE, ROOT, container_args, execute, record, save

PREFIX = "phase3a-h1-integrated-v1"
WINDOWS_PS = Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")


def read(target: Path) -> dict:
    target = checked_path(target, ROOT)
    value = json.loads(target.read_bytes())
    if not isinstance(value, dict):
        raise ValueError("host proof must be an object")
    return value


def sha(target: Path) -> str:
    return hashlib.sha256(checked_path(target, ROOT).read_bytes()).hexdigest()


def inspections(directory: Path) -> set[str]:
    """Names only until the exact public inspection suffix is selected."""
    directory = checked_path(directory, ROOT, missing=True)
    if not directory.exists():
        return set()
    return {name for name in os.listdir(directory) if name.endswith(".inspection.json")}


def from_container(raw: str) -> Path:
    prefix = "/results/" + PREFIX + "/"
    if not isinstance(raw, str) or not raw.startswith(prefix):
        raise ValueError("matrix path escaped the fresh HI namespace")
    return checked_path(ROOT / "runs" / raw.removeprefix("/results/"), ROOT / "runs" / PREFIX)


def launch_checks(output: Path, study: dict, matrix: dict) -> None:
    directory = ROOT / "runs" / PREFIX / "launcher"
    expected = "/results/" + output.relative_to(ROOT / "runs").as_posix() + "/release/"
    if any(matrix.get(key) != expected + name for key, name in (
            ("study_path", "study.json"), ("mock_grant_path", "mock-grant.json"),
            ("live_grant_path", "live-grant.json"))):
        raise ValueError("launcher inputs differ from this exact matrix release")
    rows = []
    for action, field in (("mock", "mock_grant_path"), ("config", "live_grant_path")):
        before = inspections(directory)
        command = [str(WINDOWS_PS), "-NoProfile", "-File", str(ROOT / "phase3a-h1-integrated.ps1"),
                   "-Action", action, "-Study", matrix["study_path"].removeprefix("/results/"),
                   "-Grant", matrix[field].removeprefix("/results/"), "-Stage", "all"]
        result = execute(command)
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
        if (any(checked.get(k) != study[k] for k in BINDINGS)
                or checked["mode"] != ("mock" if fixture else "provider-config")
                or checked["fixture"] is not fixture or checked["provider_calls"] != 0
                or container["image"] != IMAGE
                or container["network_mode"] != ("none" if fixture else "bridge")
                or container["state_at_inspection"] != "created"
                or not container["read_only_rootfs"]):
            raise ValueError("actual launcher proof has foreign mode, source or runtime")
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
        rows.append(row)
    record(output, "launcher", study, {"passed": True, "actions": rows,
            "Windows_PowerShell_5_bootstrap": str(WINDOWS_PS), "provider_configuration_started": False})


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
                    or proof.get("roundtrip_equal") is not True or proof.get("samples") != 8
                    or proof.get("source_attachment_bytes_preserved") is not True
                    or any(proof["model_network_attempts"].values())
                    or actual["image"] != INSPECT_IMAGE or actual["network_mode"] != "none"
                    or not actual["read_only_root"] or cleanup["exit_code"] != 0):
                raise ValueError("actual isolated Inspect export failed")
            semantics.append(sha(target / "export/semantic.json"))
            rows.append({"checkpoint": checkpoint, "repeat": repeat, "output": str(target),
                         "result_sha256": sha(target / "visibility-result.json"),
                         "actual_container_sha256": sha(target / "actual-container.json"),
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
        args[args.index(IMAGE) + 1:] = ["-B", "-m", "followups.phase3a_h1_integrated_v1.native_fixture",
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
                    or not actual["HostConfig"]["ReadonlyRootfs"] or mounts != {
                        (str(ROOT), "/workspace", False), (str(isolated), "/results/" + PREFIX, True)}):
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


def complete_host_checks(output: Path) -> None:
    from .regression import complete_regression

    study, matrix = read(output / "release/study.json"), read(output / "matrix.json")
    if not matrix.get("passed") or any(matrix.get(k) != study[k] for k in BINDINGS):
        raise ValueError("host coverage requires this exact complete offline matrix")
    launch_checks(output, study, matrix)
    inspect_checks(output, study, matrix)
    native_fixture_checks(output, study)
    if complete_regression(output).get("passed") is not True:
        raise ValueError("affected frozen helper regression failed")
