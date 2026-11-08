"""P4-CM1 native assessments and saved-record analysis; dispatch owns all spending."""
from __future__ import annotations

import math
import statistics
from types import SimpleNamespace
from typing import Any, cast

from buddha2.artifacts import ContractError, digest
from buddha2.phase2_contracts import validate_portfolio
from buddha2.phase2_native import GROUP_CONFIG, SCORE_CONFIG, _json_values

PERMUTATIONS = {"reverse": tuple(range(9, -1, -1)), "rotate": tuple(range(5, 10)) + tuple(range(5))}
TARGETS = ("fixed", "c1", "c2")
T_CRITICAL_23 = 2.06865761041904
KIND = "phase4-cm1-target-assessment-v1"


def _require(condition, message):
    if not condition:
        raise ContractError(message)


def target_slots(evaluator, assessment_id: str) -> dict[str, str]:
    """The finite thirteen-slot envelope, including reused official head slots."""
    prefix = evaluator.slot_prefix(assessment_id)
    return {prefix + ".group": "group",
            **{f"{prefix}.quality.{i:02d}": "quality" for i in range(10)},
            **{evaluator.slot_prefix(assessment_id + ":" + name) + ".group": "group"
               for name in PERMUTATIONS}}


def _group_view(evaluator, portfolio: dict, order: tuple[int, ...]) -> tuple[dict, dict]:
    # Permute only the native judge input, never generated-answer provenance.
    instance = evaluator._instance(portfolio)
    instance["generations"] = [instance["generations"][i] for i in order]
    call, = evaluator.modules["partition"].partition_calls(instance, GROUP_CONFIG)
    request = evaluator.group_request(portfolio)
    request["messages"] = [{"role": "system", "content": call.system},
                           {"role": "user", "content": call.user}]
    return instance, request


def _fold_group_view(evaluator, instance, response):
    if response.get("refusal") or response.get("stop_reason") in ("refusal", "content_filter"):
        raise evaluator.modules["judge"].JudgeRefusal("group judge declined")
    _require(response.get("stop_reason") == "stop", "group judge did not finish normally")
    output = evaluator._strict_object(response["text"], evaluator.modules["partition"].Partition)
    _require(all(output.groups), "partition groups must be nonempty")
    fields = evaluator.modules["partition"].partition_fold(instance, [output], GROUP_CONFIG)
    evaluator._validate_partition(fields["partition"])
    return fields["partition"]


def _quality(evaluator, portfolio, slot, request, result):
    response = evaluator._response(result, slot, "quality", request, portfolio)
    try:
        schema = evaluator.modules["score"].Score
        message = SimpleNamespace(stop_reason=response.get("stop_reason"),
            content=[SimpleNamespace(type="text", text=response["text"])])
        evaluator.modules["judge"].parse_message(message, schema)
        value = evaluator._strict_object(response["text"], schema)
        _require(type(value.score) is int and 1 <= value.score <= 10, "quality outside 1..10")
        return value, None
    except evaluator.modules["judge"].JudgeRefusal:
        return None, "quality_refused"
    except ValueError:
        return None, "invalid_quality"


