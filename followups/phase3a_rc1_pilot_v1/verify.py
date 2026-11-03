"""Whole P3A-HI offline gate; never a credential or provider-call entry point."""

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
PREFIX = "phase3a-rc1-pilot-v1"
MODULE = "followups.phase3a_rc1_pilot_v1.verify"
IMAGE = "sha256:ce1d4ab2241ce9d141a5447c3da15fb44f62e521c3e2bbe49b74611ff36e3800"
PWSH = Path(r"C:\Users\arvik\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe")
BINDINGS = ("study_sha256", "source_sha256", "runtime_sha256", "policy_sha256", "launcher_sha256")


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
        expected_mounts = {(str(ROOT), "/workspace", False),
                           (str(ROOT / "runs" / PREFIX), "/results/" + PREFIX, True)}
        mounts = {(m["Source"], m["Destination"], m["RW"]) for m in actual["Mounts"]}
        if (actual["Image"] != IMAGE or actual["HostConfig"]["NetworkMode"] != "none"
                or not actual["HostConfig"]["ReadonlyRootfs"] or mounts != expected_mounts):
            raise ValueError("actual offline runtime or mount whitelist differs")
        result = execute(["docker", "start", "--attach", owner])
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
    value = {"kind": "phase3a-rp1-" + name + "-v1", **details,
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


def inside(output: Path) -> int:
    from buddha2.artifacts import file_hash

    from . import accounting, workflow
    from .mocks import StudyMock
    from .report import write_report
    from .support import preserve, source_identity

    if {p.name for p in Path("/sys/class/net").iterdir()} != {"lo"}:
        raise ValueError("offline matrix requires actual network-none containment")
    source, history = source_identity(), preserve()
    save(output / "source-before.json", source)
    save(output / "preservation-before.json", history)
    study = workflow.prepare(output / "release")
    study_path = output / "release/study.json"
    for fixture in (True, False):
        save(output / "release" / ("mock-grant.json" if fixture else "live-grant.json"),
             workflow.make_grant(study_path, fixture))
    commands = [
        [sys.executable, "-B", "-m", "ruff", "check", "--no-cache", "followups/phase3a_rc1_pilot_v1",
         "evidence/phase3a-rc1-pilot-v1/package_public.py"],
        [sys.executable, "-B", "-m", "mypy", "--explicit-package-bases", "--follow-imports", "silent",
         "--ignore-missing-imports", "--no-incremental", "--cache-dir", "/tmp/hi-mypy",  # nosec B108
         "followups/phase3a_rc1_pilot_v1", "evidence/phase3a-rc1-pilot-v1/package_public.py"],
        [sys.executable, "-B", "-m", "bandit", "-q", "-r", "followups/phase3a_rc1_pilot_v1",
         "evidence/phase3a-rc1-pilot-v1/package_public.py", "--exclude", "tests_native.py,tests_launch.py,test_inspect.py,test_release.py,tests_accounting.py,test_regression.py,deadline_regression.py,tests_core_view.py,test_bootstrap.py"],
    ]
    statics = []
    for index, command in enumerate(commands):
        result = execute(command)
        save(output / f"static-{index}.json", result)
        statics.append({"command": command, "exit_code": result["exit_code"]})
    record(output, "static", study, {"passed": all(r["exit_code"] == 0 for r in statics), "commands": statics})
    if any(r["exit_code"] for r in statics):
        return 1
    # Cheap boundary failures must be caught before the long native rehearsal.
    if not run_tests(output, study):
        preservation_check(output, study, source, history)
        return 1
    grant = output / "release/mock-grant.json"
    with StudyMock() as mock:
        summary = workflow.run(study_path, grant, stage="all", transport=mock.transport)
        run, journal = workflow.paths(study, True)
        state = accounting.replay(journal)
        resources = workflow.read(run / "reports/final/accounting.json")["resource_report"]
        financial_profile = (
            resources["current_study_cap_micro_usd"] == 200000000
            and resources["defined_max_cumulative_exposure_micro_usd"] == 247343235
            and summary["prior_real_phase3a_spent_micro_usd"] == 24463235
            and summary["prior_real_phase3a_reserved_micro_usd"] == 22880000
            and summary["prior_real_phase3a_provider_calls"] == 1233)
        proofs = mock.proofs()
        profiles = (set(proofs) == {f"p3a-{i:02}" for i in range(1, 5)}
            and all(set(sessions) == {"inv1.a1", "dom1.a1", "agg1.a1"} for sessions in proofs.values())
            and all(proof.get("fixture") is True and proof.get("normal_final") is True
                and proof.get("HI_deliberately_inefficient_evidence_reading") is True
                and proof.get("notes_reread_model_visible") is True
                and proof.get("decision_after_complete_evidence") is True
                and proof.get("verification_after_write") is True
                and proof.get("terminal_note_used") is False
                and proof.get("evidence_read_batches") == 4
                and 7 < proof.get("ordinary_rounds", 0) <= 15
                and proof.get("effective_changed") is (not label.startswith("dom"))
                for sessions in proofs.values() for label, proof in sessions.items()))
        passed = (summary["primary_scored"] == 8 and summary["status"] == "mock-complete" and profiles and financial_profile
                  and state["reserved_micro_usd"] == 0 and state["attempts"] == mock.http_calls <= 775
                  and len(study["slots"]) == 967)
        record(output, "matrix", study, {"passed": passed, "summary": summary,
            "mock_http_calls": mock.http_calls, "real_provider_calls": 0,
            "potential_slots": 967, "maximum_admitted_attempts": 775, "all_twelve_native_editor_profiles_valid": profiles,
            "new_global_and_historical_financial_profile": financial_profile,
            "study_path": str(study_path), "mock_grant_path": str(grant),
            "live_grant_path": str(output / "release/live-grant.json"), "run": str(run), "journal": str(journal)})
        save(output / "mock-proof.json", proofs)
        save(output / "mock-wire.json", {"fixture": True, "records": mock.records})
        if not passed:
            return 1
        calls, journal_bytes = mock.http_calls, (journal / "events.jsonl").read_bytes()
        repeated = workflow.run(study_path, grant, stage="all", transport=mock.transport)
        with ExitStack() as blocks:
            for target in ("anthropic.Anthropic", "anthropic.AsyncAnthropic", "openai.OpenAI", "openai.AsyncOpenAI",
                           "socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex"):
                blocks.enter_context(patch(target, side_effect=AssertionError("saved report attempted external activity")))
            write_report(workflow.snapshot(study_path, grant, True), run / "reports/replay")
        names = ("rows.json", "coverage.json", "analysis.json", "summary.json", "accounting.json", "protocol.json",
                 "readiness.json", "PHASE3A_REPORT.md")
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


def seal_gate(output: Path) -> int:
    from buddha2.artifacts import digest, file_hash

    from .support import preserve, read
    from .workflow import load_study
    study = load_study(output / "release/study.json")
    refs = {}
    for name in ("static", "matrix", "replay", "tests", "windows-tests", "launcher", "inspect", "preservation", "regression", "native-fixtures"):
        item = read(output / (name + ".json"))
        if item.get("passed") is not True or any(item.get(k) != study[k] for k in BINDINGS):
            raise ValueError("whole gate has a failed or foreign group: " + name)
        refs[name] = {"path": str(output / (name + ".json")), "sha256": file_hash(output / (name + ".json"))}
    after_host = preserve()
    if after_host != read(output / "preservation-before.json"):
        raise ValueError("historical preservation failed after host checks")
    save(output / "preservation-after-host.json", after_host)
    value = {"kind": "phase3a-rp1-offline-gate-v1", "passed": True, **{k: study[k] for k in BINDINGS},
             "checks": refs, "provider_calls": 0, "real_credentials_used": False}
    save(output / "release/offline-gate.json", {**value, "sha256": digest(value)})
    return 0


def host(raw: str) -> int:
    output = output_path(raw)
    if not shutil.which("docker") or not PWSH.is_file():
        raise ValueError("the existing Docker and inspected bundled PowerShell runtime are required")
    output.mkdir(parents=True)
    if contained(output, "inside"):
        return 1
    environment = {name: os.environ[name] for name in ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "PATHEXT") if name in os.environ}
    environment.update(PATH=str(PWSH.parent) + os.pathsep + environment.get("PATH", ""),
        PYTHONPATH=os.pathsep.join(str(p) for p in (ROOT, ROOT / "src", ROOT / ".upstream/harness2")),
        BUDDHA2_OUTPUT_ROOT=str(ROOT / "runs"), PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
    result = execute([sys.executable, "-B", "-m", MODULE, "--windows", "--output", str(output)], environment=environment)
    save(output / "windows-execution.json", result)
    if result["exit_code"]:
        return 1
    # Explicitly separate actual host coverage/Inspect image exports from the native matrix.
    from .host_checks import complete_host_checks
    complete_host_checks(output)
    return contained(output, "seal")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--inside", action="store_true")
    modes.add_argument("--windows", action="store_true")
    modes.add_argument("--seal", action="store_true")
    args = parser.parse_args()
    if args.inside:
        return inside(Path(args.output))
    if args.seal:
        return seal_gate(Path(args.output))
    if args.windows:
        return windows(output_path(args.output, existing=True))
    return host(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
