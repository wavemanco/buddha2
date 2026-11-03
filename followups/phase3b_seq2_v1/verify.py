"""Whole P3B-S2 offline gate; never a credential or provider-call entry point."""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess  # nosec B404
import sys
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from followups.inspect_visibility_i1.paths import checked_path

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "phase3b-seq2-v1"
MODULE = "followups.phase3b_seq2_v1.verify"
IMAGE = "sha256:ce1d4ab2241ce9d141a5447c3da15fb44f62e521c3e2bbe49b74611ff36e3800"
PWSH = Path(r"C:\Users\arvik\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe")
BINDINGS = ("study_sha256", "source_sha256", "runtime_sha256", "policy_sha256", "launcher_sha256")
GATE_GROUPS = ("static", "matrix", "replay", "tests", "windows-tests", "launcher", "inspect",
               "preservation", "regression", "native-fixtures", "semantics", "supervision")
OFFLINE_LIFECYCLE_TIMEOUT_SECONDS = 10_800


def save(target: Path, value: dict) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def execute(args: list[str], *, timeout: int = 7200, environment: dict | None = None) -> dict:
    result = subprocess.run(  # nosec B603
        args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False, timeout=timeout, env=environment,
    )
    return {"command": args, "exit_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def output_path(raw: str, *, existing: bool = False) -> Path:
    value = Path(raw)
    if not value.is_absolute():
        value = ROOT / value
    value = checked_path(value, ROOT / "runs" / PREFIX, missing=not existing)
    if value == ROOT / "runs" / PREFIX or (not value.is_dir() if existing else value.exists()):
        raise ValueError("verification requires a fresh ordinary output root")
    return value


def container_args(output: Path, *, mode: str) -> list[str]:
    target = "/results/" + output.relative_to(ROOT / "runs").as_posix()
    return ["docker", "create", "--pull=never", "--network", "none", "--read-only",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--pids-limit", "256",
        "--memory", "4g", "--cpus", "2", "--entrypoint", "python",
        "--mount", f"type=bind,source={ROOT},target=/workspace,readonly",
        "--mount", f"type=bind,source={ROOT / 'runs' / PREFIX},target=/results/{PREFIX}",
        "--tmpfs", "/tmp:rw,nosuid,nodev,size=1073741824,mode=1777",  # nosec B108
        "--workdir", "/workspace", "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-e", "PYTHONPATH=/workspace/src:/workspace/.upstream/harness2:/workspace",
        "-e", "BUDDHA2_OUTPUT_ROOT=/results", "-e", "BUDDHA2_IMAGE_ID=" + IMAGE,
        "-e", "BUDDHA2_OFFLINE=1", "-e", "PHASE3A_OPENCODE=/opt/phase3a-opencode",
        "-e", "PHASE3A_BUN=/usr/local/bin/bun", IMAGE, "-B", "-m", MODULE,
        "--" + mode, "--output", target]




def expected_mounts(output: Path) -> set[tuple[str, str, bool]]:
    return {(str(ROOT), "/workspace", False),
            (str(ROOT / "runs" / PREFIX), "/results/" + PREFIX, True)}


def contained(output: Path, mode: str) -> int:
    created = execute(container_args(output, mode=mode), timeout=60)
    if created["exit_code"]:
        save(output / f"{mode}-create.json", created)
        return int(created["exit_code"])
    owner = created["stdout"].strip()
    if len(owner) != 64 or any(c not in "0123456789abcdef" for c in owner):
        raise ValueError("Docker returned no exact owned container identity")
    try:
        save(output / f"{mode}-create.json", created)
        inspected = execute(["docker", "inspect", owner], timeout=60)
        save(output / f"{mode}-actual-container.json", inspected)
        actual = json.loads(inspected["stdout"])[0]
        mounts = {(m["Source"], m["Destination"], m["RW"]) for m in actual["Mounts"]}
        if (actual["Image"] != IMAGE or actual["HostConfig"]["NetworkMode"] != "none"
                or not actual["HostConfig"]["ReadonlyRootfs"] or mounts != expected_mounts(output)):
            raise ValueError("actual offline runtime or mount whitelist differs")
        result = execute(["docker", "start", "--attach", owner],
                         timeout=OFFLINE_LIFECYCLE_TIMEOUT_SECONDS if mode == "inside" else 7200)
        save(output / f"{mode}-execution.json", result)
        return int(result["exit_code"])
    finally:
        terminal = execute(["docker", "inspect", owner], timeout=60)
        save(output / f"{mode}-terminal.json", terminal)
        if terminal["exit_code"] == 0 and json.loads(terminal["stdout"])[0]["State"]["Running"]:
            save(output / f"{mode}-stop.json", execute(["docker", "stop", "--time", "10", owner], timeout=30))
        save(output / f"{mode}-remove.json", execute(["docker", "rm", owner], timeout=30))


def record(output: Path, name: str, study: dict, details: dict) -> None:
    from buddha2.artifacts import digest
    value = {"kind": "phase3b-s2-" + name + "-v1", **details,
             **{k: study[k] for k in BINDINGS}, "created_utc": datetime.now(timezone.utc).isoformat()}
    save(output / (name + ".json"), {**value, "sha256": digest(value)})


def run_tests(output: Path, study: dict) -> bool:
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent), pattern="test*.py", top_level_dir=str(ROOT))
    log = io.StringIO()
    with redirect_stdout(log), redirect_stderr(log):
        tested = unittest.TextTestRunner(stream=log, verbosity=2, failfast=True).run(suite)
    with (output / "tests.log").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(log.getvalue())
    record(output, "tests", study, {"passed": tested.wasSuccessful(), "tests": tested.testsRun,
        "failures": len(tested.failures), "errors": len(tested.errors),
        "skipped_test_ids": [test.id() for test, _ in tested.skipped]})
    return tested.wasSuccessful()


