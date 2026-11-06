"""Separate live-v2 portfolios and lossless native exchange; no scores or providers."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from .artifacts import ContractError, digest, read_json, write_bytes_once, write_once

MAX_PROMPT_CHARS = 100_000
MAX_RESPONSE_CHARS = 100_000

_KINDS = {False: "phase2-portfolio-live-v2", True: "phase2-portfolio-walkthrough-v2"}
_PORTFOLIO_KEYS = {
    "schema_version", "kind", "fixture", "portfolio_id", "task", "responses", "provenance",
}
_PROVENANCE_KEYS = {
    "method", "repeat", "model", "settings_sha256", "procedure_sha256", "request_ids",
    "parent_sha256", "study_sha256",
}


def _text(value: Any, label: str, limit: int) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise ContractError(f"invalid {label}")


def _hash(value: Any, label: str, length: int = 64) -> None:
    if (
        not isinstance(value, str) or len(value) != length
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ContractError(f"invalid {label}")


def _record(value: Any, keys: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise ContractError(f"invalid {label} fields")


def _reject_constant(value: str) -> None:
    raise ContractError(f"nonfinite native JSON value: {value}")


def slot_prefix(task_id: str, method: str, repeat: int) -> str:
    """Stable logical slots precede observation; provider request IDs live in outcomes."""
    _text(task_id, "task identity", 256)
    if not isinstance(method, str) or method not in ("A", "B", "C"):
        raise ContractError("unknown Phase 2 method")
    if type(repeat) is not int or repeat not in (1, 2):
        raise ContractError("Phase 2 repeat must be 1 or 2")
    return "p2-" + digest({"task_id": task_id, "method": method, "repeat": repeat})[:24]


def make_portfolio(
    task: dict, responses: list[dict], *, method: str, repeat: int, model: dict,
    settings_sha256: str, procedure_sha256: str, request_ids: list[str], study_sha256: str,
    fixture: bool = False, parent_sha256: str | None = None,
) -> dict:
    """Finalize a ten-slot order; non-success text is a visible native placeholder."""
    if type(fixture) is not bool:
        raise ContractError("fixture must be an explicit boolean")
    value = {
        "schema_version": 2, "kind": _KINDS[fixture], "fixture": fixture,
        "task": copy.deepcopy(task), "responses": copy.deepcopy(responses),
        "provenance": {
            "method": method, "repeat": repeat, "model": copy.deepcopy(model),
            "settings_sha256": settings_sha256, "procedure_sha256": procedure_sha256,
            "request_ids": copy.deepcopy(request_ids), "parent_sha256": parent_sha256,
            "study_sha256": study_sha256,
        },
    }
    try:
        value["portfolio_id"] = "portfolio-" + digest(value)
    except (TypeError, ValueError) as exc:
        raise ContractError("portfolio must contain finite JSON") from exc
    validate_portfolio(value)
    return value


def validate_portfolio(value: Any) -> None:
    _record(value, _PORTFOLIO_KEYS, "live-v2 portfolio")
    if (
        type(value["schema_version"]) is not int or value["schema_version"] != 2
        or type(value["fixture"]) is not bool
        or value["kind"] != _KINDS[value["fixture"]]
    ):
        raise ContractError("incompatible live/walkthrough schema")
    task = value["task"]
    _record(task, {"id", "prompt", "domain", "source_context"}, "task")
    for field in ("id", "prompt", "domain"):
        _text(task[field], f"task {field}", MAX_PROMPT_CHARS if field == "prompt" else 256)
    context = task["source_context"]
    _record(context, {"dataset", "revision", "source_sha256", "source_task_id"}, "source")
    for field in ("dataset", "source_task_id"):
        _text(context[field], f"source {field}", 256)
    _hash(context["revision"], "source revision", 40)
    _hash(context["source_sha256"], "source file identity")
    provenance = value["provenance"]
    _record(provenance, _PROVENANCE_KEYS, "provenance")
    slot_prefix(task["id"], provenance["method"], provenance["repeat"])
    _record(provenance["model"], {"requested", "returned"}, "model")
    for field in ("requested", "returned"):
        _text(provenance["model"][field], f"model {field}", 256)
    for field in ("settings_sha256", "procedure_sha256", "study_sha256"):
        _hash(provenance[field], field)
    method = provenance["method"]
    if method == "C":
        _hash(provenance["parent_sha256"], "parent portfolio identity")
    elif provenance["parent_sha256"] is not None:
        raise ContractError("generated portfolios cannot claim a permutation parent")
    requests = provenance["request_ids"]
    if not isinstance(requests, list) or len(requests) != {"A": 10, "B": 11, "C": 12}[method]:
        raise ContractError("method request-slot count is incompatible")
    for request in requests:
        _text(request, "request slot identity", 256)
    if len(set(requests)) != len(requests):
        raise ContractError("request slot identities must be unique")
    responses = value["responses"]
    if not isinstance(responses, list) or len(responses) != 10:
        raise ContractError("live-v2 requires exactly ten answer slots")
    ids, answer_requests = [], []
    for response in responses:
        _record(response, {"id", "text", "status", "request_id"}, "response")
        for field in ("id", "request_id"):
            _text(response[field], f"response {field}", 256)
        _text(response["text"], "response text", MAX_RESPONSE_CHARS)
        if (
            not isinstance(response["status"], str)
            or response["status"] not in ("ok", "refused", "empty", "truncated")
            or response["request_id"] not in requests
        ):
            raise ContractError("response outcome or request reference is incompatible")
        ids.append(response["id"])
        answer_requests.append(response["request_id"])
    if len(set(ids)) != 10 or len(set(answer_requests)) != 10:
        raise ContractError("response and answer request identities must be unique")
    if method != "C" and sorted(answer_requests, key=requests.index) != answer_requests:
        raise ContractError("generated answer order must preserve request order")
    try:
        expected = "portfolio-" + digest({k: v for k, v in value.items() if k != "portfolio_id"})
    except (TypeError, ValueError) as exc:
        raise ContractError("portfolio must contain finite JSON") from exc
    if value["portfolio_id"] != expected:
        raise ContractError("portfolio content identity is stale")


def permute_portfolio(
    parent: dict, order: list[str], *, request_id: str, settings_sha256: str,
    procedure_sha256: str, model: dict | None = None,
) -> dict:
    """Create C from B without rewriting, removing or replacing any answer field."""
    validate_portfolio(parent)
    if parent["provenance"]["method"] != "B":
        raise ContractError("reranking requires a planner portfolio parent")
    ids = [response["id"] for response in parent["responses"]]
    if (
        not isinstance(order, list) or len(order) != 10
        or any(not isinstance(identity, str) for identity in order) or sorted(order) != sorted(ids)
    ):
        raise ContractError("reranking must return an exact response-ID permutation")
    mapping = {response["id"]: response for response in parent["responses"]}
    child = make_portfolio(
        parent["task"], [mapping[identity] for identity in order], method="C",
        repeat=parent["provenance"]["repeat"],
        model=model if model is not None else parent["provenance"]["model"],
        settings_sha256=settings_sha256, procedure_sha256=procedure_sha256,
        request_ids=parent["provenance"]["request_ids"] + [request_id],
        study_sha256=parent["provenance"]["study_sha256"],
        fixture=parent["fixture"], parent_sha256=digest(parent),
    )
    validate_permutation(parent, child)
    return child


def validate_permutation(parent: dict, child: dict) -> None:
    validate_portfolio(parent)
    validate_portfolio(child)
    if (
        parent["provenance"]["method"] != "B" or child["provenance"]["method"] != "C"
        or child["provenance"]["parent_sha256"] != digest(parent)
        or child["fixture"] != parent["fixture"] or child["task"] != parent["task"]
        or child["provenance"]["repeat"] != parent["provenance"]["repeat"]
        or child["provenance"]["study_sha256"] != parent["provenance"]["study_sha256"]
        or child["provenance"]["settings_sha256"] != parent["provenance"]["settings_sha256"]
        or child["provenance"]["model"] != parent["provenance"]["model"]
        or child["provenance"]["request_ids"][:-1] != parent["provenance"]["request_ids"]
        or {row["id"]: row for row in child["responses"]}
        != {row["id"]: row for row in parent["responses"]}
    ):
        raise ContractError("permutation parent, contents, model/profile or logical requests changed")


def _native_row(portfolio: dict) -> dict:
    return {
        "id": portfolio["task"]["id"], "prompt": portfolio["task"]["prompt"],
        "model": "fixture-no-model" if portfolio["fixture"]
        else portfolio["provenance"]["model"]["returned"],
        "generations": [response["text"] for response in portfolio["responses"]],
    }


def export_native(portfolio: dict, destination: Path) -> None:
    validate_portfolio(portfolio)
    row = _native_row(portfolio)
    identity = {
        "schema_version": 2, "kind": "phase2-native-identities-v2",
        "fixture": portfolio["fixture"], "portfolio_id": portfolio["portfolio_id"],
        "portfolio_sha256": digest(portfolio), "native_row_sha256": digest(row),
        "task": portfolio["task"], "provenance": portfolio["provenance"],
        "responses": [
            {"index": index, "id": response["id"], "status": response["status"],
             "request_id": response["request_id"],
             "text_sha256": hashlib.sha256(response["text"].encode("utf-8")).hexdigest()}
            for index, response in enumerate(portfolio["responses"])
        ],
    }
    raw = json.dumps(row, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"
    write_bytes_once(destination / "generations.jsonl", raw.encode("utf-8"))
    write_once(destination / "identities.json", identity)


def import_native(source: Path) -> dict:
    path = source / "generations.jsonl"
    try:
        if source.is_symlink() or path.is_symlink() or (source / "identities.json").is_symlink():
            raise ContractError("symlink native exchange is unsupported")
        if path.stat().st_size > 2_000_000:
            raise ContractError("native exchange exceeds profile limit")
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) != 1:
            raise ContractError("live-v2 imports exactly one portfolio per exchange")
        row = json.loads(lines[0], parse_constant=_reject_constant)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError("unreadable native generation exchange") from exc
    identity = read_json(source / "identities.json")
    _record(row, {"id", "prompt", "model", "generations"}, "native generation")
    _record(identity, {
        "schema_version", "kind", "fixture", "portfolio_id", "portfolio_sha256",
        "native_row_sha256", "task", "provenance", "responses",
    }, "native identity companion")
    if (
        type(identity["schema_version"]) is not int or identity["schema_version"] != 2
        or identity["kind"] != "phase2-native-identities-v2"
        or type(identity["fixture"]) is not bool
        or identity["native_row_sha256"] != digest(row)
    ):
        raise ContractError("native identity schema or row hash is incompatible")
    texts, bindings = row["generations"], identity["responses"]
    if not isinstance(texts, list) or not isinstance(bindings, list) or len(texts) != 10 or len(bindings) != 10:
        raise ContractError("native exchange needs ten mapped responses")
    responses = []
    for index, (text, binding) in enumerate(zip(texts, bindings, strict=True)):
        _text(text, "native response", MAX_RESPONSE_CHARS)
        _record(binding, {"index", "id", "status", "request_id", "text_sha256"}, "binding")
        if (
            type(binding["index"]) is not int or binding["index"] != index
            or binding["text_sha256"] != hashlib.sha256(text.encode("utf-8")).hexdigest()
        ):
            raise ContractError("native response mapping or order is stale")
        responses.append({key: binding[key] for key in ("id", "status", "request_id")} | {"text": text})
    portfolio = {
        "schema_version": 2, "kind": _KINDS[identity["fixture"]],
        "fixture": identity["fixture"], "portfolio_id": identity["portfolio_id"],
        "task": identity["task"], "responses": responses, "provenance": identity["provenance"],
    }
    validate_portfolio(portfolio)
    if digest(portfolio) != identity["portfolio_sha256"] or row != _native_row(portfolio):
        raise ContractError("native task/model/portfolio identity is incompatible")
    return portfolio
