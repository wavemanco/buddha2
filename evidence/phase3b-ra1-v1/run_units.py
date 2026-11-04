"""RA1 current-source unit preflight; no workflow or standalone bootstrap retries."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess  # nosec B404
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / ".upstream/harness2")]

from followups.phase3b_seq2_v1 import verify  # noqa: E402
from followups.phase3b_seq2_v1.support import read, release_authority, source_identity  # noqa: E402

HERE = ROOT / "evidence/phase3b-ra1-v1"
OUT = ROOT / "runs/phase3b-seq2-v1/ra1-unit-preflight-v1"
ENTRY = "evidence/phase3b-seq2-c2-v1/composed_acceptance.py"


def helper():
    spec = importlib.util.spec_from_file_location("bd1_inventory_primitives", ROOT / "evidence/phase3b-bd1-v1/run_units.py")
    if spec is None or spec.loader is None:
        raise ValueError("reviewed inventory primitives unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def admission_history():
    directory = HERE / "preflight-admissions"
    directory.mkdir(exist_ok=True)
    allowed = {f"{mode}-{number}.json" for mode in ("suite", "windows") for number in (1, 2, 3)}
    rows = []
    primitives = helper()
    for name in sorted(os.listdir(directory)):
        if name not in allowed:
            raise ValueError("foreign/private preflight admission name rejected before metadata")
        target = directory / name
        primitives.source_bytes(target.relative_to(ROOT).as_posix())
        row = read(target)
        mode, number = name.removesuffix(".json").split("-")
        manifest_path = OUT / (mode + "-" + number) / "manifest.json"
        manifest_raw = primitives.source_bytes(manifest_path.relative_to(ROOT).as_posix())
        manifest = read(manifest_path)
        if (set(row) != {"mode", "source_sha256", "at_utc", "manifest_sha256", "preflight_set_counted_at_Linux_admission"}
                or row["mode"] != mode or row["source_sha256"] != manifest.get("source_sha256")
                or row["manifest_sha256"] != sha(manifest_raw)
                or manifest.get("mode") != mode or manifest.get("number") != int(number)
                or row["preflight_set_counted_at_Linux_admission"] is not True
                or datetime.fromisoformat(row["at_utc"]).tzinfo is None):
            raise ValueError("preflight admission history changed or is foreign")
        rows.append(row)
    return rows


def freeze(mode, number):
    release_authority()
    output = OUT / (mode + "-" + str(number))
    if output.exists():
        raise ValueError("RA1 preflight output already exists")
    source = source_identity()
    primitives = helper()
    # Classification in source_identity authenticates canonical historical originals;
    # preflight never copies or directly reopens those stream paths.
    files = {name: expected for name, expected in source["files"].items()
             if not any("stdout" in part.casefold() or "stderr" in part.casefold() for part in Path(name).parts)}
    ids = primitives.inventory()
    selected = [name for name in ids if "test_actual_windows_bootstrap_" in name
                or name.endswith("test_host_evidence_writer_outside_runtime_base_is_exclusive")] if mode == "windows" else ids
    bindings = {"source_sha256": source["sha256"], "study_sha256": sha(("RA1-unit-only:" + source["sha256"]).encode()),
        "runtime_sha256": verify.IMAGE.removeprefix("sha256:"),
        "policy_sha256": sha(primitives.source_bytes("specifications/amendments/phase3b-release-acceptance-1.0.md")),
        "launcher_sha256": files[ENTRY]}
    manifest = {"kind": "phase3b-ra1-prospective-unit-manifest-v1", "mode": mode, "number": number,
        "source_sha256": source["sha256"], "files": files, "discovered_ids": ids, "selected_ids": selected,
        "unit_bindings": bindings, "native_study_or_release_identity": False,
        "command": ["python", "-B", "/workspace/" + ENTRY, "--phase", "units", "--unit-mode", mode,
                    "--output", "/results/" + output.relative_to(ROOT / "runs").as_posix()],
        "campaign_prepare_omitted": True, "instrumented_import_profile": False,
        "container_environment": read(ROOT / "runs/phase3b-seq2-v1/ra1-component-v3/result.json")["container_environment"]}
    output.mkdir(parents=True)
    verify.save(output / "manifest.json", manifest)
    if mode == "suite":
        runtime = output / "runtime/ra1-unit-preflight-v1" / output.name
        runtime.mkdir(parents=True)
        verify.save(runtime / "manifest.json", manifest)
    return output, manifest


def run(mode, number):
    release_authority()
    output = OUT / (mode + "-" + str(number))
    manifest = read(output / "manifest.json")
    review = read(output / "prospective-review.json")
    if (review.get("passed") is not True or review.get("reviewer") != "/root/ra1_path_review"
            or review.get("manifest_sha256") != sha((output / "manifest.json").read_bytes())
            or source_identity()["sha256"] != manifest["source_sha256"]):
        raise ValueError("current RA1 preflight is not prospectively reviewed or source changed")
    primitives = helper()
    for name, expected in manifest["files"].items():
        if sha(primitives.source_bytes(name)) != expected:
            raise ValueError("RA1 preflight source drift")
    admissions = HERE / "preflight-admissions"
    prior = [row for row in admission_history() if row["mode"] == "suite"]
    if mode == "suite":
        if len(prior) >= 3 or any(row["source_sha256"] == manifest["source_sha256"] for row in prior):
            raise ValueError("RA1 preflight set cap or same-revision allowance exhausted")
    else:
        suite = OUT / ("suite-" + str(number)) / "runtime/ra1-unit-preflight-v1" / ("suite-" + str(number))
        result = read(suite / "result.json")
        if result.get("passed") is not True or result.get("source_sha256") != manifest["source_sha256"]:
            raise ValueError("matching completed Linux set required before Windows")
    verify.save(admissions / (output.name + ".json"), {"mode": mode, "source_sha256": manifest["source_sha256"],
        "at_utc": datetime.now(timezone.utc).isoformat(), "manifest_sha256": sha((output / "manifest.json").read_bytes()),
        "preflight_set_counted_at_Linux_admission": True})
    if mode == "windows":
        env = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "PATHEXT") if k in os.environ}
        env.update(PYTHONPATH=os.pathsep.join(str(p) for p in (ROOT, ROOT / "src", ROOT / ".upstream/harness2")),
            PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1", BUDDHA2_OUTPUT_ROOT=str(ROOT / "runs"))
        result = verify.execute([sys.executable, "-B", str(ROOT / ENTRY), "--phase", "units", "--unit-mode", mode,
                                 "--output", str(output)], timeout=7200, environment=env)
        verify.save(output / "execution.json", result)
        return int(result["exit_code"])
    args = verify.container_args(output, mode="inside")
    runtime = output / "runtime"
    mount = f"type=bind,source={ROOT / 'runs/phase3b-seq2-v1'},target=/results/phase3b-seq2-v1"
    args[args.index(mount)] = f"type=bind,source={runtime},target=/results/phase3b-seq2-v1"
    args[2:2] = ["--log-driver", "none"]
    args[args.index(verify.IMAGE) + 1:] = manifest["command"][1:]
    owner = None
    try:
        created = verify.execute(args, timeout=60)
        verify.save(output / "create.json", created)
        owner = created["stdout"].strip()
        if created["exit_code"] or len(owner) != 64 or any(c not in "0123456789abcdef" for c in owner):
            owner = None
            raise ValueError("no exact RA1 preflight owner")
        actual = json.loads(verify.execute(["docker", "inspect", owner], timeout=60)["stdout"])[0]
        host = actual["HostConfig"]
        mounts = {(m["Source"], m["Destination"], m["RW"]) for m in actual["Mounts"]}
        if (actual["Image"] != verify.IMAGE or host["NetworkMode"] != "none" or not host["ReadonlyRootfs"]
                or mounts != {(str(ROOT), "/workspace", False), (str(runtime), "/results/phase3b-seq2-v1", True)}
                or host["Privileged"] or actual["State"]["Running"]
                or host["Memory"] != 4294967296 or host["NanoCpus"] != 2000000000 or host["PidsLimit"] != 256
                or host["CapDrop"] != ["ALL"] or host["SecurityOpt"] not in (["no-new-privileges"], ["no-new-privileges:true"])
                or host["Tmpfs"] != {"/tmp": "rw,nosuid,nodev,size=1073741824,mode=1777"}  # nosec B108
                or host["LogConfig"]["Type"] != "none" or actual["Config"]["Cmd"] != manifest["command"][1:]
                or actual["Config"]["Entrypoint"] != ["python"] or actual["Config"]["WorkingDir"] != "/workspace"
                or sorted(actual["Config"]["Env"]) != manifest["container_environment"]):
            raise ValueError("actual RA1 preflight containment differs")
        verify.save(output / "inspection.json", {"passed": True, "owner": owner, "image": actual["Image"],
            "mounts": actual["Mounts"], "argv": actual["Config"]["Cmd"], "network": "none", "readonly_root": True})
        result = verify.execute(["docker", "start", "--attach", owner], timeout=7200)
        verify.save(output / "execution.json", result)
        return int(result["exit_code"])
    finally:
        if owner:
            deadline = time.monotonic() + 60
            def settle(command, requested):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return {"exit_code": 124, "stdout": "", "stderr": "cleanup budget exhausted"}
                try:
                    return verify.execute(command, timeout=min(requested, remaining))
                except (subprocess.TimeoutExpired, OSError) as exc:
                    return {"exit_code": 124, "stdout": "", "stderr": "cleanup command failed", "exception_type": type(exc).__name__}
            terminal = settle(["docker", "inspect", "--format", "{{json .State.Running}}", owner], 15)
            cleanup = {"owner": owner, "terminal": terminal}
            if terminal["exit_code"] == 0 and terminal["stdout"].strip() == "true":
                cleanup["stop"] = settle(["docker", "stop", "--time", "10", owner], 30)
            cleanup["remove"] = settle(["docker", "rm", owner], 30)
            cleanup["absence"] = settle(["docker", "inspect", "--format", "{{json .State.Running}}", owner], 15)
            cleanup["passed"] = cleanup["remove"]["exit_code"] == 0 and cleanup["absence"]["exit_code"] != 0 and "no such object" in cleanup["absence"]["stderr"].casefold()
            verify.save(output / "cleanup.json", cleanup)
            if not cleanup["passed"]:
                raise ValueError("RA1 preflight exact owner cleanup unconfirmed")


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("action", choices=("freeze", "run"))
    parser.add_argument("mode", choices=("suite", "windows"))
    parser.add_argument("number", type=int, choices=(1, 2, 3))
    args = parser.parse_args()
    if args.action == "freeze":
        output, manifest = freeze(args.mode, args.number)
        print(json.dumps({"manifest": str(output / "manifest.json"), "source_sha256": manifest["source_sha256"],
            "discovered": len(manifest["discovered_ids"]), "selected": len(manifest["selected_ids"])}))
        return 0
    return run(args.mode, args.number)


if __name__ == "__main__":
    raise SystemExit(main())
