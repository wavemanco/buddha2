"""One sequential critic, immutable attempts, and conservative replay accounting."""

from __future__ import annotations

import hashlib
import json
import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Protocol

from .artifacts import ContractError, digest, read_json, tree_hashes, write_once
from .pairs import make_judgment, validate_judgment, validate_pair, validate_presentation

PROFILE: dict[str, Any] = {
    "model": "claude-sonnet-5-5", "max_tokens": 2048,
    "thinking": {"type": "adaptive"}, "output_config": {"effort": "medium"},
    "service_tier": "standard_only", "inference_geo": "global", "input_token_limit": 8000,
    "input_micro_usd_per_token": 2, "output_micro_usd_per_token": 10,
}
RESERVATION = 36_480
ENDPOINT = "https://api.anthropic.com"


class TransientRejected(Exception):
    """An explicit provider rejection with no accepted generation or charge."""

    def __init__(self, status_code: int):
        if status_code not in (429, 529):
            raise ContractError("only declared rejected transient requests may retry")
        self.status_code = status_code


class AmbiguousDelivery(Exception):
    """Delivery, returned usage or billing cannot be established."""

    def __init__(self, status_code: int | None = None, request_id: str | None = None):
        self.status_code = status_code if type(status_code) is int and 100 <= status_code <= 599 else None
        self.request_id = request_id if isinstance(request_id, str) and re.fullmatch(
            r"req_[A-Za-z0-9_-]{1,120}", request_id
        ) else None


class Transport(Protocol):
    fixture: bool

    def count(self, request: dict) -> int: ...

    def create(self, request: dict) -> dict: ...


@contextmanager
def writer_lock(run: Path) -> Iterator[None]:
    """OS-owned lock releases on death; unfinished intents remain liabilities."""
    import fcntl

    run.mkdir(parents=True, exist_ok=True)
    if any(path.is_symlink() for path in (run, *run.parents, *run.rglob("*"))):
        raise ContractError("run paths may not contain symlinks")
    with (run / ".writer.lock").open("a+b") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ContractError("another concurrent writer owns this run") from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def _plan(plan: Any) -> tuple[dict, dict]:
    if not isinstance(plan, dict) or set(plan) != {
        "pairs", "presentations", "stages", "profile", "image_id"
    } or plan["profile"] != PROFILE or not re.fullmatch(
        r"sha256:[0-9a-f]{64}", str(plan["image_id"])
    ):
        raise ContractError("incompatible phase 1 plan/profile/image identity")
    pairs, shown = {}, {}
    if not isinstance(plan["pairs"], list) or not isinstance(plan["presentations"], list):
        raise ContractError("plan requires pair and presentation worklists")
    for pair in plan["pairs"]:
        validate_pair(pair)
        if pair["pair_id"] in pairs:
            raise ContractError("duplicate pair")
        pairs[pair["pair_id"]] = pair
    for presentation in plan["presentations"]:
        if not isinstance(presentation, dict) or presentation.get("pair_id") not in pairs:
            raise ContractError("missing pair for presentation")
        validate_presentation(pairs[presentation["pair_id"]], presentation)
        if presentation["presentation_id"] in shown:
            raise ContractError("duplicate presentation")
        shown[presentation["presentation_id"]] = presentation
    stages = plan["stages"]
    if not pairs or len(shown) > 48 or not shown or not isinstance(stages, dict) or set(stages) != {
        "calibration", "audit"
    } or any(not isinstance(ids, list) for ids in stages.values()):
        raise ContractError("invalid bounded stage worklists")
    allocated = stages["calibration"] + stages["audit"]
    if len(allocated) != len(set(allocated)) or set(allocated) != set(shown):
        raise ContractError("stages must partition every scheduled presentation")
    if len({pair["fixture"] for pair in pairs.values()}) != 1:
        raise ContractError("fixture and live pairs cannot share an execution run")
    return pairs, shown