def preservation_check(output: Path, study: dict, source: dict, history: dict) -> bool:
    from .support import preserve, source_identity

    after_source, after = source_identity(), preserve()
    save(output / "source-after.json", after_source)
    save(output / "preservation-after.json", after)
    passed = source == after_source and history == after
    record(output, "preservation", study, {"passed": passed,
        "source_unchanged": source == after_source, "history_unchanged": history == after})
    return passed


def normal_fixture_path(branch: dict, results: dict) -> bool:
    """Fixture normality is engineering evidence; it must never assert live authenticity."""
    from . import native

    stages = branch.get("stage_dispositions", [])
    selection = branch.get("native", {}).get("selections", {}).get("seq", {})
    return bool(branch.get("fixture") is True and branch.get("authentic") is False
        and len(stages) == 6 and {row.get("label") for row in stages} == set(native.STAGES)
        and all(not row.get("fell_back") and row.get("accepted_editor_sessions")
                and row.get("model_backed") and row.get("authentic_eligible") is True
                and not row.get("terminal_note_used") for row in stages)
        and len(branch.get("rollouts", {})) == 8 and set(branch.get("checkpoints", {})) == {"c1", "c2"}
        and native._selector_normal(branch.get("editor_evidence", {}), selection, results))


def inside(output: Path) -> int:
    from buddha2.artifacts import file_hash

    from . import accounting, workflow
    from .mocks import StudyMock
    from .report import NAMES, write_report
    from .support import preserve, source_identity
    if {p.name for p in Path("/sys/class/net").iterdir()} != {"lo"}:
        raise ValueError("actual network-none containment required")
    source, history = source_identity(), preserve()
    save(output / "source-before.json", source)
    save(output / "preservation-before.json", history)
    study = workflow.prepare(output / "release")
    study_path = output / "release/study.json"
    for fixture in (True, False):
        save(output / "release" / ("mock-grant.json" if fixture else "live-grant.json"),
             workflow.make_grant(study_path, fixture))
    commands = [
        [sys.executable, "-B", "-m", "ruff", "check", "--no-cache", "followups/phase3b_seq2_v1",
         "evidence/phase3b-seq2-v1/package_public.py"],
        [sys.executable, "-B", "-m", "mypy", "--explicit-package-bases", "--follow-imports", "silent",
         "--ignore-missing-imports", "--no-incremental", "--cache-dir", "/tmp/s2-mypy",  # nosec B108
         "followups/phase3b_seq2_v1", "evidence/phase3b-seq2-v1/package_public.py"],
        [sys.executable, "-B", "-m", "bandit", "-q", "-r", "followups/phase3b_seq2_v1",
         "evidence/phase3b-seq2-v1/package_public.py", "--exclude",
         ",".join(p.name for p in Path(__file__).parent.glob("test*.py")) + ",deadline_regression.py"],
    ]
    statics = []
    for index, command in enumerate(commands):
        result = execute(command)
        save(output / f"static-{index}.json", result)
        statics.append({"command": command, "exit_code": result["exit_code"]})
    record(output, "static", study, {"passed": all(r["exit_code"] == 0 for r in statics), "commands": statics})
    if any(r["exit_code"] for r in statics) or not run_tests(output, study):
        preservation_check(output, study, source, history)
        return 1
    capacity_root = workflow.NATIVE / ("capacity-" + output.name)
    capacity_execution = execute([sys.executable, "-B", "-m", "followups.phase3b_seq2_v1.capacity",
                                  "--output", str(capacity_root)])
    save(output / "capacity-execution.json", capacity_execution)
    capacity = workflow.read(capacity_root / "capacity.json")
    if capacity_execution["exit_code"] or capacity.get("passed") is not True:
        record(output, "semantics", study, {"passed": False, "capacity": capacity,
                                            "capacity_root": str(capacity_root)})
        preservation_check(output, study, source, history)
        return 1
    grant = output / "release/mock-grant.json"
    with StudyMock() as mock:
        summary = workflow.run(study_path, grant, stage="all", transport=mock.transport)
        run, journal = workflow.paths(study, True)
        state = accounting.replay(journal)
        branches = [workflow.read(run / "branches" / (f"p3b-{i:02}-adaptive.json"))["result"] for i in range(1, 5)]
        native_paths = all(normal_fixture_path(branch, state["results"]) for branch in branches)
        passed = (summary["primary_scored"] == 8 and summary["assessment_scored"] == 12
            and summary["status"] == "mock-complete" and native_paths
            and summary["scientific_complete"] is False and summary["authentic_live_path"] is False
            and state["reserved_micro_usd"] == 0 and state["attempts"] == mock.http_calls <= 2344
            and len(study["slots"]) == 2344)
        record(output, "matrix", study, {"passed": passed, "summary": summary, "mock_http_calls": mock.http_calls,
            "real_provider_calls": 0, "potential_slots": 2344, "maximum_admitted_attempts": 2344,
            "all_four_native_two_round_paths_normal": native_paths, "assessment_targets": 12,
            "delivered_outputs": 8, "study_path": str(study_path), "mock_grant_path": str(grant),
            "live_grant_path": str(output / "release/live-grant.json"), "run": str(run), "journal": str(journal)})
        save(output / "mock-proof.json", mock.proofs())
        save(output / "mock-wire.json", {"fixture": True, "records": mock.records})
        record(output, "semantics", study, {"passed": native_paths,
            "capacity_root": str(capacity_root), "capacity_file_sha256": file_hash(capacity_root / "capacity.json"),
            "realistic_capacity_passed": capacity["passed"],
            "engine_commit": study["runtime"]["harness2_commit"], "rounds": 2,
            "two_reference_rollouts": True, "native_authoring_stages_per_prompt": 6,
            "normal_native_selectors": 4, "candidate_pool": ["c1", "c2"],
            "no_external_feedback_in_loop": True, "fixture_only": True,
            "branch_file_sha256": {f"p3b-{i:02}":file_hash(run / "branches" / (f"p3b-{i:02}-adaptive.json")) for i in range(1, 5)}})
        if not passed:
            return 1
        calls, journal_bytes = mock.http_calls, (journal / "events.jsonl").read_bytes()
        repeated = workflow.run(study_path, grant, stage="all", transport=mock.transport)
        with ExitStack() as blocks:
            for target in ("anthropic.Anthropic", "anthropic.AsyncAnthropic", "openai.OpenAI", "openai.AsyncOpenAI",
                           "socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex"):
                blocks.enter_context(patch(target, side_effect=AssertionError("saved report attempted external activity")))
            write_report(workflow.snapshot(study_path, grant, True), run / "reports/replay")
        names = tuple(name + ".json" for name in NAMES) + ("PHASE3B_REPORT.md",)
        record(output, "replay", study, {"passed": repeated == summary and mock.http_calls == calls
            and journal_bytes == (journal / "events.jsonl").read_bytes()
            and all(file_hash(run / "reports/final" / n) == file_hash(run / "reports/replay" / n) for n in names),
            "new_mock_calls": mock.http_calls - calls, "report_files": list(names), "SDK_and_sockets_blocked": True})
    return 0 if preservation_check(output, study, source, history) else 1