def assess_target(evaluator, portfolio: dict, assessment_id: str, dispatch, *, official=None) -> dict:
    """Keep the native primary result; add only missing qualities and two groupings.

    ``dispatch(slot, role, body)`` must be the existing accounted/replay boundary.
    Unknown delivery and foreign result identities propagate rather than becoming diagnostics.
    """
    validate_portfolio(portfolio)
    slots = target_slots(evaluator, assessment_id)
    prefix = evaluator.slot_prefix(assessment_id)
    all_requests = evaluator.quality_requests(portfolio, list(range(10)))
    views = {name: _group_view(evaluator, portfolio, order) for name, order in PERMUTATIONS.items()}
    group_requests = {name: view[1] for name, view in views.items()}
    _require(len(all_requests) == 10 and len(slots) == 13, "P4 assessment envelope differs")
    if official is None:
        official = evaluator.assess(portfolio, dispatch, assessment_id=assessment_id)
    else:
        records = official.get("requests", [])
        _require(bool(records), "official assessment lacks request evidence")
        _require(official == evaluator.finalize(portfolio, records[0], records[1:],
                                               assessment_id=assessment_id),
                 "official assessment does not replay unchanged")
    result = {"kind": KIND, "assessment_id": assessment_id,
        "portfolio_sha256": digest(portfolio), "evaluator_sha256": digest(evaluator.identity),
        "fixture": portfolio["fixture"], "official": official, "quality_scores": [None] * 10,
        "quality_failures": {}, "sensitivity": {}, "requests": list(official["requests"]),
        "complete": False}
    if official["status"] != "scored":
        result["sha256"] = digest(result)
        return result
    partition = official["native"]["partition_fields"]["partition"]
    heads = evaluator.modules["score"].heads(partition)
    qualities = dict(zip(heads, official["requests"][1:], strict=True))
    # Validate reuse compatibility before making any supplemental call.
    for head, record in qualities.items():
        evaluator._response(record, f"{prefix}.quality.{head:02d}", "quality",
                            all_requests[head], portfolio)
    parsed = {}
    for i, request in enumerate(all_requests):
        slot = f"{prefix}.quality.{i:02d}"
        if i not in qualities:
            qualities[i] = dispatch(slot, "quality", request)
        value, failure = _quality(evaluator, portfolio, slot, request, qualities[i])
        parsed[i] = value
        if failure:
            result["quality_failures"][str(i)] = failure
        else:
            result["quality_scores"][i] = value.score
    result["requests"] = [official["requests"][0], *[qualities[i] for i in range(10)]]
    for name, order in PERMUTATIONS.items():
        variant_id = assessment_id + ":" + name
        slot = evaluator.slot_prefix(variant_id) + ".group"
        record = dispatch(slot, "group", group_requests[name])
        result["requests"].append(record)
        response = evaluator._response(record, slot, "group", group_requests[name], portfolio)
        panel = {"permutation": list(order), "assessment_view_sha256": digest(views[name][0]),
                 "partition": None, "fields": None, "status": "invalid_group"}
        try:
            labels = _fold_group_view(evaluator, views[name][0], response)
            original = [0] * 10
            for position, index in enumerate(order):
                original[index] = labels[position]
            mapped = evaluator.modules["partition"].canonical(original)
            evaluator._validate_partition(mapped)
            panel.update(partition=mapped, status="quality_incomplete")
            new_heads = evaluator.modules["score"].heads(mapped)
            panel["head_changes"] = sorted(set(heads) ^ set(new_heads))
            panel["membership_disagreements"] = sum(
                (mapped[i] == mapped[j]) != (partition[i] == partition[j])
                for i in range(10) for j in range(i))
            if all(parsed[i] is not None for i in new_heads):
                instance = {**evaluator._instance(portfolio), "partition": mapped}
                fields = evaluator.modules["score"].score_fold(
                    instance, [parsed[i] for i in new_heads], SCORE_CONFIG)
                panel.update(fields=_json_values(fields), status="scored")
        except evaluator.modules["judge"].JudgeRefusal:
            panel["status"] = "group_refused"
        except ValueError:
            panel["status"] = "invalid_group"
        result["sensitivity"][name] = panel
    _require(len(result["requests"]) == 13, "P4 target exceeded its finite worklist")
    result["complete"] = not result["quality_failures"] and all(
        panel["status"] == "scored" for panel in result["sensitivity"].values())
    result["sha256"] = digest(result)
    return result


def _bundle(value):
    if value is None:
        return None
    _require(isinstance(value, dict) and value.get("kind") == KIND
        and value.get("sha256") == digest({k: v for k, v in value.items() if k != "sha256"}),
        "changed or foreign P4 assessment bundle")
    official = value["official"]
    _require(type(value.get("fixture")) is bool
        and official.get("portfolio_sha256") == value.get("portfolio_sha256")
        and digest(official.get("evaluator")) == value.get("evaluator_sha256")
        and official.get("fixture") is value.get("fixture"), "P4 assessment origins differ")
    return value


