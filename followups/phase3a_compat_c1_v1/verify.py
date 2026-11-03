"""One reproducible offline verification command; no credentials or live route."""
from __future__ import annotations

import argparse
import json
import os
import shutil

# Docker/test orchestration uses fixed argv lists and never a shell.
import subprocess  # nosec B404
import sys
import tempfile
import time
import unittest
from pathlib import Path

IMAGE = "sha256:8792a096b4881d47ab19cc7cbf6a74a232f9ff7cedc978fe93f902a71522d4f2"
ROOT = Path(__file__).resolve().parents[2]


def host_output(value: str) -> Path:
    root = ROOT / "runs/phase3a-compat-c1-v1"
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    if ".." in path.parts or not path.is_relative_to(root) or path == root:
        raise ValueError("verification output must be new and beneath the C1 run directory")
    if any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()) for p in (path, *path.parents)):
        raise ValueError("verification output cannot traverse links")
    if path.exists():
        raise ValueError("verification evidence already exists; use a fresh output")
    return path


def host(value: str) -> int:
    output = host_output(value)
    docker = shutil.which("docker")
    if docker is None:
        raise ValueError("the existing Docker runtime is required")
    inspected = subprocess.check_output([docker, "image", "inspect", "--format", "{{.Id}}", IMAGE], cwd=ROOT)  # nosec B603
    if inspected.decode().strip() != IMAGE:
        raise ValueError("the existing pinned image is required; this command never pulls or rebuilds")
    output.mkdir(parents=True, exist_ok=False)
    # This is a private bounded container tmpfs, not host temporary storage.
    temporary_mount = "/tmp:rw,nosuid,nodev,size=1073741824,mode=1777"  # nosec B108
    args = [docker, "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--pids-limit", "256", "--memory", "4g", "--cpus", "2",
        "--entrypoint", "python", "--mount", f"type=bind,source={ROOT},target=/workspace,readonly",
        "--mount", f"type=bind,source={output},target=/export",
        "--tmpfs", "/results:rw,nosuid,nodev,size=2147483648,mode=1777",
        "--tmpfs", temporary_mount, "-w", "/workspace"]
    env = {"PYTHONPATH": "/workspace/src:/workspace/.upstream/harness2:/workspace",
        "BUDDHA2_OUTPUT_ROOT": "/results", "BUDDHA2_IMAGE_ID": IMAGE,
        "PHASE3A_OPENCODE": "/opt/phase3a-opencode", "PHASE3A_BUN": "/usr/local/bin/bun",
        "PYTHONDONTWRITEBYTECODE": "1", "HF_HUB_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1", "OMP_NUM_THREADS": "1"}
    for key, value in env.items():
        args += ["-e", key + "=" + value]
    args += [IMAGE, "-B", "-m", "followups.phase3a_compat_c1_v1.verify", "--inside"]
    (output / "docker-command.json").write_text(json.dumps(args, indent=2) + "\n", encoding="utf-8")
    started = time.monotonic()
    with (output / "container.log").open("x", encoding="utf-8") as log:
        result = subprocess.run(args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)  # nosec B603
    record = {"kind": "phase3a-c1-host-execution-v1", "exit_code": result.returncode,
        "elapsed_seconds": time.monotonic() - started, "image": IMAGE, "network": "none",
        "source_mount": "new project read-only", "export_mount": str(output),
        "host_keys_forwarded": False, "provider_calls_authorized": False}
    (output / "host-execution.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record))
    return result.returncode


def export_demo(source: Path, output: Path) -> None:
    """Export public fixture artifacts only; skip ownership locks before stat/read."""
    for directory, dirs, files in os.walk(source, followlinks=False):
        relative = Path(directory).relative_to(source)
        dirs[:] = [name for name in dirs if name not in {".phase3a-home", "__pycache__"}]
        if any((Path(directory) / name).is_symlink() for name in dirs):
            raise ValueError("linked fixture export directory")
        (output / relative).mkdir(parents=True, exist_ok=True)
        for name in files:
            if name in {"credential-binding.json", ".writer.lock", ".env", "auth.json", "credentials.json"}:
                continue
            path = Path(directory) / name
            if path.is_symlink() or not path.is_file():
                raise ValueError("nonordinary fixture export file")
            shutil.copyfile(path, output / relative / name)


def inside() -> int:
    from buddha2.artifacts import digest, write_bytes_once, write_once

    from . import cli, contract, support
    cli._offline_runtime()
    output = Path("/export")
    source = support.source_identity()
    before = support.preservation()
    write_once(output / "source-before.json", source)
    write_once(output / "preservation-before.json", before)
    started = time.monotonic()
    commands = [
        [sys.executable, "-B", "-m", "ruff", "check", "--no-cache", "followups/phase3a_compat_c1_v1"],
        [sys.executable, "-B", "-m", "mypy", "--explicit-package-bases", "--follow-imports", "silent",
         "--no-incremental", "--cache-dir", str(Path(tempfile.gettempdir()) / "c1-mypy-cache"),
         "followups/phase3a_compat_c1_v1"],
        [sys.executable, "-B", "-m", "bandit", "-q", "-r", "followups/phase3a_compat_c1_v1",
         "-x", "followups/phase3a_compat_c1_v1/tests"],
    ]
    static = []
    for index, command in enumerate(commands):
        with (output / f"static-{index}.log").open("x", encoding="utf-8") as log:
            result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)  # nosec B603
        static.append({"command": command, "exit_code": result.returncode})
    write_once(output / "static.json", {"checks": static, "passed": all(row["exit_code"] == 0 for row in static)})
    if not all(row["exit_code"] == 0 for row in static):
        write_once(output / "result.json", {"kind": "phase3a-c1-contained-verification-v1", "passed": False,
            "source_sha256": source["sha256"], "stop": "static-check-failed", "provider_calls": 0})
        return 1
    demo_path = Path("/results/phase3a-compat-c1-v1/demo")
    try:
        demo = cli.demo(demo_path)
    finally:
        if demo_path.exists():
            export_demo(demo_path, output / "demo")
    # The unchanged four-prompt workflow matrix is intentionally not repeated.
    parents = ("strategy", "native", "editor", "editor_terminal", "editor_shape", "editor_attacks",
               "accounting", "transport")
    names = ["followups.phase3a_v1.tests.test_" + name for name in parents]
    names += ["followups.phase3a_compat_c1_v1.tests." + path.stem for path in
              sorted((ROOT / "followups/phase3a_compat_c1_v1/tests").glob("test_*.py"))]
    suite = unittest.defaultTestLoader.loadTestsFromNames(names)
    with (output / "tests.log").open("x", encoding="utf-8") as log:
        tested = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    write_once(output / "tests.json", {"modules": names, "tests": tested.testsRun,
        "failures": len(tested.failures), "errors": len(tested.errors), "skipped": len(tested.skipped),
        "passed": tested.wasSuccessful(), "excluded": "unchanged four-prompt workflow matrix and old launcher/grant tests"})
    history = ROOT / "runs/phase3a-r2-v1/17f35cf72cad95351e726cd9f02824be78db35a0a16c3f83db9e7bae9d762032/live/search"
    contexts = []
    for pilot in ("p3a-01", "p3a-02", "p3a-03", "p3a-04"):
        native = next((history / pilot / "adaptive/native").glob("*/*/context"))
        for label in ("inv1", "dom1", "agg1"):
            raw = next((history / pilot / "adaptive/editor-audit").glob(label + ".a1.*.mission.md"))
            prepared = contract.prepare_contract(raw.read_text(encoding="utf-8"), native / label, label + ".a1")
            target = output / "conformance" / pilot / label
            write_once(target / "manifest.json", prepared["manifest"])
            write_bytes_once(target / "native-mission.md", raw.read_bytes())
            write_bytes_once(target / "effective-mission.md", prepared["effective_mission"].encode())
            write_bytes_once(target / "C1_INDEX.md", prepared["index_text"].encode())
            contexts.append({"pilot": pilot, "label": label, "manifest_sha256": prepared["manifest"]["sha256"]})
    write_once(output / "conformance.json", {"kind": "phase3a-c1-context-conformance-v1",
        "source_sha256": source["sha256"], "contexts": contexts, "count": len(contexts), "passed": len(contexts) == 12})
    after = support.preservation()
    after_source = support.source_identity()
    write_once(output / "source-after.json", after_source)
    write_once(output / "preservation-after.json", after)
    record = {"kind": "phase3a-c1-contained-verification-v1", "source_sha256": source["sha256"],
        "passed": bool(demo) and tested.wasSuccessful() and source == after_source and before == after
                  and all(row["exit_code"] == 0 for row in static),
        "tests": tested.testsRun, "contexts": len(contexts), "demo": demo,
        "elapsed_seconds": time.monotonic() - started, "source_unchanged": source == after_source,
        "closed_evidence_unchanged": before == after, "network": "none", "image": IMAGE,
        "provider_calls": 0, "real_credentials_used": False}
    record["sha256"] = digest(record)
    write_once(output / "result.json", record)
    print(json.dumps({key: record[key] for key in ("passed", "tests", "contexts", "source_sha256", "elapsed_seconds")}))
    return 0 if record["passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", help="fresh directory beneath runs/phase3a-compat-c1-v1")
    parser.add_argument("--inside", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.inside:
        return inside()
    if not args.output:
        parser.error("--output is required")
    return host(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
