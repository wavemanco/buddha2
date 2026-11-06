"""Pure S2 checkpoint/selected-alias reporting; never dispatches or reads providers."""

from __future__ import annotations

import copy
import math
from collections import Counter
from pathlib import Path

from buddha2.artifacts import ContractError, digest, write_bytes_once, write_once

from . import accounting
from .support import ROOT, safe

ARMS = ("fixed", "adaptive")
TARGETS = ("fixed", "c1", "c2")
NAMES = ("rows", "coverage", "analysis", "summary", "accounting", "protocol", "readiness")


def _require(value: bool, message: str) -> None:
    if not value:
        raise ContractError(message)


def _historical_resources(study: dict, state: dict) -> dict:
    prior = study["prior_live_episode"]
    closed = study.get("prior_closed_attempt", {})
    repeat = study.get("prior_closed_repeat", {})
    artifact = study.get("prior_closed_artifact_attempt", {})
    continuation = study.get("prior_closed_continuation", {})
    known, reserved = prior["known_spent_micro_usd"], prior["reserved_micro_usd"]
    closed_known = (closed.get("known_spent_micro_usd", 0) + repeat.get("known_spent_micro_usd", 0)
                    + artifact.get("known_spent_micro_usd", 0) + continuation.get("known_spent_micro_usd", 0))
    closed_reserved = (closed.get("reserved_micro_usd", 0) + repeat.get("reserved_micro_usd", 0)
                       + artifact.get("reserved_micro_usd", 0) + continuation.get("reserved_micro_usd", 0))
    fixture = state["fixture"]
    total_known = None if fixture else known + closed_known + state["spent_micro_usd"]
    total_reserved = None if fixture else reserved + closed_reserved + state["reserved_micro_usd"]
    total_calls = None if fixture else (
        prior["provider_calls"] + closed.get("provider_calls", 0)
        + repeat.get("provider_calls", 0) + artifact.get("provider_calls", 0)
        + continuation.get("provider_calls", 0) + state["provider_calls"]
    )
    exposure = None if fixture else (
        known + closed_known + reserved + closed_reserved
        + state["spent_micro_usd"] + state["reserved_micro_usd"]
    )
    return {
        "prior_real_phase3a_spent_micro_usd": known,
        "prior_real_phase3a_reserved_micro_usd": reserved,
        "prior_real_phase3a_provider_calls": prior["provider_calls"],
        "prior_real_phase3a_known_responses": prior["known_requests"],
        "prior_real_phase3a_unknown_responses": prior["unknown_requests"],
        "prior_closed_phase3b_attempt": copy.deepcopy(closed),
        "prior_closed_phase3b_repeat": copy.deepcopy(repeat),
        "prior_closed_phase3b_artifact_attempt": copy.deepcopy(artifact),
        "prior_closed_phase3b_continuation": copy.deepcopy(continuation),
        "lineage_spent_micro_usd": total_known,
        "lineage_reserved_micro_usd": total_reserved,
        "lineage_max_exposure_micro_usd": exposure,
        "lineage_provider_calls": total_calls,
        "legacy_cumulative_field_scope": "Phase3A plus separately identified closed Phase3B attempts plus this run",
        "cumulative_real_phase3a_spent_micro_usd": total_known,
        "cumulative_real_phase3a_reserved_micro_usd": total_reserved,
        "cumulative_real_phase3a_max_exposure_micro_usd": exposure,
        "cumulative_real_phase3a_provider_calls": total_calls,
        "historical_accounting_settled": reserved + closed_reserved == 0,
        "historical_unknown_released": False,
    }