def _metrics(bundle, variant=None):
    if bundle is None:
        return None
    record = bundle["official"] if variant is None else bundle["sensitivity"].get(variant)
    if not record or record.get("status") != "scored":
        return None
    fields = record["metrics"] if variant is None else record["fields"]
    _require(type(fields.get("distinct")) is int and 1 <= fields["distinct"] <= 10
        and type(fields.get("utility")) in (int, float)
        and math.isfinite(fields["utility"]) and 0 <= fields["utility"] <= 10,
        "invalid saved P4 metrics")
    return {"distinct": fields["distinct"], "utility": fields["utility"]}


def _statistics(values, complete):
    n = len(values)
    mean = statistics.mean(values) if n else None
    sd = statistics.stdev(values) if n > 1 else None
    interval = None
    if complete:
        _require(n == 24, "confirmatory interval requires all 24 prompt units")
        center, deviation = cast(float, mean), cast(float, sd)
        half = T_CRITICAL_23 * deviation / math.sqrt(24)
        interval = [center - half, center + half]
    return {"n": n, "mean": mean, "median": statistics.median(values) if n else None,
        "paired_sd": sd, "interval_95": interval, "wins": sum(v > 0 for v in values),
        "losses": sum(v < 0 for v in values), "ties": sum(v == 0 for v in values),
        "leave_one_out_means": [(sum(values) - v) / 23 for v in values] if complete else None,
        "descriptive_only": not complete}