def _request(pair: dict, presentation: dict, rubric: str) -> dict:
    responses = {row["id"]: row["text"] for row in pair["responses"]}
    content = {"prompt": pair["prompt"], "A": responses[presentation["order"][0]],
               "B": responses[presentation["order"][1]]}
    return {key: value for key, value in PROFILE.items() if key in {
        "model", "max_tokens", "thinking", "output_config", "service_tier", "inference_geo"
    }} | {"system": rubric, "messages": [{"role": "user", "content": json.dumps(
        content, ensure_ascii=False, allow_nan=False
    )}]}


def request_preview(pair: dict, presentation: dict, rubric: str) -> dict:
    """Expose the exact credential-free request without constructing a transport."""
    validate_presentation(pair, presentation)
    if not isinstance(rubric, str) or not rubric.strip() or len(rubric) > 20000:
        raise ContractError("rubric is missing or invalid")
    return _request(pair, presentation, rubric)


def _stage(run: Path, stage: str) -> dict:
    value = read_json(run / "stages" / f"{stage}.json")
    if not isinstance(value, dict) or set(value) != {"stage", "rubric", "rubric_sha256"} or (
        value["stage"] != stage or not isinstance(value["rubric"], str)
        or value["rubric_sha256"] != hashlib.sha256(value["rubric"].encode()).hexdigest()
    ):
        raise ContractError("stage rubric identity is invalid")
    return value


def _zero_activity(value: Any) -> bool:
    return value is None or type(value) is int and value == 0 or (
        isinstance(value, dict) and all(_zero_activity(item) for item in value.values())
    )


def _judgment(pair: dict, presentation: dict, rubric: dict, response: dict) -> tuple[dict, int, bool]:
    usage = response.get("usage")
    tokens = None
    if isinstance(usage, dict) and all(type(usage.get(key)) is int and usage[key] >= 0
                                       for key in ("input_tokens", "output_tokens")):
        tokens = {key: usage[key] for key in ("input_tokens", "output_tokens")}
    returned = response.get("model")
    billing_known = tokens is not None and isinstance(usage, dict) and returned == PROFILE["model"]
    if billing_known and isinstance(usage, dict):
        billing_known = not any(not _zero_activity(usage.get(key)) for key in (
            "cache_creation_input_tokens", "cache_read_input_tokens", "cache_creation",
            "server_tool_use",
        )) and usage.get("service_tier") == "standard" and usage.get("inference_geo") in (None, "global")
        billing_known = billing_known and usage.get("speed") in (None, "standard") and not set(usage).difference({
            "input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens",
            "cache_creation", "server_tool_use", "service_tier", "inference_geo", "speed", "output_tokens_details",
        })
    cost = tokens["input_tokens"] * 2 + tokens["output_tokens"] * 10 if billing_known and tokens else None
    unexpected = not billing_known or tokens is None or tokens["input_tokens"] > 8000 or tokens["output_tokens"] > 2048
    stop = response.get("stop_reason")
    status, choice, reason = "malformed", None, "Provider output did not satisfy the JSON contract."
    if stop == "refusal" or response.get("stop_details_type") == "refusal":
        status, reason = "refused", "Provider refused the comparison."
    elif stop == "max_tokens":
        status, reason = "truncated", "Provider exhausted the reserved output budget."
    elif stop == "end_turn":
        try:
            value = json.loads(response.get("text", ""))
            if not isinstance(value, dict) or set(value) != {"choice", "reason"}:
                raise ValueError
            if value["choice"] not in ("A", "B", "tie", "abstain") or not isinstance(
                value["reason"], str
            ) or not 0 < len(value["reason"].strip()) <= 4000:
                raise ValueError
            status, choice, reason = "ok", value["choice"], value["reason"]
        except (ValueError, TypeError):
            pass
    else:
        unexpected = True
    if unexpected:
        status, choice, reason = "unknown", None, "Returned model, controls or billing profile require review."
    judgment = make_judgment(pair, presentation, status=status, choice=choice, reason=reason,
                            model={"requested": PROFILE["model"], "returned": returned},
                            rubric_sha256=rubric["rubric_sha256"], settings_sha256=digest(PROFILE),
                            usage=tokens, cost_usd=None if cost is None else cost / 1_000_000)
    return judgment, cost or 0, unexpected


