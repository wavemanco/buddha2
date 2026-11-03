"""An offline-only native C1 demonstration; no live command or grant route."""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
from pathlib import Path
from typing import Any


def output_path(value: str) -> Path:
    """Reject foreign, existing and linked outputs before creating anything."""
    root_value = os.environ.get("BUDDHA2_OUTPUT_ROOT")
    if not root_value:
        raise ValueError("BUDDHA2_OUTPUT_ROOT must name the contained output mount")
    root = Path(root_value) / "phase3a-compat-c1-v1"
    output = Path(value)
    if (not root.is_absolute() or not output.is_absolute() or ".." in output.parts
            or not output.is_relative_to(root) or output == root):
        raise ValueError("output must be a new directory beneath the C1 output root")
    for path in (output, *output.parents):
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise ValueError("linked output paths are forbidden")
    if output.exists():
        raise ValueError("demo requires a fresh output; existing evidence is never overwritten")
    return output


def _offline_runtime() -> None:
    if os.environ.get("BUDDHA2_OUTPUT_ROOT") != "/results":
        raise ValueError("demo requires the fixed contained /results mount")
    if sys.platform != "linux" or {p.name for p in Path("/sys/class/net").iterdir()} != {"lo"}:
        raise ValueError("demo requires the pinned Linux runtime with network denied")


def synthetic_tasks() -> list[dict]:
    from buddha2.artifacts import digest
    return [{"pilot_id": f"p3a-{i:02}", "parent_task_id": f"c1-synthetic-{i:02}",
              "prompt": "SYNTHETIC compatibility task: suggest ten useful ways to welcome a visitor.",
              "source_context": {"dataset": "C1 explicitly synthetic software fixture",
                  "revision": digest({"synthetic_revision": "c1-v1"})[:40],
                  "source_sha256": digest({"synthetic_task": i}), "source_task_id": f"synthetic-{i:02}"},
              "arm_order": ["fixed", "adaptive"]} for i in range(1, 5)]


