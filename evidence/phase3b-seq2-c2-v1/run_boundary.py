"""Exact-owned keyless H1/I1 boundary regression; no generation entry point."""
from __future__ import annotations

import base64
import json
import os
import subprocess  # nosec B404
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs/phase3b-seq2-v1/verification-v3/boundary-contract"
IMAGE = "sha256:ce1d4ab2241ce9d141a5447c3da15fb44f62e521c3e2bbe49b74611ff36e3800"


def main() -> int:
    from followups.phase3b_seq2_v1.verify import container_args, expected_mounts, save

    if OUT.exists() or Path.cwd().resolve() != ROOT:
        raise ValueError("fresh exact boundary output required")
    OUT.mkdir(parents=True)
    env = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "PATHEXT") if k in os.environ}
    env.update(PYTHONPATH=os.pathsep.join(str(p) for p in (ROOT, ROOT / "src", ROOT / ".upstream/harness2")),
               BUDDHA2_OUTPUT_ROOT=str(ROOT / "runs"), PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
    target = "/results/phase3b-seq2-v1/verification-v3/boundary-contract/fixture"
    owners, processes = [], []

    def run(args, timeout=60):
        try:
            done = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True,  # nosec B603
                                  encoding="utf-8", errors="replace", timeout=timeout, check=False)
            return {"command": args, "exit_code": done.returncode, "output": done.stdout, "error": done.stderr}
        except (subprocess.TimeoutExpired, OSError) as exc:
            return {"command": args, "exit_code": 124, "exception_type": type(exc).__name__,
                    "exception_message": str(exc), "traceback": traceback.format_exc(),
                    "output": "", "error": "", **partial(exc)}

    def partial(exc):
        def encoded(value):
            return base64.b64encode(value if isinstance(value, bytes) else (value or "").encode()).decode()
        return {"partial_output_base64": encoded(getattr(exc, "stdout", None)),
                "partial_error_base64": encoded(getattr(exc, "stderr", None))}

    def create(label, module_args):
        args = container_args(OUT, mode="inside")
        args[args.index(IMAGE) + 1:] = ["-B", *module_args]
        args[2:2] = ["--log-driver", "none"]
        result = run(args)
        save(OUT / (label + "-create.json"), result)
        owner = result["output"].strip()
        if result["exit_code"] or len(owner) != 64 or any(c not in "0123456789abcdef" for c in owner):
            raise ValueError("no exact boundary owner")
        owners.append(owner)
        inspected = run(["docker", "inspect", owner])
        if inspected["exit_code"]:
            raise ValueError("boundary owner inspection failed")
        actual = json.loads(inspected["output"])[0]
        host = actual["HostConfig"]
        mounts = {(m["Source"], m["Destination"], m["RW"]) for m in actual["Mounts"]}
        if (actual["Image"] != IMAGE or host["NetworkMode"] != "none" or not host["ReadonlyRootfs"]
                or mounts != expected_mounts(OUT) or host["Privileged"] or host["PidsLimit"] != 256
                or host["Memory"] != 4294967296 or host["NanoCpus"] != 2000000000
                or host["CapDrop"] != ["ALL"] or host["SecurityOpt"] not in (["no-new-privileges"], ["no-new-privileges:true"])
                or host["Tmpfs"] != {"/tmp": "rw,nosuid,nodev,size=1073741824,mode=1777"}
                or host["LogConfig"]["Type"] != "none" or actual["State"]["Running"]):
            raise ValueError("boundary owner containment differs")
        save(OUT / (label + "-inspection.json"), {"passed": True, "owner": owner,
             "image": actual["Image"], "network": "none", "mounts": actual["Mounts"],
             "readonly_root": True, "tmpfs": host["Tmpfs"], "arguments": actual["Args"]})
        return owner

    passed, cleanup_passed = False, True
    try:
        unit = create("negative-tests", ["-m", "unittest", "followups.phase3b_seq2_v1.test_inspect_s2.VisibilitySettlementTests"])
        result = run(["docker", "start", "--attach", unit], 120)
        save(OUT / "negative-tests-execution.json", result)
        if result["exit_code"]:
            raise ValueError("negative contract tests failed")
        result = run([sys.executable, "-B", "-m", "followups.phase3b_seq2_v1.boundary_contract",
                      "negative", "--output", str(OUT / "negative-host")], 120)
        save(OUT / "host-negatives-execution.json", result)
        if result["exit_code"]:
            raise ValueError("actual host contract negatives failed")
        prepared = create("prepare", ["-m", "followups.phase3b_seq2_v1.boundary_contract", "prepare", "--output", target])
        result = run(["docker", "start", "--attach", prepared], 600)
        save(OUT / "prepare-execution.json", result)
        if result["exit_code"]:
            raise ValueError("boundary preparation failed")
        core = create("core", ["-m", "followups.phase3b_seq2_v1.boundary_contract", "core", "--output", target])
        # No parent-chat acknowledgement is needed. This host independently waits
        # for both real requests, each retaining its original <=600s deadline.
        host_process = subprocess.Popen([sys.executable, "-B", "-m", "followups.phase3b_seq2_v1.boundary_contract",  # nosec B603
             "host", "--output", str(OUT / "fixture")], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        processes.append(host_process)
        core_process = subprocess.Popen(["docker", "start", "--attach", core], cwd=ROOT, env=env,  # nosec B603,B607: existing inspected Docker CLI; exact owned ID
             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        processes.append(core_process)
        deadline = time.monotonic() + 1800
        for label, process in (("core", core_process), ("host", host_process)):
            output, error = process.communicate(timeout=max(1, deadline - time.monotonic()))
            save(OUT / (label + "-execution.json"), {"exit_code": process.returncode,
                 "output": output.decode("utf-8", errors="replace"), "error": error.decode("utf-8", errors="replace")})
            if process.returncode:
                raise ValueError("real boundary " + label + " failed")
        passed = True
    except BaseException as exc:
        save(OUT / "failure.json", {"passed": False, "exception_type": type(exc).__name__,
             "exception_message": str(exc), "traceback": traceback.format_exc(), **partial(exc)})
    finally:
        for process in processes:
            if process.poll() is None:
                try:
                    process.kill()
                    process.communicate(timeout=15)
                except (OSError, subprocess.TimeoutExpired):
                    cleanup_passed = False
        cleanup = []
        for owner in owners:
            state = run(["docker", "inspect", "--format", "{{json .State.Running}}", owner])
            stopped = None
            if state["exit_code"] != 0 or state["output"].strip() == "true":
                stopped = run(["docker", "stop", "--time", "10", owner], 30)
            removed = run(["docker", "rm", owner])
            absent = run(["docker", "inspect", "--format", "{{json .State.Running}}", owner])
            valid = removed["exit_code"] == 0 and absent["exit_code"] != 0 and "no such object" in absent["error"].casefold()
            cleanup_passed &= valid
            cleanup.append({"owner": owner, "terminal": state, "stop": stopped,
                            "remove": removed, "absence": absent, "passed": valid})
        save(OUT / "cleanup.json", {"passed": cleanup_passed, "owners": cleanup})
        exporters = []
        prepared_path = OUT / "fixture/prepared.json"
        if prepared_path.is_file():
            try:
                prepared = json.loads(prepared_path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                prepared = {}
                cleanup_passed = False
            study_id = prepared.get("study_sha256", "")
            if len(study_id) != 64 or any(c not in "0123456789abcdef" for c in study_id):
                cleanup_passed = False
            else:
                for checkpoint in ("first-pair", "closure"):
                    directory = ROOT / "runs/phase3b-seq2-v1/visibility-exports" / study_id / "mock" / checkpoint / "boundary-contract"
                    create_path = directory / "create.json"
                    if not create_path.is_file():
                        continue
                    proof = {"checkpoint": checkpoint, "passed": False}
                    try:
                        created = json.loads(create_path.read_text(encoding="utf-8"))
                        owner = created.get("stdout", "").strip()
                        proof = {"checkpoint": checkpoint, "passed": False}
                        if created.get("exit_code") == 0 and len(owner) == 64 and all(c in "0123456789abcdef" for c in owner):
                            proof["owner"] = owner
                            actual = run(["docker", "inspect", "--format", "{{json .Image}}", owner], 15)
                            proof["image"] = actual
                            if actual["exit_code"] == 0 and actual["output"].strip('"\r\n') == "sha256:25b07e51ef9ae948e7f3de5314b91b1ec4c120219ceebfde4b4064525c40a03d":
                                proof["stop"] = run(["docker", "stop", "--time", "10", owner], 30)
                                proof["remove"] = run(["docker", "rm", owner], 30)
                            absent = run(["docker", "inspect", "--format", "{{json .State.Running}}", owner], 15)
                            proof["absence"] = absent
                            proof["passed"] = absent["exit_code"] != 0 and "no such object" in absent["error"].casefold()
                    except (ValueError, OSError) as exc:
                        proof.update(error_type=type(exc).__name__, error_message=str(exc))
                    cleanup_passed &= proof["passed"]
                    exporters.append(proof)
        save(OUT / "exporter-cleanup.json", {"passed": cleanup_passed, "owners": exporters})
    result = {"kind": "p3b-s2-c2-real-boundary-result-v1", "passed": passed and cleanup_passed,
              "real_provider_calls": 0, "generations": 0, "cleanup_passed": cleanup_passed}
    save(OUT / "result.json", result)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
