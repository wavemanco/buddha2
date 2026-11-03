"""Pure reporting of validated completion-study evidence; never dispatches work."""
from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import Any

from buddha2.artifacts import ContractError, digest, write_bytes_once, write_once
from followups.phase3a_v1 import workflow as parent

ARMS = ("fixed", "adaptive")
ROOT = Path(__file__).resolve().parents[2]


def _require(value: bool, message: str) -> None:
    if not value:
        raise ContractError(message)


def _metrics(assessment: dict | None) -> dict:
    if not assessment or assessment.get("status") != "scored":
        return {"utility": None, "distinct": None}
    metrics = assessment.get("metrics", {})
    _require(all(type(metrics.get(k)) in (int, float) and math.isfinite(metrics[k])
                 for k in ("utility", "distinct")), "scored assessment lacks finite native metrics")
    return copy.deepcopy(metrics)


def _plan(study: dict) -> tuple[dict, dict]:
    primary, diagnostics = {}, []
    pilots = [task["pilot_id"] for task in study["tasks"]]
    _require(len(pilots) == len(set(pilots)) == 4, "report requires four distinct paired tasks")
    for row in study["assessment_plan"]:
        if row.get("diagnostic"):
            diagnostics.append(row)
        else:
            key = (row["pilot"], row["arm"])
            _require(key not in primary, "duplicate primary assessment plan")
            primary[key] = row
    _require(set(primary) == {(p, a) for p in pilots for a in ARMS}
             and len(diagnostics) == 1 and diagnostics[0]["pilot"] == pilots[0]
             and diagnostics[0]["arm"] == "fixed", "report assessment population differs")
    return primary, diagnostics[0]


def _diagnostic(primary: dict | None, repeated: dict | None, assessment_id: str) -> dict:
    result: dict[str, Any] = {"assessment_id": assessment_id,
        "status": repeated.get("status", "missing") if repeated else "missing",
        "primary_unchanged": True, "partition_equal": None, "utility_difference": None,
        "shared_head_positions": [], "shared_head_score_disagreements": None}
    if not primary or not repeated or primary.get("status") != "scored" or repeated.get("status") != "scored":
        return result
    p, r = primary["native"], repeated["native"]
    ps, rs = p["fields"]["generation_scores"], r["fields"]["generation_scores"]
    shared = [i for i in range(10) if ps[i] is not None and rs[i] is not None]
    pp, rp = p["partition_fields"]["partition"], r["partition_fields"]["partition"]
    result.update(partition_equal=all((pp[i] == pp[j]) == (rp[i] == rp[j])
                                    for i in range(10) for j in range(10)),
        utility_difference=_metrics(repeated)["utility"] - _metrics(primary)["utility"],
        shared_head_positions=shared,
        shared_head_score_disagreements=sum(ps[i] != rs[i] for i in shared))
    return result