def _resources(study: dict, state: dict) -> dict:
    """Authoritative usage totals remain separate from native action accounting."""
    profiles: dict[str, dict] = {}
    for slot, result in state["results"].items():
        request = state["intents"][slot]["request"]
        profile = {
            "role": result["role"],
            "model": request["model"],
            "effort": request.get("output_config", {}).get(
                "effort", request.get("reasoning_effort")
            ),
            "thinking": request.get("thinking"),
            "max_tokens": request.get("max_tokens", request.get("max_completion_tokens")),
        }
        key = digest(profile)
        row = profiles.setdefault(
            key,
            profile
            | {
                "attempts": 0,
                "known": 0,
                "unknown": 0,
                "spent_micro_usd": 0,
                "reserved_micro_usd": 0,
                "uncached_input_tokens": 0,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
                "output_tokens": 0,
                "reported_reasoning_tokens": 0,
                "reasoning_usage_reported_calls": 0,
            },
        )
        row["attempts"] += 1
        row["reserved_micro_usd"] += result["reserved_micro_usd"]
        if result["status"] != "response":
            row["unknown"] += 1
            continue
        row["known"] += 1
        row["spent_micro_usd"] += result["spent_micro_usd"]
        usage = result["response"]["usage"]
        for target, source in (
            ("uncached_input_tokens", "input_tokens"),
            ("cache_creation_input_tokens", "cache_creation_input_tokens"),
            ("cache_read_input_tokens", "cache_read_input_tokens"),
            ("output_tokens", "output_tokens"),
        ):
            row[target] += usage.get(source, 0)
        reasoning = (usage.get("output_tokens_details") or {}).get(
            "reasoning_tokens" if result["role"] == "group" else "thinking_tokens"
        )
        if reasoning is not None:
            row["reported_reasoning_tokens"] += reasoning
            row["reasoning_usage_reported_calls"] += 1
    utilization = {}
    for cell, values in state["cells"].items():
        utilization[cell] = {
            "spent_fraction": values["spent_micro_usd"] / accounting.POLICY["cell_micro_usd"],
            "http_fraction": values["attempts"] / accounting.POLICY["cell_http"],
            "input_fraction": values["input_tokens"] / accounting.POLICY["cell_input"],
            "output_fraction": values["output_tokens"] / accounting.POLICY["cell_output"],
        }
    return {
        "profiles": [profiles[key] for key in sorted(profiles)],
        "inference_allowance_utilization": utilization,
        **_historical_resources(study, state),
        "original_phase3a_cap_micro_usd": 220000000,
        "current_study_cap_micro_usd": accounting.POLICY["phase_micro_usd"],
        "assessment_allowance_micro_usd": accounting.POLICY["assessment_micro_usd"],
        "inference_allowance_micro_usd_per_cell": accounting.POLICY["cell_micro_usd"],
        "wall_time_seconds": None,
        "wall_time_basis": "Retain actual host launch/runtime records separately; not measured by the request journal.",
        "thinking_usage_note": "Reported reasoning is a subset of output, not an extra charge. Unreported thinking is not inferred as zero.",
        "cost_basis": accounting.POLICY["cost_basis"],
        "fixture": state["fixture"],
        "study_sha256": study["study_sha256"],
    }


def _metrics(assessment: dict | None) -> dict:
    if not assessment or assessment.get("status") != "scored":
        return {"utility": None, "distinct": None}
    metrics = assessment.get("metrics", {})
    _require(
        all(
            type(metrics.get(key)) in (int, float) and math.isfinite(metrics[key])
            for key in ("utility", "distinct")
        ),
        "scored assessment lacks finite native metrics",
    )
    return copy.deepcopy(metrics)


def fixed_pool_complete(result: dict, results: dict) -> bool:
    """A fixed best-of-twelve final requires twelve complete recorded candidates."""
    candidates = result.get("candidates")
    run_id = result.get("run_id")
    selection = result.get("selection")
    if (result.get("status") != "complete" or not isinstance(run_id, str)
        or not isinstance(candidates, list) or len(candidates) != 12
        or not all(isinstance(row, dict) for row in candidates)
        or not isinstance(selection, dict)):
        return False
    expected = [f"{run_id}/candidate-{index:02}" for index in range(1, 13)]
    if ([row.get("run_id") for row in candidates] != expected
        or any(row.get("status") != "complete" or not isinstance(row.get("portfolio"), dict)
            for row in candidates)):
        return False
    mapping, slot = selection.get("candidate_map"), selection.get("slot_id")
    selected = result.get("selected_run_id")
    if (not isinstance(mapping, dict) or set(mapping) != {f"candidate-{index:02}" for index in range(1, 13)}
        or not all(isinstance(value, str) for value in mapping.values()) or set(mapping.values()) != set(expected)
        or selected not in expected or not isinstance(slot, str) or slot not in results):
        return False
    record = results[slot]
    if not isinstance(record, dict):
        return False
    chosen = candidates[expected.index(selected)]
    return bool(selection.get("result") == record and record.get("role") == "fixed_selector"
        and record.get("status") == "response" and (record.get("response") or {}).get("stop_reason") == "end_turn"
        and result.get("portfolio") == chosen["portfolio"])


