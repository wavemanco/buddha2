"""A bounded pair-evaluator workflow; labels are opened only by offline analysis."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from .__main__ import PROJECT, _offline, _output, _without_links
from .artifacts import (
    ContractError,
    digest,
    file_hash,
    read_json,
    tree_hashes,
    write_bytes_once,
    write_once,
)
from .muce import SOURCE, prepare_muce
from .pairs import (
    analyze_pairs,
    make_label,
    make_pair,
    make_presentation,
    validate_pair,
    validate_presentation,
)
from .phase1_runner import PROFILE, DirectAnthropicTransport, replay_run, request_preview, run_stage


def validate_worklists(pairs: list, work: dict) -> None:
    if not isinstance(pairs, list) or len(pairs) != 24 or not isinstance(work, dict) or set(work) != {
        "schema_version", "kind", "calibration", "audit"
    } or work["schema_version"] != 1 or work["kind"] != "pair-worklists":
        raise ContractError("Phase 1 requires the frozen 24-prompt pair worklists")
    by_id, prompts, groups, flags = {}, set(), set(), set()
    for pair in pairs:
        validate_pair(pair)
        if pair["pair_id"] in by_id or pair["prompt_id"] in prompts or pair["prompt_group_sha256"] in groups:
            raise ContractError("duplicate pair or prompt leakage across stages")
        by_id[pair["pair_id"]] = pair
        prompts.add(pair["prompt_id"])
        groups.add(pair["prompt_group_sha256"])
        flags.add(pair["fixture"])
    if len(flags) != 1:
        raise ContractError("mixed fixture and real population")
    allocated, presentation_ids = [], set()
    for stage in ("calibration", "audit"):
        value = work[stage]
        if not isinstance(value, dict) or set(value) != {"pair_ids", "presentations"} or (
            not isinstance(value["pair_ids"], list) or len(value["pair_ids"]) != 12
            or not isinstance(value["presentations"], list) or len(value["presentations"]) != 24
        ):
            raise ContractError("each stage requires 12 pairs and 24 presentations")
        stage_pairs = value["pair_ids"]
        if len(set(stage_pairs)) != 12 or any(identity not in by_id for identity in stage_pairs):
            raise ContractError("stage pair membership is invalid")
        allocated.extend(stage_pairs)
        orders: dict[str, list] = {identity: [] for identity in stage_pairs}
        for shown in value["presentations"]:
            if not isinstance(shown, dict) or shown.get("pair_id") not in orders:
                raise ContractError("presentation belongs to another stage")
            validate_presentation(by_id[shown["pair_id"]], shown)
            if shown["presentation_id"] in presentation_ids:
                raise ContractError("duplicate presentation")
            presentation_ids.add(shown["presentation_id"])
            orders[shown["pair_id"]].append(shown["order"])
        if any(len(value) != 2 or value[0] != value[1][::-1] for value in orders.values()):
            raise ContractError("each pair requires both inverse orders")
    if len(set(allocated)) != 24 or set(allocated) != set(by_id):
        raise ContractError("calibration and audit must be disjoint and exhaustive")


def _prepared(directory: Path) -> tuple[dict, list, dict]:
    _without_links(directory)
    if any(path.is_symlink() for path in directory.rglob("*")):
        raise ContractError("population paths may not contain symlinks")
    manifest = read_json(directory / "manifest.json")
    if not isinstance(manifest, dict) or manifest.get("status") != "prepared" or (
        manifest.get("selected_pairs") != 24 or manifest.get("model_requests") != 0
    ):
        raise ContractError("population is incomplete or incompatible")
    fixture = manifest.get("fixture", False)
    if type(fixture) is not bool:
        raise ContractError("invalid population fixture identity")
    if not fixture and (manifest.get("kind") != "muce-preparation" or any(
        manifest.get("source", {}).get(key) != value for key, value in SOURCE.items()
    )):
        raise ContractError("population is not the pinned MuCE source")
    if not fixture and (manifest.get("policy") != read_json(PROJECT / "configs/phase1/selection.json")
                        or manifest.get("policy_sha256") != digest(manifest.get("policy"))):
        raise ContractError("population differs from the approved selection policy identity")
    for name in ("pairs.json", "worklists.json"):
        if manifest.get("files", {}).get(name, {}).get("sha256") != file_hash(directory / name):
            raise ContractError("population input hash identity differs")
    pairs, work = read_json(directory / "pairs.json"), read_json(directory / "worklists.json")
    validate_worklists(pairs, work)
    if any(pair["fixture"] != fixture for pair in pairs):
        raise ContractError("population fixture identity differs")
    return manifest, pairs, work


def fixture_population(output: Path) -> dict:
    pairs: list[dict] = []
    labels: dict[str, list] = {"calibration": [], "audit": []}
    work: dict[str, Any] = {"schema_version": 1, "kind": "pair-worklists"}
    for stage in ("calibration", "audit"):
        work[stage] = {"pair_ids": [], "presentations": []}
        for index in range(12):
            pair = make_pair(f"fixture-{stage}-{index}", f"SYNTHETIC metaphor task {stage} {index}",
                             "synthetic-metaphors", [
                                 {"id": "fixture-ordinary", "text": "SYNTHETIC ordinary comparison."},
                                 {"id": "fixture-preferred", "text": "SYNTHETIC preferred comparison."},
                             ], fixture=True)
            order = [row["id"] for row in pair["responses"]]
            if index % 2:
                order.reverse()
            pairs.append(pair)
            work[stage]["pair_ids"].append(pair["pair_id"])
            work[stage]["presentations"].extend((make_presentation(pair, order), make_presentation(pair, order[::-1])))
            labels[stage].append(make_label(pair, "fixture-preferred", {"synthetic": True}))
    records = {"pairs.json": pairs, "worklists.json": work,
               **{f"labels.{stage}.json": value for stage, value in labels.items()}}
    for name, value in records.items():
        write_once(output / name, value)
    manifest = {"schema_version": 1, "kind": "fixture-preparation", "fixture": True,
                "status": "prepared", "selected_pairs": 24, "model_requests": 0,
                "files": {name: {"sha256": file_hash(output / name)} for name in records}}
    write_once(output / "manifest.json", manifest)
    return manifest


def stage_population(prepared: Path, output: Path, rubric: Path, image_id: str) -> dict:
    manifest, pairs, work = _prepared(prepared)
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise ContractError("staging requires the immutable runtime image identity")
    text = _without_links(rubric).read_text(encoding="utf-8")
    if not 0 < len(text.strip()) <= 20000:
        raise ContractError("invalid evaluator rubric")
    plan = {"pairs": pairs,
            "presentations": work["calibration"]["presentations"] + work["audit"]["presentations"],
            "stages": {stage: [shown["presentation_id"] for shown in work[stage]["presentations"]]
                       for stage in ("calibration", "audit")},
            "profile": PROFILE, "image_id": image_id}
    write_once(output / "plan.json", plan)
    write_once(output / "preparation.json", manifest)
    write_bytes_once(output / "initial-rubric.md", text.encode("utf-8"))
    bundle = {"schema_version": 1, "kind": "phase1-evaluator-bundle",
              "files": {name: file_hash(output / name) for name in (
                  "plan.json", "preparation.json", "initial-rubric.md")},
              "package_files": tree_hashes(Path(__file__).parent),
              "labels_staged": False}
    write_once(output / "bundle.json", bundle)
    return {"status": "staged", "fixture": pairs[0]["fixture"], "pairs": 24,
            "scheduled_presentations": 48, "bundle_sha256": digest(bundle), "provider_calls": 0}


def _bundle(run: Path) -> tuple[dict, dict, str]:
    _without_links(run)
    if any(path.is_symlink() for path in run.rglob("*")):
        raise ContractError("run paths may not contain symlinks")
    bundle = read_json(run / "bundle.json")
    if not isinstance(bundle, dict) or bundle.get("kind") != "phase1-evaluator-bundle" or (
        bundle.get("labels_staged") is not False
        or bundle.get("package_files") != tree_hashes(Path(__file__).parent)
        or set(bundle.get("files", {})) != {"plan.json", "preparation.json", "initial-rubric.md"}
    ):
        raise ContractError("staged bundle or code identity differs")
    for name, identity in bundle["files"].items():
        if file_hash(run / name) != identity:
            raise ContractError("staged input hash identity differs")
    plan = read_json(run / "plan.json")
    if plan.get("profile") != PROFILE:
        raise ContractError("unreviewed provider profile")
    return bundle, plan, (run / "initial-rubric.md").read_text(encoding="utf-8")


def _stage_state(run: Path, stage: str) -> tuple[dict, list]:
    state = replay_run(run / "execution")
    plan = read_json(run / "plan.json")
    identities = set(plan["stages"][stage])
    judgments = [value for value in state["judgments"] if value["presentation_id"] in identities]
    return state, judgments


def _audit_freeze(run: Path, bundle: dict) -> dict:
    path = run / "controls" / "audit-freeze.json"
    if not path.is_file():
        raise ContractError("audit requires its reviewed rubric freeze")
    record = read_json(path)
    _, judgments = _stage_state(run, "calibration")
    if not isinstance(record, dict) or record.get("bundle_sha256") != digest(bundle) or (
        not isinstance(record.get("rubric"), str)
        or record.get("rubric_sha256") != hashlib.sha256(record["rubric"].encode()).hexdigest()
        or record.get("calibration_judgments_sha256") != digest(judgments)
        or record.get("calibration_sha256") != file_hash(run / "assessments" / "calibration.json")
        or record.get("wording_revisions") not in (0, 1)
    ):
        raise ContractError("audit freeze identity differs")
    stage_path = run / "execution" / "stages" / "audit.json"
    if stage_path.exists():
        executed = read_json(stage_path)
        if executed.get("rubric") != record["rubric"] or executed.get("rubric_sha256") != record["rubric_sha256"]:
            raise ContractError("audit freeze differs from the executed rubric")
    return record


class FixtureTransport:
    fixture = True

    def count(self, request: dict) -> int:
        return 120

    def create(self, request: dict) -> dict:
        material = json.loads(request["messages"][0]["content"])
        choice = "A" if "SYNTHETIC preferred" in material["A"] else "B"
        return {"model": PROFILE["model"], "stop_reason": "end_turn",
                "text": json.dumps({"choice": choice, "reason": "Synthetic choice by explicit fixture marker."}),
                "usage": {"input_tokens": 120, "output_tokens": 20, "service_tier": "standard"}}


def judge(run: Path, stage: str, cap: int, *, fixture: bool) -> dict:
    if type(cap) is not int or not 0 < cap <= 5_000_000:
        raise ContractError("explicit authorization must be within the phase spending ceiling")
    bundle, plan, rubric = _bundle(run)
    maximum = 2
    if stage == "audit":
        frozen = _audit_freeze(run, bundle)
        rubric, maximum = frozen["rubric"], 24
    elif stage == "calibration":
        if (run / "controls" / "readiness.json").exists():
            review = read_json(run / "controls" / "readiness.json")
            state = replay_run(run / "execution")
            if review.get("run_id") != state["run_id"] or review.get("bundle_sha256") != digest(bundle):
                raise ContractError("readiness review identity differs")
            first_ids = set(plan["stages"]["calibration"][:2])
            first = [row for row in state["judgments"] if row["presentation_id"] in first_ids]
            if review.get("judgments_sha256") != digest(first):
                raise ContractError("readiness reviewed predictions differ")
            maximum = 24
    else:
        raise ContractError("unknown stage")
    if any(pair["fixture"] != fixture for pair in plan["pairs"]):
        raise ContractError("fixture/live invocation disagrees with the staged population")
    # Every gate precedes transport construction and credential access.
    transport = FixtureTransport() if fixture else DirectAnthropicTransport(
        api_key=os.environ.get("ANTHROPIC_API_KEY", "")
    )
    return run_stage(run / "execution", plan, stage=stage, rubric=rubric, transport=transport,
                     authorization_micro_usd=cap, max_presentations=maximum)


def record_readiness(run: Path, decision: str) -> dict:
    bundle, plan, _ = _bundle(run)
    if not (run / "execution" / "manifest.json").exists():
        raise ContractError("readiness requires the first two completed calibration presentations")
    state, judgments = _stage_state(run, "calibration")
    if state["status"] != "ready" or len(judgments) != 2 or any(row["status"] != "ok" for row in judgments):
        raise ContractError("readiness requires two valid calibration responses and complete accounting")
    if {row["presentation_id"] for row in judgments} != set(plan["stages"]["calibration"][:2]):
        raise ContractError("readiness presentations differ")
    if not decision.strip() or len(decision) > 4000:
        raise ContractError("readiness review requires an explicit decision")
    record = {"schema_version": 1, "kind": "phase1-readiness-review", "run_id": state["run_id"],
              "bundle_sha256": digest(bundle), "judgments_sha256": digest(judgments),
              "decision": decision, "fixture": state["fixture"]}
    write_once(run / "controls" / "readiness.json", record)
    return record


def freeze_audit(run: Path, rubric: Path, decision: str) -> dict:
    bundle, _, initial = _bundle(run)
    if not (run / "assessments" / "calibration.json").exists():
        raise ContractError("audit freeze requires completed calibration analysis")
    state, judgments = _stage_state(run, "calibration")
    if state["status"] != "ready" or len(judgments) != 24:
        raise ContractError("audit freeze requires complete calibration and accounting")
    if not (run / "controls" / "readiness.json").exists():
        raise ContractError("audit freeze requires readiness review")
    text = _without_links(rubric).read_text(encoding="utf-8")
    if not 0 < len(text.strip()) <= 20000 or not decision.strip() or len(decision) > 4000:
        raise ContractError("invalid rubric or missing review decision")
    record = {"schema_version": 1, "kind": "phase1-audit-freeze", "bundle_sha256": digest(bundle),
              "calibration_sha256": file_hash(run / "assessments" / "calibration.json"),
              "calibration_judgments_sha256": digest(judgments), "rubric": text,
              "rubric_sha256": hashlib.sha256(text.encode()).hexdigest(),
              "wording_revisions": int(initial != text), "decision": decision}
    write_once(run / "controls" / "audit-freeze.json", record)
    return record


def report_stage(prepared: Path, run: Path, stage: str) -> dict:
    bundle, plan, _ = _bundle(run)
    if not (run / "execution" / "manifest.json").exists():
        raise ContractError("analysis requires a complete stage prediction set")
    state, judgments = _stage_state(run, stage)
    if len(judgments) != 24 or state["status"] != "ready":
        raise ContractError("analysis requires all stage predictions and complete accounting")
    if stage == "audit":
        frozen = _audit_freeze(run, bundle)
        # Publish predictions before even resolving the audit label path.
        write_once(run / "controls" / "audit-predictions.json", {
            "schema_version": 1, "kind": "committed-audit-predictions", "run_id": state["run_id"],
            "freeze_sha256": digest(frozen), "judgments": judgments, "judgments_sha256": digest(judgments),
        })
    population, _, work = _prepared(prepared)
    if population != read_json(run / "preparation.json"):
        raise ContractError("analysis population identity differs")
    label_path = prepared / f"labels.{stage}.json"
    if file_hash(label_path) != population["files"][label_path.name]["sha256"]:
        raise ContractError("human label hash identity differs")
    labels = read_json(label_path)
    pairs = [pair for pair in plan["pairs"] if pair["pair_id"] in work[stage]["pair_ids"]]
    report = analyze_pairs(pairs, work[stage]["presentations"], judgments, labels)
    report["stage"] = stage
    # A later stage cannot change the accounting embedded in an immutable earlier report.
    intents = [read_json(path) for path in sorted((run / "execution" / "attempts").glob("*.intent.json"))]
    scoped = [value for value in intents if value["stage"] == stage]
    spent = sum(read_json(run / "execution" / "attempts" / f'{value["attempt"]:04}.result.json').get(
        "spent_micro_usd", 0
    ) for value in scoped)
    report["execution"] = {
        "scope": stage, "status": "ready", "run_id": state["run_id"], "fixture": state["fixture"],
        "attempts": len(scoped), "retries": len(scoped) - len({value["presentation_id"] for value in scoped}),
        "spent_micro_usd": spent, "reserved_micro_usd": 0, "finalized_presentations": len(judgments),
        "token_count_requests": len(scoped), "provider_calls": 0 if state["fixture"] else len(scoped),
    }
    if stage == "calibration":
        report["interpretation"] = "Development diagnostics; acceptance floors apply only to the audit."
    else:
        report["phase_execution"] = {key: value for key, value in state.items() if key != "judgments"}
    write_once(run / "assessments" / f"{stage}.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--source", type=Path, required=True)
    prepare.add_argument("--metadata", type=Path, required=True)
    prepare.add_argument("--policy", type=Path, default=PROJECT / "configs/phase1/selection.json")
    prepare.add_argument("--output", type=Path, required=True)
    fixture = commands.add_parser("fixture")
    fixture.add_argument("--output", type=Path, required=True)
    stage = commands.add_parser("stage")
    stage.add_argument("--prepared", type=Path, required=True)
    stage.add_argument("--output", type=Path, required=True)
    stage.add_argument("--rubric", type=Path, default=PROJECT / "configs/phase1/rubric.md")
    for name in ("judge", "inspect", "readiness-review", "freeze-audit", "analyze", "preview"):
        command = commands.add_parser(name)
        command.add_argument("--run", type=Path, required=True)
        if name in ("judge", "analyze"):
            command.add_argument("--stage", choices=("calibration", "audit"), required=True)
        if name == "judge":
            command.add_argument("--cap-micro-usd", type=int, required=True)
        if name in ("readiness-review", "freeze-audit"):
            command.add_argument("--decision", required=True)
        if name == "freeze-audit":
            command.add_argument("--rubric", type=Path, required=True)
        if name == "analyze":
            command.add_argument("--prepared", type=Path, required=True)
    args = parser.parse_args()
    try:
        live = os.environ.get("BUDDHA2_PHASE1_LIVE") == "1"
        if live:
            if sys.platform != "linux" or args.command != "judge":
                raise ContractError("live launcher permits only the judge command")
        else:
            _offline()
        if args.command == "prepare":
            result = prepare_muce(_without_links(args.source), read_json(_without_links(args.metadata)),
                                  read_json(_without_links(args.policy)), _output(args.output))
        elif args.command == "fixture":
            output = _output(args.output)
            prepared, run = output / "population", output / "evaluator"
            fixture_population(prepared)
            stage_population(prepared, run, PROJECT / "configs/phase1/rubric.md", os.environ["BUDDHA2_IMAGE_ID"])
            judge(run, "calibration", 5_000_000, fixture=True)
            record_readiness(run, "Synthetic fixture review; no provider readiness claim.")
            judge(run, "calibration", 5_000_000, fixture=True)
            report_stage(prepared, run, "calibration")
            freeze_audit(run, run / "initial-rubric.md", "Keep synthetic fixture rubric.")
            judge(run, "audit", 5_000_000, fixture=True)
            result = report_stage(prepared, run, "audit")
        elif args.command == "stage":
            result = stage_population(_output(args.prepared), _output(args.output), args.rubric,
                                      os.environ["BUDDHA2_IMAGE_ID"])
        else:
            run = _output(args.run)
            if args.command == "judge":
                _, plan, _ = _bundle(run)
                if plan["image_id"] != os.environ.get("BUDDHA2_IMAGE_ID"):
                    raise ContractError("staged and actual runtime image identities differ")
                if not live and not all(pair["fixture"] for pair in plan["pairs"]):
                    raise ContractError("non-fixture judging requires explicit live launch authorization")
                result = judge(run, args.stage, args.cap_micro_usd, fixture=not live)
            elif args.command == "inspect":
                result = replay_run(run / "execution")
            elif args.command == "readiness-review":
                result = record_readiness(run, args.decision)
            elif args.command == "freeze-audit":
                result = freeze_audit(run, args.rubric, args.decision)
            elif args.command == "analyze":
                result = report_stage(_output(args.prepared), run, args.stage)
            else:
                bundle, plan, rubric = _bundle(run)
                first = plan["presentations"][0]
                pair = next(value for value in plan["pairs"] if value["pair_id"] == first["pair_id"])
                request = request_preview(pair, first, rubric)
                write_once(run / "controls" / "first-request.json", request)
                result = {"bundle_sha256": digest(bundle), "request_sha256": digest(request),
                          "scheduled_presentations": 48, "generation_attempt_ceiling": 52,
                          "maximum_reservation_micro_usd": 1_896_960, "provider_calls": 0}
        # CLI output omits response texts, reasons, and the held-out label records.
        summary = {key: value for key, value in result.items() if key not in ("judgments", "prompts")}
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True, allow_nan=False))
        return 0
    except (ContractError, OSError, ValueError) as exc:
        print(f"Phase 1 refused: {type(exc).__name__}" if live else f"Phase 1 refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
