"""Versioned AM-1 payload safeguards and public-PAYG liability accounting.

Context-wide reservations are operational bounds under the documented provider
contract, not measured prompt sizes or a guarantee against provider misbilling.
Geographic surcharges are retained conservatively where the native body inherits
account settings. Settled amounts are usage-based public-price upper bounds.
"""

from __future__ import annotations

import json
import os
import re
import sys
from fractions import Fraction
from importlib.metadata import version
from pathlib import Path
from typing import Any, TypeGuard

from .artifacts import ContractError, digest

BILLING_PROFILE = "public-payg-envelope-v1"
CONTROL_POLICY: dict[str, Any] = {
    "revision": "phase2-am1-payload-liability-v1",
    "billing_profile": BILLING_PROFILE,
    "payload_utf8_bytes": {"answer": 5952, "plan": 5952, "rank": 61952,
                           "group": 61952, "quality": 5952},
    "maximum_billable_input": {"answer": 1000000, "plan": 1000000, "rank": 1000000,
                               "group": 1050000, "quality": 1000000},
    "reserved_total_output": {"answer": 4096, "plan": 4096, "rank": 4096,
                              "group": 128000, "quality": 16000},
    "maximum_rates_thousandths_micro_usd": {
        "sonnet": {"input": 2500, "output": 10000},
        "group": {"input": 1100, "output": 3960},
        "quality": {"input": 11000, "output": 27500},
    },
    "models": {"answer": "claude-sonnet-5-5", "plan": "claude-sonnet-5-5",
               "rank": "claude-sonnet-5-5", "group": "gpt-5.6-luna", "quality": "claude-opus-5"},
    "source_review": "phase2-am1-r016",
    "cost_basis": "usage-based-public-price-upper-bound-not-invoice",
    "live_permission": "requires-explicit-study-control-billing-bound-grant",
    "limits": "No provider-token estimate; inherited geography reserved at 1.1x. Public PAYG only.",
}
CONTROL_SHA256 = digest(CONTROL_POLICY)
FIRST_BLOCK_MAX_MICRO_USD = 404_086_760
FULL_STUDY_MAX_MICRO_USD = 9_698_082_240


def runtime_guard() -> None:
    if (sys.platform != "linux" or tuple(sys.version_info[:3]) != (3, 12, 15)
            or os.environ.get("BUDDHA2_IMAGE_ID") !=
            "sha256:585a5539c6091592258ec19d0bf8e216b189405f95766b167df0d2e88e251366"
            or version("anthropic") != "1.4.0" or version("openai") != "1.107.0"):
        raise ContractError("AM-1 requires the pinned Linux image, Python and installed SDKs")


def canonical_live_journal(study_sha256: str) -> Path:
    runtime_guard()
    if (os.environ.get("BUDDHA2_OUTPUT_ROOT") != "/results"
            or Path(__file__).resolve().parents[2] != Path("/workspace")):
        raise ContractError("live AM-1 requires the fixed /workspace and /results launch mounts")
    return Path("/results/phase2-am1") / study_sha256 / "first-block/journal"


def validate_policy(value: Any) -> None:
    if value != CONTROL_POLICY or digest(value) != CONTROL_SHA256:
        raise ContractError("unsupported AM-1 control policy")


def _role(role: str) -> None:
    if role not in CONTROL_POLICY["models"]:
        raise ContractError("unknown AM-1 role")


