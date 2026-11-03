"""Run unchanged reused-helper regressions in an ephemeral, keyless H1 container."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess  # nosec B404
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from followups.inspect_visibility_i1.paths import checked_path

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "phase3a-h1-integrated-v1"
IMAGE = "sha256:ce1d4ab2241ce9d141a5447c3da15fb44f62e521c3e2bbe49b74611ff36e3800"
MODULE = "followups.phase3a_h1_integrated_v1.regression"
BINDINGS = ("study_sha256", "source_sha256", "runtime_sha256", "policy_sha256", "launcher_sha256")
SUITES = (
    "followups.phase3a_c1_completion_v3.tests.test_deadline",
    "followups.phase3a_c1_completion_v3.tests.test_accounting",
    "followups.phase3a_v1.tests.test_transport",
    "followups.phase3a_v1.tests.test_strategy",
    "followups.phase3a_v1.tests.test_accounting",
    "followups.phase3a_history_compat_h1.tests",
)
DIAGNOSTICS = ("regression-inside-probe.json", "regression-component-v1/regression.json",
    "regression-cpu4-probe.json", "regression-short-deadline-diagnostic.json",
    "regression-default-deadline-diagnostic.json")


def inside() -> int:
    from .accounting import runtime_guard
    from .deadline_regression import FIXTURE_DELAYS, FIXTURE_POLICY, REPLACEMENTS
    runtime_guard()  # Check the actual H1 runtime; never relabel it as an old image.
    def cases(suite):
        for case in suite:
            if isinstance(case, unittest.TestSuite):
                yield from cases(case)
            else:
                yield case
    original = list(cases(unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in SUITES)))
    if not set(REPLACEMENTS).issubset({case.id() for case in original}):
        raise ValueError("frozen regression replacement inventory differs")
    unchanged = [case for case in original if case.id() not in REPLACEMENTS]
    replacements = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in REPLACEMENTS.values())
    replacement_count = replacements.countTestCases()
    if replacement_count != len(REPLACEMENTS):
        raise ValueError("versioned regression inventory differs")
    suite = unittest.TestSuite([*unchanged, replacements])
    log = io.StringIO()
    with redirect_stdout(log), redirect_stderr(log):
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    report = {"passed": result.wasSuccessful() and not result.skipped, "suites": list(SUITES),
        "tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
        "skipped": [(test.id(), reason) for test, reason in result.skipped], "log": log.getvalue(),
        "unchanged_frozen_cases": len(unchanged), "versioned_fixture_cases": replacement_count,
        "excluded_frozen_test_ids": list(REPLACEMENTS),
        "replacement_map": {old: {"new_test_id": new, "fixture_policy": FIXTURE_POLICY,
            "fixture_delays": FIXTURE_DELAYS} for old, new in REPLACEMENTS.items()},
        "frozen_90_passed": False, "production_policy_changed": False, "timing_parity_claimed": False,
        "actual_H1_runtime_guard": True, "provider_calls": 0, "real_credentials_used": False,
        "scope": "83 unchanged helper checks plus seven versioned semantic equivalents; frozen90 red results retained separately"}
    print(json.dumps(report, ensure_ascii=False, allow_nan=False))
    return 0 if report["passed"] else 1


def _run(arguments: list[str], *, timeout: int = 120) -> dict:
    environment = {name: os.environ[name] for name in
        ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "PATHEXT") if name in os.environ}
    try:
        result = subprocess.run(arguments, cwd=ROOT, env=environment, capture_output=True,  # nosec B603
            text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False)
        return {"command": arguments, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    except subprocess.TimeoutExpired:
        return {"command": arguments, "exit_code": 124, "timed_out": True, "stdout": "", "stderr": ""}


def complete_regression(output: Path) -> dict:
    """Host API: retain one source-bound group beneath the new public run prefix."""
    output = checked_path(output, ROOT / "runs" / PREFIX, missing=False)
    if output == ROOT / "runs" / PREFIX or not output.is_dir():
        raise ValueError("regression requires a specific existing new run directory")
    def save(name, value):
        target = checked_path(output / ("regression" + name + ".json"), output, missing=True)
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n")
    study_path = checked_path(output / "release/study.json", output, missing=False)
    study = json.loads(study_path.read_text(encoding="utf-8"))
    bindings = {key: study[key] for key in BINDINGS}
    args = ["docker", "create", "--pull=never", "--network", "none", "--read-only",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--pids-limit", "256",
        "--memory", "4g", "--cpus", "2", "--log-driver", "none", "--entrypoint", "python",
        "--mount", f"type=bind,source={ROOT},target=/workspace,readonly",
        "--tmpfs", "/results:rw,nosuid,nodev,size=1073741824,mode=1777",  # nosec B108
        "--tmpfs", "/tmp:rw,nosuid,nodev,size=1073741824,mode=1777",  # nosec B108
        "--workdir", "/workspace", "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-e", "PYTHONPATH=/workspace/src:/workspace/.upstream/harness2:/workspace",
        "-e", "BUDDHA2_OUTPUT_ROOT=/results", "-e", "BUDDHA2_IMAGE_ID=" + IMAGE,
        "-e", "BUDDHA2_OFFLINE=1", "-e", "PHASE3A_OPENCODE=/opt/phase3a-opencode",
        "-e", "PHASE3A_BUN=/usr/local/bin/bun", IMAGE, "-B", "-m", MODULE, "--inside"]
    created = _run(args)
    owner = created["stdout"].strip()
    if created["exit_code"] or len(owner) != 64 or any(c not in "0123456789abcdef" for c in owner):
        save("-create", created)
        report = {"passed": False, **bindings, "reason": "no exact owned regression container", "provider_calls": 0}
        save("", report)
        return report
    proof: dict = {}
    cleanup: dict = {}
    try:
        save("-create", created)
        inspected = _run(["docker", "inspect", owner])
        if inspected["exit_code"]:
            raise ValueError("regression inspection failed")
        actual = json.loads(inspected["stdout"])[0]
        host = actual["HostConfig"]
        mounts = actual["Mounts"]
        if (actual["Image"] != IMAGE or host["NetworkMode"] != "none" or not host["ReadonlyRootfs"]
                or host["Privileged"] or host["LogConfig"]["Type"] != "none" or host["PidsLimit"] != 256
                or host["Memory"] != 4294967296 or host["NanoCpus"] != 2000000000
                or host["CapDrop"] != ["ALL"] or host["SecurityOpt"] not in (["no-new-privileges"], ["no-new-privileges:true"])
                or len(mounts) != 1 or mounts[0]["Source"].lower() != str(ROOT).lower()
                or mounts[0]["Destination"] != "/workspace" or mounts[0]["RW"]
                or set(host["Tmpfs"]) != {"/results", "/tmp"} or actual["State"]["Running"]):  # nosec B108
            raise ValueError("actual regression container isolation differs")
        save("-inspection", {"passed": True, "container_id": owner, "image": actual["Image"],
            "network": host["NetworkMode"], "mounts": mounts, "tmpfs": host["Tmpfs"], "read_only_rootfs": True})
        execution = _run(["docker", "start", "--attach", owner], timeout=1800)
        save("-execution", execution)
        proof = json.loads(execution["stdout"]) if execution["stdout"].strip() else {}
        proof["passed"] = execution["exit_code"] == 0 and proof.get("passed") is True
    except (ValueError, KeyError, TypeError, IndexError):
        proof = {"passed": False, "reason": "regression container configuration or result rejected"}
    finally:
        terminal = _run(["docker", "inspect", owner])
        cleanup["terminal"] = terminal
        try:
            needs_stop = terminal["exit_code"] != 0 or json.loads(terminal["stdout"])[0]["State"]["Running"]
        except (ValueError, KeyError, TypeError, IndexError):
            needs_stop = True
        if needs_stop:
            cleanup["stop"] = _run(["docker", "stop", "--time", "10", owner], timeout=30)
        cleanup["remove"] = _run(["docker", "rm", owner], timeout=30)
        save("-cleanup", cleanup)
    report = {**proof, **bindings, "kind": "phase3a-hi-reused-helper-regressions-v1",
        "passed": proof.get("passed") is True and cleanup["remove"]["exit_code"] == 0,
        "ephemeral_results": True, "old_host_runs_mounted": False, "provider_calls": 0, "real_credentials_used": False}
    history = []
    for name in DIAGNOSTICS:
        target = checked_path(ROOT / "runs" / PREFIX / name, ROOT / "runs" / PREFIX, missing=False)
        history.append({"path": target.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "role": "prior offline diagnostic; no new authority"})
    report["retained_diagnostic_refs"] = history
    save("", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inside", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.inside and args.output is None:
        return inside()
    if args.output is not None and not args.inside:
        return 0 if complete_regression(args.output)["passed"] else 1
    parser.error("choose --inside or --output")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
