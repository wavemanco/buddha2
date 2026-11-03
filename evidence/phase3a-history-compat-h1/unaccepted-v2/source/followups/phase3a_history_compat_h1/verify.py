"""Offline H1 evidence driver. No provider launcher, keys, dependency setup or live grant."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess  # nosec B404
import sys
from pathlib import Path

from . import runtime

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
IMAGE = "buddha2-h1:scoped-backport"
TMPFS = "/tmp:rw,exec,size=1073741824"  # nosec B108
# This cache exists only in the private tmpfs of a disposable network-none container.
MYPY_CACHE = "/tmp/h1-mypy"  # nosec B108


def save(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")


def command(args: list[str], *, stdin: str | None = None) -> dict:
    # Commands are explicit argument arrays for the local Docker CLI, without a shell.
    result = subprocess.run(
        args, input=stdin, cwd=ROOT, text=True, capture_output=True, check=False
    )  # nosec B603
    return {
        "command": args,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def docker(image: str, *, outputs: bool = False) -> list[str]:
    args = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        TMPFS,
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--mount",
        f"type=bind,source={ROOT},target=/workspace,readonly",
    ]
    if outputs:
        args += [
            "--mount",
            f"type=bind,source={ROOT / 'runs/phase3a-history-compat-h1'},target=/workspace/runs/phase3a-history-compat-h1",
        ]
    return args + [
        "-e",
        "PYTHONPATH=/workspace/src:/workspace/.upstream/harness2:/workspace",
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        "--workdir",
        "/workspace",
        "--entrypoint",
        "python",
        image,
        "-B",
    ]


def source() -> dict:
    names = [
        p for p in HERE.iterdir() if p.suffix in {".py", ".ts", ".md"} or p.name == "Dockerfile"
    ]
    names += [ROOT / "PHASE3A_HISTORY_COMPAT_H1_DEFINITION.md"]
    return {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(names)
    }


def preserved_r3() -> dict:
    study = json.loads(
        (ROOT / "runs/phase3a-c1-completion-v4/verification-v3/release/study.json").read_text(
            encoding="utf-8"
        )
    )
    files = study["source"]["files"]
    actual = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files}
    if actual != files:
        raise ValueError("frozen R3 source changed")
    return {"source_sha256": study["source_sha256"], "files": actual, "unchanged": True}


def verify(output: Path) -> dict:
    boundary = ROOT / "runs/phase3a-history-compat-h1"
    output = output if output.is_absolute() else ROOT / output
    if ".." in output.parts or any(part.casefold() in runtime.PRIVATE for part in output.parts):
        raise ValueError("verification rejects private or traversing paths")
    if not output.is_relative_to(boundary):
        raise ValueError("verification output escaped H1")
    if any(
        p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
        for p in (output, *output.parents)
    ):
        raise ValueError("verification output cannot traverse links")
    output = output.resolve()
    if output == boundary or not output.is_relative_to(boundary) or output.exists():
        raise ValueError("verification needs a fresh H1 output directory")
    output.mkdir(parents=True)
    before = source()
    save(output / "source-before.json", before)
    save(output / "r3-preservation-before.json", preserved_r3())
    image_ids = {}
    for label, image in (("baseline", runtime.BASE_IMAGE), ("fixed", IMAGE)):
        result = command(
            ["docker", "image", "inspect", "--format", "{{json .RootFS.Layers}}|{{.Id}}", image]
        )
        save(output / (label + "-image.json"), result)
        if result["exit_code"]:
            raise ValueError("required pinned image is unavailable")
        layers, image_id = result["stdout"].strip().split("|")
        image_ids[label] = {"id": image_id, "layers": json.loads(layers)}
    if (
        image_ids["baseline"]["id"] != runtime.BASE_IMAGE
        or image_ids["fixed"]["layers"][:-1] != image_ids["baseline"]["layers"]
    ):
        raise ValueError("derived runtime does not retain every baseline layer")
    images = {label: value["id"] for label, value in image_ids.items()}
    static = {
        "ruff": [
            "-m",
            "ruff",
            "check",
            "--no-cache",
            "--config",
            "/workspace/pyproject.toml",
            "followups/phase3a_history_compat_h1",
        ],
        "mypy": [
            "-m",
            "mypy",
            "--cache-dir",
            MYPY_CACHE,
            "followups/phase3a_history_compat_h1",
        ],
        "bandit": [
            "-m",
            "bandit",
            "-q",
            "-r",
            "followups/phase3a_history_compat_h1",
            "-x",
            "followups/phase3a_history_compat_h1/tests.py",
        ],
    }
    for name, arguments in static.items():
        checked = command(docker(images["fixed"]) + arguments)
        save(output / (name + ".json"), checked)
        if checked["exit_code"]:
            raise ValueError("static check failed: " + name)
    retained = json.loads(
        (ROOT / "evidence/phase3a-history-compat-h1/filter-only-image.json").read_text(
            encoding="utf-8"
        )
    )
    intermediate_image = retained["image_id"]
    inventories, probes = {}, {}
    for label, image in images.items():
        args = [
            "docker",
            "run",
            "--rm",
            "-i",
            "--network",
            "none",
            "--read-only",
            "--entrypoint",
            "python",
            image,
            "-B",
            "-",
            "inventory",
        ]
        result = command(args, stdin=(HERE / "runtime.py").read_text(encoding="utf-8"))
        save(output / (label + "-inventory-command.json"), result)
        if result["exit_code"]:
            raise ValueError("whole-runtime inventory failed")
        inventories[label] = json.loads(result["stdout"])
        save(output / (label + "-inventory.json"), inventories[label])
        args = docker(image)
        index = args.index("--entrypoint")
        args[index + 1] = "/usr/local/bin/bun"
        args = args[:-1] + ["run", "/workspace/followups/phase3a_history_compat_h1/probe.ts"]
        result = command(args)
        save(output / (label + "-probe-command.json"), result)
        if result["exit_code"]:
            raise ValueError("actual SDK conversion probe failed")
        probes[label] = json.loads(result["stdout"])
    base_other = {k: v for k, v in inventories["baseline"].items() if k != "target_sha256"}
    fixed_other = {k: v for k, v in inventories["fixed"].items() if k != "target_sha256"}
    if (
        base_other != fixed_other
        or inventories["baseline"]["target_sha256"] != runtime.BEFORE_SHA
        or inventories["fixed"]["target_sha256"] != runtime.AFTER_SHA
    ):
        raise ValueError("runtime changed beyond its one authorized source file")
    for label, expected in (("baseline", [0, 1, 0, 0]), ("fixed", [1, 1, 1, 0])):
        if (
            probes[label]["fetch_invocations"]
            or [r["after_OpenCode"]["opaque_blocks"] for r in probes[label]["rows"]] != expected
        ):
            raise ValueError("baseline/fixed signature-aware assertion differs")
    if probes["fixed"]["order"]["actual"] != probes["fixed"]["order"]["expected"]:
        raise ValueError("valid interleaved provider history was reordered")
    checks = {}
    checks["unit"] = command(
        docker(images["fixed"]) + ["-m", "followups.phase3a_history_compat_h1.tests"]
    )
    save(output / "unit.json", checks["unit"])
    if checks["unit"]["exit_code"]:
        raise ValueError("pre-admission adverse/replay checks failed")
    native = {}
    for label, image, stage, loss, within, invalid, count in (
        ("baseline-loss", images["baseline"], "inv1.a1", True, True, False, 1),
        ("filter-only-order-loss", intermediate_image, "inv1.a1", True, True, False, 2),
        ("fixed-changed", images["fixed"], "inv1.a1", False, True, False, 1),
        ("fixed-unchanged", images["fixed"], "dom1.a1", False, True, False, 1),
        ("invalid-ending", images["fixed"], "inv1.a1", True, False, True, 1),
    ):
        target = "/workspace/" + (output / label).relative_to(ROOT).as_posix()
        script = (
            "from pathlib import Path;from followups.phase3a_history_compat_h1.fixture import native_case;"
            f"native_case(Path({target!r}),{stage!r},expect_loss={loss!r},within_response={within!r},invalid_ending={invalid!r},expected_mock_calls={count!r})"
        )
        result = command(docker(image, outputs=True) + ["-c", script])
        save(output / (label + "-command.json"), result)
        if result["exit_code"]:
            raise ValueError("native checkpoint case failed: " + label)
        native[label] = json.loads((output / label / "result.json").read_text(encoding="utf-8"))
    after = source()
    if before != after:
        raise ValueError("H1 source changed during verification")
    save(output / "source-after.json", after)
    save(output / "r3-preservation-after.json", preserved_r3())
    summary = {
        "fixture": True,
        "provider_calls": 0,
        "api_spend": 0,
        "runtime": image_ids,
        "all_other_runtime_files_unchanged": True,
        "signature_conversion_fixed": True,
        "normal_native_changed_and_unchanged": True,
        "interleaved_order_preserved": True,
        "invalid_ending_thinking_rejected": True,
        "H1_engineering_checks_passed": True,
        "H1_complete": False,
        "independent_acceptance_required": True,
        "scientific_complete": False,
        "native_cases": {
            k: {"mock_http_calls": v["mock_http_calls"], "native_reply_ok": v["native_reply_ok"]}
            for k, v in native.items()
        },
    }
    save(output / "summary.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.output), sort_keys=True))
    except (OSError, ValueError, KeyError) as error:
        print("H1 verification stopped: " + str(error), file=sys.stderr)
        raise SystemExit(1) from None
