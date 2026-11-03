"""RC1 synthetic-only rank I/O: short wire labels, unchanged N1, exact canonical answers."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from buddha2.artifacts import ContractError, digest, file_hash
from buddha2.phase2_contracts import permute_portfolio, validate_portfolio
from followups.phase3a_v1.strategy import parse_strategy, render_strategy_request
from followups.rank_format_v1.normalizer import normalize_rank

ROOT = Path(__file__).resolve().parents[2]
PROFILE_ID = "rank-io-rc1-v1"
LABELS = tuple(f"r{i:02d}" for i in range(1, 11))
N1_SOURCE_SHA256 = "a40dd9605d57b3ebb267d65b8cfc7571d6636746823bb73e2acf3a7a197e9e41"
HASH_BASIS = "UTF-8 with surrogatepass for lossless invalid-Unicode diagnostics; N1 still rejects invalid UTF-8"
_PROFILE = {"kind": PROFILE_ID, "labels": list(LABELS), "assignment": "parent-generation-order",
            "normalizer": "rank-format-N1", "normalizer_source_sha256": N1_SOURCE_SHA256,
            "request_delta": "rank input id values only", "canonical_identity": "unchanged",
            "implementation_role": "human-authored fixed experiment engineering"}
PROFILE_SHA256 = digest(_PROFILE)
_CONTEXT_KEYS = {"study_sha256", "run_id", "slot_id", "caller", "synthetic"}
_FLAGS = {"origin": "synthetic_fixture", "synthetic": True, "unscored": True,
          "provider_calls": 0, "eligible_live_result": False}


def _require(value: bool, message: str) -> None:
    if not value:
        raise ContractError(message)


def _seal(value: dict) -> dict:
    return {**value, "sha256": digest(value)}


def _checked(value: dict) -> dict:
    _require(type(value) is dict and value.get("sha256") == digest({k: v for k, v in value.items() if k != "sha256"}),
             "RC1 record seal differs")
    return value


def _raw_hash(raw_reply: str) -> str:
    _require(type(raw_reply) is str, "RC1 raw reply must be a string")
    return hashlib.sha256(raw_reply.encode("utf-8", errors="surrogatepass")).hexdigest()


def profile() -> dict:
    """A source-owned rule, separate from any particular parent, map or edited strategy."""
    _require(file_hash(ROOT / "followups/rank_format_v1/normalizer.py") == N1_SOURCE_SHA256,
             "frozen N1 source changed")
    _require(digest(_PROFILE) == PROFILE_SHA256, "RC1 profile changed")
    return copy.deepcopy(_PROFILE)


def prepare(parent_B: dict, task: dict, strategy: dict, context: dict) -> dict:
    """Seal a parent-local map and its real rendered request; never dispatch."""
    profile()
    validate_portfolio(parent_B)
    _require(parent_B["provenance"]["method"] == "B" and task == parent_B["task"],
             "RC1 requires its exact method-B parent task")
    _require(type(context) is dict and set(context) == _CONTEXT_KEYS
             and context.get("synthetic") is True
             and context.get("caller") in {"fixed-candidate", "native-rollout"}
             and context.get("study_sha256") == parent_B["provenance"]["study_sha256"],
             "RC1 context must be an explicit parent-bound synthetic caller")
    for key in ("run_id", "slot_id"):
        value = context.get(key)
        if type(value) is not str or not value.strip() or len(value) > 256 or "\x00" in value:
            raise ContractError("RC1 context identity is invalid")
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise ContractError("RC1 context identity is not UTF-8") from exc
    _require(context["slot_id"].startswith("rc1-synthetic-")
             and context["slot_id"] not in parent_B["provenance"]["request_ids"],
             "RC1 synthetic rank slot must be distinct and explicitly named")
    _require(type(strategy) is dict, "RC1 strategy must be the three-field record")
    checked_strategy = parse_strategy(json.dumps(strategy, ensure_ascii=False, allow_nan=False))
    mapping = _seal({"kind": "rc1-rank-map-v1", "profile_sha256": PROFILE_SHA256,
        "parent_sha256": digest(parent_B), "task_sha256": digest(task),
        "strategy_sha256": digest(checked_strategy), "context": copy.deepcopy(context),
        "entries": [{"label": label, "canonical_id": response["id"]}
                    for label, response in zip(LABELS, parent_B["responses"], strict=True)]})
    wire_responses = [{**response, "id": label} for label, response in zip(LABELS, parent_B["responses"], strict=True)]
    request = render_strategy_request("rank", task, checked_strategy, responses=wire_responses)
    request_binding = _seal({"kind": "rc1-rank-request-binding-v1", "map_sha256": mapping["sha256"],
        "profile_sha256": PROFILE_SHA256, "context_sha256": digest(context), "request_sha256": digest(request)})
    return _seal({"kind": "rc1-rank-prepared-v1", "mapping": mapping,
                  "request_binding": request_binding, "request": request})


def synthetic_result_binding(prepared: dict, raw_reply: str) -> dict:
    """Integrity bind a test reply. This cannot attest provider origin or live eligibility."""
    _checked(prepared)
    _require(prepared.get("kind") == "rc1-rank-prepared-v1", "foreign RC1 preparation")
    mapping, request_binding = _checked(prepared["mapping"]), _checked(prepared["request_binding"])
    _require(mapping["context"]["synthetic"] is True and mapping["profile_sha256"] == PROFILE_SHA256
             and request_binding["map_sha256"] == mapping["sha256"]
             and request_binding["request_sha256"] == digest(prepared["request"]),
             "RC1 test result requires consistent synthetic preparation")
    return _seal({"kind": "rc1-synthetic-result-binding-v1", **_FLAGS,
        "prepared_sha256": prepared["sha256"], "map_sha256": mapping["sha256"],
        "request_sha256": request_binding["request_sha256"], "context_sha256": digest(mapping["context"]),
        "parent_sha256": mapping["parent_sha256"], "strategy_sha256": mapping["strategy_sha256"],
        "profile_sha256": PROFILE_SHA256, "raw_reply_sha256": _raw_hash(raw_reply), "raw_reply_hash_basis": HASH_BASIS})


def derive(parent_B: dict, task: dict, strategy: dict, context: dict, prepared: dict,
           raw_reply: str, result_binding: dict) -> dict:
    """Reject stale provenance before interpreting aliases; return only synthetic derivations."""
    expected = prepare(parent_B, task, strategy, context)
    _checked(prepared)
    _checked(result_binding)
    _require(prepared == expected, "RC1 prepared parent/map/context/strategy/request differs")
    _require(result_binding == synthetic_result_binding(expected, raw_reply),
             "RC1 synthetic result binding differs; no live or unbound reply is eligible")
    mapping, request_binding = expected["mapping"], expected["request_binding"]
    normalization = normalize_rank(raw_reply, list(LABELS))
    label_order = normalization["order"] if normalization["status"] == "accepted" else None
    canonical_order = None
    output = None
    procedure = {"kind": "phase3a-RC1-permutation-v1", "profile_sha256": PROFILE_SHA256,
        "mapping_rule": "r01-r10-by-parent-generation-order", "normalizer_source_sha256": N1_SOURCE_SHA256,
        "strategy_sha256": mapping["strategy_sha256"]}
    if label_order is not None:
        lookup = {entry["label"]: entry["canonical_id"] for entry in mapping["entries"]}
        canonical_order = [lookup[label] for label in label_order]
        output = permute_portfolio(parent_B, canonical_order, request_id=context["slot_id"],
            settings_sha256=parent_B["provenance"]["settings_sha256"], procedure_sha256=digest(procedure))
    return _seal({"kind": "rc1-rank-derivation-v1", **_FLAGS,
        "status": normalization["status"], "reason": normalization["reason"],
        "parent_sha256": mapping["parent_sha256"], "map_sha256": mapping["sha256"],
        "prepared_sha256": expected["sha256"], "request_sha256": request_binding["request_sha256"],
        "context": copy.deepcopy(context), "strategy_sha256": mapping["strategy_sha256"],
        "profile_sha256": PROFILE_SHA256, "procedure": procedure, "procedure_sha256": digest(procedure),
        "result_binding_sha256": result_binding["sha256"], "raw_reply_sha256": _raw_hash(raw_reply),
        "raw_reply_hash_basis": HASH_BASIS, "normalization": normalization, "label_order": label_order,
        "canonical_order": canonical_order, "canonical_output": output,
        "canonical_output_sha256": digest(output) if output is not None else None,
        "canonical_output_origin": "Historical parent source/model/fixture flags are inherited; the test rank is synthetic, unscored and never an eligible primary."})
