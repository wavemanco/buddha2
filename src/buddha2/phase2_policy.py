"""Offline track decisions over immutable Phase 2 executions; never dispatch calls."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path

from .artifacts import (
    ContractError,
    digest,
    file_hash,
    read_json,
    tree_hashes,
    write_bytes_once,
    write_once,
)
from .phase2 import IMAGE_ID, PROJECT, _output, _templates, cost_sheet, validate_study
from .phase2_analysis import build_human_packets
from .phase2_contracts import slot_prefix
from .phase2_dispatch import replay_dispatch

ORIGINAL_STUDY = "4de2d582d4a5f6f289df70284295da2c67961a1a26384957dd3a43a2635c982e"
ORIGINAL_ARCHIVE = "54ae99efa70c513da92578a0edad4a2f26b2581ac9466c38dace83630f5f3084"


def _input(path: Path) -> Path:
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ContractError("policy inputs cannot traverse links")
    path = path.resolve(strict=True)
    roots = (PROJECT, Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", PROJECT / "runs")).resolve())
    if not any(path.is_relative_to(root) for root in roots):
        raise ContractError("policy inputs must remain in the new project")
    return path


def original_study() -> dict:
    study = read_json(PROJECT / "runs/phase2-r010/frozen-study/study.json")
    validate_study(study, current_sources=False)
    if study["study_sha256"] != ORIGINAL_STUDY:
        raise ContractError("preserved parent study differs")
    return study


def _original_sources(study: dict) -> None:
    archive_path = PROJECT / "evidence/phase2-r010/phase2a-kit.zip"
    if file_hash(archive_path) != ORIGINAL_ARCHIVE:
        raise ContractError("historical source archive differs")
    with zipfile.ZipFile(archive_path) as archive:
        for relative, expected in study["package_files"].items():
            raw = archive.read("src/buddha2/" + relative)
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ContractError("historical execution source differs")


def validate_execution_study(study: dict, study_path: Path) -> None:
    """Check original execution identity separately from current assessment code."""
    from .phase2_native import NativeAssessment

    validate_study(study, current_sources=False)
    old = original_study()
    for key in ("tasks", "source_audit", "exposure", "selection_policy", "worklist", "templates",
                "profiles", "procedure_hashes", "shared_generator_settings_sha256", "human_check",
                "caps", "admission", "failure_policy", "upstream_pins", "lockfiles",
                "runtime_image_id", "runtime_python", "native_evaluator"):
        if study.get(key) != old[key]:
            raise ContractError(f"execution changed outside the policy update: {key}")
    if study["templates"] != _templates():
        raise ContractError("effective strategy templates differ")
    if study["native_evaluator"] != NativeAssessment(PROJECT / ".upstream/novelty-bench").identity:
        raise ContractError("effective native evaluator differs")
    if any(file_hash(PROJECT / key) != value for key, value in study["lockfiles"].items()):
        raise ContractError("effective dependency locks differ")
    if study["study_sha256"] == ORIGINAL_STUDY:
        _original_sources(study)
    else:
        from .phase2_decisions import POLICIES

        if (study.get("specification") != "0.12"
                or study.get("parent_preparation_sha256") != ORIGINAL_STUDY
                or study.get("decision_policies") != POLICIES
                or study.get("decision_policy_sha256") != digest(POLICIES)
                or study.get("specification_sha256") != file_hash(
                    PROJECT / "evidence/phase2-r012/specification-0.12.md")):
            raise ContractError("refreshed study lacks its frozen policies/specification/parent")
        source_root = _input(study_path.parent / "source")
        if tree_hashes(source_root) != study["package_files"]:
            raise ContractError("retained execution source bundle differs")
    # These unchanged modules implement the replay used for either generation identity.
    # A future change needs an explicit compatibility review or historical-source replay.
    for name in ("phase2.py", "phase2_contracts.py", "phase2_dispatch.py", "phase2_analysis.py",
                 "phase2_native.py", "phase2_coverage.py", "artifacts.py"):
        if file_hash(PROJECT / "src/buddha2" / name) != study["package_files"][name]:
            raise ContractError(f"execution replay compatibility needs review: {name}")


def prepare_policy(output: Path) -> dict:
    from .phase2_decisions import POLICIES

    output = _output(output)
    if os.environ.get("BUDDHA2_IMAGE_ID") != IMAGE_ID or tuple(sys.version_info[:3]) != (3, 12, 15):
        raise ContractError("policy preparation requires the pinned image and Python 3.12.15")
    study = copy.deepcopy(original_study())
    _original_sources(study)
    study.pop("study_sha256")
    study.update({
        "specification": "0.12",
        "specification_sha256": file_hash(PROJECT / "evidence/phase2-r012/specification-0.12.md"),
        "preparation_start_sha256": file_hash(PROJECT / "evidence/phase2-r012/before.json"),
        "parent_preparation_sha256": ORIGINAL_STUDY,
        "package_files": tree_hashes(PROJECT / "src/buddha2"),
        "decision_policies": POLICIES, "decision_policy_sha256": digest(POLICIES),
        "selection_rule": {"policies_sha256": digest(POLICIES),
                           "benchmark_requires_humans": False,
                           "human_augmented_is_separate": True},
        "execution_authorized": False,
    })
    study["remaining_live_prerequisites"] = [item for item in study["remaining_live_prerequisites"]
                                            if item != "two eligible pilot-output readers and availability"]
    study["study_sha256"] = digest(study)
    for relative in study["package_files"]:
        write_bytes_once(output / "source" / relative, (PROJECT / "src/buddha2" / relative).read_bytes())
    write_once(output / "study.json", study)
    validate_execution_study(study, output / "study.json")
    for name, value in (("worklist.json", study["worklist"]), ("templates.json", study["templates"]),
                        ("cost-sheet.json", cost_sheet(study)), ("decision-policies.json", POLICIES)):
        write_once(output / name, value)
    write_once(output / "authorization-request.json", {
        "authorized": False, "study_sha256": study["study_sha256"], "live_ready": False,
        "note": "Offline preparation only; no spending grant or human collection activation."})
    return {"status": "prepared-offline", "study_sha256": study["study_sha256"],
            "parent_preparation_sha256": ORIGINAL_STUDY, "provider_calls": 0,
            "human_collection_started": False, "live_ready": False, "runtime_image_id": IMAGE_ID}


def load_execution(study_path: Path, run: Path) -> tuple:
    """Read and reassess saved results only; no transport is constructed."""
    from .phase2_native import NativeAssessment

    study_path, run = _input(study_path), _input(run)
    study = read_json(study_path)
    validate_execution_study(study, study_path)
    state = replay_dispatch(run / "journal")
    if type(state.get("fixture")) is not bool:
        raise ContractError("saved execution must declare fixture/live identity")
    portfolios, assessments = [], []
    expected_assessment_paths = set()
    for path in sorted((run / "portfolios").glob("*.json")):
        portfolio = read_json(_input(path))
        provenance = portfolio["provenance"]
        prefix = slot_prefix(portfolio["task"]["id"], provenance["method"], provenance["repeat"])
        portfolios.append(portfolio)
        assessment_path = run / "assessments" / f"{prefix}.json"
        expected_assessment_paths.add(assessment_path)
        if not assessment_path.exists():
            continue
        assessment = read_json(_input(assessment_path))
        assessments.append({**assessment, "method": provenance["method"],
                            "repeat": provenance["repeat"], "order_id": prefix,
                            "study_sha256": study["study_sha256"]})
    if set((run / "assessments").glob("*.json")) - expected_assessment_paths:
        raise ContractError("saved native assessment lacks its original portfolio")
    return study, portfolios, assessments, state, NativeAssessment(PROJECT / ".upstream/novelty-bench")


def save_bundle(output: Path, bundle: dict) -> None:
    output = _output(output)
    for key, value in bundle.items():
        write_once(output / f"{key}.json", value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--output", type=Path, required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("--study", type=Path, required=True)
    for name in ("decide", "human-packets", "human-import"):
        command = commands.add_parser(name)
        command.add_argument("--study", type=Path, required=True)
        command.add_argument("--run", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        if name in ("decide", "human-import"):
            command.add_argument("--cutoff", required=True)
        if name == "decide":
            command.add_argument("--track", choices=("benchmark", "human-augmented"), required=True)
            command.add_argument("--human-assessment", type=Path)
            command.add_argument("--parent", type=Path)
        elif name == "human-import":
            command.add_argument("--submissions", type=Path, required=True)
            command.add_argument("--window", type=Path)
            command.add_argument("--previous", type=Path)
    compatibility = commands.add_parser("compatibility")
    compatibility.add_argument("--parent", type=Path, required=True)
    compatibility.add_argument("--candidate", type=Path, required=True)
    compatibility.add_argument("--parent-context", type=Path, required=True)
    compatibility.add_argument("--candidate-context", type=Path, required=True)
    compatibility.add_argument("--confirmation-opened", action="store_true")
    compatibility.add_argument("--claim", choices=("development", "retrospective", "confirmatory"), default="development")
    compatibility.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        from .__main__ import _offline, _upstreams

        _offline()
        _upstreams()
        if args.command == "prepare":
            result = prepare_policy(args.output)
        elif args.command == "inspect":
            path = _input(args.study)
            study = read_json(path)
            validate_execution_study(study, path)
            result = {"study_sha256": study["study_sha256"], "tasks": len(study["tasks"]),
                      "decision_policies": study.get("decision_policies"), "live_ready": False,
                      "remaining_live_prerequisites": study["remaining_live_prerequisites"]}
        elif args.command == "compatibility":
            from .phase2_decisions import continuation_compatibility

            result = continuation_compatibility(
                read_json(_input(args.parent)), read_json(_input(args.candidate)),
                read_json(_input(args.parent_context)), read_json(_input(args.candidate_context)),
                confirmation_opened=args.confirmation_opened, claim=args.claim)
            write_once(_output(args.output) / "compatibility.json", result)
        else:
            study, portfolios, assessments, state, native = load_execution(args.study, args.run)
            fixture = state["fixture"]
            if args.command == "decide":
                from .phase2_decisions import build_decision

                human = read_json(_input(args.human_assessment)) if args.human_assessment else None
                parent = read_json(_input(args.parent)) if args.parent else None
                bundle = build_decision(study, portfolios, assessments, state, native,
                                        track=args.track, cutoff=args.cutoff,
                                        human_assessment=human, parent=parent, fixture=fixture)
                save_bundle(args.output, bundle)
                result = bundle["decision"]
            elif args.command == "human-packets":
                bundle = build_human_packets(study, portfolios, fixture=fixture)
                output = _output(args.output)
                for reader, packet in bundle["packets"].items():
                    write_once(output / f"{reader}.json", packet)
                write_once(output / "private/unit-mapping.json", bundle["private_mapping"])
                result = {"status": "packets-prepared", "fixture": fixture,
                          "human_collection_started": False, "provider_calls": 0}
            else:
                from .phase2_human import make_human_assessment

                previous = read_json(_input(args.previous)) if args.previous else None
                window = read_json(_input(args.window)) if args.window else None
                record = make_human_assessment(study, portfolios,
                    read_json(_input(args.submissions)), cutoff=args.cutoff,
                    previous=previous, fixture=fixture, window=window)
                write_once(_output(args.output) / "human-assessment.json", record)
                result = {"assessment_sha256": record["assessment_sha256"],
                          "complete": record["complete"], "provider_calls": 0}
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except (ContractError, OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
