"""Fresh R3 whole-study proof and inspected host replay; no live credential route."""
from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess  # nosec B404
import sys
import tempfile
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from followups.phase3a_c1_completion_v3.verify import BINDINGS, IMAGE, PWSH, _record

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "phase3a-c1-completion-v4"
MODULE = "followups.phase3a_c1_completion_v4.verify"
PRIVATE = {"credential-binding.json", ".writer.lock", ".env", "auth.json", "credentials.json"}


def _host_output(value: str, *, existing: bool = False) -> Path:
    output = Path(value)
    if not output.is_absolute():
        output = ROOT / output
    boundary = ROOT / "runs" / PREFIX
    if (".." in output.parts or not output.is_relative_to(boundary) or output == boundary
            or any(part.casefold() in PRIVATE for part in output.parts)
            or any(path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())
                   for path in (output, *output.parents))
            or (not output.is_dir() if existing else output.exists())):
        raise ValueError("verification requires a fresh ordinary R3 output")
    return output


def _container_args(docker: str, output: str, *, seal: bool = False) -> list[str]:
    return [docker, "run", "--rm", "--pull=never", "--network", "none", "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--pids-limit", "256", "--memory", "4g", "--cpus", "2",
        "--entrypoint", "python", "--mount", f"type=bind,source={ROOT},target=/workspace,readonly",
        "--mount", f"type=bind,source={ROOT / 'runs'},target=/results",
        "--tmpfs", "/tmp:rw,nosuid,nodev,size=1073741824,mode=1777",  # nosec B108
        "-w", "/workspace", "-e", "BUDDHA2_OUTPUT_ROOT=/results", "-e", "BUDDHA2_IMAGE_ID=" + IMAGE,
        "-e", "PHASE3A_OPENCODE=/opt/phase3a-opencode", "-e", "PHASE3A_BUN=/usr/local/bin/bun",
        "-e", "PYTHONPATH=/workspace/src:/workspace/.upstream/harness2:/workspace", "-e", "PYTHONDONTWRITEBYTECODE=1",
        IMAGE, "-B", "-m", MODULE, "--seal" if seal else "--inside", "--output", output]