def analyze_pairs(rows: list[dict]) -> dict:
    """Analyze only saved P4 bundles; missing data never become invented scores."""
    _require(isinstance(rows, list) and len(rows) <= 24, "P4 has exactly 24 planned prompt units")
    identities = [row.get("prompt_id") for row in rows]
    _require(all(isinstance(i, str) and i for i in identities)
             and len(set(identities)) == len(rows), "duplicate or invalid prompt identity")
    contrasts: dict[str, dict[str, list[float]]] = {
        name: {metric: [] for metric in ("utility", "distinct")}
        for name in ("official", *PERMUTATIONS)}
    panels, ratios = [], []
    complete, supplemental = len(rows) == 24, len(rows) == 24
    native_total = fixed_total = 0
    cost_complete = len(rows) == 24
    for row in rows:
        targets = row.get("targets")
        _require(isinstance(targets, dict) and set(targets) == set(TARGETS), "P4 target inventory differs")
        targets = cast(dict, targets)
        targets = {name: _bundle(value) for name, value in targets.items()}
        present = [value for value in targets.values() if value is not None]
        _require(len({v["official"]["task_id"] for v in present}) <= 1
            and len({v["fixture"] for v in present}) <= 1
            and len({v["assessment_id"] for v in present}) == len(present),
            "mixed task/fixture or repeated target assessment")
        _require(all(v["official"]["task_id"] == row["prompt_id"] for v in present),
                 "assessment task does not match its prompt unit")
        choice = row.get("selected_checkpoint")
        _require(choice in (None, "c1", "c2"), "foreign native checkpoint choice")
        metrics = {name: _metrics(value) for name, value in targets.items()}
        complete = complete and all(metrics.values()) and choice is not None
        supplemental = supplemental and all(value and value["complete"] for value in targets.values())
        quality: dict[str, Any] = {}
        for name, bundle in targets.items():
            if bundle is None:
                quality[name] = None
                continue
            scores = bundle["quality_scores"]
            _require(isinstance(scores, list) and len(scores) == 10 and all(
                score is None or type(score) is int and 1 <= score <= 10 for score in scores),
                "invalid quality coverage")
            observed = [v for v in scores if v is not None]
            mean = statistics.mean(observed) if len(observed) == 10 else None
            quality[name] = {"scores": scores, "observed_count": len(observed), "all_response_mean": mean,
                "first_answer_quality": scores[0],
                "placement_residual": metrics[name]["utility"] - mean
                if metrics[name] and metrics[name]["distinct"] == 10 and mean is not None else None}
        selected = metrics.get(choice)
        for variant in contrasts:
            pair = (_metrics(targets.get(choice), None if variant == "official" else variant),
                    _metrics(targets["fixed"], None if variant == "official" else variant))
            if all(pair):
                for metric in ("utility", "distinct"):
                    contrasts[variant][metric].append(pair[0][metric] - pair[1][metric])
        costs = [row.get("native_micro_usd"), row.get("fixed_micro_usd")]
        _require(all(v is None or type(v) is int and v >= 0 for v in costs), "invalid inference cost")
        native_total += costs[0] or 0
        fixed_total += costs[1] or 0
        native_cost, fixed_cost = costs
        ratio = fixed_cost / native_cost if native_cost is not None and fixed_cost is not None and native_cost > 0 else None
        ratios.append(ratio)
        cost_complete = cost_complete and ratio is not None
        stages = []
        for stage in row.get("stage_dispositions", []):
            before, after = stage.get("input_effective_strategy_sha256"), stage.get("effective_strategy_sha256")
            stages.append({"label": stage.get("label"), "changed_from_input": before != after
                if before is not None and after is not None else None, "reported_KEEP": stage.get("kept_base")})
        fixed = metrics["fixed"]
        decomposition = None
        if selected and fixed:
            sq, fq = quality[cast(str, choice)], quality["fixed"]
            covered = sq["placement_residual"] is not None and fq["placement_residual"] is not None
            decomposition = {"utility_delta": selected["utility"] - fixed["utility"],
                "distinct_delta": selected["distinct"] - fixed["distinct"],
                "all_response_quality_delta": sq["all_response_mean"] - fq["all_response_mean"]
                if covered else None,
                "placement_delta": sq["placement_residual"] - fq["placement_residual"]
                if covered else None, "descriptive_not_causal": True}
        panels.append({"prompt_id": row["prompt_id"], "metrics": metrics, "quality": quality,
            "selected_minus_fixed": decomposition,
            "selected_checkpoint": choice, "cost_ratio": ratio, "strategy_changes": stages,
            "selected_minus_c1": selected["utility"] - metrics["c1"]["utility"]
            if selected and metrics["c1"] else None,
            "c2_minus_c1": metrics["c2"]["utility"] - metrics["c1"]["utility"]
            if metrics["c1"] and metrics["c2"] else None})
    complete = bool(complete)
    supplemental = bool(supplemental and complete)
    stats = {variant: {metric: _statistics(values, complete if variant == "official" else supplemental)
                      for metric, values in measures.items()} for variant, measures in contrasts.items()}
    aggregate = fixed_total / native_total if cost_complete and native_total else None
    within = sum(r is not None and 0.8 <= r <= 1.2 for r in ratios)
    matched = cost_complete and aggregate is not None and 0.9 <= aggregate <= 1.1 and within >= 20
    interval = stats["official"]["utility"]["interval_95"]
    benefit = bool(interval is not None and interval[0] > 0 and matched)
    means = [stats[name]["utility"]["mean"] for name in PERMUTATIONS]
    return {"kind": "phase4-cm1-saved-analysis-v1", "planned_prompts": 24,
        "primary_complete": complete, "sensitivity_complete": supplemental,
        "scientific_complete": complete and supplemental and cost_complete,
        "contrasts": stats, "pairs": panels,
        "loss_prompt_ids": [panel["prompt_id"] for panel in panels
            if panel["selected_minus_fixed"] and panel["selected_minus_fixed"]["utility_delta"] < 0],
        "case_counts": {"provided": len(rows), "compared": len(contrasts["official"]["utility"]),
            "wins": sum(v > 0 for v in contrasts["official"]["utility"]),
            "losses": sum(v < 0 for v in contrasts["official"]["utility"]),
            "ties": sum(v == 0 for v in contrasts["official"]["utility"]),
            "missing_comparison": 24 - len(contrasts["official"]["utility"])},
        "costs": {"native_micro_usd": native_total, "fixed_micro_usd": fixed_total,
            "aggregate_ratio": aggregate, "pair_ratios": ratios, "pairs_within_20_percent": within,
            "coverage_complete": bool(cost_complete),
            "totals_scope": "Known provided inference costs only; missing is not zero",
            "approximately_matched": bool(matched)}, "matched_primary_benefit": benefit,
        "positive_under_both_perturbations": bool(benefit and supplemental and all(v > 0 for v in means)),
        "partition_sensitive": bool(complete and supplemental and any(v < 0 for v in means)
                                    and stats["official"]["utility"]["mean"] > 0),
        "external_novelty_measured": False, "causal_edit_effect_established": False}
