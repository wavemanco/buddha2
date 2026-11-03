"""Bind analysis to replayed artifacts and keep reader packets free of method labels."""

from __future__ import annotations

import datetime
from typing import Any

from .artifacts import ContractError, digest
from .phase2_contracts import slot_prefix, validate_permutation, validate_portfolio

_METHODS = ("A", "B", "C")
_NOTES = ("reason", "task_fitness_notes", "variety_notes", "duplication_notes")
_ELIGIBILITY = (
    "actual_human", "english_fluent", "fresh_to_outputs", "no_scores_or_methods_seen",
    "independent_no_tools_or_discussion", "volunteer",
)
_INSTRUCTIONS = (
    "Work separately, without an LLM, discussion, benchmark scores or method labels. "
    "For each ordered portfolio, record brief task-fitness/constraint, meaningful-variety "
    "and duplication notes, then acceptable, substantive concern or cannot judge and a reason. "
    "Flag prior recognition and missing context. Shared texts may reveal relationships between "
    "portfolios; describe any inferred relationship in the notes. No creativity score or forced "
    "preference is requested. Eligibility refers to the time before first viewing these outputs. "
    "The no_scores_or_methods_seen field means no provided labels or scores; inferring relationships "
    "from shared texts does not by itself change eligibility. Submit once; do not discuss or revise "
    "after comparing results."
)


def _study(study: dict) -> dict[str, dict]:
    if not isinstance(study, dict) or study.get("study_sha256") != digest(
        {key: value for key, value in study.items() if key != "study_sha256"}
    ):
        raise ContractError("analysis requires the unchanged frozen study")
    tasks = study.get("tasks")
    if (not isinstance(tasks, list) or len(tasks) != 12
            or any(not isinstance(task, dict) or not isinstance(task.get("id"), str) for task in tasks)
            or len({task["id"] for task in tasks}) != 12):
        raise ContractError("analysis requires twelve distinct declared tasks")
    return {task["id"]: task for task in tasks}


def _portfolios(study: dict, portfolios: list[dict], fixture: bool) -> dict[str, dict]:
    tasks = _study(study)
    if type(fixture) is not bool or not isinstance(portfolios, list):
        raise ContractError("explicit analysis mode and portfolio list required")
    indexed = {}
    for portfolio in portfolios:
        validate_portfolio(portfolio)
        provenance = portfolio["provenance"]
        identity = slot_prefix(portfolio["task"]["id"], provenance["method"], provenance["repeat"])
        if (identity in indexed or portfolio["fixture"] is not fixture
                or portfolio["task"] != tasks.get(portfolio["task"]["id"])
                or provenance["study_sha256"] != study["study_sha256"]
                or provenance["settings_sha256"] != study["shared_generator_settings_sha256"]
                or provenance["procedure_sha256"] != study["procedure_hashes"][provenance["method"]]):
            raise ContractError("portfolio is duplicate or not bound to the declared study/procedure")
        indexed[identity] = portfolio
    for portfolio in portfolios:
        if portfolio["provenance"]["method"] == "C":
            parent = indexed.get(slot_prefix(portfolio["task"]["id"], "B", portfolio["provenance"]["repeat"]))
            if parent is None:
                raise ContractError("a saved permutation needs its original planner artifact")
            validate_permutation(parent, portfolio)
    return indexed


def _saved(state: dict, study: dict, slot: str, role: str, fixture: bool, request: dict | None = None) -> dict:
    value = state["results"].get(slot)
    if (not isinstance(value, dict) or value.get("slot_id") != slot or value.get("role") != role
            or value.get("study_sha256") != study["study_sha256"]
            or value.get("fixture") is not fixture or value.get("status") != "response"
            or not isinstance(value.get("response"), dict)
            or request is not None and value.get("request_sha256") != digest(request)):
        raise ContractError("artifact lacks its exact settled, study-bound dispatch result")
    if type(value.get("spent_micro_usd")) is not int or value["spent_micro_usd"] < 0:
        raise ContractError("finalized artifacts need settled request costs")
    return value


def _generation(study: dict, portfolio: dict, state: dict, fixture: bool, indexed: dict) -> None:
    # Runtime import avoids making strategy rendering and analysis mutually import at startup.
    from .phase2 import generate_order, rank_order

    provenance, task = portfolio["provenance"], portfolio["task"]
    prefix = slot_prefix(task["id"], provenance["method"], provenance["repeat"])

    def saved(slot: str, role: str, request: dict, **_: Any) -> dict:
        return _saved(state, study, slot, role, fixture, request)

    if provenance["method"] == "C":
        parent = indexed[slot_prefix(task["id"], "B", provenance["repeat"])]
        checkpoint = study["worklist"]["slots"][prefix + ".rank"]["checkpoint"]
        reconstructed = rank_order(study, parent, saved, checkpoint=checkpoint)
    else:
        first = prefix + (".plan" if provenance["method"] == "B" else ".answer.00")
        checkpoint = study["worklist"]["slots"][first]["checkpoint"]
        reconstructed = generate_order(study, task, provenance["repeat"], provenance["method"],
                                       saved, checkpoint=checkpoint, fixture=fixture)
    if reconstructed != portfolio:
        raise ContractError("portfolio differs from exact replay of its saved request outcomes")