def windows(output: Path) -> int:
    """Run the exact host-only cases, in a credential-free child environment."""
    from .support import read
    study = read(output / "release/study.json")
    linux = read(output / "tests.json")
    names = linux["skipped_test_ids"]
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in names)
    log = io.StringIO()
    with redirect_stdout(log), redirect_stderr(log):
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    with (output / "windows-tests.log").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(log.getvalue())
    record(output, "windows-tests", study, {"passed": result.wasSuccessful() and not result.skipped,
        "case_ids": names, "tests": result.testsRun, "errors": len(result.errors),
        "failures": len(result.failures), "skipped": len(result.skipped), "PowerShell_path": str(PWSH)})
    return 0 if result.wasSuccessful() and not result.skipped else 1


def prepare_supervised(output: Path) -> int:
    """A distinct mock-only study makes the actual supervisor exercise fresh handoffs."""
    from . import workflow

    study = workflow.prepare(output / "release", supervised_fixture=True)
    study_path = output / "release/study.json"
    grant_path = output / "release/mock-grant.json"
    save(grant_path, workflow.make_grant(study_path, True))
    save(output / "prepared.json", {**{key: study[key] for key in BINDINGS},
        "study_path": str(study_path), "mock_grant_path": str(grant_path),
        "run": str(workflow.paths(study, True)[0]), "fixture": True,
        "fixture_supervision_rehearsal": True, "provider_calls": 0,
        "provider_grant_permitted": False})
    return 0


