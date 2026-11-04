"""Owned BD1 unit commands, source authentication and finite admission counters."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import stat
import subprocess  # nosec B404
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from followups.phase3b_seq2_v1 import verify
from followups.phase3b_seq2_v1.support import ROOT

HERE = ROOT / "evidence/phase3b-bd1-v1"
OUT = ROOT / "runs/phase3b-seq2-v1/bd1-unit-preflight-v1"
ENTRY = "evidence/phase3b-seq2-c2-v1/composed_acceptance.py"
PRIVATE = {".env", "auth.json", "credentials.json", "credential-binding.json", ".writer.lock",
           "__pycache__", ".cache", ".mypy_cache", ".ruff_cache", ".pytest_cache", ".git"}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def source_bytes(name):
    rel = Path(name)
    if rel.is_absolute() or ".." in rel.parts or any(
            p.casefold() in PRIVATE or "stdout" in p.casefold() or "stderr" in p.casefold() for p in rel.parts):
        raise ValueError("excluded BD1 source before metadata")
    current = ROOT
    for part in rel.parts:
        current /= part
        info = current.lstat()
        if current.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("linked BD1 source")
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("nonordinary BD1 source")
    return current.read_bytes()


def inventory():
    result = []
    folder = ROOT / "followups/phase3b_seq2_v1"
    for name in sorted(os.listdir(folder)):
        if not name.startswith("test") or not name.endswith(".py"):
            continue
        tree = ast.parse(source_bytes("followups/phase3b_seq2_v1/" + name))
        for cls in sorted((n for n in tree.body if isinstance(n, ast.ClassDef)), key=lambda n: n.name):
            if not any(isinstance(b, ast.Attribute) and b.attr == "TestCase" for b in cls.bases):
                continue
            for method in sorted(n.name for n in cls.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test")):
                result.append("followups.phase3b_seq2_v1." + name[:-3] + "." + cls.name + "." + method)
    return result


def freeze(mode, number, profile_imports=False):
    output = OUT / (mode + "-" + str(number))
    if output.exists():
        raise ValueError("BD1 invocation root already exists")
    original = json.loads(source_bytes("evidence/phase3b-bd1-v1/baseline/source.json"))
    originals = json.loads(source_bytes("evidence/phase3b-bd1-v1/baseline/preservation-receipt.json"))["canonical_originals"]
    names = [name for name in original["files"] if name not in originals]
    names += ["evidence/phase3b-bd1-v1/authority.json", "evidence/phase3b-bd1-v1/unit_preflight.py",
              "evidence/phase3b-bd1-v1/run_units.py", "specifications/amendments/phase3b-bootstrap-diagnostic-1.0.md",
              "followups/phase3b_seq2_v1/test_z_bd1_diagnostics_s2.py"]
    files = {name: sha(source_bytes(name)) for name in sorted(set(names))}
    ids = inventory()
    if mode == "bootstrap":
        selected = [name for name in ids if ".test_bootstrap.BootstrapTests." in name]
    elif mode == "windows":
        selected = [name for name in ids if "test_actual_windows_bootstrap_" in name
                    or name.endswith("test_host_evidence_writer_outside_runtime_base_is_exclusive")]
    else:
        selected = ids
    source_sha = sha(json.dumps(files, sort_keys=True, separators=(",", ":")).encode())
    bindings = {"source_sha256": source_sha, "study_sha256": sha(("BD1-unit-only:" + source_sha).encode()),
                "runtime_sha256": verify.IMAGE.removeprefix("sha256:"),
                "policy_sha256": sha(source_bytes("specifications/amendments/phase3b-bootstrap-diagnostic-1.0.md")),
                "launcher_sha256": files[ENTRY]}
    output.mkdir(parents=True)
    manifest = {"kind": "phase3b-bd1-prospective-unit-manifest-v1", "mode": mode, "number": number,
        "source_sha256": source_sha, "files": files, "discovered_ids": ids, "selected_ids": selected,
        "unit_bindings": bindings, "native_study_or_release_identity": False,
        "command": ["python", "-B", "/workspace/" + ENTRY, "--phase", "units", "--unit-mode", mode,
                    "--output", "/results/" + output.relative_to(ROOT / "runs").as_posix()],
        "campaign_prepare_omitted": True, "first_four_discovery_order_preserved": selected == ids[:4] if mode == "bootstrap" else None}
    manifest["instrumented_import_profile"] = profile_imports
    if profile_imports:
        manifest["command"][1:1] = ["-X", "importtime"]
        manifest["diagnostic_question"] = "Which completed import events are observable before the unchanged spawned-worker wait expires?"
        manifest["interpretation_limit"] = "Profiling changes startup cost; events mix parent, worker and resource-tracker without PID attribution. No unprofiled or historical bottleneck is established."
    verify.save(output / "manifest.json", manifest)
    if mode != "windows":
        runtime_output = output / "runtime" / "bd1-unit-preflight-v1" / output.name
        runtime_output.mkdir(parents=True)
        verify.save(runtime_output / "manifest.json", manifest)
    return output, manifest


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("action", choices=("freeze", "run"))
    parser.add_argument("mode", choices=("bootstrap", "suite", "windows"))
    parser.add_argument("number", type=int, choices=(1, 2, 3, 4))
    parser.add_argument("--profile-imports", action="store_true")
    args = parser.parse_args()
    if args.profile_imports and (args.action != "freeze" or args.mode != "bootstrap"):
        raise ValueError("import profiling is only a prospective standalone diagnostic")
    if args.action == "freeze":
        output, manifest = freeze(args.mode, args.number, args.profile_imports)
        print(json.dumps({"manifest": str(output / "manifest.json"), "source_sha256": manifest["source_sha256"],
                          "discovered": len(manifest["discovered_ids"]), "selected": len(manifest["selected_ids"])}))
        return 0
    output = OUT / (args.mode + "-" + str(args.number))
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    review = json.loads((output / "prospective-review.json").read_text(encoding="utf-8"))
    if review.get("passed") is not True or review.get("manifest_sha256") != sha((output / "manifest.json").read_bytes()):
        raise ValueError("actual BD1 command is not prospectively reviewed")
    for name, expected in manifest["files"].items():
        if sha(source_bytes(name)) != expected:
            raise ValueError("reviewed source drift")
    admissions = HERE / "admissions"
    admissions.mkdir(exist_ok=True)
    limit = 3 if args.mode == "bootstrap" else 2
    prior = [name for name in os.listdir(admissions) if name.startswith(args.mode + "-") and name.endswith(".json")]
    if len(prior) >= limit or (admissions / output.with_suffix(".json").name).exists():
        raise ValueError("BD1 invocation cap exhausted")
    if args.mode == "suite":
        for name in prior:
            if json.loads((admissions / name).read_text(encoding="utf-8"))["source_sha256"] == manifest["source_sha256"]:
                raise ValueError("full suite already attempted on this development source")
    verify.save(admissions / output.with_suffix(".json").name, {"mode": args.mode, "source_sha256": manifest["source_sha256"],
        "at_utc": datetime.now(timezone.utc).isoformat(), "manifest_sha256": sha((output / "manifest.json").read_bytes())})
    if args.mode == "windows":
        environment = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "PATHEXT") if k in os.environ}
        environment.update(PYTHONPATH=os.pathsep.join(str(p) for p in (ROOT, ROOT / "src", ROOT / ".upstream/harness2")),
            PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1", BUDDHA2_OUTPUT_ROOT=str(ROOT / "runs"))
        command = [sys.executable, "-B", str(ROOT / ENTRY), "--phase", "units", "--unit-mode", "windows", "--output", str(output)]
        result = verify.execute(command, timeout=7200, environment=environment)
        verify.save(output / "execution.json", result)
        return int(result["exit_code"])
    command = verify.container_args(output, mode="inside")
    runtime_root = output / "runtime"
    original_mount = f"type=bind,source={ROOT / 'runs' / 'phase3b-seq2-v1'},target=/results/phase3b-seq2-v1"
    command[command.index(original_mount)] = f"type=bind,source={runtime_root},target=/results/phase3b-seq2-v1"
    command[2:2] = ["--log-driver", "none"]
    command[command.index(verify.IMAGE) + 1:] = manifest["command"][1:]
    owner = None
    try:
        created = verify.execute(command, timeout=60)
        verify.save(output / "create.json", created)
        owner = created["stdout"].strip()
        if created["exit_code"] or len(owner) != 64 or any(c not in "0123456789abcdef" for c in owner):
            owner = None
            raise ValueError("no exact BD1 container owner")
        actual = json.loads(verify.execute(["docker", "inspect", owner], timeout=60)["stdout"])[0]
        host = actual["HostConfig"]
        mounts = {(m["Source"], m["Destination"], m["RW"]) for m in actual["Mounts"]}
        if (actual["Image"] != verify.IMAGE or host["NetworkMode"] != "none" or not host["ReadonlyRootfs"]
            or mounts != {(str(ROOT), "/workspace", False), (str(runtime_root), "/results/phase3b-seq2-v1", True)}
            or host["Privileged"] or actual["State"]["Running"]
            or host["Memory"] != 4294967296 or host["NanoCpus"] != 2000000000 or host["PidsLimit"] != 256
            or host["CapDrop"] != ["ALL"] or host["SecurityOpt"] not in (["no-new-privileges"], ["no-new-privileges:true"])
            or host["Tmpfs"] != {"/tmp": "rw,nosuid,nodev,size=1073741824,mode=1777"}  # nosec B108
            or host["LogConfig"]["Type"] != "none" or actual["Config"]["Cmd"] != manifest["command"][1:]):
            raise ValueError("actual BD1 containment or command differs")
        verify.save(output / "inspection.json", {"passed": True, "owner": owner, "image": actual["Image"],
            "mounts": actual["Mounts"], "argv": actual["Config"]["Cmd"], "network": "none", "readonly_root": True})
        result = verify.execute(["docker", "start", "--attach", owner], timeout=120 if args.mode == "bootstrap" else 7200)
        if manifest.get("instrumented_import_profile") is True:
            events = []
            unmatched = 0
            for line in result["stderr"].splitlines():
                match = re.fullmatch(r"import time:\s+(\d+)\s*\|\s*(\d+)\s*\|\s*([A-Za-z_][A-Za-z0-9_.]*)\s*", line)
                if match:
                    events.append({"module": match[3], "reported_self_microseconds": int(match[1]),
                                   "reported_cumulative_microseconds": int(match[2])})
                else:
                    unmatched += 1
            if len(events) > 20000:
                raise ValueError("bounded import-event inventory exceeded")
            verify.save(output / "import-profile.json", {"instrumented": True, "events": events,
                "unmatched_line_count": unmatched, "raw_stream_retained": False,
                "process_attribution_established": False, "profiling_alters_startup_timing": True,
                "interpretation_limit": manifest["interpretation_limit"]})
            result = {**result, "stderr": "", "stderr_bytes": len(result["stderr"].encode()),
                      "stderr_sha256": sha(result["stderr"].encode()), "raw_stderr_retained": False}
        verify.save(output / "execution.json", result)
        return int(result["exit_code"])
    finally:
        if owner:
            cleanup_deadline = time.monotonic() + 60
            def cleanup_call(command, requested):
                remaining = cleanup_deadline - time.monotonic()
                if remaining <= 0:
                    return {"exit_code": 124, "stdout": "", "stderr": "cleanup budget exhausted"}
                try:
                    return verify.execute(command, timeout=min(requested, remaining))
                except (subprocess.TimeoutExpired, OSError) as exc:
                    return {"exit_code": 124, "stdout": "", "stderr": "cleanup command failed",
                            "exception_type": type(exc).__name__}
            terminal = cleanup_call(["docker", "inspect", "--format", "{{json .State.Running}}", owner], 15)
            cleanup = {"owner": owner, "terminal": terminal}
            if terminal["exit_code"] == 0 and terminal["stdout"].strip() == "true":
                cleanup["stop"] = cleanup_call(["docker", "stop", "--time", "10", owner], 30)
            cleanup["remove"] = cleanup_call(["docker", "rm", owner], 30)
            cleanup["absence"] = cleanup_call(["docker", "inspect", "--format", "{{json .State.Running}}", owner], 15)
            cleanup["passed"] = (cleanup["remove"]["exit_code"] == 0 and cleanup["absence"]["exit_code"] != 0
                                  and "no such object" in cleanup["absence"]["stderr"].casefold())
            verify.save(output / "cleanup.json", cleanup)
            if not cleanup["passed"]:
                raise ValueError("BD1 exact owner cleanup unconfirmed")


if __name__ == "__main__":
    raise SystemExit(main())
