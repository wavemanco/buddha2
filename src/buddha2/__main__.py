"""Small CLI for the explicitly offline Phase 0 integration kit."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import sys
from pathlib import Path

from .artifacts import (
    ContractError,
    digest,
    export_native,
    file_hash,
    import_native,
    read_json,
    tree_hashes,
    validate_portfolio,
    write_bytes_once,
    write_once,
)
from .evaluation import evaluate_mechanical, evaluate_native
from .nb_worker import validate_grading

PROJECT = Path(__file__).resolve().parents[2]
PINS = {
    "harness2": "1cfe254e8d25b15f37048c3730134686abe60335",
    "novelty-bench": "64a23be6b18ec1dacc298830aab276061b6e143c",
}


def _without_links(path: Path) -> Path:
    absolute = path if path.is_absolute() else Path.cwd() / path
    for candidate in (absolute, *absolute.parents):
        if candidate.is_symlink():
            raise ContractError("symlink paths are not supported")
    return absolute.resolve()


def _output(path: Path) -> Path:
    root = _without_links(Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", PROJECT / "runs")))
    destination = _without_links(path)
    if not destination.is_relative_to(root):
        raise ContractError("output must remain beneath BUDDHA2_OUTPUT_ROOT")
    if destination.exists():
        if not destination.is_dir():
            raise ContractError("output destination must be a directory")
        if any(child.is_symlink() for child in destination.rglob("*")):
            raise ContractError("output trees may not contain symlinks")
    return destination


def _offline() -> None:
    if sys.platform != "linux" or os.environ.get("BUDDHA2_OFFLINE") != "1":
        raise ContractError("native fixture execution requires the offline Linux launcher")
    interfaces = {path.name for path in Path("/sys/class/net").iterdir()}
    if interfaces != {"lo"}:
        raise ContractError("native fixture execution requires a network-disabled runtime")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", os.environ.get("BUDDHA2_IMAGE_ID", "")):
        raise ContractError("native execution requires the launcher's immutable image identity")


def _upstreams() -> dict:
    lock = read_json(PROJECT / "upstreams.lock.json")
    if not isinstance(lock, dict) or type(lock.get("schema_version")) is not int or lock["schema_version"] != 1:
        raise ContractError("upstreams.lock.json is missing or incompatible")
    records = lock.get("upstreams")
    if not isinstance(records, dict) or set(records) != set(PINS):
        raise ContractError("upstream source records are missing")
    for name, commit in PINS.items():
        record = records.get(name)
        if (
            not isinstance(record, dict) or record.get("commit") != commit
            or not isinstance(record.get("files"), dict) or not record["files"]
        ):
            raise ContractError(f"source pin is missing or incompatible: {name}")
        source = _without_links(PROJECT / ".upstream" / name)
        if not source.is_relative_to(PROJECT) or tree_hashes(source) != record["files"]:
            raise ContractError(f"pinned upstream source integrity failed: {name}")
    return lock


def _native_path(value: Path | None) -> Path:
    expected = _without_links(PROJECT / ".upstream/novelty-bench")
    if value is not None and _without_links(value) != expected:
        raise ContractError("--noveltybench must identify the pinned project checkout")
    return expected


def _manifest(lock: dict) -> dict:
    task = read_json(PROJECT / "fixtures/task.json")
    inputs = {
        "task": task,
        "configuration": {
            "fixture": True, "mode": "agg", "k": 1, "pool_policy": "finals",
            "library": None, "provider_calls": 0,
            "protocol": {"version": "1.1", "patience": 0.8, "responses": 10},
            "roles": {
                "proposer": {"kind": "deterministic-fixture", "model": "local/deterministic"},
                "selector": {"kind": "native-trivial", "model": "local/deterministic"},
                "executor": "local-materialized-fixture",
                "judge": "frozen-synthetic-inputs",
            },
        },
        "environment": {
            "image_id": os.environ["BUDDHA2_IMAGE_ID"],
            "python": platform.python_version(),
            "platform": sys.platform,
            "architecture": platform.machine(),
        },
        "strategy_files": tree_hashes(PROJECT / "strategies/planner"),
        "package_files": tree_hashes(PROJECT / "src/buddha2"),
        "requirements": {
            name: file_hash(PROJECT / name)
            for name in ("requirements.lock", "requirements-build.lock")
        },
        "grading_template_sha256": file_hash(PROJECT / "fixtures/grading.json"),
        "specification_sha256": file_hash(PROJECT / "docs/research/PHASE_DEFINITIONS.md"),
        "decisions_sha256": file_hash(PROJECT / "docs/phases/phase-0/DECISIONS.md"),
        "upstreams_lock_sha256": file_hash(PROJECT / "upstreams.lock.json"),
        "upstreams": {
            name: {"commit": record["commit"], "files_sha256": digest(record["files"])}
            for name, record in lock["upstreams"].items()
        },
    }
    return {"schema_version": 1, "fixture": True, "run_id": digest(inputs), "inputs": inputs}


def _portfolio(manifest: dict, engine: dict, run: Path) -> dict:
    if engine.get("fixture") is not True or engine.get("provider_calls") != 0:
        raise ContractError("engine did not return declared offline fixture evidence")
    scheduler = PROJECT / ".upstream/harness2/harness2/core/schedule.py"
    native = engine.get("native_source", {})
    if (
        native.get("scheduler") != str(scheduler.resolve())
        or native.get("scheduler_sha256") != file_hash(scheduler)
        or native.get("expected_commit") != PINS["harness2"]
    ):
        raise ContractError("executed scheduler does not match the pinned upstream source")
    selected = _without_links(Path(engine["selected_harness_dir"]))
    if not selected.is_relative_to(run / "engine"):
        raise ContractError("selected harness evidence escapes the run")
    portfolio = {
        "schema_version": 1, "fixture": True, "task": manifest["inputs"]["task"],
        "responses": [
            {"id": "response-" + digest({"run_id": manifest["run_id"], "index": index, "text": text})[:24],
             "text": text}
            for index, text in enumerate(engine["generations"])
        ],
        "provenance": {
            "fixture": True, "run_id": manifest["run_id"], "provider_calls": 0,
            "strategy": "planner", "selected_label": engine["selected_label"],
            "selected_harness_files": tree_hashes(selected),
            "engine_evidence": "engine/engine.json",
            "engine_evidence_sha256": file_hash(run / "engine/engine.json"),
            "upstreams": PINS,
        },
    }
    validate_portfolio(portfolio)
    return portfolio


def _checkpoint(run: Path, portfolio: dict, manifest: dict) -> dict:
    return {
        "schema_version": 1, "fixture": True, "run_id": manifest["run_id"],
        "portfolio_sha256": digest(portfolio),
        "files": {
            relative: file_hash(run / relative)
            for relative in ("portfolio.json", "grading.json", "native/generations.jsonl", "native/identities.json")
        },
        "engine_files": tree_hashes(run / "engine"),
    }


def _restore_output(run: Path, manifest: dict) -> dict:
    if (
        not isinstance(manifest, dict) or manifest.get("fixture") is not True
        or not isinstance(manifest.get("inputs"), dict)
        or manifest.get("run_id") != digest(manifest["inputs"])
    ):
        raise ContractError("saved manifest identity is invalid")
    portfolio = read_json(run / "portfolio.json")
    validate_portfolio(portfolio)
    if (
        portfolio["task"] != manifest["inputs"].get("task")
        or portfolio["provenance"].get("run_id") != manifest["run_id"]
    ):
        raise ContractError("saved portfolio does not belong to this manifest")
    _validate_completion(run, portfolio, manifest)
    previous = read_json(run / "output.json")
    if previous != _checkpoint(run, portfolio, manifest):
        raise ContractError("saved output or engine evidence changed; refuse stale resume")
    if import_native(run / "native") != portfolio:
        raise ContractError("saved native export does not match the portfolio")
    validate_grading(portfolio, read_json(run / "grading.json"))
    return portfolio


def _completion_record(run: Path, portfolio: dict, manifest: dict) -> dict:
    assessments = {}
    for name in ("mechanical", "noveltybench-fixture"):
        record = read_json(_without_links(run / "assessments" / f"{name}.json"))
        if (
            not isinstance(record, dict) or record.get("fixture") is not True
            or record.get("portfolio_sha256") != digest(portfolio)
        ):
            raise ContractError("completed assessment is incompatible with this portfolio")
        assessments[name] = digest(record)
    return {
        "schema_version": 1, "fixture": True, "status": "complete", "run_id": manifest["run_id"],
        "portfolio_sha256": digest(portfolio), "provider_calls": 0,
        "assessments": assessments,
        "report_sha256": file_hash(_without_links(run / "report.md")),
    }


def _validate_completion(run: Path, portfolio: dict, manifest: dict) -> None:
    path = run / "completion.json"
    if not path.exists() and not path.is_symlink():
        return
    record = read_json(_without_links(path))
    fields = {
        "schema_version", "fixture", "status", "run_id", "portfolio_sha256",
        "provider_calls", "assessments", "report_sha256",
    }
    if (
        not isinstance(record, dict) or set(record) != fields
        or type(record["schema_version"]) is not int or record["schema_version"] != 1
        or record["fixture"] is not True or record["status"] != "complete"
        or type(record["provider_calls"]) is not int or record["provider_calls"] != 0
        or record["run_id"] != manifest["run_id"]
        or record["portfolio_sha256"] != digest(portfolio)
        or not isinstance(record["assessments"], dict)
        or set(record["assessments"]) != {"mechanical", "noveltybench-fixture"}
        or record != _completion_record(run, portfolio, manifest)
    ):
        raise ContractError("completed evidence is corrupt or incompatible; refusing repair")


def _assess(portfolio: dict, destination: Path, grading: dict | None, upstream: Path | None) -> dict:
    destination = _output(destination)
    assessment_dir = _output(destination / "assessments")
    validate_portfolio(portfolio)
    mechanical = evaluate_mechanical(portfolio)
    results = {"mechanical": mechanical}
    if grading is not None:
        _offline()
        validate_grading(portfolio, grading)
        _upstreams()
        results["noveltybench-fixture"] = evaluate_native(portfolio, grading, _native_path(upstream))
    for name, result in results.items():
        write_once(assessment_dir / f"{name}.json", result)
    return results


def _report(run: Path, portfolio: dict, results: dict) -> None:
    metrics = results["noveltybench-fixture"]["metrics"]
    text = (
        "# Phase 0 offline fixture\n\n"
        "This is a synthetic integration example. No model or provider calls occurred.\n\n"
        f"Task: `{portfolio['task']['id']}`. Ten ordered responses are preserved in `portfolio.json`.\n"
        "The unchanged upstream Harness² scheduler ran parallel k=1: four local executor rollouts, "
        "three deterministic editor/composer calls, and trivial native selection.\n\n"
        f"Synthetic native distinctness: {metrics['distinct']}. "
        f"Synthetic native utility: {metrics['utility']:.15g}.\n"
        "The partitions and head scores are declared fixture inputs, not model judgments.\n\n"
        "Inspect `manifest.json`, `engine/engine.json`, retained harnesses and trajectories, "
        "`native/`, `grading.json`, and the two separate `assessments/` records.\n\n"
        "Live generation, OpenCode execution, model-backed proposal/selection, official judges, "
        "semantic quality, billing enforcement, and recursive-improvement effectiveness remain unverified.\n"
    )
    write_bytes_once(run / "report.md", text.encode("utf-8"))


def _demo(args: argparse.Namespace) -> dict:
    _offline()
    run = _output(args.output)
    lock = _upstreams()
    manifest = _manifest(lock)
    if args.resume:
        if read_json(run / "manifest.json") != manifest:
            raise ContractError("effective inputs changed; use a new output directory")
    elif run.exists() and any(run.iterdir()):
        raise ContractError("output is not empty; use --resume for unchanged inputs")
    if (run / "completion.json").exists() or (run / "completion.json").is_symlink():
        _restore_output(run, manifest)
        return {"status": "complete", "fixture": True, "run": str(run), "provider_calls": 0}
    write_once(run / "manifest.json", manifest)
    if (run / "output.json").exists():
        portfolio = _restore_output(run, manifest)
    else:
        # Keep native imports behind explicit fixture/runtime/source validation.
        from .engine import run_fixture

        engine = run_fixture(_output(run / "engine"), PROJECT / "strategies/planner", manifest["inputs"]["task"])
        portfolio = _portfolio(manifest, engine, run)
        write_once(run / "portfolio.json", portfolio)
        export_native(portfolio, _output(run / "native"))
        grading = read_json(PROJECT / "fixtures/grading.json")
        grading["portfolio_sha256"] = digest(portfolio)
        validate_grading(portfolio, grading)
        write_once(run / "grading.json", grading)
        write_once(run / "output.json", _checkpoint(run, portfolio, manifest))
    if args.stop_after_output:
        return {"status": "output-checkpoint", "fixture": True, "run": str(run), "provider_calls": 0}
    results = _assess(portfolio, run, read_json(run / "grading.json"), None)
    _report(run, portfolio, results)
    write_once(run / "completion.json", _completion_record(run, portfolio, manifest))
    return {"status": "complete", "fixture": True, "run": str(run), "provider_calls": 0}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("phase2", help="offline Phase 2 preparation; use phase2 --help")
    commands.add_parser("phase2-policy", help="offline track decisions and optional human supplements")
    commands.add_parser("phase2-am1", help="AM-1 offline preflight and SDK/mock first block")
    commands.add_parser("phase2-release", help="complete Phase 2B execution kit; offline operator commands")
    demo = commands.add_parser("demo", help="run or resume the offline native fixture")
    demo.add_argument("--output", type=Path, required=True)
    demo.add_argument("--mode", choices=("fixture",), default="fixture")
    demo.add_argument("--resume", action="store_true")
    demo.add_argument("--stop-after-output", action="store_true")
    inspect = commands.add_parser("inspect", help="inspect a saved run without generation")
    inspect.add_argument("--run", type=Path, required=True)
    export = commands.add_parser("export", help="export a portfolio to native NoveltyBench format")
    export.add_argument("--portfolio", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    native_import = commands.add_parser("import", help="validate native generations and identity mapping")
    native_import.add_argument("--source", type=Path, required=True)
    native_import.add_argument("--output", type=Path, required=True)
    assess = commands.add_parser("assess", help="assess saved responses without generation")
    assess.add_argument("--portfolio", type=Path, required=True)
    assess.add_argument("--output", type=Path, required=True)
    assess.add_argument("--grading", type=Path)
    assess.add_argument("--noveltybench", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "phase2-release":
        from .phase2_release import main as release_main

        return release_main(arguments[1:])
    if arguments and arguments[0] == "phase2-am1":
        from .phase2_am1 import main as am1_main

        return am1_main(arguments[1:])
    if arguments and arguments[0] == "phase2-policy":
        from .phase2_policy import main as policy_main

        return policy_main(arguments[1:])
    if arguments and arguments[0] == "phase2":
        from .phase2 import main as phase2_main

        return phase2_main(arguments[1:])
    args = _parser().parse_args(argv)
    try:
        if args.command == "demo":
            result = _demo(args)
        elif args.command == "export":
            destination = _output(args.output)
            export_native(read_json(args.portfolio), destination)
            result = {"status": "exported", "output": str(destination), "fixture": True}
        elif args.command == "import":
            destination = _output(args.output)
            portfolio = import_native(args.source)
            write_once(destination / "portfolio.json", portfolio)
            result = {"status": "imported", "portfolio_sha256": digest(portfolio), "fixture": True}
        elif args.command == "assess":
            if args.noveltybench is not None and args.grading is None:
                raise ContractError("--noveltybench requires matching --grading evidence")
            results = _assess(
                read_json(args.portfolio), args.output,
                read_json(args.grading) if args.grading is not None else None,
                args.noveltybench,
            )
            result = {"status": "assessed", "fixture": True, "evaluators": list(results)}
        else:
            run = _without_links(args.run)
            manifest = read_json(run / "manifest.json")
            portfolio = _restore_output(run, manifest)
            result = {
                "manifest": manifest, "portfolio": portfolio,
                "engine": read_json(run / "engine/engine.json"),
                "status": "complete" if (run / "completion.json").exists() else "output-checkpoint",
                "limitations": "Synthetic offline fixture; no live model, judge, or billing validation.",
            }
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        return 0
    except (ContractError, ValueError, OSError, RuntimeError, KeyError, TypeError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