def replay_run(run: Path) -> dict:
    """Validate all saved evidence; never construct a client or consult credentials."""
    if any(path.is_symlink() for path in (run, *run.parents, *run.rglob("*"))):
        raise ContractError("run paths may not contain symlinks")
    manifest = read_json(run / "manifest.json")
    if not isinstance(manifest, dict) or manifest.get("run_id") != digest(manifest.get("inputs")):
        raise ContractError("invalid run manifest identity")
    plan = manifest["inputs"]["plan"]
    pairs, shown = _plan(plan)
    spent, reserved, retries, judgments, unknown, blocked_usage = 0, 0, 0, {}, False, False
    attempts = sorted((run / "attempts").glob("*.intent.json"))
    counts: dict[str, int] = {}
    for index, path in enumerate(attempts, start=1):
        if unknown or blocked_usage:
            raise ContractError("generation continued after an unresolved stop condition")
        intent = read_json(path)
        if path.name != f"{index:04}.intent.json" or not isinstance(intent, dict):
            raise ContractError("attempt sequence is incomplete")
        identity, stage = intent.get("presentation_id"), intent.get("stage")
        if not isinstance(identity, str) or not isinstance(stage, str) or (
            identity not in shown or stage not in plan["stages"] or identity not in plan["stages"][stage]
        ):
            raise ContractError("attempt worklist identity is invalid")
        presentation = shown[identity]
        pair = pairs[presentation["pair_id"]]
        rubric = _stage(run, stage)
        request = _request(pair, presentation, rubric["rubric"])
        expected = {"run_id": manifest["run_id"], "stage": stage, "presentation_id": identity,
                    "request_sha256": digest(request), "reservation_micro_usd": RESERVATION,
                    "attempt": index, "request": request}
        if intent != expected or identity in judgments:
            raise ContractError("attempt request identity is stale or duplicated")
        count_intent = {"request_sha256": digest(request), "attempt": index}
        count_result = read_json(run / "counts" / f"{index:04}.result.json")
        if read_json(run / "counts" / f"{index:04}.intent.json") != count_intent or (
            not isinstance(count_result, dict)
            or set(count_result) != {"status", "input_tokens", "request_sha256", "attempt"}
            or count_result != {"status": "ok", "input_tokens": count_result.get("input_tokens"), **count_intent}
            or type(count_result["input_tokens"]) is not int
            or not 0 <= count_result["input_tokens"] <= 8000
        ):
            raise ContractError("token-count evidence is missing or incompatible")
        counts[identity] = counts.get(identity, 0) + 1
        retries += counts[identity] - 1
        if index > 52 or counts[identity] > 2 or retries > 4:
            raise ContractError("attempt/retry limits were exceeded")
        result_path = path.with_name(f"{index:04}.result.json")
        if not result_path.exists():
            reserved += RESERVATION
            unknown = True
            continue
        result = read_json(result_path)
        if not isinstance(result, dict) or result.get("intent_sha256") != digest(intent) or (
            result.get("request_sha256") != intent["request_sha256"]
        ):
            raise ContractError("attempt result identity is stale")
        kind = result.get("kind")
        if kind == "rejected-transient":
            if result.get("status_code") not in (429, 529):
                raise ContractError("invalid retry evidence")
            if counts[identity] == 2 or retries >= 4:
                judgments[identity] = make_judgment(
                    pair, presentation, status="transport_error", choice=None,
                    reason="Declared transient retries exhausted.",
                    model={"requested": PROFILE["model"], "returned": None},
                    rubric_sha256=rubric["rubric_sha256"], settings_sha256=digest(PROFILE),
                    usage={"input_tokens": 0, "output_tokens": 0}, cost_usd=0,
                )
        elif kind == "unknown":
            reserved += RESERVATION
            unknown = True
        elif kind == "response":
            expected_judgment, cost, unexpected = _judgment(pair, presentation, rubric, result["response"])
            validate_judgment(pair, presentation, result["judgment"])
            if result["judgment"] != expected_judgment or result.get("spent_micro_usd") != cost or (
                result.get("unexpected_usage") is not unexpected
            ):
                raise ContractError("judgment or accounting identity is stale")
            judgments[identity] = expected_judgment
            spent += cost
            blocked_usage = blocked_usage or unexpected
            if unexpected:
                reserved += RESERVATION
        else:
            raise ContractError("unrecognized attempt outcome")
    result_files = list((run / "attempts").glob("*.result.json"))
    if any(not path.with_name(path.name.replace(".result.", ".intent.")).exists() for path in result_files):
        raise ContractError("attempt result is missing its intent")
    count_requests = list((run / "counts").glob("*.intent.json"))
    blocked_count = len(count_requests) > len(attempts)
    return {"status": "blocked-unknown" if unknown else "blocked-usage" if blocked_usage
            else "blocked-count" if blocked_count else "ready",
            "run_id": manifest["run_id"], "fixture": next(iter(pairs.values()))["fixture"],
            "attempts": len(attempts), "retries": retries, "spent_micro_usd": spent,
            "reserved_micro_usd": reserved, "finalized_presentations": len(judgments),
            "judgments": [judgments[key] for key in shown if key in judgments],
            "token_count_requests": len(count_requests), "count_incomplete": blocked_count,
            "provider_calls": 0 if next(iter(pairs.values()))["fixture"] else len(attempts)}