def native_selection_normal(result: dict, results: dict) -> bool:
    """Require the actual normal native selection evidence for every prompt."""
    from .native import _selector_normal
    evidence = result.get("editor_evidence")
    selection = (result.get("native") or {}).get("selections", {}).get("seq")
    return bool(result.get("status") == "complete" and isinstance(evidence, dict)
        and isinstance(selection, dict) and selection.get("ok") is True
        and result.get("selected_checkpoint") == selection.get("chosen_label")
        and _selector_normal(evidence, selection, results))


def _plan(study: dict) -> dict:
    pilots = [task["pilot_id"] for task in study["tasks"]]
    _require(tuple(pilots) == accounting.PAIRS, "report requires the frozen four prompt units")
    rows = study["assessment_plan"]
    _require(
        isinstance(rows, list) and len(rows) == 12 and len({row["id"] for row in rows}) == 12,
        "exact twelve distinct candidate assessment targets required",
    )
    mapped = {(row["pilot"], row["target"]): row for row in rows}
    _require(
        set(mapped) == {(pilot, target) for pilot in pilots for target in TARGETS}
        and all(
            row.get("diagnostic") is False
            and row["arm"] == ("fixed" if row["target"] == "fixed" else "adaptive")
            for row in rows
        ),
        "assessment targets or arm mapping differ",
    )
    return mapped


def _portfolio(branch: dict | None, target: str) -> dict | None:
    result = (branch or {}).get("result") or {}
    return (
        result.get("portfolio") if target == "fixed" else result.get("checkpoints", {}).get(target)
    )


def _strategy_attribution(result: dict) -> dict:
    hashes = {
        label: result.get("rollouts", {}).get(label, {}).get("effective_strategy_sha256")
        for label in ("c1", "c2")
    }
    _require(all(value is None or isinstance(value, str) and len(value) == 64
                 and all(char in "0123456789abcdef" for char in value)
                 for value in hashes.values()), "invalid checkpoint strategy identity")
    return {
        "c1_effective_strategy_sha256": hashes["c1"],
        "c2_effective_strategy_sha256": hashes["c2"],
        "c2_changed_from_c1": hashes["c1"] != hashes["c2"]
        if all(value is not None for value in hashes.values()) else None,
        "fresh_rollout_also_changes_sampling": True,
    }


def _read_consumption_audit(branches: dict) -> dict:
    """Keep every recorded session's full read audit separate from benchmark completion."""
    sessions = []
    observed = set()
    for (pilot, arm), branch in sorted(branches.items()):
        if arm != "adaptive":
            continue
        records = ((branch.get("result") or {}).get("editor_evidence") or {}).get("sessions", {})
        for label, record in sorted(records.items()):
            observed.add((pilot, label.split(".a", 1)[0]))
            information = record.get("information_proof") or {}
            normal = record.get("normal_session_proof") or {}
            before = information.get("delivery")
            audits = {
                "before_decision": copy.deepcopy(before),
                "notes_reread": copy.deepcopy(normal.get("notes_delivery")),
                "strategy_reread": copy.deepcopy(normal.get("strategy_delivery")),
            }
            available = isinstance(before, dict) and isinstance(record.get("normal_session_proof"), dict)
            complete = available and all(
                audit is None or isinstance(audit, dict) and audit.get("complete") is True
                for audit in audits.values()
            )
            sessions.append({
                "pilot": pilot, "label": label, "session_status": record.get("status"),
                "diagnostics_available": available, "complete": complete, "audits": audits,
            })
    missing = [
        {"pilot": pilot, "stage": stage}
        for pilot in accounting.PAIRS
        for stage in ("inv1", "dom1", "c1", "inv2", "dom2", "c2", "select.seq2")
        if (pilot, stage) not in observed
    ]
    return {
        "policy_id": "read-consumption-diagnostic-v1", "blocking": False,
        "complete": not missing and bool(sessions) and all(row["complete"] for row in sessions),
        "recorded_sessions": len(sessions),
        "complete_sessions": sum(row["complete"] for row in sessions),
        "missing_stages": missing, "sessions": sessions,
        "scope": "All recorded native author/selector sessions, including discarded shape attempts",
    }


