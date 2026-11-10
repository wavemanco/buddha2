"""Versioned, read-only P4 continuation display adapter; no experimental source changes."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from buddha2.artifacts import digest, file_hash, write_once
from buddha2.phase2_contracts import validate_portfolio
from followups.phase3b_seq2_v1.core_view import _blocked
from followups.phase4_cm1_v1 import release, snapshot, workflow
from followups.phase4_cm1_v1.inspect_export import aggregate_usage, validate_snapshot

VERSION = "phase4-continuation-passive-projector-v1"


def build_snapshot(study_path: Path, grant_path: Path) -> dict:
    """Validate saved science first, then count each physical journal exactly once."""
    with _blocked():
        return _build_snapshot(study_path, grant_path)


def _build_snapshot(study_path: Path, grant_path: Path) -> dict:
    require = snapshot._require
    study = workflow.load_study(study_path)
    require(bool(study.get("continuation")), "a prepared P4 continuation is required")
    outcome = workflow.report(study_path, grant_path)
    fixture = outcome["fixture"]
    run, _ = release.paths(study, fixture)
    observed: dict[Path, str | None] = {}
    def read(path):
        return snapshot._read(path, observed)

    require(read(study_path) == study, "study changed after saved validation")
    read(grant_path)
    require(read(run / "outcome.json") == outcome and outcome.get("active_child") is None,
            "project only a stable, closed saved execution")
    manifest = read(run / "confirmation-manifest.json")
    require(manifest == read(study_path.parent / "confirmation-manifest.json")
            and manifest["manifest_sha256"] == digest({k: v for k, v in manifest.items() if k != "manifest_sha256"})
            and manifest["frozen_method_sha256"] == study["continuation"]["original_method_sha256"]
            and len(manifest["selected"]) == 24, "original 24-case frame differs")
    cases = {f"p4-{i:02d}": {"id": row["source_task_id"], "prompt": "", "metrics": None,
        "outputs": None, "events": [], "model_usage": {}, "started_at": None, "completed_at": None,
        "undated_requests": [], "pair": f"p4-{i:02d}", "physical_executions": [],
        "usage_scope": "cumulative confirmation inference/assessment known usage; qualification excluded"}
        for i, row in enumerate(manifest["selected"], 1)}
    hashes = {f"p4-{i:02d}": row["prompt_sha256"] for i, row in enumerate(manifest["selected"], 1)}
    segments, qualifications, assessments = [], [], {}
    seen: dict[str, tuple[str, str, str]] = {}
    originals, adopted = [], {}
    for entry in study["continuation"]["children"]:
        for key in ("open", "closure", "result"):
            if entry.get(key) is not None:
                value = read(release._referenced(entry[key]))
                if key == "result" and entry["kind"] == "inference" and all(
                        (value.get(arm) or {}).get("status") == "complete" for arm in ("adaptive", "fixed")):
                    adopted[entry["pair"]] = value
        originals.append(("origin", entry["kind"], entry["pair"], release._referenced(entry["open"])))
    current = [("current", entry["kind"], entry["pair"], Path(entry["path"]) / "open.json")
               for entry in outcome["closed_children"]]
    for origin, kind, pair, opened_path in originals + current:
        opened = read(opened_path)
        child = opened["child_sha256"]
        identity = (kind, pair, digest(opened))
        if child in seen:
            require(seen[child] == identity, "conflicting physical execution identity")
            continue
        seen[child] = identity
        _, state, ledger, audits = snapshot._ledger(opened, fixture, observed)
        require(ledger["inputs"]["study_sha256"] == child and ledger["inputs"]["fixture"] is fixture,
                "physical journal mode/identity differs")
        profile = opened["profile"]["phase4_child"]
        events, usage, undated = snapshot.project_requests(state, audits)
        segment = {"origin": origin, "kind": kind, "pair": pair, "child_sha256": child,
            "logical_study_sha256": profile.get("continuation", {}).get("logical_study_sha256", child),
            "generation_study_sha256": opened.get("generation_study_sha256"),
            **{key: state[key] for key in ("attempts", "spent_micro_usd", "reserved_micro_usd")},
            "model_usage": usage, "undated_request_count": len(undated)}
        segments.append(segment)
        if kind == "dev":
            qualifications.append({**segment, "events": events, "undated_requests": undated})
            continue
        require(pair in cases and kind in {"inference", "assessment"}, "foreign confirmation unit")
        case, task = cases[pair], opened["task"]
        require(task["id"] == case["id"] and digest(task["prompt"]) == hashes[pair], "saved task differs from frame")
        case["prompt"] = task["prompt"]
        case["physical_executions"].append(segment)
        case["events"].extend(events)
        case["undated_requests"].extend(undated)
        case["model_usage"] = aggregate_usage([case, {"model_usage": usage}])
        if origin == "current" and kind == "assessment":
            assessments[pair] = read(opened_path.parent / "result.json")
    for key in ("attempts", "spent_micro_usd", "reserved_micro_usd"):
        require(sum(row[key] for row in segments) == outcome[key], "physical accounting does not reconcile with saved outcome")
    combined = run / "combined-assessments.json"
    if combined.exists():
        assessments = {row["pair"]: row for row in read(combined)["rows"]}
    require(set(assessments).issubset(cases), "foreign saved assessment pair")
    inference_pairs = {row["pair"] for row in segments if row["kind"] == "inference"}
    for pair, case in cases.items():
        path = run / "generations" / (pair + ".json")
        generation = read(path) if path.exists() else adopted.get(pair)
        if generation is not None:
            require(pair in inference_pairs, "generation lacks a verified physical origin")
            task, logical = generation["task"], generation["generation_study_sha256"]
            require(generation["pair"] == pair and task["id"] == case["id"]
                    and digest(task["prompt"]) == hashes[pair], "canonical generation differs from frame")
            case.update(prompt=task["prompt"], generation_study_sha256=logical)
            adaptive, fixed = generation.get("adaptive") or {}, generation.get("fixed") or {}
            outputs = {"fixed": fixed.get("portfolio"), "c1": adaptive.get("checkpoints", {}).get("c1"),
                "c2": adaptive.get("checkpoints", {}).get("c2"), "selected_checkpoint": adaptive.get("selected_checkpoint")}
            require(outputs["selected_checkpoint"] in (None, "c1", "c2"), "foreign checkpoint choice")
            for portfolio in (outputs[key] for key in ("fixed", "c1", "c2")):
                if portfolio is not None:
                    validate_portfolio(portfolio)
                    require(portfolio["fixture"] is fixture and portfolio["task"] == task
                            and portfolio["provenance"]["study_sha256"] == logical, "logical portfolio identity differs")
            choice = outputs["selected_checkpoint"]
            require(choice is None or outputs[choice] is not None and adaptive["portfolio"] == outputs[choice],
                    "saved native selection differs")
            case["outputs"] = outputs if any(outputs[key] is not None for key in ("fixed", "c1", "c2")) else None
        if pair in assessments:
            row = assessments[pair]
            require(row["prompt_id"] == case["id"] and row["selected_checkpoint"]
                    == (case["outputs"] or {}).get("selected_checkpoint"), "assessment task/choice differs")
            case["metrics"] = {"targets": snapshot._targets(row, case["outputs"], {"id": case["id"]}, fixture),
                               "selected_checkpoint": row["selected_checkpoint"]}
        case["events"].sort(key=lambda row: (snapshot._utc(row["timestamp"]), row["data"]["slot_id"]))
        if case["events"]:
            case["started_at"] = min(snapshot._utc(row["data"]["started_at"]) for row in case["events"]).isoformat()
            case["completed_at"] = max(snapshot._utc(row["data"]["completed_at"]) for row in case["events"]).isoformat()
    analysis = read(run / "analysis.json") if (run / "analysis.json").exists() else None
    panels = {row["prompt_id"]: row for row in analysis["pairs"]} if analysis else {}
    for case in cases.values():
        if case["id"] in panels:
            case["metrics"] = {**(case["metrics"] or {}), "analysis_panel": copy.deepcopy(panels[case["id"]])}
    require(release.source_identity() == study["source"] and all(
        (file_hash(path) if path.exists() else None) == expected for path, expected in observed.items()),
        "saved source artifacts changed during passive projection")
    payload = {"kind": "phase4-cm1-snapshot-v1", "projector": {"kind": VERSION, "sha256": file_hash(Path(__file__))},
        "study_sha256": study["study_sha256"], "source_sha256": study["source_sha256"],
        "definition_sha256": study["method"]["definition_sha256"], "fixture": fixture, "status": outcome["status"],
        "scope": "confirmation_24_prompt_units", "analysis": analysis, "read_only_sources_unchanged": True,
        "original_frame_method_sha256": manifest["frozen_method_sha256"], "execution_method_sha256": study["method_sha256"],
        "accounting": {key: copy.deepcopy(outcome[key]) for key in ("attempts", "spent_micro_usd", "reserved_micro_usd",
            "spent_by_allocation_micro_usd", "reserved_by_allocation_micro_usd", "historical_held_micro_usd")},
        "physical_executions": segments, "qualification": {"scope": "development only; excluded from confirmation cases",
            "executions": qualifications, "model_usage": aggregate_usage(qualifications)},
        "cases": sorted(cases.values(), key=lambda row: row["id"]),
        "source_artifacts": [{"path": str(path), "sha256": value} for path, value in sorted(observed.items()) if value is not None]}
    validate_snapshot(payload)
    return payload


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("study", "grant", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args(argv)
    payload = build_snapshot(args.study, args.grant)
    write_once(release.path(args.output), payload)
    print(json.dumps({"projector": VERSION, "snapshot_sha256": digest(payload),
                      "cases": len(payload["cases"]), "provider_calls": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
