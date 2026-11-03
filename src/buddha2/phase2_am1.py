"""AM-1 preparation, non-sending preflight and bounded first-block execution.

The public command exposes only offline preparation and actual-SDK mock HTTP.
Historical studies must use their retained source; they are never relabelled.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from .artifacts import (
    ContractError,
    digest,
    file_hash,
    read_json,
    tree_hashes,
    write_bytes_once,
    write_once,
)
from .phase2 import (
    IMAGE_ID,
    PROJECT,
    _output,
    _templates,
    generate_order,
    make_worklist,
    rank_order,
    render_request,
    validate_study,
)
from .phase2_am1_controls import (
    BILLING_PROFILE,
    CONTROL_POLICY,
    CONTROL_SHA256,
    admission,
    canonical_live_journal,
    reservation,
    runtime_guard,
)
from .phase2_contracts import export_native, slot_prefix
from .phase2_coverage import slot_coverage
from .phase2_decisions import build_decision
from .phase2_dispatch import Dispatcher, replay_dispatch, writer_lock

PARENT = "84fcfa743a45ac8dd2cf2e4b4d7ecec1e76b9e8b42b633c90a0325ff0623df92"
EVIDENCE = PROJECT / "evidence/phase2-am1-r016"
DEFAULT_CUTOFF = "2026-10-27T05:37:10Z"


def _parent() -> dict:
    path = PROJECT / "runs/phase2-r012/frozen-study/study.json"
    study = read_json(path)
    validate_study(study, current_sources=False)
    if study["study_sha256"] != PARENT or tree_hashes(path.parent / "source") != study["package_files"]:
        raise ContractError("preserved r012 parent/source differs")
    return study


def _definition() -> dict:
    from .phase2_native import NativeAssessment

    study = copy.deepcopy(_parent())
    study.pop("study_sha256")
    if study["templates"] != _templates() or study["worklist"] != make_worklist(study["tasks"]):
        raise ContractError("fixed strategies or full-study worklist differ")
    if study["native_evaluator"] != NativeAssessment(PROJECT / ".upstream/novelty-bench").identity:
        raise ContractError("native evaluator differs")
    if any(file_hash(PROJECT / name) != value for name, value in study["lockfiles"].items()):
        raise ContractError("pinned dependency locks differ")
    proof_names = ("admission-review.json", "billing-review.json", "gate-decision.json")
    decision = read_json(EVIDENCE / "gate-decision.json")
    if decision.get("outcome") != "pass-for-declared-public-payg-profile":
        raise ContractError("AM-1 evidence gate has not passed")
    study.update({
        "specification": "0.16",
        "specification_sha256": file_hash(EVIDENCE / "specification-0.16.md"),
        "preparation_start_sha256": file_hash(EVIDENCE / "before.json"),
        "parent_preparation_sha256": PARENT,
        "package_files": tree_hashes(PROJECT / "src/buddha2"),
        "admission": copy.deepcopy(CONTROL_POLICY),
        "control_policy_sha256": CONTROL_SHA256,
        "billing_profile": BILLING_PROFILE,
        "evidence_gate": {name: file_hash(EVIDENCE / name) for name in proof_names},
        "static_input_candidates": [
            {"task_id": task["id"], "role": role,
             **admission(role, render_request(role, task, templates=study["templates"]))}
            for task in study["tasks"] for role in ("answer", "plan")
        ],
        "caps": {**study["caps"], "proposed_micro_usd": None, "canary_micro_usd": None,
                 "grant_required": True},
        "execution_scope": "first selected task / repeat 1 only; expansion disabled",
        "remaining_live_prerequisites": [
            "applicable explicit grant bound to this study/control/public PAYG profile",
            "operator verification of current public PAYG account/pricing/geography compatibility",
            "separate explicit-key network launch; account/model access and real billing unverified",
            "review counted first-block results before any expansion",
        ],
        "execution_authorized": False,
    })
    study["study_sha256"] = digest(study)
    return study


def validate_candidate(study: dict, source: Path | None = None) -> None:
    if not isinstance(study, dict) or study != _definition():
        raise ContractError("AM-1 candidate differs from its exact source/control/parent definition")
    if source is not None and tree_hashes(source) != study["package_files"]:
        raise ContractError("retained AM-1 source bundle differs")


def cost_sheet(study: dict) -> dict:
    counts = Counter(value["role"] for value in study["worklist"]["slots"].values())
    first = Counter(value["role"] for value in study["worklist"]["slots"].values()
                    if value["checkpoint"] == "canary")
    amounts = {role: reservation(role) for role in counts}
    return {
        "study_sha256": study["study_sha256"], "control_policy_sha256": CONTROL_SHA256,
        "price_date_local": "2026-10-26", "currency": "USD", "billing_profile": BILLING_PROFILE,
        "reservation_micro_usd_per_role": amounts, "first_block_counts": dict(first),
        "full_worklist_counts": dict(counts),
        "first_block_sum_max_micro_usd": sum(first[role] * amounts[role] for role in first),
        "full_worklist_sum_max_micro_usd": sum(counts[role] * amounts[role] for role in counts),
        "authorized": False, "expected_expenditure_established": False,
        "limitation": "Sum of conservative per-request envelopes, not expected expenditure or a grant. "
                      "Serial settlement releases reservations; an unresolved attempt halts with liability. "
                      "Geographic envelope charges can exceed the eventual invoice. Old $5/$125 proposals "
                      "are not revised grants; $5 cannot admit a quality request.",
    }


def prepare(output: Path) -> dict:
    output = _output(output)
    if os.environ.get("BUDDHA2_IMAGE_ID") != IMAGE_ID or tuple(sys.version_info[:3]) != (3, 12, 15):
        raise ContractError("AM-1 preparation requires the pinned image/Python")
    study = _definition()
    for name in study["package_files"]:
        write_bytes_once(output / "source" / name, (PROJECT / "src/buddha2" / name).read_bytes())
    write_once(output / "study.json", study)
    validate_candidate(study, output / "source")
    write_once(output / "cost-sheet.json", cost_sheet(study))
    packet = {"kind": "am1-unapproved-launch-packet", "authorized": False,
              "study_sha256": study["study_sha256"], "control_policy_sha256": CONTROL_SHA256,
              "billing_profile": BILLING_PROFILE, "provider_calls_authorized": 0,
              "expansion_authorized": False, "first_block_request_slots_max": 55,
              "live_access_verified": False, "account_profile_verified": False,
              "required_before_live": study["remaining_live_prerequisites"],
              "cap_micro_usd": None, "canary_cap_micro_usd": None,
              "cost_sheet_sha256": digest(cost_sheet(study))}
    write_once(output / "authorization-request.json", packet)
    return {"status": "prepared-offline", "study_sha256": study["study_sha256"],
            "provider_calls": 0, "execution_authorized": False}


def preflight(study: dict) -> dict:
    """Validate/render only; never instantiate a transport or read credentials."""
    validate_candidate(study)
    block, = [row for row in study["worklist"]["blocks"] if row["checkpoint"] == "canary"]
    task = next(row for row in study["tasks"] if row["id"] == block["task_id"])
    requests = {role: render_request(role, task, templates=study["templates"])
                for role in ("answer", "plan")}
    return {"status": "offline-preflight-only", "study_sha256": study["study_sha256"],
            "first_block": block, "static_requests": requests,
            "admission": {role: admission(role, request) for role, request in requests.items()},
            "dynamic_requests": "Own B angle, all B texts for ranking, and native group/head quality "
                                "are checked at dispatch; static rendering cannot admit them early.",
            "provider_calls": 0, "credential_access": False, "live_ready": False,
            "authorization_required": True, "cost_sheet": cost_sheet(study)}


def mock_grant(study: dict) -> dict:
    maximum = cost_sheet(study)["first_block_sum_max_micro_usd"]
    return {"study_sha256": study["study_sha256"], "authorization_id": "synthetic-am1-mock-only",
            "authorized": False, "cap_micro_usd": maximum, "canary_cap_micro_usd": maximum,
            "expansion_authorized": False, "control_policy_sha256": CONTROL_SHA256,
            "billing_profile": BILLING_PROFILE}


def first_block(study: dict, output: Path, transport: Any, *, authorization: dict,
                cutoff: str = DEFAULT_CUTOFF) -> dict:
    """Only the fixed first block; the full-study denominator remains unchanged."""
    from .phase2_native import NativeAssessment

    validate_candidate(study)
    runtime_guard()
    output = _output(output)
    if transport.fixture is not True:
        canonical = canonical_live_journal(study["study_sha256"]).parent
        if output != canonical:
            raise ContractError("live first block requires its single canonical study journal")
    # The run owner spans all requests and report finalization, not just one call.
    with writer_lock(output / "owner"):
        return _first_block_locked(study, output, transport, authorization, cutoff, NativeAssessment)


def _first_block_locked(study: dict, output: Path, transport: Any, authorization: dict,
                        cutoff: str, native_type: Any) -> dict:
    slots = {key: value for key, value in study["worklist"]["slots"].items()
             if value["checkpoint"] == "canary"}
    if len(slots) != 55 or authorization.get("expansion_authorized") is not False:
        raise ContractError("first-block runner refuses expansion")
    dispatcher = Dispatcher(output / "journal", study_sha256=study["study_sha256"], slots=slots,
                            authorization=authorization, transport=transport, control_policy=CONTROL_POLICY)
    native = native_type(PROJECT / ".upstream/novelty-bench")
    block, = [row for row in study["worklist"]["blocks"] if row["checkpoint"] == "canary"]
    task = next(row for row in study["tasks"] if row["id"] == block["task_id"])
    fixture = transport.fixture
    portfolios, assessments = [], []
    # Verify every saved artifact before resuming any external work. A hash-valid
    # but foreign portfolio cannot be accepted merely because its path matches.
    previous_portfolios, previous_assessments = [], []
    expected_prefixes = {slot_prefix(task["id"], method, 1) for method in ("A", "B", "C")}
    for path in sorted((output / "portfolios").glob("*.json")):
        portfolio = read_json(path)
        prefix = slot_prefix(portfolio["task"]["id"], portfolio["provenance"]["method"],
                             portfolio["provenance"]["repeat"])
        if path.stem != prefix or prefix not in expected_prefixes:
            raise ContractError("saved portfolio is outside the first block")
        previous_portfolios.append(portfolio)
    for path in sorted((output / "assessments").glob("*.json")):
        matching = next((row for row in previous_portfolios if slot_prefix(
            row["task"]["id"], row["provenance"]["method"], row["provenance"]["repeat"]) == path.stem), None)
        if matching is None:
            raise ContractError("saved assessment lacks its first-block portfolio")
        previous_assessments.append({**read_json(path), "method": matching["provenance"]["method"],
                                     "repeat": 1, "order_id": path.stem,
                                     "study_sha256": study["study_sha256"]})
    build_decision(study, previous_portfolios, previous_assessments,
                   replay_dispatch(output / "journal"), native, track="benchmark", cutoff=cutoff,
                   fixture=fixture)

    def failure(stage: str, error: ContractError) -> None:
        write_once(output / "failures" / f"{stage}.json", {"stage": stage, "error": str(error)})

    def dispatch(slot: str, role: str, request: dict, **kwargs: Any) -> dict:
        if hasattr(transport, "select"):
            transport.select(role, slot)
        return dispatcher.dispatch(slot, role, request, **kwargs)

    saved = {}
    for method in block["generation_order"]:
        prefix = slot_prefix(task["id"], method, 1)
        path = output / "portfolios" / f"{prefix}.json"
        if path.exists():
            saved[method] = read_json(path)
            continue
        if replay_dispatch(output / "journal")["status"] != "ready":
            break
        try:
            saved[method] = generate_order(study, task, 1, method, dispatch,
                                           checkpoint="canary", fixture=fixture)
        except ContractError as exc:
            failure("generation-" + method, exc)
            if replay_dispatch(output / "journal")["status"] != "ready":
                break
        if method in saved:
            write_once(path, saved[method])
    child_path = output / "portfolios" / f"{slot_prefix(task['id'], 'C', 1)}.json"
    if child_path.exists():
        saved["C"] = read_json(child_path)
    elif "B" in saved and replay_dispatch(output / "journal")["status"] == "ready":
        try:
            saved["C"] = rank_order(study, saved["B"], dispatch, checkpoint="canary")
        except ContractError as exc:
            failure("rank", exc)
    for method in ("A", "B", "C"):
        if method not in saved:
            continue
        portfolio = saved[method]
        prefix = slot_prefix(task["id"], method, 1)
        write_once(output / "portfolios" / f"{prefix}.json", portfolio)
        export_native(portfolio, output / "native" / prefix)
        if native.load_export(output / "native" / prefix) != portfolio:
            raise ContractError("native export/import changed the portfolio")
        portfolios.append(portfolio)
        assessment_path = output / "assessments" / f"{prefix}.json"
        if assessment_path.exists():
            assessment = read_json(assessment_path)
            assessments.append({**assessment, "method": method, "repeat": 1, "order_id": prefix,
                                "study_sha256": study["study_sha256"]})
            continue
        if replay_dispatch(output / "journal")["status"] != "ready":
            continue
        try:
            assessment = native.assess(portfolio, dispatch, checkpoint="canary")
            write_once(output / "assessments" / f"{prefix}.json", assessment)
            assessments.append({**assessment, "method": method, "repeat": 1, "order_id": prefix,
                                "study_sha256": study["study_sha256"]})
        except ContractError as exc:
            failure("assessment-" + method, exc)
    state = replay_dispatch(output / "journal")
    coverage = slot_coverage(study, state["results"], portfolios, assessments)
    bundle = build_decision(study, portfolios, assessments, state, native,
                            track="benchmark", cutoff=cutoff, fixture=fixture)
    if bundle["decision"]["status"] != "inconclusive" or bundle["decision"]["selected_method"] is not None:
        raise ContractError("first-block evidence cannot select a study seed")
    expected_portfolios = {output / "portfolios" / f"{slot_prefix(task['id'], method, 1)}.json"
                           for method in saved}
    if set((output / "portfolios").glob("*.json")) != expected_portfolios:
        raise ContractError("run contains a portfolio outside the first block")
    expected_assessments = {output / "assessments" / f"{row['order_id']}.json" for row in assessments}
    if set((output / "assessments").glob("*.json")) != expected_assessments:
        raise ContractError("run contains an assessment outside the first block")
    failures = [read_json(path) for path in sorted((output / "failures").glob("*.json"))]
    snapshot = {"coverage": coverage, "bundle": bundle, "state": state, "failures": failures}
    snapshot_id = digest(snapshot)
    destination = output / "snapshots" / snapshot_id
    for name, value in (("coverage", coverage), ("state", state), ("failures", failures), *bundle.items()):
        write_once(destination / f"{name}.json", value)
    return {"status": "mock-first-block-complete" if fixture and len(assessments) == 3 else "first-block-partial",
            "fixture": fixture, "study_sha256": study["study_sha256"], "snapshot_sha256": snapshot_id,
            "snapshot": str(destination), "orders": len(assessments), "attempts": state["attempts"],
            "reserved_micro_usd": state["reserved_micro_usd"], "provider_calls": state["provider_calls"],
            "experiment_api_spend_micro_usd": 0 if fixture else None,
            "decision_status": bundle["decision"]["status"], "selected_method": None,
            "missing_assessments": bundle["native_assessment"]["coverage"]["missing_assessments"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--output", type=Path, required=True)
    for name in ("inspect", "preflight", "mock-first-block"):
        command = commands.add_parser(name)
        command.add_argument("--study", type=Path, required=True)
        if name == "mock-first-block":
            command.add_argument("--output", type=Path, required=True)
            command.add_argument("--partition", choices=("distinct", "pairs"), default="distinct")
    args = parser.parse_args(argv)
    try:
        from .__main__ import _offline, _upstreams

        _offline()
        _upstreams()
        if args.command == "prepare":
            result = prepare(args.output)
        else:
            study = read_json(args.study)
            validate_candidate(study, args.study.parent / "source")
            if args.command in ("inspect", "preflight"):
                result = preflight(study)
            else:
                from .phase2_am1_mock import SDKMock

                with SDKMock(partition=args.partition) as mock:
                    result = first_block(study, args.output, mock.transport, authorization=mock_grant(study))
                    for row in mock.records:
                        write_once(_output(args.output) / "wire" / f"{row['slot_id']}.json", row)
                    result["new_mock_http_calls"] = mock.http_calls
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
