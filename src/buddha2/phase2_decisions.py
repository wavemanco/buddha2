"""Independent research decisions over unchanged, replay-validated Phase 2 evidence."""

from __future__ import annotations

import copy
import datetime
import re
from pathlib import Path
from typing import Any

from .artifacts import ContractError, digest, tree_hashes
from .phase2 import analyze
from .phase2_analysis import validate_analysis_evidence
from .phase2_contracts import slot_prefix

_METHODS = ("A", "B", "C")
POLICIES = {
    "benchmark": {
        "id": "phase2-benchmark-v1", "version": 1,
        "requires": ["complete comparable native coverage", "reconciled accounting"],
        "human_required": False,
        "sort": ["highest mean utility", "lowest actual generation/ranking cost", "A then B then C"],
    },
    "human-augmented": {
        "id": "phase2-human-augmented-v1", "version": 1,
        "requires": ["complete comparable native coverage", "reconciled accounting",
                     "two eligible complete independent reader forms", "no cannot judge or missing context"],
        "candidate_rule": "no substantive concern from either eligible reader",
        "human_required": True,
        "sort": ["highest mean utility", "lowest actual generation/ranking cost", "A then B then C"],
    },
}
_CONTEXT_HASHES = (
    "task_outputs_sha256", "effective_method_sha256", "model_settings_sha256",
    "budget_policy_sha256", "information_access_sha256",
)


def _sha(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _time(value: Any) -> datetime.datetime:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value):
        raise ContractError("evidence cutoff must be an explicit UTC timestamp ending in Z")
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("invalid evidence cutoff") from exc


def _sealed(body: dict, field: str) -> dict:
    return {**body, field: digest(body)}


def _seal(value: Any, field: str, kind: str) -> None:
    if (not isinstance(value, dict) or value.get("kind") != kind
            or value.get(field) != digest({k: v for k, v in value.items() if k != field})):
        raise ContractError(f"invalid immutable {kind} identity")


def implementation_identity() -> dict:
    """Assessment code has its own revision; original generation sources stay original."""
    root = Path(__file__).parent
    return {"id": "phase2-independent-decisions-v1",
            "files": tree_hashes(root)}


def _accounting(state: dict) -> None:
    totals = {"spent_micro_usd": 0, "reserved_micro_usd": 0}
    for result in state["results"].values():
        for field in totals:
            value = result.get(field)
            if value is None and field == "spent_micro_usd":
                value = 0
            if type(value) is not int or value < 0:
                raise ContractError("invalid journal accounting amount")
            totals[field] += value
    if any(type(state.get(key)) is not int or state[key] != value for key, value in totals.items()):
        raise ContractError("journal accounting summary does not reconcile with saved results")