def admission(role: str, request: dict) -> dict:
    _role(role)
    try:
        raw = json.dumps(request, sort_keys=True, ensure_ascii=False,
                         allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ContractError("request is not canonical UTF-8 JSON") from exc
    return {"revision": CONTROL_POLICY["revision"], "control_policy_sha256": CONTROL_SHA256,
            "serialized_utf8_bytes": len(raw),
            "payload_limit_utf8_bytes": CONTROL_POLICY["payload_utf8_bytes"][role],
            "maximum_billable_input": CONTROL_POLICY["maximum_billable_input"][role],
            "request_sha256": digest(request), "provider_token_estimate": None}


def admitted(role: str, request: dict) -> bool:
    value = admission(role, request)
    return value["serialized_utf8_bytes"] <= value["payload_limit_utf8_bytes"]


def reservation(role: str) -> int:
    _role(role)
    family = "group" if role == "group" else "quality" if role == "quality" else "sonnet"
    rates = CONTROL_POLICY["maximum_rates_thousandths_micro_usd"][family]
    amount = (CONTROL_POLICY["maximum_billable_input"][role] * rates["input"]
              + CONTROL_POLICY["reserved_total_output"][role] * rates["output"])
    return (amount + 999) // 1000


def _nonnegative(value: Any) -> TypeGuard[int]:
    return type(value) is int and value >= 0


def _zero(value: Any) -> bool:
    return value is None or type(value) is int and value == 0 or isinstance(value, dict) and all(
        _zero(part) for part in value.values())


def normalize_group_usage(usage: Any, service_tier: Any) -> dict:
    """Keep exact Chat Completions read/write categories; omissions are unknown."""
    unknown = {"unsupported_usage": True}
    if not isinstance(usage, dict) or set(usage).difference({
        "prompt_tokens", "completion_tokens", "total_tokens", "prompt_tokens_details",
        "completion_tokens_details",
    }):
        return unknown
    prompt, output, total = (usage.get(key) for key in (
        "prompt_tokens", "completion_tokens", "total_tokens"))
    details = usage.get("prompt_tokens_details")
    output_details = usage.get("completion_tokens_details")
    if not (_nonnegative(prompt) and _nonnegative(output) and _nonnegative(total)):
        return unknown
    if (total != prompt + output or not isinstance(details, dict)
            or set(details).difference({"cached_tokens", "cache_write_tokens", "audio_tokens", "image_tokens", "text_tokens"})
            or not {"cached_tokens", "cache_write_tokens"}.issubset(details)
            or not _zero(details.get("audio_tokens")) or not _zero(details.get("image_tokens"))
            or "text_tokens" in details and (not _nonnegative(details["text_tokens"])
                                             or details["text_tokens"] > prompt)):
        return unknown
    read, write = details["cached_tokens"], details["cache_write_tokens"]
    if not _nonnegative(read) or not _nonnegative(write) or read + write > prompt:
        return unknown
    if output_details is None:
        output_details = {}
    if (not isinstance(output_details, dict) or set(output_details).difference({
        "reasoning_tokens", "text_tokens", "image_tokens", "audio_tokens",
        "accepted_prediction_tokens", "rejected_prediction_tokens",
    }) or any(not _zero(value) for key, value in output_details.items()
              if key not in {"reasoning_tokens", "text_tokens"})
            or not _nonnegative(output_details.get("reasoning_tokens", 0))
            or output_details.get("reasoning_tokens", 0) > output
            or "text_tokens" in output_details and (not _nonnegative(output_details["text_tokens"])
                                                    or output_details["text_tokens"] > output)):
        return unknown
    return {"input_tokens": prompt - read - write, "output_tokens": output,
            "cache_read_input_tokens": read, "cache_creation_input_tokens": write,
            "input_tokens_details": {"cached_tokens": read, "cache_write_tokens": write},
            "output_tokens_details": {"reasoning_tokens": output_details.get("reasoning_tokens", 0)},
            "service_tier": service_tier}


def account(role: str, response: Any) -> tuple[int | None, bool]:
    """Settle understood usage at documented rates with conservative geography."""
    _role(role)
    model = CONTROL_POLICY["models"][role]
    if (not isinstance(response, dict) or not isinstance(response.get("model"), str)
            or re.fullmatch(re.escape(model) + r"(?:-\d{8})?", response["model"]) is None):
        return None, False
    usage = response.get("usage")
    allowed = {"input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens",
               "cache_creation", "service_tier", "inference_geo", "speed", "output_tokens_details",
               "input_tokens_details", "server_tool_use"}
    if not isinstance(usage, dict) or set(usage).difference(allowed):
        return None, False
    keys = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    if (not set(keys).issubset(usage)
            or any(not _nonnegative(usage.get(key, 0)) for key in keys)):
        return None, False
    base, output, write, read = (usage.get(key, 0) for key in keys)
    total_input = base + write + read
    if (total_input > CONTROL_POLICY["maximum_billable_input"][role]
            or output > CONTROL_POLICY["reserved_total_output"][role]
            or not _zero(usage.get("server_tool_use"))
            or usage.get("speed") not in (None, "standard")):
        return None, False
    output_details = usage.get("output_tokens_details")
    thinking = "reasoning_tokens" if role == "group" else "thinking_tokens"
    if output_details is not None and (not isinstance(output_details, dict)
            or set(output_details).difference({thinking})
            or any(not _nonnegative(value) or value > output for value in output_details.values())):
        return None, False
    input_details = usage.get("input_tokens_details")
    if role == "group":
        if (usage.get("service_tier") not in ("default", "flex", "priority")
                or usage.get("inference_geo") is not None or usage.get("cache_creation") is not None
                or input_details != {"cached_tokens": read, "cache_write_tokens": write}):
            return None, False
        # Thousandths of micro-USD/token; category prices are total prices.
        input_cost = base * 200 + write * 250 + read * 20
        output_cost = output * 1200
        if total_input > 272000:
            input_cost *= 2
            output_cost = output_cost * 3 // 2
        tier = {"default": Fraction(1), "flex": Fraction(1, 2), "priority": Fraction(2)}[usage["service_tier"]]
        amount = Fraction(input_cost + output_cost) * tier * Fraction(11, 10)
    else:
        if (usage.get("service_tier") != "standard"
                or usage.get("inference_geo") not in ((None, "global", "us") if role == "quality" else (None, "global"))
                or input_details is not None and input_details != {"cached_tokens": read}):
            return None, False
        cache = usage.get("cache_creation")
        if cache is None:
            if write:
                return None, False
            five = hour = 0
        else:
            if (not isinstance(cache, dict) or set(cache).difference({
                "ephemeral_5m_input_tokens", "ephemeral_1h_input_tokens",
            }) or any(not _nonnegative(value) for value in cache.values())):
                return None, False
            five, hour = cache.get("ephemeral_5m_input_tokens", 0), cache.get("ephemeral_1h_input_tokens", 0)
            if five + hour != write or role != "quality" and hour:
                return None, False
        amount = (Fraction(base * 5500 + five * 6875 + hour * 11000 + read * 550 + output * 27500)
                  if role == "quality" else Fraction(base * 2000 + five * 2500 + read * 100 + output * 10000))
    cost = (amount.numerator + amount.denominator * 1000 - 1) // (amount.denominator * 1000)
    return (cost, True) if cost <= reservation(role) else (None, False)