def _coverage(study: dict, state: dict, saved: dict, ready: bool) -> dict:
    slots = dict.fromkeys(study["slots"], "not_attempted")
    first = accounting.PAIRS[0]
    for slot, meta in study["slots"].items():
        if meta["cell"] in state.get("stopped_cells", []):
            slots[slot] = "not_attempted_cell_budget"
        elif meta["cell"] == "assessment" and state.get("assessment_stopped"):
            slots[slot] = "not_attempted_assessment_budget"
        elif not ready and (meta["pair"] != first or meta["cell"] != first + ":adaptive"):
            slots[slot] = "not_attempted_readiness_gate"
        elif ready and not state.get("engineering_review") and meta["pair"] != first:
            slots[slot] = "not_attempted_engineering_review"
    for slot, result in state["results"].items():
        if result["status"] != "response":
            slots[slot] = "unknown_liability"
            continue
        response = result["response"]
        content = response.get(
            "content", (response.get("provider_response") or {}).get("content", [])
        )
        tools = result["role"] in {"editor", "native_selector"} and any(
            isinstance(block, dict) and block.get("type") == "tool_use" for block in content
        )
        slots[slot] = (
            "refused"
            if response.get("refusal")
            or response.get("stop_reason") in {"refusal", "content_filter"}
            else "truncated"
            if response.get("stop_reason") in {"max_tokens", "length"}
            else "known_tool_response"
            if tools
            else "empty"
            if not response.get("text", "").strip()
            else "known_response"
        )
    from .native import Phase3NativeAssessment

    for planned in study["assessment_plan"]:
        assessment = saved["assessments"].get(planned["id"])
        prefix = Phase3NativeAssessment.slot_prefix(planned["id"])
        fields = (assessment.get("native") or {}).get("partition_fields") if assessment else None
        if fields is not None:
            # Partition positions are already strictly validated by saved replay.
            partition = fields["partition"]
            heads = {
                next(index for index, value in enumerate(partition) if value == group)
                for group in set(partition)
            }
            for index in range(10):
                if index not in heads:
                    slot = f"{prefix}.quality.{index:02}"
                    _require(slot not in state["results"], "nonhead quality was dispatched")
                    slots[slot] = "not_needed_nonhead"
        elif assessment:
            for index in range(10):
                slot = f"{prefix}.quality.{index:02}"
                if slot not in state["results"]:
                    slots[slot] = "skipped_invalid_group"
    active = state.get("active_unsettled_intents", [])
    for slot in active:
        slots[slot] = "pending_active_intent"
    return {
        "slots": slots,
        "slot_counts": dict(Counter(slots.values())),
        "scheduled_slots": len(slots),
    }