def build_decision(
    study: dict, portfolios: list[dict], assessments: list[dict], state: dict, native: Any,
    *, track: str, cutoff: str, human_assessment: dict | None = None,
    parent: dict | None = None, fixture: bool = False,
) -> dict:
    """Build separate execution, native-assessment and decision records, with no transport.

    ``state`` must come from replay_dispatch, never an imported summary. Every native
    assessment and generation artifact is replayed against its saved request results.
    Historical studies retain their original package/study identities. Repeating this
    function with the same evidence, cutoff and implementation is deterministic.
    """
    if not isinstance(track, str) or track not in POLICIES:
        raise ContractError("unknown research track")
    _time(cutoff)
    if track == "benchmark" and human_assessment is not None:
        raise ContractError("benchmark decisions do not ingest human evidence")
    if track == "benchmark" and parent is not None:
        raise ContractError("the benchmark decision is the root for this execution")
    if "decision_policies" in study and study["decision_policies"] != POLICIES:
        raise ContractError("study's frozen decision policies differ")
    evidence = validate_analysis_evidence(study, assessments, portfolios, state, native, fixture=fixture)
    _accounting(state)
    costs = evidence["generation_costs_by_method"]
    legacy = analyze(study, assessments, [], costs, fixture=fixture,
                     portfolios=portfolios, state=state, native=native)
    # Native descriptive statistics are reusable; the legacy human-gated status is not.
    analysis = {key: value for key, value in legacy.items() if key not in {
        "status", "human_records", "missing_human_judgments", "human_statuses",
        "human_compromised_or_cannot_judge", "selected_method", "synthetic_selected_method",
    }}
    analysis["kind"] = "phase2-native-descriptive-analysis-v1"
    native_complete = (evidence["complete"] and legacy["scored_orders"] == 72
                       and all(value is not None for value in legacy["mean_utility"].values()))
    execution = _sealed({
        "kind": "phase2-execution-record-v1", "fixture": fixture,
        "study_sha256": study["study_sha256"],
        "original_execution_package_files": study.get("package_files", {}),
        "portfolios": {slot_prefix(row["task"]["id"], row["provenance"]["method"], row["provenance"]["repeat"]):
                       digest(row) for row in sorted(portfolios, key=lambda item: digest(item))},
        "generation_results": {slot: digest(result) for slot, result in sorted(state["results"].items())
                               if result["role"] in ("answer", "plan", "rank")},
    }, "execution_sha256")
    native_evidence = {
        "kind": "phase2-native-assessment-set-v1", "fixture": fixture,
        "study_sha256": study["study_sha256"], "execution_sha256": execution["execution_sha256"],
        "native_evaluator": study["native_evaluator"],
        "assessments": {row["order_id"]: digest(row) for row in sorted(assessments, key=lambda row: row["order_id"])},
        "journal_state_sha256": digest(state), "coverage": evidence,
    }
    native_assessment = _sealed({
        **native_evidence, "native_evidence_sha256": digest(native_evidence),
        "analysis_sha256": digest(analysis), "implementation": implementation_identity(),
    }, "assessment_sha256")
    if parent is not None:
        validate_decision(parent)
        if parent["track"] != "benchmark" or parent["parent_decision_sha256"] is not None:
            raise ContractError("human decisions reference the original benchmark root; supplements link their assessment predecessors")
        rebuilt = build_decision(study, portfolios, assessments, state, native,
                                 track="benchmark", cutoff=parent["cutoff"], fixture=fixture)["decision"]
        # A later analysis revision may bind different code/assessment identities.
        # Every substantive parent field must still replay from original evidence.
        revision_fields = {"implementation", "native_assessment_sha256", "decision_sha256"}
        if (set(parent) != set(rebuilt) or _time(parent["cutoff"]) > _time(cutoff)
                or any(parent[key] != value for key, value in rebuilt.items() if key not in revision_fields)):
            raise ContractError("parent decision differs from authoritative benchmark replay or has a future cutoff")
    if track == "human-augmented" and parent is None:
        raise ContractError("human-augmented decision must reference its original benchmark root")
    human_status = "not-required" if track == "benchmark" else "absent"
    human_hash = None
    eligible = list(_METHODS)
    if track == "human-augmented":
        eligible = []
        if human_assessment is not None:
            from .phase2_human import validate_human_assessment

            checked = validate_human_assessment(study, portfolios, human_assessment, fixture=fixture)
            if _time(checked["cutoff"]) > _time(cutoff):
                raise ContractError("human evidence is later than the decision cutoff")
            human_hash = checked["assessment_sha256"]
            human_status = "complete" if not checked["selection_inconclusive"] else "inconclusive"
            if not checked["selection_inconclusive"]:
                eligible = checked["eligible_methods"]
    selected = None
    if native_complete and eligible:
        selected = min(eligible, key=lambda method: (-legacy["mean_utility"][method],
                                                      costs[method], _METHODS.index(method)))
    decision = _sealed({
        "kind": "phase2-track-decision-v1", "fixture": fixture,
        "track": track, "study_sha256": study["study_sha256"],
        "execution_sha256": execution["execution_sha256"],
        "native_assessment_sha256": native_assessment["assessment_sha256"],
        "native_evidence_sha256": native_assessment["native_evidence_sha256"],
        "human_assessment_sha256": human_hash, "human_status": human_status,
        "benchmark_decision_sha256": (parent["decision_sha256"] if parent and parent["track"] == "benchmark"
                                      else parent["benchmark_decision_sha256"] if parent else None),
        "parent_decision_sha256": parent["decision_sha256"] if parent else None,
        "policy": copy.deepcopy(POLICIES[track]), "policy_sha256": digest(POLICIES[track]),
        "policy_predeclared_for_execution": study.get("decision_policies") == POLICIES,
        "cutoff": cutoff, "implementation": implementation_identity(),
        "native_complete": native_complete, "eligible_methods": eligible,
        "mean_utility": legacy["mean_utility"], "candidate_cost_micro_usd": costs,
        "status": "complete-development" if selected else "inconclusive",
        "selected_method": None if fixture else selected,
        "synthetic_selected_method": selected if fixture else None,
        "selected_procedure_sha256": study["procedure_hashes"][selected] if selected else None,
        "limitations": ["Development-only decision; fixtures never select a real seed.",
                        "Shared outputs are not independent replication.",
                        "Human review applies only to its declared sample, not later outputs.",
                        "Shared source/scoring/accounting defects invalidate affected tracks."],
    }, "decision_sha256")
    validate_decision(decision)
    return {"execution": execution, "native_assessment": native_assessment,
            "analysis": analysis, "decision": decision}


