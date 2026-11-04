"""Owned, network-disabled main/replay commands for one frozen C2 candidate."""
from __future__ import annotations

import argparse
import base64
import json
import subprocess  # nosec B404
import traceback
from pathlib import Path

from followups.phase3b_seq2_v1 import verify
from followups.phase3b_seq2_v1.support import recovery_config

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs/phase3b-seq2-v1" / recovery_config()["verification"]


def encoded(value):
    return base64.b64encode(value if isinstance(value, bytes) else (value or "").encode()).decode()


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("phase", choices=("main", "replay", "supervised", "seal"))
    phase = parser.parse_args().phase
    output = OUT / "operational-rehearsal" if phase == "supervised" else OUT
    if phase == "supervised":
        output.mkdir()
    target = "/results/" + output.relative_to(ROOT / "runs").as_posix()
    args = verify.container_args(output, mode=phase if phase in ("supervised", "seal") else "inside")
    args[2:2] = ["--log-driver", "none"]
    if phase in ("main", "replay"):
        args[args.index(verify.IMAGE) + 1:] = ["-B", "/workspace/evidence/phase3b-seq2-c2-v1/composed_acceptance.py",
                                            "--phase", phase, "--output", target]
    owner, passed = None, False
    prefix = "c2-" + phase

    def execute(command, timeout):
        try:
            return verify.execute(command, timeout=timeout)
        except (subprocess.TimeoutExpired, TimeoutError, OSError) as exc:
            return {"command": command, "exit_code": 124, "stdout": "", "stderr": "",
                    "exception_type": type(exc).__name__, "exception_message": str(exc),
                    "partial_output_base64": encoded(getattr(exc, "stdout", None)),
                    "partial_error_base64": encoded(getattr(exc, "stderr", None))}

    try:
        created = verify.execute(args, timeout=60)
        verify.save(OUT / (prefix + "-create.json"), created)
        owner = created["stdout"].strip()
        if created["exit_code"] or len(owner) != 64 or any(c not in "0123456789abcdef" for c in owner):
            owner = None
            raise ValueError("no exact C2 owner")
        inspection = verify.execute(["docker", "inspect", owner], timeout=60)
        actual = json.loads(inspection["stdout"])[0]
        host = actual["HostConfig"]
        mounts = {(m["Source"], m["Destination"], m["RW"]) for m in actual["Mounts"]}
        if (actual["Image"] != verify.IMAGE or host["NetworkMode"] != "none" or not host["ReadonlyRootfs"]
                or mounts != verify.expected_mounts(OUT) or host["Privileged"]
                or host["Memory"] != 4294967296 or host["NanoCpus"] != 2000000000 or host["PidsLimit"] != 256
                or host["CapDrop"] != ["ALL"] or host["SecurityOpt"] not in (["no-new-privileges"], ["no-new-privileges:true"])
                or host["Tmpfs"] != {"/tmp": "rw,nosuid,nodev,size=1073741824,mode=1777"}  # nosec B108
                or host["LogConfig"]["Type"] != "none" or actual["State"]["Running"]):
            raise ValueError("actual C2 containment differs")
        verify.save(OUT / (prefix + "-inspection.json"), {"owner": owner, "passed": True,
                    "image": actual["Image"], "mounts": actual["Mounts"], "network": "none", "readonly_root": True})
        # Prospective outer ceilings bound two distinct offline operations. Native
        # conversations/HTTP/startup/review/export timers are never changed.
        execution = verify.execute(["docker", "start", "--attach", owner], timeout=21600 if phase == "main" else 7200)
        verify.save(OUT / (prefix + "-execution.json"), execution)
        passed = execution["exit_code"] == 0
    except BaseException as exc:
        verify.save(OUT / (prefix + "-failure.json"), {"passed": False, "exception_type": type(exc).__name__,
                    "exception_message": str(exc), "traceback": traceback.format_exc(),
                    "partial_output_base64": encoded(getattr(exc, "stdout", None)),
                    "partial_error_base64": encoded(getattr(exc, "stderr", None))})
    finally:
        cleanup: dict = {"passed": False, "owner": owner}
        if owner:
            terminal = execute(["docker", "inspect", "--format", "{{json .State.Running}}", owner], 15)
            cleanup["terminal"] = terminal
            if terminal["exit_code"] or terminal["stdout"].strip() == "true":
                cleanup["stop"] = execute(["docker", "stop", "--time", "10", owner], 30)
            cleanup["remove"] = execute(["docker", "rm", owner], 30)
            cleanup["absence"] = execute(["docker", "inspect", "--format", "{{json .State.Running}}", owner], 15)
            cleanup["passed"] = (cleanup["remove"]["exit_code"] == 0 and cleanup["absence"]["exit_code"] != 0
                                  and "no such object" in cleanup["absence"]["stderr"].casefold())
        verify.save(OUT / (prefix + "-cleanup.json"), cleanup)
    return 0 if passed and cleanup["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