def build(study: dict, state: dict, saved: dict, fixture: bool) -> dict:
    """Project validated records; checkpoints are targets, selected finals are aliases."""
    _require(
        type(fixture) is bool and state["fixture"] is fixture, "report mode differs from ledger"
    )
    _require(
        study["policy"] == accounting.POLICY and len(study["slots"]) == 2344,
        "S2 report policy or worklist differs",
    )
    plans = _plan(study)
    validation = copy.deepcopy(saved.get("validation_failure"))
    branches = saved["branches"] if validation is None else {}
    assessments = saved["assessments"] if validation is None else {}
    read_audit = _read_consumption_audit(branches)
    readiness = copy.deepcopy(saved.get("readiness"))
    ready = isinstance(readiness, dict) and readiness.get("passed") is True
    rows = []
    for task in study["tasks"]:
        pilot = task["pilot_id"]
        for target in TARGETS:
            arm = "fixed" if target == "fixed" else "adaptive"
            branch = branches.get((pilot, arm))
            result = (branch or {}).get("result") or {}
            portfolio = _portfolio(branch, target)
            planned = plans[pilot, target]
            assessment = assessments.get(planned["id"])
            _require(
                assessment is None or portfolio is not None,
                "assessment lacks its candidate portfolio",
            )
            scores = ((assessment or {}).get("native", {}).get("fields") or {}).get(
                "generation_scores"
            )
            row = {
                "pilot": pilot,
                "parent_task_id": task["parent_task_id"],
                "arm": arm,
                "target": target,
                "diagnostic": False,
                "branch_status": result.get("status", branch.get("failure"))
                if branch
                else "not_attempted",
                "final_sha256": digest(portfolio) if portfolio else None,
                "assessment_id": planned["id"],
                "assessment_sha256": digest(assessment) if assessment else None,
                "status": assessment.get("status", "unscored")
                if assessment
                else "unscored"
                if portfolio
                else "missing_final",
                "metrics": _metrics(assessment)
                if portfolio
                else {"utility": None, "distinct": None},
                "first_answer_quality": scores[0]
                if scores and assessment is not None and assessment.get("status") == "scored"
                else None,
                "authentic": bool(not fixture and arm == "adaptive" and result.get("authentic")),
                "inference_accounting": copy.deepcopy(state["cells"].get(pilot + ":" + arm)),
                "native_actions": copy.deepcopy(
                    result.get("native", {}).get("modes", {}).get("seq", {}).get("ledger")
                )
                if arm == "adaptive"
                else None,
                "native_action_cost_is_authoritative": False,
                "stage_dispositions": copy.deepcopy(result.get("stage_dispositions"))
                if arm == "adaptive"
                else None,
                "selected_checkpoint": result.get("selected_checkpoint")
                if arm == "adaptive"
                else None,
                "fixed_candidate_dispositions": [
                    {
                        "run_id": candidate["run_id"],
                        "status": candidate["status"],
                        "reason": candidate.get("reason"),
                    }
                    for candidate in result.get("candidates", [])
                ]
                if arm == "fixed"
                else None,
            }
            if validation is not None:
                row.update(
                    status="unvalidated_integrity_hold", branch_status="unvalidated_integrity_hold"
                )
            rows.append(row)
    mapped = {(row["pilot"], row["target"]): row for row in rows}
    primaries = []
    for task in study["tasks"]:
        pilot = task["pilot_id"]
        primaries.append(copy.deepcopy(mapped[pilot, "fixed"]))
        result = (branches.get((pilot, "adaptive")) or {}).get("result") or {}
        chosen = result.get("selected_checkpoint")
        _require(
            chosen is None or chosen in {"c1", "c2"},
            "native selection is outside its checkpoint pool",
        )
        if chosen is not None:
            candidate = mapped[pilot, chosen]
            _require(
                result.get("portfolio") == result.get("checkpoints", {}).get(chosen),
                "selected native final is not its exact checkpoint alias",
            )
            primary = copy.deepcopy(candidate)
            primary.update(target="selected", selected_checkpoint=chosen, assessment_is_alias=True)
        else:
            primary = {
                **copy.deepcopy(mapped[pilot, "c1"]),
                "target": "selected",
                "selected_checkpoint": None,
                "assessment_id": None,
                "assessment_sha256": None,
                "final_sha256": None,
                "status": "missing_final",
                "metrics": {"utility": None, "distinct": None},
                "first_answer_quality": None,
                "assessment_is_alias": True,
            }
        primaries.append(primary)
    projected_unknown = sum(result["status"] != "response" for result in state["results"].values())
    active = state.get("active_unsettled_intents")
    durable_unknown = state.get("durable_unknown_results")
    pending = (
        len(active) if active is not None else len(set(state["intents"]) - set(state["results"]))
    )
    unknown = durable_unknown if durable_unknown is not None else projected_unknown
    if active is not None:
        _require(
            type(unknown) is int and unknown >= 0 and unknown + pending == projected_unknown,
            "durable and projected unknown counters differ",
        )
    settled = (
        state["status"] == "ready"
        and state["reserved_micro_usd"] == 0
        and not unknown
        and not pending
    )
    authentic = any(row["authentic"] for row in rows)
    fixed_pools = {pilot: fixed_pool_complete((branches.get((pilot, "fixed")) or {}).get("result") or {}, state["results"])
        for pilot in accounting.PAIRS}
    native_selectors = {pilot: native_selection_normal((branches.get((pilot, "adaptive")) or {}).get("result") or {}, state["results"])
        for pilot in accounting.PAIRS}
    complete_method_execution = all(fixed_pools.values()) and all(native_selectors.values())
    primary_scored = sum(row["status"] == "scored" for row in primaries)
    assessment_scored = sum(row["status"] == "scored" for row in rows)
    complete_primary = (
        primary_scored == 8 and ready and settled and validation is None and (fixture or authentic)
        and complete_method_execution
    )
    complete_checkpoints = all(
        mapped[pilot, target]["status"] == "scored"
        for pilot in accounting.PAIRS
        for target in ("c1", "c2")
    )
    complete = complete_primary and complete_checkpoints and assessment_scored == 12
    pairs, checkpoints = [], []
    for task in study["tasks"]:
        pilot = task["pilot_id"]
        paired = {row["arm"]: row for row in primaries if row["pilot"] == pilot}
        scored = all(paired[arm]["status"] == "scored" for arm in ARMS)
        pairs.append(
            {
                "pilot": pilot,
                "adaptive_minus_fixed": paired["adaptive"]["metrics"]["utility"]
                - paired["fixed"]["metrics"]["utility"]
                if scored
                else None,
                "adaptive_minus_fixed_distinct": paired["adaptive"]["metrics"]["distinct"]
                - paired["fixed"]["metrics"]["distinct"]
                if scored
                else None,
            }
        )
        c1, c2 = mapped[pilot, "c1"], mapped[pilot, "c2"]
        checkpoint_scored = c1["status"] == c2["status"] == "scored"
        selected = paired["adaptive"]
        checkpoints.append(
            {
                "pilot": pilot,
                "c2_minus_c1": c2["metrics"]["utility"] - c1["metrics"]["utility"]
                if checkpoint_scored
                else None,
                "selected_minus_c1": selected["metrics"]["utility"] - c1["metrics"]["utility"]
                if selected["status"] == c1["status"] == "scored"
                else None,
                "selected_checkpoint": selected.get("selected_checkpoint"),
                "strategy_attribution": _strategy_attribution(
                    (branches.get((pilot, "adaptive")) or {}).get("result") or {}
                ),
            }
        )
    mean = sum(row["adaptive_minus_fixed"] for row in pairs) / 4 if complete_primary else None
    checkpoint_mean = (
        sum(row["c2_minus_c1"] for row in checkpoints) / 4
        if complete_checkpoints and settled
        else None
    )
    selection_mean = (
        sum(row["selected_minus_c1"] for row in checkpoints) / 4
        if (complete_checkpoints and complete_primary)
        else None
    )
    direction = (
        "tie" if mean == 0 else "adaptive" if mean is not None and mean > 0
        else "fixed" if mean is not None else None
    )
    analysis = {
        "kind": "phase3b-seq2-analysis-v1",
        "pairs": pairs,
        "checkpoint_deltas": checkpoints,
        "paired_prompt_units": 4,
        "population_independence_established": False,
        "mean_adaptive_minus_fixed": mean,
        "mean_c2_minus_c1": checkpoint_mean,
        "mean_selected_minus_c1": selection_mean,
        "complete_primary": complete_primary,
        "complete_checkpoints": complete_checkpoints,
        "complete_method_execution": complete_method_execution,
        "fixed_pool_complete": fixed_pools,
        "native_selector_normal": native_selectors,
        "complete_assessment_targets": assessment_scored == 12,
        "scientific_complete": complete and not fixture,
        "fixture": fixture,
        "selected_method": direction if complete and not fixture and direction in ARMS else None,
        "descriptive_direction": direction,
        "selection_is_descriptive_only": True,
        "authentic_live_path": authentic,
        "readiness_passed": ready,
        "held_evidence_failure": validation,
        "diagnostic_classified": True,
        "diagnostic": None,
        "limits": [
            "Four exposed paired prompt units; no random-population, held-out or human-preference claim.",
            "Equal resource ceilings do not imply equal realized compute. c2-c1 includes fresh sampling.",
            "Selected checkpoint and fixed portfolio are complete procedures; selection gain is not an edit effect.",
        ],
        "read_consumption_audit": read_audit,
    }
    coverage = _coverage(
        study, state, {**saved, "branches": branches, "assessments": assessments}, ready
    )
    coverage.update(
        fixed_pool_complete=fixed_pools,
        native_selector_normal=native_selectors,
        primary_rows=primaries,
        assessment_targets=copy.deepcopy(study["assessment_plan"]),
        assessments=[
            {**row, "status": assessments.get(row["id"], {}).get("status", "not_attempted")}
            for row in study["assessment_plan"]
        ],
        potential_request_slots=2344,
        maximum_new_admitted_attempts=accounting.WORKLIST_PROFILE["maximum_admitted_attempts"],
        editor_max_requests=24,
        editor_max_ordinary_requests=23,
        inventory_is_authorization=False,
    )
    resources = _resources(study, state)
    resources.update(
        current_goal_cap_micro_usd=250_000_000,
        defined_max_cumulative_exposure_micro_usd=248_924_365,
        potential_request_slots=2344,
        maximum_new_admitted_attempts=accounting.WORKLIST_PROFILE["maximum_admitted_attempts"],
    )
    account = {
        key: copy.deepcopy(value)
        for key, value in state.items()
        if key not in {"results", "intents"}
    }
    account.update(
        resource_report=resources,
        known_results=len(state["results"]) - projected_unknown,
        unknown_results=unknown,
        pending_intents=pending,
        projected_unknown_results=projected_unknown,
        unknown_cost_not_inferred_zero=True,
    )
    summary = {
        "kind": "phase3b-seq2-summary-v1",
        "study_sha256": study["study_sha256"],
        "fixture": fixture,
        "status": "mock-complete"
        if complete and fixture
        else "complete"
        if complete
        else "incomplete",
        "attempts": state["attempts"],
        "provider_calls": state["provider_calls"],
        "admitted_attempts": state["attempts"],
        "spent_micro_usd": state["spent_micro_usd"],
        "reserved_micro_usd": state["reserved_micro_usd"],
        **_historical_resources(study, state),
        "journal_status": state["status"],
        "primary_scored": primary_scored,
        "primary_scheduled": 8,
        "assessment_scored": assessment_scored,
        "assessment_scheduled": 12,
        "complete_primary": complete_primary,
        "complete_checkpoints": complete_checkpoints,
        "complete_method_execution": complete_method_execution,
        "complete_fixed_pools": sum(fixed_pools.values()),
        "normal_native_selectors": sum(native_selectors.values()),
        "scientific_complete": complete and not fixture,
        "authentic_live_path": authentic,
        "readiness_passed": ready,
        "read_consumption_audit_complete": read_audit["complete"],
        "read_consumption_audit_blocking": False,
        "read_consumption_audit_recorded_sessions": read_audit["recorded_sessions"],
        "read_consumption_audit_complete_sessions": read_audit["complete_sessions"],
        "engineering_review": state.get("engineering_review"),
        "first_assessments_closed": state.get("first_assessments_closed", False),
        "unknown_results": unknown,
        "pending_intents": pending,
        "durable_unknown_results": durable_unknown,
        "active_unsettled_intents": copy.deepcopy(active),
        "projected_unknown_results": projected_unknown,
        "held_evidence_failure": validation,
        "diagnostic_scored": 0,
        "diagnostic_classified": True,
        "potential_request_slots": 2344,
        "maximum_new_admitted_attempts": accounting.WORKLIST_PROFILE["maximum_admitted_attempts"],
        "transport_audit_summary": copy.deepcopy(state.get("transport_audit_summary")),
        "deadline_stop": copy.deepcopy(state.get("deadline_stop")),
        "provider_calls_semantics": "Admitted live attempts; actual SDK invocations require physical audits.",
    }
    profile_fields = (
        "model",
        "thinking",
        "output_config",
        "reasoning_effort",
        "max_tokens",
        "max_completion_tokens",
        "temperature",
        "seed",
        "service_tier",
        "inference_geo",
    )
    requests = []
    for slot, intent in state["intents"].items():
        result = state["results"].get(slot)
        request = intent["request"]
        requests.append(
            {
                "slot_id": slot,
                "role": intent["role"],
                "request_sha256": digest(request),
                "requested_parameters": {
                    key: copy.deepcopy(request[key]) for key in profile_fields if key in request
                },
                "status": "pending"
                if slot in (active or [])
                else result["status"]
                if result
                else "pending",
                "result_sha256": digest(result) if result and slot not in (active or []) else None,
                "returned_model": ((result or {}).get("response") or {}).get("model"),
                "failure": copy.deepcopy((result or {}).get("failure")),
                "spent_micro_usd": result.get("spent_micro_usd") if result else None,
                "reserved_micro_usd": result.get("reserved_micro_usd")
                if result
                else intent["reservation"]["micro_usd"],
            }
        )
    protocol = {
        key: copy.deepcopy(study[key])
        for key in (
            "study_sha256",
            "definition_sha256",
            "specification_sha256",
            "source_sha256",
            "runtime",
            "runtime_sha256",
            "policy",
            "transport_deadline_policy",
            "conversation_timing_policy",
            "role_profiles",
            "price_verification",
            "tasks",
            "slots",
            "assessment_plan",
            "fixed_candidate_order",
            "prior_live_episode",
            "prior_closed_attempt",
            "prior_closed_repeat",
            "prior_closed_artifact_attempt",
            "prior_closed_continuation",
            "read_consumption_policy",
            "rank_io_profile",
        )
        if key in study
    }
    protocol.update(
        kind="phase3b-seq2-protocol-v1",
        fixture=fixture,
        requests=requests,
        objective="Actual native seq,k=2 versus fixed C-N best-of-twelve on four exposed development prompts",
        readiness_reuse="First native path is counted once with all6normal authoring stages and native selection.",
        authoring_intervention="24-request/2MiB external contract; actual unmodified native engine and cumulative evidence.",
        native_action_cost_is_authoritative=False,
        historical_unknown_released=False,
        selected_final_assessment_is_alias=True,
        diagnostic_assessments=0,
        maximum_new_admitted_attempts=accounting.WORKLIST_PROFILE["maximum_admitted_attempts"],
        transport_audit_summary=copy.deepcopy(state.get("transport_audit_summary")),
    )
    data = {
        "rows": rows,
        "coverage": coverage,
        "analysis": analysis,
        "summary": summary,
        "accounting": account,
        "protocol": protocol,
        "readiness": readiness,
    }
    summary["evidence_sha256"] = digest(data)
    return data