def validate_decision(decision: dict) -> None:
    """Validate a decision record. Source evidence requires build_decision replay too."""
    _seal(decision, "decision_sha256", "phase2-track-decision-v1")
    track = decision.get("track")
    if (not isinstance(track, str) or track not in POLICIES
            or decision.get("policy") != POLICIES[track]
            or decision.get("policy_sha256") != digest(POLICIES[track])):
        raise ContractError("decision policy is incompatible")
    _time(decision.get("cutoff"))
    for key in ("study_sha256", "execution_sha256", "native_assessment_sha256", "native_evidence_sha256"):
        if not _sha(decision.get(key)):
            raise ContractError("decision evidence reference is invalid")
    for key in ("human_assessment_sha256", "benchmark_decision_sha256", "parent_decision_sha256"):
        if decision.get(key) is not None and not _sha(decision[key]):
            raise ContractError("decision parent/assessment reference is invalid")
    if type(decision.get("fixture")) is not bool or type(decision.get("native_complete")) is not bool:
        raise ContractError("decision needs explicit fixture and native-completeness flags")
    selected = decision.get("synthetic_selected_method") if decision["fixture"] else decision.get("selected_method")
    other = decision.get("selected_method") if decision["fixture"] else decision.get("synthetic_selected_method")
    eligible = decision.get("eligible_methods")
    if (not isinstance(eligible, list) or any(not isinstance(method, str) for method in eligible)
            or len(set(eligible)) != len(eligible)
            or any(method not in _METHODS for method in eligible) or other is not None):
        raise ContractError("invalid candidate eligibility or fixture/live selection")
    if track == "benchmark":
        if decision.get("human_status") != "not-required" or decision.get("human_assessment_sha256") is not None or eligible != list(_METHODS):
            raise ContractError("benchmark decision must not require human evidence")
    else:
        if not _sha(decision.get("benchmark_decision_sha256")) or not _sha(decision.get("parent_decision_sha256")):
            raise ContractError("human decision lacks its independent benchmark lineage")
        if decision.get("human_status") not in ("absent", "complete", "inconclusive"):
            raise ContractError("invalid human assessment status")
        if (decision["human_status"] == "absent") != (decision.get("human_assessment_sha256") is None):
            raise ContractError("human availability differs from assessment reference")
        if eligible and decision["human_status"] != "complete":
            raise ContractError("incomplete human assessment cannot admit candidates")
    if selected is not None:
        means, costs = decision.get("mean_utility"), decision.get("candidate_cost_micro_usd")
        if not isinstance(means, dict) or not isinstance(costs, dict):
            raise ContractError("selection needs explicit native means and candidate costs")
        if (not decision["native_complete"] or selected not in eligible or not _sha(decision.get("selected_procedure_sha256"))
                or any(type(means.get(method)) not in (int, float) or not 0 <= means[method] <= 10
                       or type(costs.get(method)) is not int or costs[method] < 0 for method in eligible)
                or track == "human-augmented" and decision.get("human_status") != "complete"):
            raise ContractError("selection lacks complete valid evidence")
        if selected != min(eligible, key=lambda method: (-means[method], costs[method], _METHODS.index(method))):
            raise ContractError("selection differs from frozen ranking rule")
    elif decision.get("selected_procedure_sha256") is not None:
        raise ContractError("inconclusive decision cannot name a selected procedure")
    elif decision["native_complete"] and eligible:
        raise ContractError("complete eligible evidence requires its frozen-rule selection")
    if decision.get("status") != ("complete-development" if selected else "inconclusive"):
        raise ContractError("decision status differs from its selected outcome")


def continuation_compatibility(
    left: dict, right: dict, left_context: dict, right_context: dict,
    *, confirmation_opened: bool = False, claim: str = "development",
) -> dict:
    """Check consistency of declared reuse identities, not their external truth.

    Callers must replay both decision sources and verify these operator-supplied
    context hashes against the actual downstream work before reusing evidence.
    """
    validate_decision(left)
    validate_decision(right)
    if type(confirmation_opened) is not bool or claim not in ("development", "retrospective", "confirmatory"):
        raise ContractError("invalid confirmation claim/access declaration")
    for context in (left_context, right_context):
        if (not isinstance(context, dict) or set(context) != {*_CONTEXT_HASHES, "native_mode"}
                or any(not _sha(context.get(key)) for key in _CONTEXT_HASHES)
                or not isinstance(context["native_mode"], str) or not context["native_mode"].strip()):
            raise ContractError("continuation needs exact task/output, method, model/settings, budget, native mode and information-access identities")
    differences = [key for key in (*_CONTEXT_HASHES, "native_mode") if left_context[key] != right_context[key]]
    for key in ("study_sha256", "execution_sha256", "selected_procedure_sha256", "fixture"):
        if left[key] != right[key]:
            differences.append(key)
    ready = left["status"] == right["status"] == "complete-development"
    shared = ready and not differences
    if confirmation_opened and not shared and claim == "confirmatory":
        raise ContractError("changed continuation requires fresh unopened confirmation material")
    return {"kind": "phase2-continuation-compatibility-v1",
            "left_parent_decision_sha256": left["decision_sha256"],
            "right_parent_decision_sha256": right["decision_sha256"],
            "can_reuse": shared, "relationship": "shared-compatible" if shared else "divergent-or-inconclusive",
            "differences": differences, "parents_complete": ready,
            "independent_replication": False,
            "fresh_confirmation_required": confirmation_opened and not shared,
            "claim": claim, "automatic_execution_or_budget_authorized": False}