def host(value: str) -> int:
    output = _host_output(value)
    docker = shutil.which("docker")
    if docker is None or not PWSH.is_file():
        raise ValueError("existing Docker and the inspected PowerShell runtime are required")
    image = subprocess.check_output([docker, "image", "inspect", "--format", "{{.Id}}", IMAGE], cwd=ROOT)  # nosec B603
    if image.decode().strip() != IMAGE:
        raise ValueError("pinned image unavailable; verifier never pulls or rebuilds")
    output.mkdir(parents=True, exist_ok=False)
    container_output = "/results/" + output.relative_to(ROOT / "runs").as_posix()
    args = _container_args(docker, container_output)
    (output / "docker-command.json").write_text(json.dumps(args, indent=2) + "\n", encoding="utf-8")
    with (output / "container.log").open("x", encoding="utf-8") as log:
        result = subprocess.run(args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)  # nosec B603
    if result.returncode:
        return result.returncode
    environment = {name: os.environ[name] for name in ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "PATHEXT")
                   if name in os.environ}
    environment.update(PATH=str(PWSH.parent) + os.pathsep + environment.get("PATH", ""),
        PYTHONPATH=os.pathsep.join(str(path) for path in (ROOT, ROOT / "src", ROOT / ".upstream/harness2")),
        BUDDHA2_OUTPUT_ROOT=str(ROOT / "runs"), PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
    windows = subprocess.run([sys.executable, "-B", "-m", MODULE, "--windows", "--output", str(output)],
                             cwd=ROOT, env=environment, check=False)  # nosec B603
    if windows.returncode:
        return windows.returncode
    matrix = json.loads((output / "matrix.json").read_text(encoding="utf-8"))
    expected_paths = {"study_path": container_output + "/release/study.json",
        "mock_grant_path": container_output + "/release/mock-grant.json",
        "live_grant_path": container_output + "/release/live-grant.json"}
    if any(matrix.get(key) != expected for key, expected in expected_paths.items()):
        raise ValueError("matrix launcher inputs escaped this exact verification release")
    study = matrix["study_path"].removeprefix("/results/")
    launcher = ROOT / "runs" / PREFIX / "launcher"
    rows = []
    for action, field in (("mock", "mock_grant_path"), ("config", "live_grant_path")):
        grant = matrix[field].removeprefix("/results/")
        before = {path.name for path in launcher.glob("*.inspection.json")}
        command = [str(PWSH), "-NoProfile", "-File", str(ROOT / "phase3a-c1-completion-r3.ps1"),
            "-Action", action, "-Study", study, "-Grant", grant, "-Stage", "all"]
        with (output / ("launcher-" + action + ".log")).open("x", encoding="utf-8") as log:
            result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)  # nosec B603
        if result.returncode:
            return result.returncode
        fresh = [path for path in launcher.glob("*.inspection.json") if path.name not in before]
        if len(fresh) != 1:
            raise ValueError("launcher did not retain exactly one fresh inspected action")
        inspection = fresh[0]
        runtime = inspection.with_name(inspection.name.replace(".inspection.json", ".result.json"))
        rows.append({"action": action, "exit_code": result.returncode, "command": command,
            "inspection_path": "/results/" + inspection.relative_to(ROOT / "runs").as_posix(),
            "runtime_path": "/results/" + runtime.relative_to(ROOT / "runs").as_posix() if runtime.exists() else None})
    (output / "launcher-host.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    with (output / "gate-seal.log").open("x", encoding="utf-8") as log:
        result = subprocess.run(_container_args(docker, container_output, seal=True), cwd=ROOT,
                                stdout=log, stderr=subprocess.STDOUT, check=False)  # nosec B603
    print(json.dumps({"status": "offline-passed" if result.returncode == 0 else "offline-incomplete", "output": str(output)}))
    return result.returncode


def windows_checks(value: str) -> int:
    """Exercise the exact three host-only cases under the fresh five bindings."""
    import time

    from buddha2.artifacts import digest, write_once
    from followups.phase3a_compat_c1_v1.support import sha

    from .support import read
    from .tests.test_launch import LaunchTests

    output = _host_output(value, existing=True)
    study = read(output / "release/study.json")
    bindings = {key: study[key] for key in BINDINGS}
    if (study["study_sha256"] != digest({key: value for key, value in study.items() if key != "study_sha256"})
            or study["source_sha256"] != digest(study["source"]["files"])):
        raise ValueError("Windows evidence has a foreign study/source seal")
    source_names = ("phase3a-c1-completion-r3.ps1", "followups/phase3a_c1_completion_v4/tests/test_launch.py")
    before = {name: sha(name) for name in source_names}
    if any(before[name] != study["source"]["files"][name] for name in before) or before[source_names[0]] != study["launcher_sha256"]:
        raise ValueError("Windows source differs from the frozen study")
    names = ("test_powershell_inputs_reject_private_and_old_scope_before_path_inspection",
        "test_powershell_private_names_are_skipped_before_inspection",
        "test_powershell_native_guard_preserves_real_reparse_ancestor_and_link_rejection")
    cases = [LaunchTests(name) for name in names]
    suite = unittest.TestSuite(cases)
    identities = [test.id() for test in cases]
    log = io.StringIO()
    started = time.monotonic()
    with redirect_stdout(log), redirect_stderr(log):
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    after = {name: sha(name) for name in source_names}
    text = log.getvalue()
    from buddha2.artifacts import write_bytes_once

    write_bytes_once(output / "windows-tests.log", text.encode("utf-8"))
    passed = (result.wasSuccessful() and result.testsRun == 3 and not result.skipped and before == after
              and read(output / "release/study.json") == study)
    record = {"kind": "phase3a-c1-completion-r3-Windows-checks-v1", **bindings,
        "created_utc": datetime.now(timezone.utc).isoformat(), "passed": passed, "tests": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
        "case_ids": identities, "elapsed_seconds": time.monotonic() - started, "PowerShell_path": str(PWSH),
        "host_runtime": "Windows Python " + sys.version.split()[0], "source_files_before": before,
        "source_files_after": after, "source_files_unchanged": before == after,
        "log_sha256": sha((output / "windows-tests.log").relative_to(ROOT).as_posix()),
        "actual_junction_and_missing_descendant_rejection_verified": "JUNCTION_ANCESTOR_REJECTED" in text,
        "file_symlink_creation_unavailable": "FILE_LINK_UNAVAILABLE" in text,
        "file_symlink_rejection_verified": "FILE_LINK_REJECTED" in text,
        "file_symlink_limit": "Unavailable creation is reported explicitly; it is not an exercised file-link rejection.",
        "provider_calls": 0, "credentials_read": False}
    write_once(output / "windows-tests.json", record)
    print(json.dumps({"Windows_checks_passed": passed, "tests": result.testsRun, "output": str(output)}))
    return 0 if passed else 1


def mock_profiles(proofs: dict) -> bool:
    """Require actual fixture proofs beyond seven rounds, including unchanged DOM."""
    expected = {f"p3a-{index:02}" for index in range(1, 5)}
    if set(proofs) != expected:
        return False
    for sessions in proofs.values():
        if set(sessions) != {"inv1.a1", "dom1.a1", "agg1.a1"}:
            return False
        for label, proof in sessions.items():
            if (not all(proof.get(key) is True for key in ("fixture", "normal_final", "notes_reread_model_visible",
                    "decision_after_complete_evidence", "verification_after_write", "R3_deliberately_inefficient_evidence_reading"))
                    or proof.get("terminal_note_used") is not False
                    or type(proof.get("ordinary_rounds")) is not int or not 7 < proof["ordinary_rounds"] <= 15
                    or proof.get("evidence_read_batches") != 4
                    or proof.get("effective_changed") is not (not label.startswith("dom"))):
                return False
    return True


def _suite() -> tuple[unittest.TestSuite, list[str]]:
    modules = ["followups.phase3a_c1_completion_v4.tests." + path.stem
               for path in sorted((ROOT / "followups/phase3a_c1_completion_v4/tests").glob("test_*.py"))]
    modules += ["followups.phase3a_c1_completion_v3.tests.test_" + name for name in ("deadline", "accounting")]
    modules += ["followups.phase3a_v1.tests.test_strategy"]
    suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    def ids(group):
        for test in group:
            if isinstance(test, unittest.TestSuite):
                yield from ids(test)
            else:
                yield test.id()
    identities = list(ids(suite))
    if len(identities) != len(set(identities)):
        raise ValueError("duplicate scheduled unittest identity")
    return suite, modules


def inside(output: Path) -> int:
    from buddha2.artifacts import file_hash, write_once
    from followups.phase3a_compat_c1_v1.cli import _offline_runtime

    from . import accounting, workflow
    from .mocks import StudyMock
    from .report import write_report
    from .support import path, preserve, source_identity

    _offline_runtime()
    output = path(output)
    source, before = source_identity(), preserve()
    write_once(output / "source-before.json", source)
    write_once(output / "preservation-before.json", before)
    study = workflow.prepare(output / "release")
    study_path = output / "release/study.json"
    for fixture in (True, False):
        write_once(output / "release" / ("mock-grant.json" if fixture else "live-grant.json"), workflow.make_grant(study_path, fixture))
    grant = output / "release/mock-grant.json"
    packager = "evidence/phase3a-c1-completion-v4/package_public.py"
    commands = [[sys.executable, "-B", "-m", "ruff", "check", "--no-cache", "followups/phase3a_c1_completion_v4", packager],
        [sys.executable, "-B", "-m", "mypy", "--explicit-package-bases", "--follow-imports", "silent",
         "--no-incremental", "--cache-dir", str(Path(tempfile.gettempdir()) / "r3-mypy"), "followups/phase3a_c1_completion_v4", packager],
        [sys.executable, "-B", "-m", "bandit", "-q", "-r", "followups/phase3a_c1_completion_v4", packager,
         "-x", "followups/phase3a_c1_completion_v4/tests"]]
    static = []
    for index, command in enumerate(commands):
        with (output / f"static-{index}.log").open("x", encoding="utf-8") as log:
            result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)  # nosec B603
        static.append({"command": command, "exit_code": result.returncode})
    _record(output, "static", study, {"passed": all(row["exit_code"] == 0 for row in static), "commands": static})
    if any(row["exit_code"] for row in static):
        return 1
    with StudyMock() as mock:
        summary = workflow.run(study_path, grant, stage="all", transport=mock.transport)
        run, journal = workflow.paths(study, True)
        state = accounting.replay(journal)
        proofs = mock.proofs()
        passed = (summary["status"] == "mock-complete" and summary["primary_scored"] == 8
            and state["reserved_micro_usd"] == 0 and mock_profiles(proofs)
            and len(study["slots"]) == 967 and state["attempts"] <= 775 and state["attempts"] == mock.http_calls)
        _record(output, "matrix", study, {"passed": passed, "summary": summary, "mock_http_calls": mock.http_calls,
            "real_provider_calls": 0, "potential_slots": 967, "maximum_admitted_attempts": 775,
            "inefficient_normal_completion_and_KEEP_BASE": mock_profiles(proofs), "study_path": str(study_path),
            "mock_grant_path": str(grant), "live_grant_path": str(output / "release/live-grant.json")})
        write_once(output / "mock-proof.json", proofs)
        write_once(output / "mock-wire.json", mock.records)
        if not passed:
            return 1
        calls, journal_bytes = mock.http_calls, (journal / "events.jsonl").read_bytes()
        repeated = workflow.run(study_path, grant, stage="all", transport=mock.transport)
        with ExitStack() as guards:
            for target in ("anthropic.Anthropic", "anthropic.AsyncAnthropic", "openai.OpenAI", "openai.AsyncOpenAI",
                           "socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex"):
                guards.enter_context(patch(target, side_effect=AssertionError("saved reporting attempted external activity")))
            write_report(workflow.snapshot(study_path, grant, True), run / "reports/replay")
        reports = sorted((run / "reports/final").iterdir())
        _record(output, "replay", study, {"passed": calls == mock.http_calls and repeated == summary
            and journal_bytes == (journal / "events.jsonl").read_bytes()
            and len(reports) == 8 and all(file_hash(file) == file_hash(run / "reports/replay" / file.name) for file in reports),
            "new_mock_calls": mock.http_calls - calls, "report_files": [file.name for file in reports],
            "SDK_and_sockets_blocked_for_report": True})
    os.environ["BUDDHA2_R3_EVIDENCE_FIXTURE"] = str(run)
    suite, modules = _suite()
    with (output / "tests.log").open("x", encoding="utf-8") as log:
        tested = unittest.TextTestRunner(stream=log, verbosity=2, failfast=True).run(suite)
    _record(output, "tests", study, {"passed": tested.wasSuccessful(), "tests": tested.testsRun,
        "errors": len(tested.errors), "failures": len(tested.failures), "skipped": len(tested.skipped),
        "skipped_test_ids": [test.id() for test, _ in tested.skipped],
        "modules": modules, "scheduled_test_ids_unique": True, "fail_fast_on_error": True})
    after, after_source = preserve(), source_identity()
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
    windows = read(output / "windows-tests.json")
    tests = read(output / "tests.json")
    require(windows["passed"] is True and windows["tests"] == 3 and windows["skipped"] == 0
            and windows["errors"] == windows["failures"] == 0
            and all(windows[key] == study[key] for key in BINDINGS)
            and set(tests["skipped_test_ids"]) == set(windows["case_ids"])
            and windows["log_sha256"] == file_hash(output / "windows-tests.log"),
            "fresh Windows coverage does not cover the exact contained platform skips")
    logs = [output / ("launcher-" + action + ".log") for action in ("mock", "config")]
    require(all(log.is_file() and log.stat().st_size for log in logs), "actual host logs missing")
    host = json.loads(path(output / "launcher-host.json").read_text(encoding="utf-8"))
    require(isinstance(host, list) and len(host) == 2 and {row["action"] for row in host} == {"mock", "config"},
            "actual host coverage differs")
    inspected = {}
    for row in host:
        target = path(Path(row["inspection_path"]))
        actual = read(target)
        checked = actual["preflight"]
        require(row["exit_code"] == 0 and all(checked[key] == study[key] for key in BINDINGS)
            and checked["stage"] == "all" and checked["mode"] == ("mock" if row["action"] == "mock" else "provider-config"),
            "actual launcher used foreign scope/source")
        validate_inspection(actual, checked, target)
        inspected[str(target)] = file_hash(target)
        if row["action"] == "mock":
            runtime_path = path(Path(row["runtime_path"]))
            runtime = read(runtime_path)
            require(runtime["exit_code"] == 0 and runtime["actual_credentials_supplied"] is False, "mock host did not settle safely")
            inspected[str(runtime_path)] = file_hash(runtime_path)
            stdout = target.with_name(target.name.replace(".inspection.json", ".stdout.log"))
            messages = [json.loads(line) for line in stdout.read_text(encoding="utf-8").splitlines() if line.startswith("{")]
            require(bool(messages) and messages[-1].get("new_mock_http_calls") == 0
                    and messages[-1].get("complete_primary") is True, "host mock did not replay without calls")
            inspected[str(stdout)] = file_hash(stdout)
        else:
            require(row["runtime_path"] is None, "provider configuration was executed")
    _record(output, "launcher", study, {"passed": True, "mock_replay": "actual network-none inspected container; zero new calls",
        "provider_configuration": "bridge container created/inspected, never started or keyed",
        "windows_evidence_sha256": file_hash(output / "windows-tests.json"),
        "distinct_scheduled_checks": tests["tests"], "same_contained_skips_passed_on_Windows": 3,
        "host_logs": {str(log): file_hash(log) for log in logs}, "inspected_metadata": inspected})
    refs = {}
    for name in ("tests", "static", "matrix", "replay", "launcher", "preservation"):
        record = read(output / (name + ".json"))
        require(record["passed"] is True and all(record[key] == study[key] for key in BINDINGS), "failed/foreign acceptance group")
        refs[name] = {"path": str(output / (name + ".json")), "sha256": file_hash(output / (name + ".json"))}
    write_once(output / "release/offline-gate.json", seal({"kind": "phase3a-c1-completion-offline-gate-v1", "passed": True,
        **{key: study[key] for key in BINDINGS}, "checks": refs, "provider_calls": 0, "real_credentials_used": False}))
    print(json.dumps({"passed": True, "study_sha256": study["study_sha256"], "gate": str(output / "release/offline-gate.json")}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--inside", action="store_true")
    mode.add_argument("--seal", action="store_true")
    mode.add_argument("--windows", action="store_true")
    args = parser.parse_args()
    if args.windows:
        return windows_checks(args.output)
    return inside(Path(args.output)) if args.inside else seal_gate(Path(args.output)) if args.seal else host(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