def run_stage(run: Path, plan: dict, *, stage: str, rubric: str, transport: Transport,
              authorization_micro_usd: int, max_presentations: int = 2) -> dict:
    pairs, shown = _plan(plan)
    if stage not in plan["stages"] or not isinstance(rubric, str) or not rubric.strip() or len(rubric) > 20000:
        raise ContractError("stage/rubric is missing or invalid")
    if type(max_presentations) is not int or not 1 <= max_presentations <= 48:
        raise ContractError("invalid presentation checkpoint")
    if type(authorization_micro_usd) is not int or not 0 < authorization_micro_usd <= 5_000_000:
        raise ContractError("explicit authorization must be within the phase spending ceiling")
    if type(transport.fixture) is not bool or transport.fixture != next(iter(pairs.values()))["fixture"]:
        raise ContractError("fixture/live transport and pair identities disagree")
    inputs = {"plan": plan, "authorization_micro_usd": authorization_micro_usd,
              "package_files": tree_hashes(Path(__file__).parent), "fixture": transport.fixture}
    manifest = {"schema_version": 1, "run_id": digest(inputs), "inputs": inputs}
    with writer_lock(run):
        write_once(run / "manifest.json", manifest)
        write_once(run / "stages" / f"{stage}.json", {"stage": stage, "rubric": rubric,
                   "rubric_sha256": hashlib.sha256(rubric.encode()).hexdigest()})
        pending = iter(plan["stages"][stage][:max_presentations])
        identity = next(pending, None)
        while identity is not None:
            state = replay_run(run)
            if state["status"].startswith("blocked"):
                return state
            if identity in {row["presentation_id"] for row in state["judgments"]}:
                identity = next(pending, None)
                continue
            if state["attempts"] >= 52 or state["spent_micro_usd"] + RESERVATION > authorization_micro_usd:
                raise ContractError("attempt or budget reservation ceiling reached")
            presentation = shown[identity]
            request = _request(pairs[presentation["pair_id"]], presentation, rubric)
            attempt = state["attempts"] + 1
            count_path = run / "counts" / f"{attempt:04}"
            count_intent = {"request_sha256": digest(request), "attempt": attempt}
            write_once(count_path.with_suffix(".intent.json"), count_intent)
            try:
                count = transport.count(request)
            except Exception:
                write_once(count_path.with_suffix(".result.json"), {"status": "error", **count_intent})
                raise ContractError("token-count request failed; generation was not dispatched") from None
            write_once(count_path.with_suffix(".result.json"), {"status": "ok", "input_tokens": count, **count_intent})
            if type(count) is not int or not 0 <= count <= 8000:
                raise ContractError("complete request exceeds the input token limit")
            intent = {"run_id": manifest["run_id"], "stage": stage, "presentation_id": identity,
                      "request_sha256": digest(request), "reservation_micro_usd": RESERVATION,
                      "attempt": attempt, "request": request}
            intent_path = run / "attempts" / f"{attempt:04}.intent.json"
            write_once(intent_path, intent)
            result: dict[str, Any] = {"intent_sha256": digest(intent), "request_sha256": digest(request)}
            try:
                response = transport.create(request)
                judgment, cost, unexpected = _judgment(pairs[presentation["pair_id"]], presentation,
                                                       _stage(run, stage), response)
                result.update(kind="response", response=response, judgment=judgment,
                              spent_micro_usd=cost, unexpected_usage=unexpected)
            except TransientRejected as exc:
                if transport.fixture:
                    result.update(kind="rejected-transient", status_code=exc.status_code)
                else:
                    result.update(kind="unknown", status_code=exc.status_code)
            except AmbiguousDelivery as exc:
                result.update(kind="unknown", status_code=exc.status_code, request_id=exc.request_id)
            except Exception:
                result.update(kind="unknown")
            write_once(intent_path.with_name(f"{attempt:04}.result.json"), result)
            if result["kind"] == "rejected-transient":
                # Repeat the same presentation only for this explicitly unaccepted request.
                continue
            identity = next(pending, None)
        return replay_run(run)


