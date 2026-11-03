"""Whole-study offline proof and inspected no-call launch replay, before live keys."""
from __future__ import annotations

import argparse
import json
import os
import shutil

# Fixed executable/argv orchestration, with no shell or credential arguments.
import subprocess  # nosec B404
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
IMAGE = "sha256:8792a096b4881d47ab19cc7cbf6a74a232f9ff7cedc978fe93f902a71522d4f2"
MODULE = "followups.phase3a_c1_completion_v3.verify"
PWSH = Path(r"C:\Users\arvik\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe")
BINDINGS = ("study_sha256", "source_sha256", "runtime_sha256", "policy_sha256", "launcher_sha256")


def _host_output(value: str) -> Path:
    output = Path(value)
    if not output.is_absolute():
        output = ROOT / output
    boundary = ROOT / "runs/phase3a-c1-completion-v3"
    if (".." in output.parts or not output.is_relative_to(boundary) or output == boundary
            or any(part.casefold() in {"credential-binding.json", ".writer.lock", ".env", "auth.json", "credentials.json"} for part in output.parts)
            or any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()) for p in (output, *output.parents))
            or output.exists()):
        raise ValueError("verification needs a fresh ordinary completion output")
    return output


def host(value: str) -> int:
    output = _host_output(value)
    docker = shutil.which("docker")
    if docker is None or not PWSH.is_file():
        raise ValueError("existing Docker and the inspected PowerShell runtime are required")
    image = subprocess.check_output([docker, "image", "inspect", "--format", "{{.Id}}", IMAGE], cwd=ROOT)  # nosec B603
    if image.decode().strip() != IMAGE:
        raise ValueError("pinned image missing; verification never downloads/rebuilds")
    output.mkdir(parents=True, exist_ok=False)
    container_output = "/results/" + output.relative_to(ROOT / "runs").as_posix()
    # Private bounded container temporary memory, never host credential storage.
    temporary_mount = "/tmp:rw,nosuid,nodev,size=1073741824,mode=1777"  # nosec B108
    args = [docker, "run", "--rm", "--pull=never", "--network", "none", "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--pids-limit", "256", "--memory", "4g", "--cpus", "2",
        "--entrypoint", "python", "--mount", f"type=bind,source={ROOT},target=/workspace,readonly",
        "--mount", f"type=bind,source={ROOT / 'runs'},target=/results", "--tmpfs", temporary_mount,
        "-w", "/workspace", "-e", "BUDDHA2_OUTPUT_ROOT=/results", "-e", "BUDDHA2_IMAGE_ID=" + IMAGE,
        "-e", "PHASE3A_OPENCODE=/opt/phase3a-opencode", "-e", "PHASE3A_BUN=/usr/local/bin/bun",
        "-e", "PYTHONPATH=/workspace/src:/workspace/.upstream/harness2:/workspace", "-e", "PYTHONDONTWRITEBYTECODE=1",
        IMAGE, "-B", "-m", MODULE, "--inside", "--output", container_output]
    (output / "docker-command.json").write_text(json.dumps(args, indent=2) + "\n", encoding="utf-8")
    with (output / "container.log").open("x", encoding="utf-8") as log:
        completed = subprocess.run(args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)  # nosec B603
    if completed.returncode:
        print(json.dumps({"status": "offline-incomplete", "exit_code": completed.returncode, "output": str(output)}))
        return completed.returncode
    matrix = json.loads((output / "matrix.json").read_text())
    study = matrix["study_path"].removeprefix("/results/")
    mock_grant = matrix["mock_grant_path"].removeprefix("/results/")
    live_grant = matrix["live_grant_path"].removeprefix("/results/")
    launcher_records = []
    launcher_root = ROOT / "runs/phase3a-c1-completion-v3/launcher"
    for action, grant in (("mock", mock_grant), ("config", live_grant)):
        before_names = {p.name for p in launcher_root.glob("*.inspection.json")}
        command = [str(PWSH), "-NoProfile", "-File", str(ROOT / "phase3a-c1-completion-r2.ps1"),
            "-Action", action, "-Study", study, "-Grant", grant, "-Stage", "all"]
        with (output / f"launcher-{action}.log").open("x", encoding="utf-8") as log:
            result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)  # nosec B603
        if result.returncode:
            print(json.dumps({"status": "offline-incomplete", "stage": "launcher-" + action, "output": str(output)}))
            return result.returncode
        fresh = [p for p in launcher_root.glob("*.inspection.json") if p.name not in before_names]
        if len(fresh) != 1:
            raise ValueError("launcher did not retain exactly one fresh inspected execution")
        inspection = fresh[0]
        runtime_path = inspection.with_name(inspection.name.replace(".inspection.json", ".result.json"))
        launcher_records.append({"action": action, "exit_code": result.returncode,
            "inspection_path": "/results/" + inspection.relative_to(ROOT / "runs").as_posix(),
            "runtime_path": "/results/" + runtime_path.relative_to(ROOT / "runs").as_posix() if runtime_path.exists() else None,
            "command": command})
    (output / "launcher-host.json").write_text(json.dumps(launcher_records, indent=2) + "\n", encoding="utf-8")
    # Seal the final gate only after the actual no-key host launcher checks.
    final = list(args)
    final[-4:] = [MODULE, "--seal", "--output", container_output]
    with (output / "gate-seal.log").open("x", encoding="utf-8") as log:
        result = subprocess.run(final, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)  # nosec B603
    print(json.dumps({"status": "offline-passed" if result.returncode == 0 else "offline-incomplete", "output": str(output)}))
    return result.returncode


