"""Read-only coverage of every frozen Phase 2 request and ordered portfolio.

Consumes reconciled dispatch results. It neither repairs outputs nor executes,
retries, authorizes, scores, or independently settles provider charges.
"""

from __future__ import annotations

from collections import Counter

from .artifacts import ContractError, digest
from .phase2_contracts import slot_prefix, validate_permutation, validate_portfolio


def slot_coverage(study: dict, results: dict, portfolios: list[dict], assessments: list[dict]) -> dict:
    """Preserve failures, unavailable work and non-head slots in fixed denominators."""
    # Called only after phase2 has defined these functions. Reuse its exact
    # strategy contracts without a module-level circular import or second parser.
    from .phase2 import _object, make_worklist, parse_angles, parse_order

    work = study.get("worklist") if isinstance(study, dict) else None
    if not isinstance(work, dict) or work != make_worklist(study["tasks"]):
        raise ContractError("coverage requires the unchanged twelve-task frozen worklist")
    if (not isinstance(results, dict) or set(results).difference(work["slots"])
            or not isinstance(portfolios, list) or not isinstance(assessments, list)):
        raise ContractError("coverage includes unexpected results or malformed collections")
    slots = dict.fromkeys(work["slots"], "not_attempted")
    orders = dict.fromkeys((row["order_id"] for row in work["outputs"]), "not_attempted")
    indexed_portfolios, indexed_assessments = {}, {}
    for portfolio in portfolios:
        validate_portfolio(portfolio)
        provenance = portfolio["provenance"]
        prefix = slot_prefix(portfolio["task"]["id"], provenance["method"], provenance["repeat"])
        if prefix not in orders or prefix in indexed_portfolios:
            raise ContractError("coverage includes an unexpected or duplicate portfolio")
        if study.get("study_sha256", provenance["study_sha256"]) != provenance["study_sha256"]:
            raise ContractError("portfolio belongs to another frozen study")
        indexed_portfolios[prefix] = portfolio
    for assessment in assessments:
        if not isinstance(assessment, dict):
            raise ContractError("invalid assessment coverage record")
        prefix = slot_prefix(assessment["task_id"], assessment["method"], assessment["repeat"])
        assessed_portfolio = indexed_portfolios.get(prefix)
        if (prefix not in orders or prefix in indexed_assessments or assessed_portfolio is None
                or assessment.get("order_id", prefix) != prefix
                or assessment.get("portfolio_sha256") != digest(assessed_portfolio)
                or assessment.get("fixture") is not assessed_portfolio["fixture"]):
            raise ContractError("assessment coverage lacks its exact portfolio identity")
        indexed_assessments[prefix] = assessment

    def raw(slot: str) -> dict | None:
        result = results.get(slot)
        if result is None:
            return None
        if not isinstance(result, dict) or result.get("status") not in ("response", "unknown"):
            raise ContractError("coverage requires classified reconciled dispatch results")
        if result.get("slot_id", slot) != slot or result.get("role", work["slots"][slot]["role"]) != work["slots"][slot]["role"]:
            raise ContractError("dispatch coverage slot or role differs")
        if ("study_sha256" in study and result.get("study_sha256") != study["study_sha256"]):
            raise ContractError("dispatch coverage belongs to another frozen study")
        if result["status"] == "unknown":
            return None
        response = result.get("response")
        if (not isinstance(response, dict) or not isinstance(response.get("text"), str)
                or not isinstance(response.get("stop_reason"), str)):
            raise ContractError("classified response lacks text/stop evidence")
        return response

    def response_status(slot: str) -> str:
        if slot not in results:
            return "not_attempted"
        response = raw(slot)
        if response is None:
            return "unknown_liability"
        role = work["slots"][slot]["role"]
        stop, text = response["stop_reason"], response["text"]
        if response.get("refusal") or stop in ("refusal", "content_filter"):
            return "refused"
        if not text.strip():
            return "empty"
        if stop in ("max_tokens", "length"):
            return "truncated"
        if stop != ("stop" if role == "group" else "end_turn"):
            return "invalid_stop_reason"
        try:
            if role == "plan":
                parse_angles(_object(text))
            elif role == "quality":
                score = _object(text)
                if set(score) != {"score"} or type(score["score"]) is not int or not 1 <= score["score"] <= 10:
                    return "invalid_quality"
            elif role == "group":
                group_heads(slot)
        except (ValueError, TypeError, KeyError):
            return "invalid_" + role
        return "ok"

    def group_heads(slot: str) -> set[int]:
        response = raw(slot)
        if response is None:
            raise ContractError("grouping output is unavailable")
        value = _object(response["text"])
        groups = value.get("groups")
        if (set(value) != {"groups"} or not isinstance(groups, list) or not groups
                or any(not isinstance(group, list) or not group for group in groups)
                or any(type(index) is not int for group in groups for index in group)
                or sorted(index for group in groups for index in group) != list(range(10))):
            raise ContractError("grouping is not a strict partition of ten delivered responses")
        # Seed=None displays the delivered order, so a group's first delivered
        # member is its head. No utility or quality arithmetic is copied here.
        return {min(group) for group in groups}

    for slot in results:
        slots[slot] = response_status(slot)

    def skip(prefix: str, reason: str) -> None:
        for slot in slots:
            if slot.startswith(prefix + ".") and (".group" in slot or ".quality." in slot):
                if slot in results:
                    raise ContractError("a dependent request ran after its prerequisite failed")
                slots[slot] = reason

    def assess_order(prefix: str) -> str:
        if prefix not in indexed_portfolios:
            return "missing_portfolio"
        group_slot = prefix + ".group"
        group_status = slots[group_slot]
        if group_status == "not_attempted":
            return "awaiting_assessment"
        if group_status == "unknown_liability":
            skip_quality(prefix, "skipped_unknown_liability")
            return "unresolved_assessment"
        if group_status != "ok":
            skip_quality(prefix, "skipped_group_refused" if group_status == "refused" else "skipped_invalid_group")
            return "group_refused" if group_status == "refused" else "invalid_group"
        heads = group_heads(group_slot)
        for i in range(10):
            slot = f"{prefix}.quality.{i:02d}"
            if i not in heads:
                if slot in results:
                    raise ContractError("a non-head quality request was dispatched")
                slots[slot] = "not_needed_nonhead"
        head_statuses = [slots[f"{prefix}.quality.{i:02d}"] for i in sorted(heads)]
        if "unknown_liability" in head_statuses:
            return "unresolved_assessment"
        if "refused" in head_statuses:
            return "quality_refused"
        if any(status not in ("ok", "not_attempted") for status in head_statuses):
            return "invalid_quality"
        if "not_attempted" in head_statuses:
            if indexed_assessments.get(prefix, {}).get("status") == "scored":
                raise ContractError("scored assessment is missing a required native head")
            return "incomplete_quality"
        assessment = indexed_assessments.get(prefix)
        return assessment["status"] if assessment is not None else "missing_assessment"

    def skip_quality(prefix: str, reason: str) -> None:
        for i in range(10):
            slot = f"{prefix}.quality.{i:02d}"
            if slot in results:
                raise ContractError("a quality request ran without a valid grouping result")
            slots[slot] = reason

    for block in work["blocks"]:
        a, b, c = [slot_prefix(block["task_id"], method, block["repeat"]) for method in ("A", "B", "C")]
        plan_status = slots[b + ".plan"]
        invalid_plan = plan_status not in ("ok", "not_attempted", "unknown_liability")
        if invalid_plan or plan_status == "unknown_liability":
            reason = "skipped_invalid_plan" if invalid_plan else "skipped_unknown_liability"
            # Exclude the plan itself from dependency marking.
            for prefix in (b, c):
                for slot in slots:
                    if slot.startswith(prefix + ".") and slot != b + ".plan":
                        if slot in results:
                            raise ContractError("a dependent request ran after an invalid/unresolved plan")
                        slots[slot] = reason
                orders[prefix] = "invalid_plan" if invalid_plan else "unresolved_plan"
        for prefix in (a, b):
            if prefix == b and (invalid_plan or plan_status == "unknown_liability"):
                continue
            answer_statuses = [slots[f"{prefix}.answer.{i:02d}"] for i in range(10)]
            if prefix == b and plan_status == "not_attempted":
                if any(slot in results for slot in slots if slot.startswith(b + ".") or slot.startswith(c + ".")):
                    raise ContractError("planner dependents ran before their plan")
                continue
            if all(status == "not_attempted" for status in answer_statuses):
                if any(slot in results for slot in slots if slot.startswith(prefix + ".group") or slot.startswith(prefix + ".quality.")):
                    raise ContractError("assessment ran before generation")
                continue
            if "unknown_liability" in answer_statuses:
                orders[prefix] = "unresolved_generation"
            elif any(status not in ("ok", "refused", "empty", "truncated", "not_attempted") for status in answer_statuses):
                orders[prefix] = "invalid_generation"
                skip(prefix, "skipped_invalid_generation")
            elif "not_attempted" in answer_statuses:
                orders[prefix] = "incomplete_generation"
            else:
                orders[prefix] = assess_order(prefix)
        if invalid_plan or plan_status == "unknown_liability":
            continue
        parent, child = indexed_portfolios.get(b), indexed_portfolios.get(c)
        rank_slot = c + ".rank"
        if rank_slot not in results:
            continue
        rank_status = slots[rank_slot]
        if rank_status == "unknown_liability":
            orders[c] = "unresolved_rank"
            skip(c, "skipped_unknown_liability")
            continue
        try:
            response = raw(rank_slot)
            if rank_status != "ok" or parent is None or response is None:
                raise ContractError("rank lacks a valid parent or completed result")
            order = parse_order(_object(response["text"]), [r["id"] for r in parent["responses"]])
        except (ValueError, TypeError, KeyError):
            slots[rank_slot] = "invalid_rank" if rank_status == "ok" else rank_status
            orders[c] = "invalid_rank"
            skip(c, "skipped_invalid_rank")
            continue
        if child is None:
            orders[c] = "missing_portfolio"
            continue
        validate_permutation(parent, child)
        if [r["id"] for r in child["responses"]] != order:
            raise ContractError("saved permutation differs from its rank result")
        orders[c] = assess_order(c)
    return {
        "schema_version": 2, "kind": "phase2-slot-coverage-v2",
        "scheduled_request_slots": len(slots), "scheduled_order_assessments": len(orders),
        "recorded_request_results": len(results), "available_portfolios": len(indexed_portfolios),
        "available_assessments": len(indexed_assessments), "slots": slots, "orders": orders,
        "slot_status_counts": dict(sorted(Counter(slots.values()).items())),
        "order_status_counts": dict(sorted(Counter(orders.values()).items())),
        "unknown_liability_slots": sorted(slot for slot, status in slots.items() if status == "unknown_liability"),
        "limitation": "Coverage consumes reconciled results; no repair, retries, metric substitution or billing certification.",
    }
