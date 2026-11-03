"""Run unchanged reused-helper regressions in an ephemeral, keyless H1 container."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess  # nosec B404
from pathlib import Path

from followups.inspect_visibility_i1.paths import checked_path

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "phase3b-seq2-v1"
IMAGE = "sha256:ce1d4ab2241ce9d141a5447c3da15fb44f62e521c3e2bbe49b74611ff36e3800"
MODULE = "followups.phase3b_seq2_v1.regression"
BINDINGS = ("study_sha256", "source_sha256", "runtime_sha256", "policy_sha256", "launcher_sha256")
SUITES = (
    "followups.phase3a_c1_completion_v3.tests.test_deadline",
    "followups.phase3a_c1_completion_v3.tests.test_accounting",
    "followups.phase3a_v1.tests.test_transport",
    "followups.phase3a_v1.tests.test_strategy",
    "followups.phase3a_v1.tests.test_accounting",
    "followups.phase3a_history_compat_h1.tests",
)
DIAGNOSTICS = {
    "regression-inside-probe.json": "cdb1f16fd5f1fc920aaeabc39615661bd0ba72d0e757bc6bcee9e95cf98389df",
    "regression-component-v1/regression.json": "4a3d141fec5b3eb58a321945964d8ca2b68c8e139410ba3c76cfe279be597fc9",
    "regression-cpu4-probe.json": "dfe2082b89aef78a10df9c7736219df91f344c40f076345520944f2ee184800a",
    "regression-short-deadline-diagnostic.json": "3c24cf7ce3e8d4d2eabb5e0305e4b2193298544d516bc20bd5f42c092c989741",
    "regression-default-deadline-diagnostic.json": "225eabc31845a0f1d526293dc51d59dcbef0e2ae9f510a9dfc1675f81aada2b3",
}


def retain_diagnostics(output: Path) -> list[dict]:
    """Copy the exact five accepted historical diagnostics, never relabel them."""
    from .support import safe

    history = []
    for name, expected in DIAGNOSTICS.items():
        original = safe(ROOT / "runs/phase3a-rc1-pilot-v1" / name)
        raw = original.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("accepted helper diagnostic changed")
        target = safe(output / "retained-helper-diagnostics" / name)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
        history.append({"path": target.relative_to(ROOT).as_posix(), "sha256": expected,
                        "original_path": original.relative_to(ROOT).as_posix(),
                        "role": "unchanged prior offline diagnostic; no new authority"})
    return history


def inside() -> int:
    from followups.phase3a_readiness_recovery_v1.regression import inside as accepted
    return accepted()


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
    report = {**proof, **bindings, "kind": "phase3b-s2-reused-helper-regressions-v1",
        "passed": proof.get("passed") is True and cleanup["remove"]["exit_code"] == 0,
        "ephemeral_results": True, "old_host_runs_mounted": False, "provider_calls": 0, "real_credentials_used": False}
    report["retained_diagnostic_refs"] = retain_diagnostics(output)
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
