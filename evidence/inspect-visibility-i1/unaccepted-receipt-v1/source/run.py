"""Run only I1 tests and two passive imports inside isolated Linux containers."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess  # nosec B404
from pathlib import Path

from .importer import CASES
from .paths import checked_path as boundary_path
from .setup import HERE, IMAGE, ROOT, save


def execute(args: list[str]) -> dict:
    result = subprocess.run(args, cwd=ROOT, text=True, encoding="utf-8", errors="replace",
                            capture_output=True, check=False)  # nosec B603
    return {"command": args, "exit_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def checked_path(path: Path) -> Path:
    return boundary_path(path, ROOT)


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = boundary_path(args.output, ROOT / "runs" / "inspect-visibility-i1", missing=True)
    if out.exists():
        raise ValueError("fresh output under runs/inspect-visibility-i1 required")
    checked_path(out.parent)
    inputs = ROOT / "runs" / "phase3a-history-compat-h1" / "verification-v3"
    mounts = ["--mount", f"type=bind,source={checked_path(HERE)},target=/i1,readonly"]
    before = {}
    for case, files in CASES.items():
        for filename, digest in files.items():
            source = checked_path(inputs / case / filename)
            actual = hashlib.sha256(source.read_bytes()).hexdigest()
            if actual != digest:
                raise ValueError("input changed before Docker creation")
            before[f"{case}/{filename}"] = actual
            mounts += ["--mount", f"type=bind,source={source},target=/inputs/{case}/{filename},readonly"]
    out.mkdir(parents=True)
    mounts += ["--mount", f"type=bind,source={checked_path(out)},target=/out"]
    inspect_image = execute(["docker", "image", "inspect", IMAGE])
    if inspect_image["exit_code"]:
        raise RuntimeError("Inspect image missing; run isolated setup first")
    image = json.loads(inspect_image["stdout"])[0]["Id"]
    save(out / "image.json", {"image_id": image})
    commands = [["python", "-B", "-m", "i1.tests"],
                ["python", "-B", "-m", "i1.importer", "--inputs", "/inputs", "--output", "/out/replay-1"],
                ["python", "-B", "-m", "i1.importer", "--inputs", "/inputs", "--output", "/out/replay-2"]]
    for index, command in enumerate(commands):
        name = f"buddha2-inspect-i1-{out.name}-{index}"
        create = execute(["docker", "create", "--name", name, "--network", "none", "--read-only",
                          "--tmpfs", "/tmp:rw,nosuid,nodev,size=268435456", "--cap-drop", "ALL",  # nosec B108 - disposable private container tmpfs
                          "--security-opt", "no-new-privileges", *mounts, "--env", "PYTHONPATH=/", "--workdir", "/out", image, *command])
        save(out / f"{index}-create.json", create)
        if create["exit_code"]:
            raise RuntimeError("container creation failed")
        try:
            inspection = execute(["docker", "inspect", name])
            save(out / f"{index}-actual-container.json", inspection)
            detail = json.loads(inspection["stdout"])[0]
            if detail["HostConfig"]["NetworkMode"] != "none" or not detail["HostConfig"]["ReadonlyRootfs"]:
                raise ValueError("actual containment differs")
            if len(detail["Mounts"]) != 6 or sum(m["RW"] for m in detail["Mounts"]) != 1:
                raise ValueError("actual mount whitelist differs")
            result = execute(["docker", "start", "--attach", name])
            save(out / f"{index}-execution.json", result)
            if result["exit_code"]:
                raise RuntimeError(f"offline I1 command {index} failed; see retained execution record")
        finally:
            save(out / f"{index}-terminal.json", execute(["docker", "inspect", name]))
            save(out / f"{index}-remove.json", execute(["docker", "rm", "-f", name]))
    first = (out / "replay-1" / "semantic.json").read_bytes()
    second = (out / "replay-2" / "semantic.json").read_bytes()
    if first != second:
        raise AssertionError("two saved-log roundtrips differ")
    after = {f"{case}/{filename}": hashlib.sha256((inputs / case / filename).read_bytes()).hexdigest()
             for case, files in CASES.items() for filename in files}
    if before != after:
        raise AssertionError("source fixture bytes changed")
    save(out / "summary.json", {"passed": True, "image_id": image,
                               "two_replays_semantically_identical": True,
                               "input_before": before, "input_after": after,
                               "provider_calls": 0, "api_spend": 0,
                               "viewer": "replay-1/viewer/index.html"})
    print(out)


if __name__ == "__main__":
    main()