def write_report(data: dict, output: Path) -> dict:
    roots = tuple(
        base / "phase3b-seq2-v1" for base in (ROOT / "runs", ROOT / "evidence", Path("/results"))
    )
    output = Path(output)
    _require(
        output.is_absolute()
        and any(output != root and output.is_relative_to(root) for root in roots),
        "report output is outside S2 namespace",
    )
    output = safe(output, roots=roots)
    allowed = {name + ".json" for name in NAMES} | {"PHASE3B_REPORT.md"}
    if output.exists():
        _require(
            output.is_dir() and all(child.name in allowed for child in output.iterdir()),
            "report output contains foreign artifacts",
        )
    for name in NAMES:
        write_once(output / (name + ".json"), data[name])
    summary, analysis = data["summary"], data["analysis"]
    text = (
        "# Phase3B native two-round development pilot\n\n"
        + (
            "Synthetic engineering evidence only; no live readiness or quality claim.\n\n"
            if summary["fixture"]
            else "Four exposed paired prompt units; no held-out, population or human-preference claim.\n\n"
        )
        + f"Status: {summary['status']}. Primary aliases scored: {summary['primary_scored']}/8. "
        + f"Candidate targets scored: {summary['assessment_scored']}/12.\n\n"
        + f"Mean selected-native minus fixed: {analysis['mean_adaptive_minus_fixed']}. "
        + f"Mean c2 minus c1: {analysis['mean_c2_minus_c1']}. "
        + f"Mean selected minus c1: {analysis['mean_selected_minus_c1']}.\n\n"
        + "Native selected-final scores alias c1/c2 assessments; no extra judging or independent observations. "
        + "A later fresh rollout may change with an unchanged strategy. Selection gain is not an edit effect.\n\n"
        + "Exhaustive read-consumption audit (diagnostic; separate from benchmark completion): "
        + f"complete={summary['read_consumption_audit_complete']}; "
        + f"complete recorded sessions={summary['read_consumption_audit_complete_sessions']}/"
        + f"{summary['read_consumption_audit_recorded_sessions']}. "
        + "Full per-file coverage, missing ranges and parse errors are retained in analysis.json under read_consumption_audit.\n\n"
        + f"Admitted requests: {summary['attempts']}/{summary['maximum_new_admitted_attempts']} maximum; known micro-USD: {summary['spent_micro_usd']}; "
        + f"new held micro-USD: {summary['reserved_micro_usd']}. Old held liabilities remain22880000micro-USD.\n\n"
        + f"Equal35USD fresh inference-cell allowances and{data['protocol']['policy']['phase_micro_usd'] / 1_000_000:.6f}USD remaining global exposure cap do not imply equal realized cost. "
        + "The earlier stopped Phase3B attempt is accounted for separately and remains charged to the original allowance. "
        + "Failed/discarded authoring/selector/solver work remains fully counted. No automatic repetition.\n"
    )
    write_bytes_once(output / "PHASE3B_REPORT.md", text.encode("utf-8"))
    return {**summary, "report_output": str(output), "reporting_provider_calls": 0}