def build(study: dict, state: dict, saved: dict, fixture: bool) -> dict:
    """Project already-validated study/ledger/native records without changing them."""
    _require(type(fixture) is bool and state["fixture"] is fixture, "report mode differs from ledger")
    primary, diagnostic_plan = _plan(study)
    branches, assessments = saved["branches"], saved["assessments"]
    validation_failure = copy.deepcopy(saved.get("validation_failure"))
    if validation_failure is not None:
        branches, assessments = {}, {}
    readiness = copy.deepcopy(saved.get("readiness"))
    ready = isinstance(readiness, dict) and readiness.get("passed") is True
    rows = []
    for task in study["tasks"]:
        pilot = task["pilot_id"]
        for arm in ARMS:
            branch = branches.get((pilot, arm))
            result = (branch.get("result") or {}) if branch else {}
            portfolio = result.get("portfolio")
            aid = primary[pilot, arm]["id"]
            assessment = assessments.get(aid)
            scores = ((assessment or {}).get("native", {}).get("fields") or {}).get("generation_scores")
            metrics = _metrics(assessment) if portfolio else {"utility": None, "distinct": None}
            rows.append({"pilot": pilot, "parent_task_id": task["parent_task_id"], "arm": arm,
                "branch_status": result.get("status", branch.get("failure")) if branch else "not_attempted",
                "final_sha256": digest(portfolio) if portfolio else None,
                "assessment_id": aid, "assessment_sha256": digest(assessment) if assessment else None,
                "status": (assessment.get("status", "unscored") if assessment else
                    "assessment_budget_stop" if state.get("assessment_stopped") else "unscored")
                    if portfolio else "missing_final",
                "metrics": metrics,
                "first_answer_quality": scores[0] if scores and assessment.get("status") == "scored" else None,
                "authentic": bool(not fixture and arm == "adaptive" and result.get("authentic")),
                "inference_accounting": copy.deepcopy(state["cells"].get(pilot + ":" + arm)),
                "native_actions": copy.deepcopy(result.get("native", {}).get("modes", {}).get("agg", {}).get("ledger"))
                    if arm == "adaptive" else None,
                "native_action_cost_is_authoritative": False,
                "stage_dispositions": copy.deepcopy(result.get("stage_dispositions")) if arm == "adaptive" else None,
                "fixed_candidate_dispositions": [{"run_id": c["run_id"], "status": c["status"],
                    "reason": c.get("reason")} for c in result.get("candidates", [])] if arm == "fixed" else None})
            if validation_failure is not None:
                rows[-1].update(status="unvalidated_integrity_hold", branch_status="unvalidated_integrity_hold")
    unknown = sum(r["status"] != "response" for r in state["results"].values())
    pending = len(set(state["intents"]) - set(state["results"]))
    authentic = any(row["authentic"] for row in rows)
    complete = (all(row["status"] == "scored" for row in rows) and ready and state["status"] == "ready"
                and state["reserved_micro_usd"] == 0 and not unknown and not pending
                and validation_failure is None and (fixture or authentic))
    pairs = []
    for task in study["tasks"]:
        paired = {row["arm"]: row for row in rows if row["pilot"] == task["pilot_id"]}
        scored = all(paired[arm]["status"] == "scored" for arm in ARMS)
        pairs.append({"pilot": task["pilot_id"], "adaptive_minus_fixed":
            paired["adaptive"]["metrics"]["utility"] - paired["fixed"]["metrics"]["utility"] if scored else None,
            "adaptive_minus_fixed_distinct": paired["adaptive"]["metrics"]["distinct"]
                - paired["fixed"]["metrics"]["distinct"] if scored else None})
    first = study["tasks"][0]["pilot_id"]
    diagnostic = _diagnostic(assessments.get(primary[first, "fixed"]["id"]),
                             assessments.get(diagnostic_plan["id"]), diagnostic_plan["id"])
    diagnostic_classified = diagnostic["status"] != "missing"
    complete = complete and diagnostic_classified
    mean = sum(pair["adaptive_minus_fixed"] for pair in pairs) / 4 if complete else None
    direction = ("adaptive" if mean > 0 else "fixed" if mean < 0 else "tie") if mean is not None else None
    analysis = {"kind": "phase3a-c1-completion-analysis-v1", "pairs": pairs,
        "independent_prompt_units": 4, "mean_adaptive_minus_fixed": mean,
        "complete_primary": complete, "scientific_complete": complete and not fixture,
        "authentic_live_path": authentic, "fixture": fixture,
        "selected_method": direction if complete and not fixture else None,
        "descriptive_direction": direction, "selection_is_descriptive_only": True,
        "readiness_passed": ready, "diagnostic_classified": diagnostic_classified, "diagnostic": diagnostic,
        "held_evidence_failure": validation_failure,
        "limits": ["Four exposed development prompts; no population, held-out, human-preference or equal-realized-compute causal claim.",
                   "A diagnostic repeat never replaces a primary; synthetic contrasts select no real method."]}
    coverage = parent._coverage(study, state, {**saved, "branches": branches, "assessments": assessments})
    for slot, classification in coverage["slots"].items():
        if classification != "not_attempted":
            continue
        meta = study["slots"][slot]
        if not ready and (meta["pair"] != first or meta["cell"] != first + ":adaptive"):
            coverage["slots"][slot] = "not_attempted_readiness_gate"
        elif ready and not state.get("engineering_review") and meta["pair"] != first:
            coverage["slots"][slot] = "not_attempted_engineering_review"
    from collections import Counter

    coverage["slot_counts"] = dict(Counter(coverage["slots"].values()))
    coverage["assessments"] = [{**row, "status": assessments[row["id"]]["status"]
        if row["id"] in assessments else "unvalidated_integrity_hold" if validation_failure is not None
        else "not_attempted"} for row in study["assessment_plan"]]
    resources = parent._resources(study, state)
    resources["current_goal_cap_micro_usd"] = 250_000_000
    resources["defined_max_cumulative_exposure_micro_usd"] = (
        study["prior_live_episode"]["known_spent_micro_usd"] + study["prior_live_episode"]["reserved_micro_usd"]
        + study["policy"]["phase_micro_usd"])
    accounting = {key: copy.deepcopy(value) for key, value in state.items() if key not in ("results", "intents")}
    accounting.update(resource_report=resources, known_results=len(state["results"]) - unknown,
                      unknown_results=unknown, pending_intents=pending, unknown_cost_not_inferred_zero=True)
    summary = {"kind": "phase3a-c1-completion-summary-v1", "study_sha256": study["study_sha256"],
        "fixture": fixture, "status": "mock-complete" if complete and fixture else "complete" if complete else "incomplete",
        "attempts": state["attempts"], "provider_calls": state["provider_calls"],
        "spent_micro_usd": state["spent_micro_usd"], "reserved_micro_usd": state["reserved_micro_usd"],
        **parent._historical_resources(study, state), "journal_status": state["status"],
        "primary_scored": sum(row["status"] == "scored" for row in rows), "primary_scheduled": 8,
        "diagnostic_scored": int(diagnostic["status"] == "scored"), "diagnostic_classified": diagnostic_classified,
        "complete_primary": complete,
        "scientific_complete": complete and not fixture, "authentic_live_path": authentic,
        "readiness_passed": ready, "engineering_review": state.get("engineering_review"),
        "first_assessments_closed": state.get("first_assessments_closed", False),
        "unknown_results": unknown, "pending_intents": pending, "held_evidence_failure": validation_failure}
    profile_fields = ("model", "thinking", "output_config", "reasoning_effort", "max_tokens",
                      "max_completion_tokens", "temperature", "seed", "service_tier", "inference_geo")
    requests = []
    for slot, intent in state["intents"].items():
        result = state["results"].get(slot)
        request = intent["request"]
        requests.append({"slot_id": slot, "role": intent["role"], "request_sha256": digest(request),
            "requested_parameters": {key: copy.deepcopy(request[key]) for key in profile_fields if key in request},
            "status": result["status"] if result else "pending", "result_sha256": digest(result) if result else None,
            "returned_model": ((result or {}).get("response") or {}).get("model"),
            "failure": copy.deepcopy((result or {}).get("failure")),
            "spent_micro_usd": result.get("spent_micro_usd") if result else None,
            "reserved_micro_usd": result.get("reserved_micro_usd") if result else intent.get("reservation", {}).get("micro_usd")})
    protocol = {key: copy.deepcopy(study[key]) for key in ("study_sha256", "definition_sha256", "specification_sha256",
        "source_sha256", "runtime", "runtime_sha256", "policy", "role_profiles", "price_verification",
        "tasks", "slots", "assessment_plan", "fixed_candidate_order", "prior_live_episode") if key in study}
    protocol.update(kind="phase3a-c1-completion-protocol-v1", fixture=fixture, requests=requests,
        objective="C1-backed native agg,k=1 versus fixed C-N best-of-six on four exposed development tasks",
        readiness_reuse="Adaptive p3a-01 is counted once inside this same study/cell; no separate or replacement outcome.",
        authoring_intervention="Declared coherent SYSTEM/MISSION/lossless-index policy; actual native orchestration retained.",
        native_action_cost_is_authoritative=False, historical_unknown_released=False)
    result = {"rows": rows, "coverage": coverage, "analysis": analysis, "summary": summary,
              "accounting": accounting, "protocol": protocol, "readiness": readiness}
    summary["evidence_sha256"] = digest(result)
    return result