def demo(output: Path) -> dict[str, Any]:
    """Run exactly one synthetic adaptive cell through actual native orchestration."""
    _offline_runtime()
    from buddha2 import phase2_am1_controls as am1
    from buddha2.artifacts import digest, file_hash, write_once
    from followups.phase3a_v1 import accounting, native, strategy, workflow

    from .adapter import CompatibleProposer
    from .mocks import SDKMock
    from .support import ROOT, preservation, require, runtime_identity, source_identity

    # Validate again for programmatic callers; no execution can select another root.
    output = output_path(str(output))
    source = source_identity()
    before = preservation()
    require(before["passed"], "closed public preservation failed before demo")
    runtime = runtime_identity()
    output.mkdir(parents=True, exist_ok=False)
    write_once(output / "source.json", source)
    write_once(output / "runtime.json", runtime)
    write_once(output / "preservation-before.json", before)
    nonce = digest({"source": source["sha256"], "output": str(output)})[:20]
    tag = "c1-synthetic-" + nonce
    tasks = synthetic_tasks()
    for entry in tasks:
        strategy._task(workflow._task(entry))
    carrier = {"execution_tag": tag, "tasks": tasks}
    slots, assessment_plan = workflow._plan_slots(carrier)
    require(len(slots) == 775, "strict inherited ledger carrier differs")
    study = {"kind": "phase3a-c1-synthetic-demo-study-v1", "fixture": True,
        "source_sha256": source["sha256"], "runtime_sha256": digest(runtime),
        "policy_sha256": digest(accounting.POLICY), "execution_tag": tag,
        "tasks": tasks, "slots": slots, "assessment_plan": assessment_plan,
        "executed_scope": {"pilot": "p3a-01", "arm": "adaptive", "roles": ["plan", "answer", "rank", "editor"]},
        "carrier_only": "Unexecuted slots enforce the inherited ledger shape; they are not a planned experiment.",
        "real_provider_calls": 0, "real_spent_micro_usd": 0}
    study["study_sha256"] = digest(study)
    write_once(output / "study.json", study)
    authority = {"study_sha256": study["study_sha256"], "authorization_id": "c1-synthetic-fixture-only",
        "authorized": False, "cap_micro_usd": accounting.POLICY["phase_micro_usd"],
        "canary_cap_micro_usd": accounting.POLICY["first_micro_usd"], "expansion_authorized": False,
        "control_policy_sha256": am1.CONTROL_SHA256, "billing_profile": am1.BILLING_PROFILE}
    bindings = {"source_sha256": source["sha256"], "policy_sha256": study["policy_sha256"],
                "launcher_sha256": file_hash(Path(__file__))}
    write_once(output / "fixture-authority.json", authority)
    tools = json.loads((ROOT / "followups/phase3a_v1/editor-tools.json").read_text(encoding="utf-8"))
    seed = output / "seed"
    strategy.materialize_seed(seed)
    task = workflow._task(tasks[0])
    with SDKMock() as mock:
        require(mock.transport.fixture is True, "demo refuses a live transport")
        ledger = accounting.Ledger(output / "journal", study_sha256=study["study_sha256"],
            slots=slots, authority=authority, transport=mock.transport, bindings=bindings, editor_tools=tools)

        def dispatch(slot: str, role: str, request: dict) -> dict:
            meta = slots.get(slot)
            if (meta is None or meta["role"] != role or meta["pair"] != "p3a-01"
                    or meta["cell"] != "p3a-01:adaptive" or role not in {"plan", "answer", "rank", "editor"}):
                ledger.halt("c1_demo_scope_violation")
                raise accounting.IntegrityStop("demo refuses fixed, judging or other-prompt dispatch")
            return ledger.dispatch(slot, role, request, checkpoint="canary")

        proposer = CompatibleProposer(pilot="p3a-01", study_sha256=study["study_sha256"],
            dispatch=dispatch, audit_dir=output / "adapt/editor-audit", fixture=True,
            halt=ledger.halt, register_contract=mock.register_contract, source_sha256=source["sha256"])
        result = native.run_adaptation(task, seed, study_sha256=study["study_sha256"],
            run_root=output / "adapt", tag=workflow._native_tag(carrier, "p3a-01"), dispatch=dispatch,
            fixture=True, prop=proposer, known_results={}, result_snapshot=lambda: ledger.state()["results"],
            halt=ledger.halt)
        state = ledger.state()
        # Retain observed fixture evidence even when a following acceptance check fails.
        write_once(output / "native-result.json", result)
        write_once(output / "model-visible-proof.json", mock.c1_sessions)
        write_once(output / "editor-proof.json", proposer.phase3a_evidence())
        write_once(output / "contract-proof.json", proposer.c1_evidence())
        write_once(output / "mock-http-records.json", mock.records)
        write_once(output / "ledger-replay.json", state)
        require(result["status"] == "complete" and result["authentic"] is False,
                "synthetic native result is incomplete or mislabeled live")
        require(state["status"] == "ready" and state["provider_calls"] == 0,
                "fixture ledger halted or claims real provider activity")
        counts = collections.Counter(row["role"] for row in state["results"].values())
        require(counts == {"plan": 4, "answer": 40, "rank": 4, "editor": 20}
                and state["attempts"] == mock.http_calls == len(mock.records) == 68,
                "composite fixture call topology differs")
        require(all(row["status"] == "response" and row["reserved_micro_usd"] == 0
                    for row in state["results"].values()), "fixture has missing/unknown usage")
        stages = {row["label"]: row for row in result["stage_dispositions"]}
        require(set(stages) == {"inv1", "dom1", "agg1"}
                and all(row["authentic_eligible"] and not row["fell_back"] and not row["terminal_note_used"]
                        for row in stages.values())
                and stages["dom1"]["kept_base"] and not stages["inv1"]["kept_base"],
                "fixture stage eligibility/unchanged decision differs")
        require(set(mock.c1_sessions) == {"inv1.a1", "dom1.a1", "agg1.a1"}, "fixture stage delivery proof is missing")
        for proof in mock.c1_sessions.values():
            require(proof["mission_visible_before_evidence"] and proof["configured_system_visible_before_mission"]
                    and proof["decision_after_complete_evidence"] and proof["verification_after_write"]
                    and proof["normal_final"] and proof["notes_reread_model_visible"]
                    and proof["ordinary_rounds"] <= 7 and not proof["terminal_note_used"],
                    "fixture did not deliver/verify/complete within ordinary rounds")
        require(accounting.replay(output / "journal") == state, "saved ledger replay differs")
    after_source = source_identity()
    require(after_source == source, "effective source changed during demo; result cannot be accepted")
    after = preservation()
    require(after["passed"] and after["public_inventory_sha256"] == before["public_inventory_sha256"],
            "closed public evidence changed during demo")
    write_once(output / "source-after.json", after_source)
    write_once(output / "preservation-after.json", after)
    report = {"kind": "phase3a-c1-synthetic-demo-report-v1", "status": "synthetic-demo-complete",
        "fixture": True, "study_sha256": study["study_sha256"], "source_sha256": source["sha256"],
        "runtime_sha256": digest(runtime), "synthetic_http_calls": 68, "synthetic_role_counts": dict(counts),
        "fixture_accounted_micro_usd": sum(row["spent_micro_usd"] for row in state["results"].values()),
        "real_provider_calls": 0, "real_spent_micro_usd": 0, "remaining_carrier_slots_not_experiments": 707,
        "native_rollouts": 4, "editor_rounds": {label: proof["ordinary_rounds"] for label, proof in mock.c1_sessions.items()},
        "stage_dispositions": [{key: row[key] for key in ("label", "kept_base", "fell_back", "authentic_eligible",
                                                        "terminal_note_used", "effective_changed")}
                               for row in result["stage_dispositions"]],
        "preservation_passed": True, "ledger_replay_identical": True,
        "live_readiness_established": False, "scientific_effectiveness_established": False,
        "full_c1_acceptance_established_by_demo_alone": False,
        "limitations": "Scripted SDK responses prove a mechanical native path; real-model behavior remains untested."}
    write_once(output / "report.json", report)
    text = ("# C1 synthetic native demonstration\n\n"
            "Completed one actual pinned Harness²/OpenCode fixture path with four C-N rollouts.\n"
            "All source evidence was delivered before the scripted decisions; edits and notes were reread.\n"
            "INV edits, DOM normally keeps the base, and AGG composes. All stages finish before the terminal instruction.\n\n"
            "Synthetic HTTP calls: 68 (48 solver, 20 editor). Real provider calls and API spend: 0.\n"
            "The other 707 inherited ledger carrier slots are unexecuted mechanical declarations, not experiments.\n"
            "Closed evidence and source identities were checked before/after; ledger replay is identical.\n\n"
            "This demonstration does not establish live-model authoring readiness, scientific effectiveness,\n"
            "or the full C1 acceptance suite by itself. No live route or spending authority is provided.\n")
    from buddha2.artifacts import write_bytes_once
    write_bytes_once(output / "DEMO_REPORT.md", text.encode("utf-8"))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("demo", help="run one network-disabled synthetic native fixture")
    command.add_argument("--output", required=True, help="fresh directory beneath the C1 output mount")
    args = parser.parse_args(argv)
    try:
        result = demo(Path(args.output))
    except Exception as error:
        print(json.dumps({"status": "incomplete", "error_type": type(error).__name__,
                          "provider_calls_authorized": False}), file=sys.stderr)
        return 1
    print(json.dumps({key: result[key] for key in ("status", "study_sha256", "synthetic_http_calls",
                                                  "real_provider_calls", "real_spent_micro_usd")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