def validate_analysis_evidence(
    study: dict, assessments: list[dict], portfolios: list[dict], state: dict, native: Any,
    *, fixture: bool = False,
) -> dict:
    """Validate full evidence from ``replay_dispatch``; missing coverage stays visible.

    The caller obtains ``state`` by replaying the immutable journal, rather than
    importing an arbitrary summary. Native finalization is replayed with those
    exact saved results, without any transport or generation.
    """
    if not fixture:
        from .phase2_native import NativeAssessment

        if not isinstance(native, NativeAssessment):
            raise ContractError("real analysis requires the actual pinned NativeAssessment")
    indexed = _portfolios(study, portfolios, fixture)
    if (not isinstance(state, dict) or state.get("fixture") is not fixture
            or not isinstance(state.get("results"), dict) or not isinstance(assessments, list)
            or native.identity != study["native_evaluator"]):
        raise ContractError("analysis journal/native identity is incompatible")
    for slot, result in state["results"].items():
        declared = study["worklist"]["slots"].get(slot)
        if (not declared or not isinstance(result, dict) or result.get("slot_id") != slot
                or result.get("role") != declared["role"] or result.get("fixture") is not fixture
                or result.get("study_sha256") != study["study_sha256"]):
            raise ContractError("journal contains an undeclared or foreign request result")
    referenced = set()
    for portfolio in portfolios:
        _generation(study, portfolio, state, fixture, indexed)
        referenced.update(portfolio["provenance"]["request_ids"])
    seen = set()
    for assessment in assessments:
        if not isinstance(assessment, dict) or not isinstance(assessment.get("order_id"), str):
            raise ContractError("assessment must identify its frozen order")
        order = assessment["order_id"]
        matching_portfolio = indexed.get(order)
        if matching_portfolio is None or order in seen:
            raise ContractError("assessment is duplicate or lacks its full portfolio")
        seen.add(order)
        saved = assessment.get("requests")
        if not isinstance(saved, list) or not saved:
            raise ContractError("assessment lacks accounted native results")
        for result in saved:
            if not isinstance(result, dict) or result != state["results"].get(result.get("slot_id")):
                raise ContractError("assessment request differs from the immutable journal")
            referenced.add(result["slot_id"])
        expected = native.finalize(matching_portfolio, saved[0], saved[1:]) | {
            "study_sha256": study["study_sha256"], "method": matching_portfolio["provenance"]["method"],
            "repeat": matching_portfolio["provenance"]["repeat"], "order_id": order,
        }
        if assessment != expected:
            raise ContractError("assessment metrics/identity differ from native saved-result replay")
    generation_costs = {}
    for method in _METHODS:
        method_portfolios = [p for p in portfolios if p["provenance"]["method"] == method]
        slots = {slot for p in method_portfolios for slot in p["provenance"]["request_ids"]}
        generation_costs[method] = sum(state["results"][slot]["spent_micro_usd"] for slot in slots) if len(method_portfolios) == 24 else None
    unresolved = state.get("status") != "ready" or state.get("reserved_micro_usd") != 0
    complete = len(indexed) == len(seen) == 72 and not unresolved
    unreferenced = sorted(set(state["results"]) - referenced)
    if complete and unreferenced:
        raise ContractError("completed analysis contains unaccounted extra request results")
    return {"complete": complete, "selection_inconclusive": not complete,
            "portfolio_records": len(indexed), "assessment_records": len(seen),
            "missing_portfolios": 72 - len(indexed), "missing_assessments": 72 - len(seen),
            "unresolved_liabilities": unresolved, "unreferenced_request_slots": unreferenced,
            "generation_costs_by_method": generation_costs}


def build_human_templates(study: dict) -> dict:
    return build_human_packets(study, [], fixture=False)