def write_report(data: dict, output: Path) -> dict:
    """Write immutable public report files; the caller owns snapshot validation."""
    output = Path(output)
    roots = (ROOT / "runs/phase3a-compat-c1-v1/completion-v1",
             ROOT / "runs/phase3a-c1-completion-v1",
             ROOT / "evidence/phase3a-c1-completion-v1",
             Path("/results/phase3a-compat-c1-v1/completion-v1"),
             Path("/results/phase3a-c1-completion-v1"))
    _require(output.is_absolute() and ".." not in output.parts
             and not {"credential-binding.json", ".writer.lock", ".env", "auth.json", "credentials.json"}.intersection(output.parts)
             and any(output.is_relative_to(p) for p in roots),
             "report output is outside the new completion namespace")
    _require(not any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
                     for p in (output, *output.parents)), "report output traverses a link")
    names = ("rows", "coverage", "analysis", "summary", "accounting", "protocol", "readiness")
    if output.exists():
        allowed = {name + ".json" for name in names} | {"PHASE3A_REPORT.md"}
        _require(output.is_dir() and all(p.name in allowed for p in output.iterdir()),
                 "report output contains artifacts owned by another operation")
    for name in names:
        write_once(output / f"{name}.json", data[name])
    summary, analysis = data["summary"], data["analysis"]
    text = ("# Phase 3A C1-backed paired development pilot\n\n"
        + ("Synthetic evidence only; no live readiness or effectiveness conclusion.\n\n" if summary["fixture"] else
           "Four exposed paired development units; no held-out, population or equal-realized-compute causal claim.\n\n")
        + f"Status: {summary['status']}. Primary scores: {summary['primary_scored']}/8. "
        + f"Readiness passed: {summary['readiness_passed']}. Authentic live path: {summary['authentic_live_path']}.\n\n"
        + f"Attempts: {summary['attempts']}; accounted micro-USD: {summary['spent_micro_usd']}; "
        + f"new unresolved reservation: {summary['reserved_micro_usd']}.\n\n"
        + f"Complete-primary mean adaptive-minus-fixed: {analysis['mean_adaptive_minus_fixed']}. "
        + "Missing readiness, primary coverage, known accounting or authentic live execution keeps the aggregate unset. "
        + "Native fallback outcomes remain included and classified.\n\n"
        + f"Historical known accounting: {summary['prior_real_phase3a_spent_micro_usd']} micro-USD; "
        + f"historical unresolved reservation: {summary['prior_real_phase3a_reserved_micro_usd']} micro-USD, retained in full. "
        + ("Fixture costs are separate; no cumulative real total is inferred.\n\n" if summary["fixture"] else
           f"Cumulative known accounting: {summary['cumulative_real_phase3a_spent_micro_usd']} micro-USD.\n\n")
        + "The fixed first-prompt duplicate is diagnostic only and never replaces the primary. "
        + "Readiness is counted once in adaptive01; equal ceilings are allowances, not invoices or equal realized compute.\n")
    write_bytes_once(output / "PHASE3A_REPORT.md", text.encode("utf-8"))
    return {**summary, "report_output": str(output), "reporting_provider_calls": 0}
