"""RC1 wire labels bound to actual settled rank ownership; no synthetic live proof."""
from __future__ import annotations

import copy
import hashlib
import json

from buddha2.artifacts import digest
from buddha2.phase2_contracts import permute_portfolio, validate_portfolio
from followups.phase3a_rank_contract_v1.adapter import LABELS, N1_SOURCE_SHA256, PROFILE_SHA256
from followups.phase3a_rank_contract_v1.adapter import profile as accepted_profile
from followups.phase3a_v1.accounting import IntegrityStop
from followups.phase3a_v1.strategy import parse_strategy, render_strategy_request, verified_response
from followups.rank_format_v1.normalizer import normalize_rank


def profile() -> dict:
    return accepted_profile()


def _require(value: bool, message: str) -> None:
    if not value:
        raise IntegrityStop(message)


def _seal(value: dict) -> dict:
    return {**value, "sha256": digest(value)}


def prepare(parent_B: dict, task: dict, strategy: dict, context: dict) -> dict:
    profile()
    validate_portfolio(parent_B)
    _require(parent_B["provenance"]["method"] == "B" and task == parent_B["task"], "RC1 requires its exact method-B task")
    _require(type(context) is dict and set(context) == {"study_sha256", "run_id", "slot_id", "arm", "fixture"}
        and context["study_sha256"] == parent_B["provenance"]["study_sha256"]
        and context["fixture"] is parent_B["fixture"] and type(context["arm"]) is str
        and context["arm"] in {"fixed", "adaptive"}, "RC1 context differs")
    _require(all(type(context[k]) is str and context[k].strip() and len(context[k]) <= 512 and "\x00" not in context[k]
                 for k in ("run_id", "slot_id")), "RC1 context identity is invalid")
    _require(context["slot_id"] not in parent_B["provenance"]["request_ids"], "rank slot already belongs to the parent")
    consumed = parse_strategy(json.dumps(strategy, ensure_ascii=False, allow_nan=False))
    mapping = _seal({"kind": "rp1-rc1-map-v1", "profile_sha256": PROFILE_SHA256,
        "parent_sha256": digest(parent_B), "task_sha256": digest(task), "strategy_sha256": digest(consumed),
        "context": copy.deepcopy(context), "entries": [{"label": label, "canonical_id": row["id"]}
            for label, row in zip(LABELS, parent_B["responses"], strict=True)]})
    wire = [{**row, "id": label} for label, row in zip(LABELS, parent_B["responses"], strict=True)]
    request = render_strategy_request("rank", task, consumed, responses=wire)
    binding = _seal({"kind": "rp1-rc1-request-binding-v1", "map_sha256": mapping["sha256"],
        "profile_sha256": PROFILE_SHA256, "context_sha256": digest(context), "request_sha256": digest(request)})
    return _seal({"kind": "rp1-rc1-prepared-v1", "mapping": mapping, "request_binding": binding, "request": request})


def derive(parent_B: dict, task: dict, strategy: dict, context: dict, prepared: dict, result: dict) -> dict:
    expected = prepare(parent_B, task, strategy, context)
    _require(type(prepared) is dict and digest(prepared) == digest(expected), "RC1 stale map/strategy/context/request")
    response = verified_response(result, study_sha256=context["study_sha256"], fixture=context["fixture"],
        slot_id=context["slot_id"], role="rank", request=expected["request"])
    _require(context["fixture"] or response["model"] == parent_B["provenance"]["model"]["returned"], "RC1 returned model changed")
    raw = response["text"]
    normalization = normalize_rank(raw, list(LABELS)) if response["stop_reason"] == "end_turn" else None
    accepted = normalization is not None and normalization["status"] == "accepted"
    label_order = normalization["order"] if accepted and normalization is not None else None
    lookup = {entry["label"]: entry["canonical_id"] for entry in expected["mapping"]["entries"]}
    order = [lookup[label] for label in label_order] if label_order is not None else None
    procedure = {"kind": "phase3a-RC1-permutation-v1", "profile_sha256": PROFILE_SHA256,
        "mapping_rule": "r01-r10-by-parent-generation-order", "normalizer_source_sha256": N1_SOURCE_SHA256,
        "strategy_sha256": expected["mapping"]["strategy_sha256"]}
    portfolio = permute_portfolio(parent_B, order, request_id=context["slot_id"],
        settings_sha256=parent_B["provenance"]["settings_sha256"], procedure_sha256=digest(procedure)) if order is not None else None
    return _seal({"kind": "rp1-rc1-rank-derivation-v1", "fixture": context["fixture"],
        "eligible_live_result": accepted and not context["fixture"], "ownership_basis": "settled verified slot/study/request result; caller binds exact authoritative journal record",
        "status": "accepted" if accepted else "rejected",
        "reason": normalization["reason"] if normalization is not None else "ranker_not_finished",
        "prepared_sha256": expected["sha256"], "mapping": expected["mapping"], "request_binding": expected["request_binding"],
        "result_sha256": digest(result), "intent_sha256": result["intent_sha256"], "request_id": response.get("request_id"),
        "raw_reply_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "normalization": normalization, "label_order": label_order, "canonical_order": order,
        "procedure": procedure, "procedure_sha256": digest(procedure), "portfolio": portfolio,
        "portfolio_sha256": digest(portfolio) if portfolio is not None else None})
