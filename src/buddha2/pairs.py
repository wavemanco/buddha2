"""Strict two-response artifacts and replayable, prompt-level evaluator analysis."""

from __future__ import annotations

import math
import unicodedata
from typing import Any

from .artifacts import ContractError, digest

_PAIR_KEYS = {
    "schema_version", "kind", "fixture", "pair_id", "prompt_id", "prompt",
    "prompt_group_sha256", "family", "responses",
}
_PRESENTATION_KEYS = {
    "schema_version", "kind", "presentation_id", "pair_id", "pair_sha256", "order",
}
_LABEL_KEYS = {
    "schema_version", "kind", "pair_id", "pair_sha256", "preferred_response_id",
    "rating_context",
}
_JUDGMENT_KEYS = {
    "schema_version", "kind", "presentation_id", "presentation_sha256", "pair_sha256",
    "status", "choice", "reason", "model", "rubric_sha256", "settings_sha256", "usage",
    "cost_usd",
}
STATUSES = ("ok", "refused", "truncated", "malformed", "transport_error", "unknown", "missing")


def _text(value: Any, name: str, limit: int = 100_000) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise ContractError(f"invalid {name}")


def _hash(value: Any, name: str) -> None:
    if (
        not isinstance(value, str) or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ContractError(f"invalid {name}")


def _record(value: Any, keys: set[str], kind: str) -> None:
    if (
        not isinstance(value, dict) or set(value) != keys
        or type(value.get("schema_version")) is not int or value["schema_version"] != 1
        or value.get("kind") != kind
    ):
        raise ContractError(f"invalid {kind} schema or unexpected fields")


def _prompt_hash(prompt: str) -> str:
    normalized = " ".join(unicodedata.normalize("NFKC", prompt).casefold().split())
    return digest(normalized)


def make_pair(
    prompt_id: str, prompt: str, family: str, responses: list[dict], *, fixture: bool = False
) -> dict:
    """Construct a canonical pair; presentation order and human labels live elsewhere."""
    if not isinstance(responses, list) or any(not isinstance(row, dict) for row in responses):
        raise ContractError("responses must be records")
    for response in responses:
        if set(response) != {"id", "text"}:
            raise ContractError("responses require only id and text")
        _text(response["id"], "response id", 256)
        _text(response["text"], "response text")
    _text(prompt, "prompt")
    _text(prompt_id, "prompt_id", 256)
    _text(family, "family", 256)
    if type(fixture) is not bool:
        raise ContractError("fixture must be explicit boolean")
    value = {
        "schema_version": 1, "kind": "creativity-pair", "fixture": fixture,
        "prompt_id": prompt_id, "prompt": prompt, "prompt_group_sha256": _prompt_hash(prompt),
        "family": family, "responses": sorted(
            ({"id": row["id"], "text": row["text"]} for row in responses),
            key=lambda row: row["id"],
        ),
    }
    value["pair_id"] = "pair-" + digest(value)
    validate_pair(value)
    return value


def validate_pair(value: Any) -> None:
    _record(value, _PAIR_KEYS, "creativity-pair")
    if type(value["fixture"]) is not bool:
        raise ContractError("fixture must be explicit boolean")
    for name in ("prompt_id", "family"):
        _text(value[name], name, 256)
    _text(value["prompt"], "prompt")
    if value["prompt_group_sha256"] != _prompt_hash(value["prompt"]):
        raise ContractError("prompt normalization identity is stale")
    responses = value["responses"]
    if not isinstance(responses, list) or len(responses) != 2:
        raise ContractError("a pair requires exactly two responses")
    for response in responses:
        if not isinstance(response, dict) or set(response) != {"id", "text"}:
            raise ContractError("responses require only id and text")
        _text(response["id"], "response id", 256)
        _text(response["text"], "response text")
    ids = [response["id"] for response in responses]
    if ids[0] == ids[1] or ids != sorted(ids):
        raise ContractError("response IDs must be unique and canonically ordered")
    if responses[0]["text"] == responses[1]["text"]:
        raise ContractError("a preference pair requires different response texts")
    if value["pair_id"] != "pair-" + digest({k: v for k, v in value.items() if k != "pair_id"}):
        raise ContractError("pair identity is stale")


def make_presentation(pair: dict, order: list[str]) -> dict:
    validate_pair(pair)
    if not isinstance(order, list):
        raise ContractError("presentation order must be a list")
    value = {
        "schema_version": 1, "kind": "pair-presentation", "pair_id": pair["pair_id"],
        "pair_sha256": digest(pair), "order": list(order),
    }
    value["presentation_id"] = "presentation-" + digest(value)
    validate_presentation(pair, value)
    return value


def validate_presentation(pair: dict, value: Any) -> None:
    validate_pair(pair)
    _record(value, _PRESENTATION_KEYS, "pair-presentation")
    order = value["order"]
    if (
        value["pair_id"] != pair["pair_id"] or value["pair_sha256"] != digest(pair)
        or not isinstance(order, list) or len(order) != 2
        or any(not isinstance(identity, str) for identity in order)
        or sorted(order) != [response["id"] for response in pair["responses"]]
    ):
        raise ContractError("presentation response identity/order does not match pair")
    if value["presentation_id"] != "presentation-" + digest(
        {k: v for k, v in value.items() if k != "presentation_id"}
    ):
        raise ContractError("presentation identity is stale")


def make_label(pair: dict, preferred_response_id: str, rating_context: dict) -> dict:
    validate_pair(pair)
    value = {
        "schema_version": 1, "kind": "human-pair-label", "pair_id": pair["pair_id"],
        "pair_sha256": digest(pair), "preferred_response_id": preferred_response_id,
        "rating_context": rating_context,
    }
    validate_label(pair, value)
    return value


def validate_label(pair: dict, value: Any) -> None:
    validate_pair(pair)
    _record(value, _LABEL_KEYS, "human-pair-label")
    if (
        value["pair_id"] != pair["pair_id"] or value["pair_sha256"] != digest(pair)
        or value["preferred_response_id"] not in [row["id"] for row in pair["responses"]]
        or not isinstance(value["rating_context"], dict) or not value["rating_context"]
    ):
        raise ContractError("human label context or pair identity is incompatible")
    try:
        digest(value["rating_context"])
    except (ValueError, TypeError) as exc:
        raise ContractError("rating context must be finite JSON") from exc


def make_judgment(
    pair: dict, presentation: dict, *, status: str, choice: str | None, reason: str,
    model: dict, rubric_sha256: str, settings_sha256: str,
    usage: dict | None = None, cost_usd: float | None = None,
) -> dict:
    validate_presentation(pair, presentation)
    value = {
        "schema_version": 1, "kind": "pair-judgment",
        "presentation_id": presentation["presentation_id"],
        "presentation_sha256": digest(presentation), "pair_sha256": digest(pair),
        "status": status, "choice": choice, "reason": reason, "model": model,
        "rubric_sha256": rubric_sha256, "settings_sha256": settings_sha256,
        "usage": usage, "cost_usd": cost_usd,
    }
    validate_judgment(pair, presentation, value)
    return value


def validate_judgment(pair: dict, presentation: dict, value: Any) -> None:
    validate_presentation(pair, presentation)
    _record(value, _JUDGMENT_KEYS, "pair-judgment")
    if (
        value["presentation_id"] != presentation["presentation_id"]
        or value["presentation_sha256"] != digest(presentation)
        or value["pair_sha256"] != digest(pair)
    ):
        raise ContractError("judgment input/order identity is stale")
    if value["status"] not in STATUSES:
        raise ContractError("unknown execution status")
    if value["status"] == "ok":
        if value["choice"] not in ("A", "B", "tie", "abstain"):
            raise ContractError("successful judgment requires a supported choice")
    elif value["choice"] is not None:
        raise ContractError("failed execution cannot carry a preference")
    _text(value["reason"], "judgment reason", 4_000)
    model = value["model"]
    if not isinstance(model, dict) or set(model) != {"requested", "returned"}:
        raise ContractError("model provenance must identify requested and returned model")
    _text(model["requested"], "requested model", 256)
    if value["status"] == "ok" or model["returned"] is not None:
        _text(model["returned"], "returned model", 256)
    _hash(value["rubric_sha256"], "rubric identity")
    _hash(value["settings_sha256"], "settings identity")
    usage = value["usage"]
    if usage is not None and (
        not isinstance(usage, dict) or set(usage) != {"input_tokens", "output_tokens"}
        or any(type(count) is not int or count < 0 for count in usage.values())
    ):
        raise ContractError("usage must contain nonnegative integer token counts")
    cost = value["cost_usd"]
    if cost is not None and (
        type(cost) not in (int, float) or not math.isfinite(cost) or cost < 0
    ):
        raise ContractError("cost must be finite nonnegative USD or unknown")


def wilson_interval(successes: int, total: int) -> list[float | None]:
    """Two-sided 95% Wilson interval, with no pseudo-observations for empty samples."""
    if (
        type(successes) is not int or type(total) is not int
        or successes < 0 or total < successes
    ):
        raise ContractError("invalid binomial denominator or success count")
    if total == 0:
        return [None, None]
    z = 1.959963984540054
    proportion = successes / total
    divisor = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / divisor
    radius = z * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total**2)) / divisor
    return [max(0.0, center - radius), min(1.0, center + radius)]