def _record(output: Path, name: str, study: dict, body: dict) -> dict:
    from buddha2.artifacts import write_once
    record = {"kind": "phase3a-c1-completion-offline-check-v1", "group": name,
        **body, **{key: study[key] for key in BINDINGS}}
    write_once(output / (name + ".json"), record)
    return record


def inside(output: Path) -> int:
    from buddha2.artifacts import file_hash, write_once
    from followups.phase3a_compat_c1_v1.cli import _offline_runtime

    from . import accounting, workflow
    from .mocks import StudyMock
    from .report import write_report
    from .support import path, preserve, source_identity
    _offline_runtime()
    output = path(output)
    source = source_identity()
    before = preserve()
    write_once(output / "source-before.json", source)
    write_once(output / "preservation-before.json", before)
    study = workflow.prepare(output / "release")
    study_path = output / "release/study.json"
    for fixture in (True, False):
        write_once(output / "release" / ("mock-grant.json" if fixture else "live-grant.json"), workflow.make_grant(study_path, fixture))
    grant = output / "release/mock-grant.json"
    commands = [[sys.executable, "-B", "-m", "ruff", "check", "--no-cache", "followups/phase3a_c1_completion_v3"],
        [sys.executable, "-B", "-m", "mypy", "--explicit-package-bases", "--follow-imports", "silent",
            "--no-incremental", "--cache-dir", str(Path(tempfile.gettempdir()) / "c1-completion-mypy"), "followups/phase3a_c1_completion_v3"],
        [sys.executable, "-B", "-m", "bandit", "-q", "-r", "followups/phase3a_c1_completion_v3", "-x", "followups/phase3a_c1_completion_v3/tests"]]
    static = []
    for number, command in enumerate(commands):
        with (output / f"static-{number}.log").open("x", encoding="utf-8") as log:
            result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)  # nosec B603
        static.append({"command": command, "exit_code": result.returncode})
    _record(output, "static", study, {"passed": all(row["exit_code"] == 0 for row in static), "commands": static})
    if any(row["exit_code"] for row in static):
        return 1
    # One complete actual SDK/OpenCode matrix, then identical settled replay.
    with StudyMock() as mock:
        summary = workflow.run(study_path, grant, stage="all", transport=mock.transport)
        run, journal = workflow.paths(study, True)
        state = accounting.replay(journal)
        matrix = _record(output, "matrix", study, {"passed": summary["status"] == "mock-complete"
            and summary["primary_scored"] == 8 and len(mock.proofs()) == 4 and state["reserved_micro_usd"] == 0,
            "summary": summary, "mock_http_calls": mock.http_calls, "real_provider_calls": 0,
            "study_path": str(study_path), "mock_grant_path": str(grant),
            "live_grant_path": str(output / "release/live-grant.json")})
        write_once(output / "mock-proof.json", mock.proofs())
        write_once(output / "mock-wire.json", mock.records)
        if not matrix["passed"]:
            return 1
        calls, journal_bytes = mock.http_calls, (journal / "events.jsonl").read_bytes()
        replay = workflow.run(study_path, grant, stage="all", transport=mock.transport)
        with ExitStack() as guards:
            for target in ("anthropic.Anthropic", "anthropic.AsyncAnthropic", "openai.OpenAI", "openai.AsyncOpenAI",
                           "socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex"):
                guards.enter_context(patch(target, side_effect=AssertionError("saved reporting attempted external activity")))
            data = workflow.snapshot(study_path, grant, True)
            write_report(data, run / "reports/replay")
        files = sorted((run / "reports/final").iterdir())
        _record(output, "replay", study, {"passed": calls == mock.http_calls and replay == summary
            and journal_bytes == (journal / "events.jsonl").read_bytes()
            and all(file_hash(p) == file_hash(run / "reports/replay" / p.name) for p in files),
            "new_mock_calls": mock.http_calls - calls, "report_files": [p.name for p in files], "SDK_and_sockets_blocked_for_report": True})
    os.environ["BUDDHA2_R2_EVIDENCE_FIXTURE"] = str(run)
    modules = ["followups.phase3a_c1_completion_v3.tests." + p.stem for p in
               sorted((ROOT / "followups/phase3a_c1_completion_v3/tests").glob("test_*.py"))]
    modules += ["followups.phase3a_v1.tests.test_" + name for name in ("strategy", "accounting", "editor_terminal", "editor_shape", "transport")]
    with (output / "tests.log").open("x", encoding="utf-8") as log:
        tested = unittest.TextTestRunner(stream=log, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(modules))
    _record(output, "tests", study, {"passed": tested.wasSuccessful(), "tests": tested.testsRun,
        "errors": len(tested.errors), "failures": len(tested.failures), "skipped": len(tested.skipped), "modules": modules})
    after = preserve()
    after_source = source_identity()
    write_once(output / "source-after.json", after_source)
    write_once(output / "preservation-after.json", after)
    _record(output, "preservation", study, {"passed": source == after_source and before == after,
        "closed_bytes_identical": before == after, "source_unchanged": source == after_source})
    return 0 if tested.wasSuccessful() and source == after_source and before == after else 1


