"""Thin, accounted v1.1 boundary around unchanged pinned NoveltyBench functions.

This module never constructs a provider client. Its injected dispatcher owns all
admission, authorization, reservations, transport and immutable result storage.
Native SDK retry/fallback/lenient-repair entry points are deliberately not called.
"""

from __future__ import annotations

import importlib
import json
import math
import re
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from .artifacts import ContractError, digest, file_hash
from .phase2_contracts import import_native, slot_prefix, validate_portfolio

UPSTREAM_COMMIT = "64a23be6b18ec1dacc298830aab276061b6e143c"
SOURCE_HASHES = {
    "__init__": "91447944015cec709e8aa7655f7e9d64e1e4508e7023a57fe3746911c0fc6fed",
    "partition": "263970891ff3ee1cc8df369a33beefe5cb5de618b5dd146a5234536d97954aca",
    "score": "418985a40e9e159cfeffe9a43ab2c727010d7a7a29407f4e14cab3c81b77cbae",
    "judge": "4decf04790b90a03368eb792dfe29045435914a73ab83a52185d9dd0d1613902",
    "common": "ba60bf0f2a409c3774d75880f305325a28ed34320610667542a4596c41f424af",
    "evaluation_io": "8a34e01308677469d984dd59e36412c2994baf2554fd3a5f026be9ef98a3a5c7",
    "summarize": "0a8bd1eb7f317584f579eaa827e580f9cefe4177a1abdc35b2cb06ef96eeea9e",
}
GROUP_CONFIG = {
    "stage": "partition", "version": "1.1", "alg": "llm",
    "judge_model": "gpt-5.6-luna", "seed": None,
}
SCORE_CONFIG = {
    "stage": "score", "version": "1.1", "scorer": "llm",
    "judge_model": "claude-opus-5", "effort": "high", "patience": 0.8,
}
_IMPORT_LOCK = threading.RLock()


def _native_modules(upstream: Path) -> dict[str, Any]:
    """Avoid collisions with the application's own top-level ``src`` namespace."""
    modules = {}
    with _IMPORT_LOCK:
        original_path = sys.path[:]
        previous = {key: value for key, value in sys.modules.items()
                    if key == "src" or key.startswith("src.")}
        for key in previous:
            del sys.modules[key]
        sys.path.insert(0, str(upstream))
        try:
            for name in SOURCE_HASHES:
                module = importlib.import_module("src" if name == "__init__" else f"src.{name}")
                if not isinstance(module.__file__, str) or Path(module.__file__).resolve(strict=True) != upstream / "src" / f"{name}.py":
                    raise ContractError("native import resolved outside the pinned source")
                modules[name] = module
        finally:
            for key in list(sys.modules):
                if key == "src" or key.startswith("src."):
                    del sys.modules[key]
            sys.modules.update(previous)
            sys.path[:] = original_path
    return modules


def _json_values(value: Any) -> Any:
    """Normalize native NumPy scalars and undefined empty-summary means for JSON."""
    if isinstance(value, dict):
        return {key: _json_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_values(item) for item in value]
    if isinstance(value, float):
        return float(value) if math.isfinite(value) else None
    if hasattr(value, "item"):
        return _json_values(value.item())
    return value