def analyze_pairs(
    pairs: list[dict], presentations: list[dict], judgments: list[dict], labels: list[dict],
    *, expected_prompts: int = 12, minimum_agreement: int = 9, minimum_consistency: int = 11,
) -> dict:
    """Replay one frozen evaluator; failed/missing orders earn zero at fixed denominators."""
    if (
        any(type(number) is not int for number in (
            expected_prompts, minimum_agreement, minimum_consistency
        )) or expected_prompts < 1
        or not 0 <= minimum_agreement <= expected_prompts
        or not 0 <= minimum_consistency <= expected_prompts
        or any(not isinstance(rows, list) for rows in (pairs, presentations, judgments, labels))
    ):
        raise ContractError("invalid analysis worklist or operational floors")
    pair_map, prompt_ids, group_ids, fixture_flags = {}, set(), set(), set()
    for pair in pairs:
        validate_pair(pair)
        if (
            pair["pair_id"] in pair_map or pair["prompt_id"] in prompt_ids
            or pair["prompt_group_sha256"] in group_ids
        ):
            raise ContractError("duplicate pair or non-independent prompt group")
        pair_map[pair["pair_id"]] = pair
        prompt_ids.add(pair["prompt_id"])
        group_ids.add(pair["prompt_group_sha256"])
        fixture_flags.add(pair["fixture"])
    if len(pairs) > expected_prompts:
        raise ContractError("pair count exceeds the frozen analysis denominator")
    if len(fixture_flags) > 1:
        raise ContractError("analysis cannot pool fixture and real observations")
    presentation_map: dict[str, dict] = {}
    pair_orders: dict[str, list[dict]] = {identity: [] for identity in pair_map}
    for shown in presentations:
        if (
            not isinstance(shown, dict) or not isinstance(shown.get("pair_id"), str)
            or shown["pair_id"] not in pair_map
        ):
            raise ContractError("presentation references an undeclared pair")
        validate_presentation(pair_map[shown["pair_id"]], shown)
        if shown["presentation_id"] in presentation_map:
            raise ContractError("duplicate presentation identity")
        presentation_map[shown["presentation_id"]] = shown
        pair_orders[shown["pair_id"]].append(shown)
    for orders in pair_orders.values():
        if len(orders) != 2 or orders[0]["order"] != list(reversed(orders[1]["order"])):
            raise ContractError("each pair requires exactly two inverse presentations")
    label_map = {}
    for label in labels:
        if (
            not isinstance(label, dict) or not isinstance(label.get("pair_id"), str)
            or label["pair_id"] not in pair_map
        ):
            raise ContractError("label references an undeclared pair")
        validate_label(pair_map[label["pair_id"]], label)
        if label["pair_id"] in label_map:
            raise ContractError("duplicate human label")
        label_map[label["pair_id"]] = label
    if set(label_map) != set(pair_map):
        raise ContractError("human label missing for a declared pair")
    result_map, evaluator_identities = {}, set()
    returned_models = set()
    for result in judgments:
        if (
            not isinstance(result, dict) or not isinstance(result.get("presentation_id"), str)
            or result["presentation_id"] not in presentation_map
        ):
            raise ContractError("judgment references an undeclared presentation")
        shown = presentation_map[result["presentation_id"]]
        validate_judgment(pair_map[shown["pair_id"]], shown, result)
        if result["presentation_id"] in result_map:
            raise ContractError("duplicate judgment; retries are not independent results")
        result_map[result["presentation_id"]] = result
        evaluator_identities.add((
            result["model"]["requested"], result["rubric_sha256"], result["settings_sha256"]
        ))
        if result["model"]["returned"] is not None:
            returned_models.add(result["model"]["returned"])
    if len(evaluator_identities) > 1:
        raise ContractError("analysis cannot pool evaluator model/rubric/settings revisions")

    statuses = dict.fromkeys(STATUSES, 0)
    choices = dict.fromkeys(("A", "B", "tie", "abstain"), 0)
    rows = []
    families: dict[str, dict[str, int]] = {}
    correct_prompts = consistent_prompts = decisive = correct_presentations = 0
    longer_choices = shorter_choices = equal_choices = wrong_longer = wrong_shorter = wrong_equal = 0
    known_cost = 0.0
    unknown_cost = unknown_usage = 0
    for pair in pairs:
        identity = pair["pair_id"]
        preferred = label_map[identity]["preferred_response_id"]
        lengths = {row["id"]: len(row["text"]) for row in pair["responses"]}
        selected_ids = []
        for shown in pair_orders[identity]:
            saved = result_map.get(shown["presentation_id"])
            status = saved["status"] if saved is not None else "missing"
            statuses[status] += 1
            if saved is None or saved["cost_usd"] is None:
                unknown_cost += 1
            else:
                known_cost += saved["cost_usd"]
            if saved is None or saved["usage"] is None:
                unknown_usage += 1
            choice = saved["choice"] if saved is not None and status == "ok" else None
            if choice is not None:
                choices[choice] += 1
            selected = shown["order"][0 if choice == "A" else 1] if choice in ("A", "B") else None
            selected_ids.append(selected)
            if selected is not None:
                decisive += 1
                correct = selected == preferred
                correct_presentations += int(correct)
                other = next(response_id for response_id in lengths if response_id != selected)
                if lengths[selected] > lengths[other]:
                    longer_choices += 1
                    wrong_longer += int(not correct)
                elif lengths[selected] < lengths[other]:
                    shorter_choices += 1
                    wrong_shorter += int(not correct)
                else:
                    equal_choices += 1
                    wrong_equal += int(not correct)
        correct = selected_ids == [preferred, preferred]
        consistent = selected_ids[0] is not None and selected_ids[0] == selected_ids[1]
        correct_prompts += int(correct)
        consistent_prompts += int(consistent)
        family = families.setdefault(pair["family"], {"prompts": 0, "human_agreement": 0, "order_consistency": 0})
        family["prompts"] += 1
        family["human_agreement"] += int(correct)
        family["order_consistency"] += int(consistent)
        rows.append({
            "pair_id": identity, "prompt_id": pair["prompt_id"], "family": pair["family"],
            "selected_response_ids": selected_ids, "human_agreement": correct,
            "order_consistency": consistent,
        })
    complete = (
        len(pairs) == expected_prompts and not unknown_cost and not unknown_usage
        and not any(statuses[status] for status in ("missing", "unknown", "transport_error"))
    )
    passed = correct_prompts >= minimum_agreement and consistent_prompts >= minimum_consistency
    evaluator = next(iter(evaluator_identities), None)
    return {
        "schema_version": 1, "kind": "pair-evaluator-analysis", "analysis_revision": "phase1-v1",
        "fixture": next(iter(fixture_flags), None),
        "outcome": "inconclusive" if not complete else "pass" if passed else "diagnostic-only",
        "independent_prompts": len(pairs), "expected_prompts": expected_prompts,
        "presentations": len(presentations), "saved_judgments": len(judgments),
        "human_agreement": {
            "successes": correct_prompts, "denominator": expected_prompts,
            "minimum": minimum_agreement, "proportion": correct_prompts / expected_prompts,
            "wilson95": wilson_interval(correct_prompts, expected_prompts),
        },
        "order_consistency": {
            "successes": consistent_prompts, "denominator": expected_prompts,
            "minimum": minimum_consistency, "proportion": consistent_prompts / expected_prompts,
            "wilson95": wilson_interval(consistent_prompts, expected_prompts),
        },
        "coverage": {
            "decisive_presentations": decisive, "scheduled_presentations": expected_prompts * 2,
            "decisive_fraction": decisive / (expected_prompts * 2),
            "human_agreeing_presentations": correct_presentations,
            "agreement_among_decisive": correct_presentations / decisive if decisive else None,
        },
        "statuses": statuses, "choices": choices,
        "first_position_preference": {
            "A_choices": choices["A"], "decisive_presentations": decisive,
            "fraction": choices["A"] / decisive if decisive else None,
            "unit": "presentation; two dependent presentations per prompt",
        },
        "length_diagnostics": {
            "unit": "Unicode code points in original response text",
            "longer_choices": longer_choices, "shorter_choices": shorter_choices,
            "equal_length_choices": equal_choices, "wrong_longer_choices": wrong_longer,
            "wrong_shorter_choices": wrong_shorter, "wrong_equal_length_choices": wrong_equal,
        },
        "families": families, "prompts": rows,
        "cost": {
            "unit": "USD", "known_total_usd": known_cost,
            "unreported_presentations": unknown_cost, "unknown_usage_presentations": unknown_usage,
            "complete_total_usd": known_cost if not unknown_cost else None,
            "scope": "final presentation records; attempt ledger additionally includes retries/liabilities",
        },
        "evaluator": None if evaluator is None else {
            "requested_model": evaluator[0], "rubric_sha256": evaluator[1],
            "settings_sha256": evaluator[2], "returned_models": sorted(returned_models),
        },
        "applicability": "Supplementary pairwise comparison on the declared population only; no absolute or portfolio validation.",
        "limitations": [
            "Operational floors are a small-sample screen, not high-confidence validation.",
            "Order, length and family diagnostics are descriptive; no additional acceptance gates.",
            "Analysis requires separate access control and a committed prediction set before audit labels.",
        ],
    }