class DirectAnthropicTransport:
    """Opt-in first-party SDK transport; constructing it performs no requests."""

    fixture = False

    def __init__(self, *, api_key: str):
        if not isinstance(api_key, str) or not api_key.strip():
            raise ContractError("an explicitly supplied provider key is required")
        ambient = {key for key, value in os.environ.items() if value and (
            key.startswith("ANTHROPIC_") and key != "ANTHROPIC_API_KEY"
            or key.upper() in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR"}
        )}
        if ambient:
            raise ContractError("ambient provider/transport configuration is not permitted")
        import anthropic

        self._client = anthropic.Anthropic(
            api_key=api_key, base_url=ENDPOINT, max_retries=0, timeout=90.0,
            http_client=anthropic.DefaultHttpxClient(trust_env=False, follow_redirects=False, timeout=90.0),
        )

    def count(self, request: dict) -> int:
        arguments = {key: value for key, value in request.items() if key not in {
            "max_tokens", "service_tier", "inference_geo"
        }}
        return self._client.messages.count_tokens(**arguments).input_tokens

    def create(self, request: dict) -> dict:
        import anthropic

        try:
            response = self._client.messages.create(**request)
        except anthropic.APIStatusError as exc:
            # Public error semantics do not establish a zero-charge guarantee.
            raise AmbiguousDelivery(exc.status_code, getattr(exc, "request_id", None)) from None
        except Exception:
            raise AmbiguousDelivery() from None
        return {"model": response.model, "stop_reason": response.stop_reason,
                "stop_details_type": getattr(getattr(response, "stop_details", None), "type", None),
                "message_id": response.id, "request_id": getattr(response, "_request_id", None),
                "text": "".join(block.text for block in response.content if block.type == "text"),
                "usage": response.usage.model_dump(mode="json", exclude_none=True)}