def seal_gate(output: Path) -> int:
    from buddha2.artifacts import file_hash, write_once

    from .launch import validate_inspection
    from .support import path, read, require, seal
    from .workflow import load_study
    output = path(output)
    study = load_study(output / "release/study.json")
    logs = [output / "launcher-mock.log", output / "launcher-config.log"]
    require(all(p.is_file() and p.stat().st_size for p in logs), "actual host launcher logs missing")
    host = json.loads((output / "launcher-host.json").read_text(encoding="utf-8"))
    require(len(host) == 2 and {row["action"] for row in host} == {"mock", "config"}, "host launcher coverage differs")
    inspected = {}
    for row in host:
        target = path(Path(row["inspection_path"]))
        actual = read(target)
        checked = actual["preflight"]
        require(row["exit_code"] == 0 and checked["study_sha256"] == study["study_sha256"]
            and checked["source_sha256"] == study["source_sha256"]
            and checked["stage"] == "all" and checked["mode"] == ("mock" if row["action"] == "mock" else "provider-config"),
            "actual launcher ran another source/scope")
        validate_inspection(actual, checked, target)
        inspected[str(target)] = file_hash(target)
        if row["action"] == "mock":
            runtime = read(path(Path(row["runtime_path"])))
            require(runtime["exit_code"] == 0 and runtime["actual_credentials_supplied"] is False,
                    "mock host execution did not settle safely")
            inspected[row["runtime_path"]] = file_hash(Path(row["runtime_path"]))
            stdout_path = target.with_name(target.name.replace(".inspection.json", ".stdout.log"))
            messages = [json.loads(line) for line in stdout_path.read_text(encoding="utf-8").splitlines() if line.startswith("{")]
            require(bool(messages) and messages[-1].get("new_mock_http_calls") == 0
                    and messages[-1].get("complete_primary") is True,
                    "actual host mock launch did not reuse the completed matrix without calls")
            inspected[str(stdout_path)] = file_hash(stdout_path)
        else:
            require(row["runtime_path"] is None, "configuration-only container was unexpectedly executed")
    _record(output, "launcher", study, {"passed": True, "mock_replay": "actual inspected network-none container; no new calls",
        "provider_configuration": "actual bridge container created/inspected, never started or keyed",
        "host_logs": {str(p): file_hash(p) for p in logs}, "inspected_metadata": inspected})
    refs = {}
    for group in ("tests", "static", "matrix", "replay", "launcher", "preservation"):
        record = read(output / (group + ".json"))
        require(record["passed"] is True and all(record[key] == study[key] for key in BINDINGS),
                "offline acceptance group failed")
        refs[group] = {"path": str(output / (group + ".json")), "sha256": file_hash(output / (group + ".json"))}
    write_once(output / "release/offline-gate.json", seal({"kind": "phase3a-c1-completion-offline-gate-v1",
        "passed": True, **{key: study[key] for key in BINDINGS},
        "checks": refs, "provider_calls": 0, "real_credentials_used": False}))
    print(json.dumps({"passed": True, "study_sha256": study["study_sha256"], "gate": str(output / "release/offline-gate.json")}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--inside", action="store_true")
    parser.add_argument("--seal", action="store_true")
    args = parser.parse_args()
    if args.inside:
        return inside(Path(args.output))
    if args.seal:
        return seal_gate(Path(args.output))
    return host(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