def seal_gate(output: Path) -> int:
    from buddha2.artifacts import digest, file_hash

    from .support import preserve, read
    from .workflow import load_study
    study = load_study(output / "release/study.json")
    refs = {}
    for name in GATE_GROUPS:
        item = read(output / (name + ".json"))
        if item.get("passed") is not True or any(item.get(k) != study[k] for k in BINDINGS):
            raise ValueError("whole gate has a failed or foreign group: " + name)
        refs[name] = {"path": str(output / (name + ".json")), "sha256": file_hash(output / (name + ".json"))}
    after_host = preserve()
    if after_host != read(output / "preservation-before.json"):
        raise ValueError("historical preservation failed after host checks")
    save(output / "preservation-after-host.json", after_host)
    value = {"kind": "phase3b-s2-offline-gate-v1", "passed": True, **{k: study[k] for k in BINDINGS},
             "checks": refs, "provider_calls": 0, "real_credentials_used": False}
    save(output / "release/offline-gate.json", {**value, "sha256": digest(value)})
    return 0


def host(raw: str, supervisor_agent: str) -> int:
    from .supervision import agent_name
    supervisor_agent = agent_name(supervisor_agent)
    output = output_path(raw)
    if not shutil.which("docker") or not PWSH.is_file():
        raise ValueError("existing Docker and inspected bundled PowerShell are required")
    output.mkdir(parents=True)
    if contained(output, "inside"):
        return 1
    environment = {name: os.environ[name] for name in
        ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "PATHEXT") if name in os.environ}
    environment.update(PATH=str(PWSH.parent) + os.pathsep + environment.get("PATH", ""),
        PYTHONPATH=os.pathsep.join(str(p) for p in (ROOT, ROOT / "src", ROOT / ".upstream/harness2")),
        BUDDHA2_OUTPUT_ROOT=str(ROOT / "runs"), PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
    result = execute([sys.executable, "-B", "-m", MODULE, "--windows", "--output", str(output)], environment=environment)
    save(output / "windows-execution.json", result)
    if result["exit_code"]:
        return 1
    rehearsal = output / "operational-rehearsal"
    rehearsal.mkdir()
    if contained(rehearsal, "supervised"):
        return 1
    from .host_checks import complete_host_checks
    complete_host_checks(output, supervisor_agent=supervisor_agent)
    return contained(output, "seal")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--supervisor-agent")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--inside", action="store_true")
    modes.add_argument("--windows", action="store_true")
    modes.add_argument("--seal", action="store_true")
    modes.add_argument("--supervised", action="store_true")
    args = parser.parse_args()
    if args.inside:
        return inside(Path(args.output))
    if args.seal:
        return seal_gate(Path(args.output))
    if args.windows:
        return windows(output_path(args.output, existing=True))
    if args.supervised:
        return prepare_supervised(Path(args.output))
    return host(args.output, args.supervisor_agent)


if __name__ == "__main__":
    raise SystemExit(main())