def build_human_packets(study: dict, portfolios: list[dict], *, fixture: bool = False) -> dict:
    """Return blinded forms and a separate private mapping; never contact readers."""
    tasks = _study(study)
    indexed = _portfolios(study, portfolios, fixture)
    units = [(task_id, method) for task_id in study["human_check"]["task_ids"] for method in _METHODS]
    if len(units) != 6 or len({tid for tid, _ in units}) != 2 or any(tid not in tasks for tid, _ in units):
        raise ContractError("human check requires its first two declared task identities")
    planning = not portfolios
    packets, mapping = {}, []
    for reader in ("R1", "R2"):
        reader_id = "fixture-" + reader if fixture else reader
        judgments = []
        sequence = list(enumerate(units, 1))[::1 if reader == "R1" else -1]
        for number, (task_id, method) in sequence:
            portfolio = indexed.get(slot_prefix(task_id, method, 1))
            if portfolio is None and not planning:
                raise ContractError("human packet lacks a prespecified complete portfolio")
            identity = digest(portfolio) if portfolio is not None else None
            unit_id = f"unit-{number:02d}"
            judgments.append({"unit_id": unit_id, "portfolio_sha256": identity,
                              "task": {key: tasks[task_id][key] for key in ("id", "prompt")},
                              "responses": [{"id": r["id"], "text": r["text"]} for r in portfolio["responses"]] if portfolio else [],
                              "status": None, **dict.fromkeys(_NOTES),
                              "recognition": None, "missing_context": None})
            mapping.append({"reader_id": reader_id, "unit_id": unit_id, "task_id": task_id,
                            "repeat": 1, "method": method, "portfolio_sha256": identity})
        packets[reader_id] = {"schema_version": 2, "kind": "phase2-human-packet-v2",
                              "fixture": fixture, "study_sha256": study["study_sha256"],
                              "reader_id": reader_id, "reader_reference": None,
                              "eligibility": dict.fromkeys(_ELIGIBILITY), "delivered_on": None,
                              "due_date": None, "planning_only": planning,
                              "instructions": _INSTRUCTIONS, "judgments": judgments}
    return {"packets": packets, "private_mapping": mapping, "planning_only": planning,
            "warning": "Keep private_mapping separate from reader-facing packets."}


def validate_human_evidence(
    study: dict, human: list[dict], portfolios: list[dict], *, fixture: bool = False,
) -> dict:
    """Validate two independently submitted forms; ambiguity never selects a seed."""
    if not isinstance(human, list) or len(human) > 2:
        raise ContractError("human evidence must be at most two original reader forms")
    if not human:
        _portfolios(study, portfolios, fixture)
        return {"complete": False, "compromised": False, "cannot_judge": False,
                "selection_inconclusive": True, "records": [], "submissions": [],
                "missing_judgments": 12}
    bundle = build_human_packets(study, portfolios, fixture=fixture)
    seen, references, records, submissions = set(), set(), [], []
    compromised = cannot_judge = False
    editable = {"status", *_NOTES, "recognition", "missing_context"}
    for form in human:
        if not isinstance(form, dict) or form.get("reader_id") not in bundle["packets"]:
            raise ContractError("human form belongs to an undeclared reader")
        reader = form["reader_id"]
        expected = bundle["packets"][reader]
        if reader in seen or set(form) != set(expected) or form.get("planning_only") is not False:
            raise ContractError("duplicate, planning-only or malformed human form")
        seen.add(reader)
        fixed = set(expected) - {"reader_reference", "eligibility", "delivered_on", "due_date", "judgments"}
        if any(form[key] != expected[key] for key in fixed):
            raise ContractError("reader form identity/instructions changed")
        eligibility = form["eligibility"]
        if not isinstance(eligibility, dict) or set(eligibility) != set(_ELIGIBILITY):
            raise ContractError("human eligibility record is incomplete")
        eligible = all(eligibility[key] is (not fixture if key == "actual_human" else True) for key in _ELIGIBILITY)
        reference = form["reader_reference"]
        if not isinstance(reference, str) or not reference.strip() or len(reference) > 256:
            compromised = True
        elif reference in references:
            compromised = True
        else:
            references.add(reference)
        compromised |= not eligible
        try:
            delivered = datetime.date.fromisoformat(form["delivered_on"])
            due = datetime.date.fromisoformat(form["due_date"])
            if not 0 <= (due - delivered).days <= 7:
                raise ValueError("date window")
        except (TypeError, ValueError) as exc:
            raise ContractError("reader collection needs one due date within seven days") from exc
        judgments = form["judgments"]
        if not isinstance(judgments, list) or len(judgments) != 6:
            raise ContractError("preserve all six human-check units including missing answers")
        private = {row["unit_id"]: row for row in bundle["private_mapping"] if row["reader_id"] == reader}
        for judgment, original in zip(judgments, expected["judgments"], strict=True):
            if (not isinstance(judgment, dict) or set(judgment) != set(original)
                    or any(judgment[key] != original[key] for key in set(original) - editable)):
                raise ContractError("human unit order/task/response/portfolio identity changed")
            if judgment["status"] is None:
                continue
            if (judgment["status"] not in ("acceptable", "substantive concern", "cannot judge")
                    or any(not isinstance(judgment[key], str) or not judgment[key].strip()
                           or len(judgment[key]) > 4000 for key in _NOTES)
                    or any(type(judgment[key]) is not bool for key in ("recognition", "missing_context"))):
                raise ContractError("completed human judgment is malformed")
            compromised |= judgment["recognition"]
            cannot_judge |= judgment["status"] == "cannot judge"
            binding = private[judgment["unit_id"]]
            records.append({**binding, "fixture": fixture, "study_sha256": study["study_sha256"],
                            "reader_reference": reference, **{key: judgment[key] for key in editable}})
        submissions.append({"reader_id": reader, "submission_sha256": digest(form)})
    complete = len(seen) == 2 and len(records) == 12 and not compromised
    return {"complete": complete, "compromised": compromised, "cannot_judge": cannot_judge,
            "selection_inconclusive": not complete or cannot_judge, "records": records,
            "submissions": submissions, "missing_judgments": 12 - len(records)}
