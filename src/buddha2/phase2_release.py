"""Complete Phase 2B execution release: preparation, authority and saved evidence.

The ordinary command remains offline. Provider execution is exposed only through
the inspected host launcher, with a completed release gate and an explicit grant.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
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
    PROJECT,
    _output,
    _templates,
    make_worklist,
    render_request,
    validate_study,
)
from .phase2_am1_controls import (
    BILLING_PROFILE,
    CONTROL_POLICY,
    CONTROL_SHA256,
    admission,
    reservation,
    runtime_guard,
)
from .phase2_decisions import POLICIES, build_decision

PARENT = "d4287971e712a15a08ffba0e8e1de3b1bcd89e8f5c7e049c860fde02e1910475"
EVIDENCE = PROJECT / "evidence/phase2-release-r018"
BUDGET_POLICY: dict[str, Any] = {"revision": "p2r-cumulative-authority-v1", "first_stage_max_micro_usd": 20_000_000,
                 "phase_max_micro_usd": 125_000_000, "first_slots_max": 55, "phase_slots_max": 1320}
FIXTURE_CUTOFF = "2026-10-27T06:32:04Z"


def _input(path: Path) -> Path:
    path = Path(path)
    if any(item.is_symlink() for item in (path, *path.parents)):
        raise ContractError("release inputs cannot traverse links")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ContractError(f"release input is unavailable: {path.name}") from exc
    roots = (PROJECT, Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", PROJECT / "runs")).resolve())
    if not any(resolved.is_relative_to(root) for root in roots):
        raise ContractError("release inputs must remain within the new project")
    return resolved


def _parent() -> dict:
    path = PROJECT / "runs/phase2-am1-r016/candidate/study.json"
    study = read_json(path)
    validate_study(study, current_sources=False)
    if study["study_sha256"] != PARENT or tree_hashes(path.parent / "source") != study["package_files"]:
        raise ContractError("retained AM-1 parent/source differs")
    return study


def _definition() -> dict:
    from .phase2_native import NativeAssessment

    study = copy.deepcopy(_parent())
    study.pop("study_sha256")
    if study["templates"] != _templates() or study["worklist"] != make_worklist(study["tasks"]):
        raise ContractError("the declared scientific task/strategy contract differs")
    native = NativeAssessment(PROJECT / ".upstream/novelty-bench")
    if study["native_evaluator"] != native.identity:
        raise ContractError("native evaluator differs from the preserved parent")
    if any(file_hash(PROJECT / name) != value for name, value in study["lockfiles"].items()):
        raise ContractError("runtime dependency locks differ")
    review = read_json(EVIDENCE / "pricing-profile-review.json")
    if review.get("status") != "public-payg-envelope-confirmed":
        raise ContractError("the dated public pricing/profile review is incomplete")
    study.update({
        "specification": "0.18", "release": "p2r-complete-execution-v1",
        "specification_sha256": file_hash(EVIDENCE / "specification-0.18.md"),
        "block_definition_sha256": file_hash(EVIDENCE / "block-definition-0.18.md"),
        "preparation_start_sha256": file_hash(EVIDENCE / "execution-start.json"),
        "parent_preparation_sha256": PARENT,
        "package_files": tree_hashes(PROJECT / "src/buddha2"),
        "launcher_sha256": file_hash(PROJECT / "phase2-release.ps1"),
        "admission": copy.deepcopy(CONTROL_POLICY), "control_policy_sha256": CONTROL_SHA256,
        "billing_profile": BILLING_PROFILE,
        "budget_policy": copy.deepcopy(BUDGET_POLICY), "budget_policy_sha256": digest(BUDGET_POLICY),
        "pricing_profile_review_sha256": file_hash(EVIDENCE / "pricing-profile-review.json"),
        "decision_policies": copy.deepcopy(POLICIES), "decision_policy_sha256": digest(POLICIES),
        "caps": {**study["caps"], "proposed_micro_usd": BUDGET_POLICY["phase_max_micro_usd"],
                 "canary_micro_usd": BUDGET_POLICY["first_stage_max_micro_usd"], "grant_required": True},
        "execution_scope": "complete 24-block phase; first block then reviewed, cumulatively authorized expansion",
        "static_input_candidates": [
            {"task_id": task["id"], "role": role,
             **admission(role, render_request(role, task, templates=study["templates"]))}
            for task in study["tasks"] for role in ("answer", "plan")
        ],
        "execution_authorized": False,
        "remaining_live_prerequisites": [
            "completed source-bound P2-R offline release acceptance",
            "applicable explicit stage grant and operator confirmation of supported public PAYG/current prices",
            "explicitly supplied credentials through the inspected provider launcher",
            "actual account/model/settings/usage acceptance observed only in the counted first block",
            "saved first-block review and cumulative grant before expansion",
        ],
    })
    study["study_sha256"] = digest(study)
    return study


def validate_release(study: dict, source: Path | None = None) -> None:
    if not isinstance(study, dict) or study != _definition():
        raise ContractError("release differs from its frozen source/control/launcher/scientific definition")
    if source is not None and tree_hashes(_input(source)) != study["package_files"]:
        raise ContractError("retained release source bundle differs")


def load_release(path: Path) -> dict:
    path = _input(path)
    study = read_json(path)
    validate_release(study, path.parent / "source")
    return study


def canonical_run(study: dict, fixture: bool) -> Path:
    if type(fixture) is not bool:
        raise ContractError("release mode must be explicitly fixture or live")
    root = Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", PROJECT / "runs")).resolve(strict=True)
    if not fixture and (root != Path("/results") or PROJECT != Path("/workspace")):
        raise ContractError("live release requires the fixed inspected /workspace and /results mounts")
    return root / "phase2-release-r018" / study["study_sha256"] / ("mock" if fixture else "live")


def cost_sheet(study: dict) -> dict:
    counts = Counter(row["role"] for row in study["worklist"]["slots"].values())
    first = Counter(row["role"] for row in study["worklist"]["slots"].values()
                    if row["checkpoint"] == "canary")
    rates = {role: reservation(role) for role in counts}
    return {"kind": "p2r-cost-and-authorization-proposal", "study_sha256": study["study_sha256"],
            "currency": "USD", "price_review_sha256": study["pricing_profile_review_sha256"],
            "counts": dict(counts), "first_counts": dict(first),
            "reservation_micro_usd_per_role": rates,
            "sum_first_envelopes_micro_usd": sum(first[role] * rates[role] for role in first),
            "sum_full_envelopes_micro_usd": sum(counts[role] * rates[role] for role in counts),
            "proposed_first_stage_micro_usd": BUDGET_POLICY["first_stage_max_micro_usd"],
            "proposed_cumulative_micro_usd": BUDGET_POLICY["phase_max_micro_usd"],
            "authorized": False, "expected_expenditure_measured": False,
            "basis": "Conservative per-request public-price liability envelopes, not expected invoices. "
                     "Cumulative grants never reset prior settled/reserved cost; unknown usage halts. "
                     "Proposed $20/$125 limits can stop the pilot incomplete."}


def prepare(output: Path) -> dict:
    runtime_guard()
    output = _output(output)
    study = _definition()
    for name in study["package_files"]:
        write_bytes_once(output / "source" / name, (PROJECT / "src/buddha2" / name).read_bytes())
    write_bytes_once(output / "launcher/phase2-release.ps1", (PROJECT / "phase2-release.ps1").read_bytes())
    write_once(output / "study.json", study)
    validate_release(study, output / "source")
    write_once(output / "cost-sheet.json", cost_sheet(study))
    write_once(output / "launch-packet.json", {
        "kind": "p2r-unapproved-launch-packet", "study_sha256": study["study_sha256"],
        "source_sha256": digest(study["package_files"]),
        "control_policy_sha256": CONTROL_SHA256, "launcher_sha256": study["launcher_sha256"],
        "billing_profile": BILLING_PROFILE, "budget_policy": BUDGET_POLICY,
        "authorized": False, "provider_requests_authorized": 0, "account_access_verified": False,
        "live_billing_verified": False, "operator_keys_supplied": False,
        "remaining": study["remaining_live_prerequisites"],
        "cost_sheet_sha256": digest(cost_sheet(study)),
    })
    return {"status": "prepared-offline", "study_sha256": study["study_sha256"],
            "source_files": len(study["package_files"]), "request_slots": 1320,
            "orders": 72, "provider_calls": 0, "execution_authorized": False}


def _live_readiness(study: dict, path: Path) -> None:
    record = read_json(_input(path.parent / "release-readiness.json"))
    if (record.get("kind") != "p2r-offline-release-acceptance"
            or record.get("acceptance_sha256") != digest({key: value for key, value in record.items()
                                                         if key != "acceptance_sha256"})
            or record.get("study_sha256") != study["study_sha256"]
            or record.get("source_sha256") != digest(study["package_files"])
            or record.get("launcher_sha256") != study["launcher_sha256"]
            or record.get("control_policy_sha256") != CONTROL_SHA256
            or record.get("requirements") != {f"R-{i}": "pass" for i in range(1, 10)}
            or record.get("offline_gate_passed") is not True
            or not isinstance(record.get("evidence"), dict) or not record["evidence"]):
        raise ContractError("the source-bound offline release gate is not complete")
    for name, expected in record["evidence"].items():
        if file_hash(_input(PROJECT / name)) != expected:
            raise ContractError("release acceptance evidence differs")


def launch_preflight(study_path: Path, grant_path: Path, stage: str, fixture: bool) -> dict:
    """No SDK, secret lookup or dispatch; validate source and exact staged authority."""
    from .phase2_release_journal import (
        AuthorityError,
        LiabilityError,
        initialize_journal,
        journal_identity,
        replay_journal,
        validate_grant,
    )

    runtime_guard()
    path = _input(study_path)
    study = load_release(path)
    if stage not in ("first", "expansion") or type(fixture) is not bool:
        raise ContractError("invalid release stage/mode")
    grant = read_json(_input(grant_path))
    if grant.get("stage") != stage or grant.get("fixture") is not fixture:
        raise ContractError("grant stage/mode differs from the requested launch")
    if not fixture:
        _live_readiness(study, path)
    run = canonical_run(study, fixture)
    initialize_journal(run / "journal", study, fixture=fixture)
    checked_grant = validate_grant(run / "journal", study, grant)
    state = replay_journal(run / "journal")
    if (checked_grant["authority_sha256"] != state.get("authority_sha256")
            and grant["previous_authority_sha256"] != state.get("authority_sha256")):
        raise AuthorityError("launch grant is historical rather than active or the next explicit authority")
    if state["status"] != "ready" or state["reserved_micro_usd"] != 0:
        raise LiabilityError("unresolved phase liability blocks launch before credential access")
    return {"kind": "p2r-nonsending-preflight", "study_sha256": study["study_sha256"],
            "source_sha256": digest(study["package_files"]),
            "control_policy_sha256": CONTROL_SHA256, "launcher_sha256": study["launcher_sha256"],
            "budget_policy_sha256": study["budget_policy_sha256"], "billing_profile": BILLING_PROFILE,
            "grant_sha256": grant["grant_sha256"], "journal_id": journal_identity(study, fixture),
            "stage": stage, "fixture": fixture, "run": str(run), "provider_calls": 0,
            "credentials_read": False, "authority_checked": True, "source_checked": True}


def launch_execute(study_path: Path, grant_path: Path, stage: str, transport: Any,
                   cutoff: str | None = None) -> dict:
    from .phase2_release_journal import publish_grant
    from .phase2_release_runner import run_stage

    checked = launch_preflight(study_path, grant_path, stage, transport.fixture)
    study = load_release(study_path)
    run = Path(checked["run"])
    publish_grant(run / "journal", study, read_json(_input(grant_path)))
    return run_stage(study, run, stage=stage, transport=transport, cutoff=cutoff)


def load_execution(study_path: Path, run: Path, *, cutoff: str | None = None) -> tuple[dict, dict]:
    from .phase2_release_runner import snapshot

    study = load_release(study_path)
    run = _output(run)
    return study, snapshot(study, run, cutoff=cutoff)


def save_bundle(output: Path, bundle: dict) -> None:
    output = _output(output)
    for name, value in bundle.items():
        write_once(output / f"{name}.json", value)


def report(study_path: Path, run: Path, output: Path, *, cutoff: str | None = None) -> dict:
    study, snapshot = load_execution(study_path, run, cutoff=cutoff)
    output = _output(output)
    save_bundle(output, snapshot["bundle"])
    write_once(output / "coverage.json", snapshot["coverage"])
    write_once(output / "summary.json", snapshot["summary"])
    decision = snapshot["bundle"]["decision"]
    analysis = snapshot["bundle"]["analysis"]
    selected = decision["synthetic_selected_method"] if snapshot["state"]["fixture"] else decision["selected_method"]
    roles = analysis["unique_request_cost_micro_usd_by_role"]
    generation = sum(roles.get(role, 0) for role in ("answer", "plan", "rank"))
    assessment = sum(roles.get(role, 0) for role in ("group", "quality"))
    write_bytes_once(output / "PHASE2_REPORT.md", (
        "# Phase 2 benchmark report\n\n"
        + ("Synthetic software rehearsal; no model, provider or human outcomes were observed.\n\n"
           if snapshot["state"]["fixture"] else "Development-only native benchmark results.\n\n")
        + f"Study: {study['study_sha256']}. Track: benchmark. Status: {decision['status']}.\n\n"
        + f"Native coverage: {snapshot['bundle']['native_assessment']['coverage']['assessment_records']}/72. "
        + f"Actual request attempts: {snapshot['state']['attempts']}. "
        + f"Accounted public-price upper bound: {snapshot['state']['spent_micro_usd']} micro-USD; "
        + f"unresolved reservation: {snapshot['state']['reserved_micro_usd']} micro-USD.\n\n"
        + f"Selected procedure{' (synthetic only)' if snapshot['state']['fixture'] else ''}: "
        + f"{selected or 'none; evidence is incomplete or ineligible'}.\n\n"
        + f"Mean native utility A/B/C: {json.dumps(analysis['mean_utility'], sort_keys=True)}. "
        + f"Primary paired contrasts: {json.dumps(analysis['contrasts'], sort_keys=True)}. "
        + "Missing means and contrasts remain null.\n\n"
        + f"Unique generation/planning/ranking cost: {generation} micro-USD; "
        + f"native assessment cost: {assessment} micro-USD. "
        + "Candidate C includes B's generation cost for comparison; the ledger charges it once.\n\n"
        + "See analysis.json for paired prompt means/contrasts, distinctness, quality, statuses, latency "
        + "and costs; coverage.json retains every planned slot. Human input is optional and absent "
        + "from this benchmark decision. Saved outputs remain independently assessable.\n"
    ).encode("utf-8"))
    return {"status": decision["status"], "fixture": snapshot["state"]["fixture"],
            "decision_sha256": decision["decision_sha256"], "provider_calls": 0,
            "new_generation_requests": 0, "output": str(output)}


def _now() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--output", type=Path, required=True)
    for name in ("inspect", "preflight", "grant-template", "review", "run-first", "run-remaining",
                 "report", "replay", "human-packets", "human-import", "human-decide"):
        command = commands.add_parser(name)
        command.add_argument("--study", type=Path, required=True)
        if name not in ("inspect",):
            command.add_argument("--run", type=Path)
            command.add_argument("--fixture", action="store_true")
            command.add_argument("--cutoff")
        if name in ("preflight", "run-first", "run-remaining"):
            command.add_argument("--grant", type=Path, required=True)
        if name in ("preflight", "grant-template"):
            command.add_argument("--stage", choices=("first", "expansion"), default="first")
        if name == "grant-template":
            command.add_argument("--grant-id", required=True)
            command.add_argument("--cap-micro-usd", type=int)
            command.add_argument("--authorize-live", action="store_true")
            command.add_argument("--confirm-public-payg", action="store_true")
        if name == "review":
            command.add_argument("--review-id", required=True)
            command.add_argument("--approve", action="store_true")
        if name in ("grant-template", "report", "replay", "human-packets", "human-import", "human-decide"):
            command.add_argument("--output", type=Path, required=True)
        if name == "human-import":
            command.add_argument("--submissions", type=Path, required=True)
            command.add_argument("--window", type=Path)
            command.add_argument("--previous", type=Path)
        if name == "human-decide":
            command.add_argument("--human-assessment", type=Path, required=True)
            command.add_argument("--parent", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        from . import phase2_release_journal as journal
        from .__main__ import _offline, _upstreams

        _offline()
        _upstreams()
        if args.command == "prepare":
            result = prepare(args.output)
        else:
            study = load_release(args.study)
            if args.command == "inspect":
                result = {"study_sha256": study["study_sha256"], "budget_policy": study["budget_policy"],
                          "cost_sheet": cost_sheet(study), "execution_authorized": False, "provider_calls": 0}
            elif args.command == "preflight":
                result = launch_preflight(args.study, args.grant, args.stage, args.fixture)
            else:
                fixture = args.fixture
                run = _output(args.run) if args.run else canonical_run(study, fixture)
                cutoff = args.cutoff
                if args.command == "grant-template":
                    journal.initialize_journal(run / "journal", study, fixture=fixture)
                    state = journal.replay_journal(run / "journal")
                    cap = args.cap_micro_usd if args.cap_micro_usd is not None else BUDGET_POLICY[
                        "first_stage_max_micro_usd" if args.stage == "first" else "phase_max_micro_usd"]
                    ceiling = BUDGET_POLICY["first_stage_max_micro_usd" if args.stage == "first"
                                             else "phase_max_micro_usd"]
                    if type(cap) is not int or not 0 < cap <= ceiling:
                        raise ContractError("grant amount exceeds its frozen stage planning ceiling")
                    if args.authorize_live:
                        if fixture or not args.confirm_public_payg:
                            raise ContractError("live authority requires explicit public PAYG confirmation and live mode")
                        _live_readiness(study, _input(args.study))
                    grant = journal.grant_template(study, fixture=fixture, stage=args.stage,
                        grant_id=args.grant_id, cumulative_cap_micro_usd=cap, authorized=args.authorize_live,
                        previous_authority_sha256=state.get("authority_sha256"),
                        review_sha256=state.get("review_sha256") if args.stage == "expansion" else None)
                    write_once(_output(args.output) / "grant.json", grant)
                    result = {"status": "fixture-grant" if fixture else
                              "explicit-live-grant" if args.authorize_live else "unapproved-live-grant-template",
                              "grant_sha256": grant["grant_sha256"], "authorized": args.authorize_live,
                              "provider_calls": 0}
                elif args.command == "review":
                    review = journal.make_first_review(run / "journal", study,
                        review_id=args.review_id, cutoff=cutoff or _now(), approved=args.approve)
                    journal.publish_review(run / "journal", study, review)
                    result = review
                elif args.command in ("run-first", "run-remaining"):
                    if not fixture or run != canonical_run(study, True):
                        raise ContractError("ordinary CLI runs only the canonical offline mock; use the guarded provider launcher")
                    from .phase2_am1_mock import SDKMock

                    stage = "first" if args.command == "run-first" else "expansion"
                    launch_preflight(args.study, args.grant, stage, True)
                    with SDKMock() as mock:
                        result = launch_execute(args.study, args.grant, stage, mock.transport, cutoff)
                        for row in mock.records:
                            write_once(run / "wire" / f"{row['slot_id']}.json", row)
                        result["new_mock_http_calls"] = mock.http_calls
                elif args.command in ("report", "replay"):
                    result = report(args.study, run, args.output, cutoff=cutoff)
                else:
                    from .phase2_analysis import build_human_packets
                    from .phase2_human import make_human_assessment

                    study, saved = load_execution(args.study, run, cutoff=cutoff)
                    if saved["state"]["fixture"] is not fixture:
                        raise ContractError("requested human operation mode differs from saved execution")
                    output = _output(args.output)
                    if args.command == "human-packets":
                        packets = build_human_packets(study, saved["portfolios"], fixture=fixture)
                        for reader, packet in packets["packets"].items():
                            write_once(output / f"{reader}.json", packet)
                        write_once(output / "private/unit-mapping.json", packets["private_mapping"])
                        result = {"status": "local-packets-only", "human_collection_started": False, "provider_calls": 0}
                    elif args.command == "human-import":
                        record = make_human_assessment(study, saved["portfolios"], read_json(_input(args.submissions)),
                            cutoff=cutoff or _now(), fixture=fixture,
                            window=read_json(_input(args.window)) if args.window else None,
                            previous=read_json(_input(args.previous)) if args.previous else None)
                        write_once(output / "human-assessment.json", record)
                        result = {"assessment_sha256": record["assessment_sha256"], "complete": record["complete"], "provider_calls": 0}
                    else:
                        from .phase2_native import NativeAssessment

                        bundle = build_decision(study, saved["portfolios"], saved["assessments"], saved["state"],
                            NativeAssessment(PROJECT / ".upstream/novelty-bench"), track="human-augmented",
                            cutoff=cutoff or _now(), fixture=fixture,
                            human_assessment=read_json(_input(args.human_assessment)), parent=read_json(_input(args.parent)))
                        save_bundle(output, bundle)
                        result = bundle["decision"]
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