class NativeAssessment:
    """Construct/fold native requests, with all execution delegated to one boundary."""

    def __init__(self, upstream: Path):
        upstream = Path(upstream)
        if upstream.is_symlink():
            raise ContractError("native source root must not be a symlink")
        self.upstream = upstream.resolve(strict=True)
        sources = {}
        for name, expected in SOURCE_HASHES.items():
            source = self.upstream / "src" / f"{name}.py"
            if source.is_symlink() or source.resolve(strict=True).parent != self.upstream / "src":
                raise ContractError("native source escapes the pinned directory")
            if file_hash(source) != expected:
                raise ContractError(f"pinned native source differs: {name}")
            sources[name] = {"path": str(source), "sha256": expected}
        self.modules = _native_modules(self.upstream)
        self.identity: dict[str, Any] = {
            "id": "noveltybench-native-accounted-v2", "revision": 1,
            "version": "1.1", "patience": 0.8, "upstream_commit": UPSTREAM_COMMIT,
            "sources": sources,
            "native_calls": [
                "src.partition.partition_calls", "src.partition.partition_fold",
                "src.partition.load_instances",
                "src.judge.strict_schema", "src.judge.anthropic_params",
                "src.judge.parse_message", "src.score.score_calls", "src.score.score_fold",
                "src.score.score_refused", "src.evaluation_io.evaluation_key",
                "src.evaluation_io.stamp", "src.summarize.summarize",
            ],
            "execution_departures": {
                "transport": "injected accounted dispatcher; no native clients",
                "sdk_retries": 0, "stage_retries": 0, "fallback": None,
                "lenient_partition_repair": False, "concurrency": 1,
                "strict_input_types": True,
                "empty_summary_means": "native nonfinite means serialized as null",
                "group_effort_and_output_cap": "omitted exactly as native; provider defaults",
            },
        }

    @staticmethod
    def _instance(portfolio: dict) -> dict:
        validate_portfolio(portfolio)
        return {
            "id": portfolio["task"]["id"], "prompt": portfolio["task"]["prompt"],
            "model": "fixture-no-model" if portfolio["fixture"] else portfolio["provenance"]["model"]["returned"],
            "generations": [row["text"] for row in portfolio["responses"]],
        }

    @staticmethod
    def _prefix(portfolio: dict) -> str:
        return slot_prefix(portfolio["task"]["id"], portfolio["provenance"]["method"], portfolio["provenance"]["repeat"])

    def group_request(self, portfolio: dict) -> dict:
        instance = self._instance(portfolio)
        call, = self.modules["partition"].partition_calls(instance, GROUP_CONFIG)
        return {
            "model": GROUP_CONFIG["judge_model"],
            "messages": [{"role": "system", "content": call.system},
                         {"role": "user", "content": call.user}],
            "response_format": {
                "type": "json_schema", "json_schema": {
                    "name": call.schema.__name__, "strict": True,
                    "schema": self.modules["judge"].strict_schema(call.schema),
                },
            },
        }

    def load_export(self, source: Path) -> dict:
        """Use the unchanged native generation loader and verify its identity mapping."""
        portfolio = import_native(source)
        loaded = self.modules["partition"].load_instances(str(source))
        if loaded != [self._instance(portfolio)]:
            raise ContractError("native loader changed the identity-verified exported row")
        return portfolio

    def quality_requests(self, portfolio: dict, partition: list[int]) -> list[dict]:
        instance = self._instance(portfolio)
        self._validate_partition(partition)
        instance["partition"] = partition
        return [self.modules["judge"].anthropic_params("claude-opus-5", call, "high")
                for call in self.modules["score"].score_calls(instance, SCORE_CONFIG)]

    def _validate_partition(self, partition: list[int]) -> None:
        if (not isinstance(partition, list) or len(partition) != 10
                or any(type(value) is not int or not 0 <= value < 10 for value in partition)
                or self.modules["partition"].canonical(partition) != partition):
            raise ContractError("partition must be ten canonical integer group labels")

    @staticmethod
    def _response(result: dict, slot_id: str, role: str, request: dict, portfolio: dict) -> dict:
        if (not isinstance(result, dict) or result.get("slot_id") != slot_id
                or result.get("role") != role or result.get("request_sha256") != digest(request)
                or not isinstance(result.get("dispatch_id"), str)
                or result.get("fixture") is not portfolio["fixture"]
                or result.get("study_sha256") != portfolio["provenance"]["study_sha256"]):
            raise ContractError("native result does not match its accounted request identity")
        if result.get("status") != "response":
            raise ContractError("native dispatch remains unresolved; stop without further calls")
        response = result.get("response")
        if (not isinstance(response, dict) or not isinstance(response.get("text"), str)
                or not isinstance(response.get("usage"), dict)):
            raise ContractError("native result lacks canonical response/usage evidence")
        actual = response.get("model")
        if not isinstance(actual, str) or re.fullmatch(re.escape(request["model"]) + r"(?:-\d{8})?", actual) is None:
            raise ContractError("native result returned a substituted model identity")
        return response

    @staticmethod
    def _strict_object(text: str, schema: Any) -> Any:
        try:
            value = json.loads(text, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise ContractError("judge output is not one JSON object") from exc
        if not isinstance(value, dict) or set(value) != set(schema.model_json_schema()["properties"]):
            raise ContractError("judge output has missing or extra fields")
        return schema.model_validate(value, strict=True)

    def fold_group(self, portfolio: dict, result: dict) -> dict:
        request = self.group_request(portfolio)
        response = self._response(result, self._prefix(portfolio) + ".group", "group", request, portfolio)
        if response.get("refusal") or response.get("stop_reason") in ("refusal", "content_filter"):
            raise self.modules["judge"].JudgeRefusal("group judge declined")
        if response.get("stop_reason") != "stop":
            raise ContractError("group judge did not finish normally")
        output = self._strict_object(response["text"], self.modules["partition"].Partition)
        if any(not group for group in output.groups):
            raise ContractError("partition groups must be nonempty")
        fields = self.modules["partition"].partition_fold(self._instance(portfolio), [output], GROUP_CONFIG)
        self._validate_partition(fields["partition"])
        return fields

    def finalize(self, portfolio: dict, group_result: dict, quality_results: list[dict]) -> dict:
        """Reassess saved accounted results without invoking generation or transport."""
        instance = self._instance(portfolio)
        prefix = self._prefix(portfolio)
        group_request = self.group_request(portfolio)
        self._response(group_result, prefix + ".group", "group", group_request, portfolio)
        partition_fields = None
        status = "scored"
        failure = None
        try:
            partition_fields = self.fold_group(portfolio, group_result)
        except self.modules["judge"].JudgeRefusal:
            status, failure = "group_refused", "judge_refusal"
        except ValueError:
            status, failure = "invalid_group", "strict_partition_validation_failed"
        if partition_fields is None:
            if quality_results:
                raise ContractError("quality evidence cannot follow an invalid grouping result")
            fields = {"generation_scores": [None] * 10, "partition_scores": [],
                      "utility": None, "distinct": None, "unscored": failure}
        else:
            instance.update(partition_fields)
            calls = self.modules["score"].score_calls(instance, SCORE_CONFIG)
            head_indices = self.modules["score"].heads(instance["partition"])
            requests = self.quality_requests(portfolio, instance["partition"])
            if len(quality_results) != len(calls):
                raise ContractError("every native head requires a classified quality result")
            outputs = []
            for index, call, request, result in zip(head_indices, calls, requests, quality_results, strict=True):
                response = self._response(result, f"{prefix}.quality.{index:02d}", "quality", request, portfolio)
                message = SimpleNamespace(stop_reason=response.get("stop_reason"), content=[SimpleNamespace(type="text", text=response["text"])])
                try:
                    self.modules["judge"].parse_message(message, call.schema)
                    outputs.append(self._strict_object(response["text"], call.schema))
                except self.modules["judge"].JudgeRefusal:
                    status, failure = "quality_refused", "judge_refusal"
                except ValueError:
                    if status != "quality_refused":
                        status, failure = "invalid_quality", "strict_quality_validation_failed"
            if status == "scored":
                try:
                    fields = self.modules["score"].score_fold(instance, outputs, SCORE_CONFIG)
                except ValueError:
                    status, failure = "invalid_quality", "strict_quality_validation_failed"
            if status == "quality_refused":
                fields = self.modules["score"].score_refused(instance)
            elif status == "invalid_quality":
                fields = {"generation_scores": [None] * 10, "partition_scores": [],
                          "utility": None, "distinct": partition_fields["distinct"], "unscored": failure}
        import pandas as pd

        native_summary = self.modules["summarize"].summarize(pd.DataFrame([{**instance, **fields}]), "1.1")
        partition_key = self.modules["evaluation_io"].evaluation_key(self._instance(portfolio), GROUP_CONFIG)
        score_key = self.modules["evaluation_io"].evaluation_key(instance, SCORE_CONFIG)
        native_row = self.modules["evaluation_io"].stamp(instance, fields, "score_key", score_key, SCORE_CONFIG)
        native_row = self.modules["evaluation_io"].stamp(native_row, partition_fields or {}, "partition_key", partition_key, GROUP_CONFIG)
        assessment = {
            "schema_version": 2,
            "kind": "phase2-assessment-walkthrough-v2" if portfolio["fixture"] else "phase2-assessment-live-v2",
            "fixture": portfolio["fixture"], "evaluator": self.identity,
            "portfolio_sha256": digest(portfolio), "task_id": portfolio["task"]["id"],
            "assessment_identity_sha256": digest({"portfolio_sha256": digest(portfolio), "evaluator": self.identity,
                                                   "group_config": GROUP_CONFIG, "score_config": SCORE_CONFIG}),
            "status": status, "failure": failure,
            "metrics": {"distinct": fields["distinct"], "utility": fields["utility"]},
            "native": {"generation_row": self._instance(portfolio), "partition_fields": partition_fields,
                       "fields": fields, "summary": native_summary, "score_row": native_row},
            "requests": [group_result, *quality_results],
        }
        return _json_values(assessment)

    def assess(self, portfolio: dict, dispatch: Callable[..., dict], *, checkpoint: str = "canary") -> dict:
        """Dispatch grouping once, then each head once, through the injected boundary."""
        self._instance(portfolio)
        prefix = self._prefix(portfolio)
        group_request = self.group_request(portfolio)
        grouped = dispatch(prefix + ".group", "group", group_request, checkpoint=checkpoint)
        self._response(grouped, prefix + ".group", "group", group_request, portfolio)
        try:
            partition_fields = self.fold_group(portfolio, grouped)
        except ValueError:
            return self.finalize(portfolio, grouped, [])
        quality_results = []
        for index, request in zip(self.modules["score"].heads(partition_fields["partition"]),
                                  self.quality_requests(portfolio, partition_fields["partition"]), strict=True):
            result = dispatch(f"{prefix}.quality.{index:02d}", "quality", request, checkpoint=checkpoint)
            self._response(result, f"{prefix}.quality.{index:02d}", "quality", request, portfolio)
            quality_results.append(result)
        return self.finalize(portfolio, grouped, quality_results)
