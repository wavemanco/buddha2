"""Passive P4 saved-log projection; never runs a model, evaluator or source path."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from buddha2.artifacts import ContractError
from followups.inspect_visibility_i1.importer import block_execution, canonical, decode
from followups.inspect_visibility_i1.paths import checked_path, lexical

NOTICE = ("IMPORTED native P4 evidence. Inspect served zero calls. Token/cost fields are imported native usage, "
          "not Inspect execution. Official and grouping-sensitivity metrics remain metadata; no Inspect scores "
          "or conversations were invented. Dated InfoEvents preserve audit activity; the Inspect Activity graph "
          "does not render those events. Native intervals describe observed admission through cleanup, not "
          "provider-server latency. Missing cases, times and usage remain explicitly missing.")
TOKEN_FIELDS = ("input_tokens", "output_tokens", "total_tokens")
OPTIONAL_TOKENS = ("input_tokens_cache_write", "input_tokens_cache_read", "reasoning_tokens")


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _utc(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        raise ContractError("native timestamp must be explicit")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ContractError("native timestamp is invalid") from None
    _require(parsed.tzinfo is not None and parsed.utcoffset() is not None, "native timestamp needs a timezone")
    return parsed.astimezone(timezone.utc)


def validate_snapshot(payload: dict) -> None:
    _require(isinstance(payload, dict) and payload.get("kind") == "phase4-cm1-snapshot-v1",
             "unsupported P4 snapshot")
    for key in ("study_sha256", "source_sha256"):
        _require(isinstance(payload.get(key), str) and re.fullmatch(r"[0-9a-f]{64}", payload[key]),
                 "snapshot identity is missing")
    _require(type(payload.get("fixture")) is bool and isinstance(payload.get("status"), str)
             and bool(payload["status"]), "snapshot fixture/status is missing")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not 0 < len(cases) <= 24:
        raise ContractError("snapshot needs its declared cases")
    ids = set()
    for case in cases:
        _require(isinstance(case, dict) and isinstance(case.get("id"), str)
                 and bool(case["id"].strip()) and case["id"] not in ids, "case ID is absent or repeated")
        ids.add(case["id"])
        _require(isinstance(case.get("prompt"), str) and "metrics" in case and "outputs" in case
                 and isinstance(case.get("events"), list) and isinstance(case.get("model_usage"), dict),
                 "case fields are incomplete")
        starts, ends = case.get("started_at"), case.get("completed_at")
        if starts is not None:
            _utc(starts)
        if ends is not None:
            _utc(ends)
        if starts is not None and ends is not None:
            _require(_utc(starts) <= _utc(ends), "native case interval is reversed")
        for event in case["events"]:
            _require(isinstance(event, dict) and set(event) == {"timestamp", "source", "data"}
                     and isinstance(event["source"], str) and bool(event["source"])
                     and isinstance(event["data"], dict), "unsupported imported InfoEvent")
            _utc(event["timestamp"])
        for model, usage in case["model_usage"].items():
            _require(isinstance(model, str) and bool(model.strip()) and isinstance(usage, dict)
                     and set(usage).issubset(set(TOKEN_FIELDS + OPTIONAL_TOKENS + ("total_cost",)))
                     and all(type(usage.get(k)) is int and usage[k] >= 0 for k in TOKEN_FIELDS),
                     "native model usage needs known token totals")
            for key in OPTIONAL_TOKENS:
                _require(usage.get(key) is None or type(usage[key]) is int and usage[key] >= 0,
                         "invalid optional native usage")
            cost = usage.get("total_cost")
            _require(cost is None or type(cost) in (int, float) and math.isfinite(cost) and cost >= 0,
                     "invalid imported native cost")
            known_input = usage["input_tokens"] + sum(usage.get(k) or 0 for k in OPTIONAL_TOKENS[:2])
            _require(usage["total_tokens"] >= known_input + usage["output_tokens"], "native token total is too small")
            if all(usage.get(k) is not None for k in OPTIONAL_TOKENS[:2]):
                _require(usage["total_tokens"] == known_input + usage["output_tokens"], "native token total differs")
    artifacts = payload.get("source_artifacts")
    if not isinstance(artifacts, list):
        raise ContractError("source artifact references are absent")
    for row in artifacts:
        _require(isinstance(row, dict) and set(row) == {"path", "sha256"}
                 and isinstance(row["path"], str) and bool(row["path"])
                 and isinstance(row["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]),
                 "invalid source artifact reference")
    try:
        canonical(payload)
    except (TypeError, ValueError, UnicodeError):
        raise ContractError("snapshot must contain only finite JSON values") from None


def aggregate_usage(cases: list[dict]) -> dict:
    """Sum actual known usage; an unknown optional category stays unknown."""
    models: dict[str, list[dict]] = {}
    for case in cases:
        for model, usage in case["model_usage"].items():
            models.setdefault(model, []).append(usage)
    return {model: {**{key: sum(row[key] for row in rows) for key in TOKEN_FIELDS},
                    **{key: sum(row[key] for row in rows) if all(row.get(key) is not None for row in rows)
                       else None for key in OPTIONAL_TOKENS + ("total_cost",)}}
            for model, rows in sorted(models.items())}


def audit_csv(payload: dict) -> str:
    """Expose dated source audit activity without reconstructing model/chat events."""
    stream = io.StringIO(newline="")
    fields = ("case_id", "timestamp", "source", "slot_id", "role", "requested_model", "returned_model",
              "status", "started_at", "completed_at", "spent_micro_usd", "reserved_micro_usd", "usage_json")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for case in payload["cases"]:
        for event in case["events"]:
            data = event["data"]
            row = {key: data[key] for key in fields[3:-1] if key in data}
            row.update(case_id=case["id"], timestamp=event["timestamp"], source=event["source"],
                       usage_json=json.dumps(data["usage"], ensure_ascii=False, sort_keys=True)
                       if data.get("usage") is not None else "")
            writer.writerow(row)
    return stream.getvalue()


def export_snapshot(snapshot: Path, output: Path) -> dict:
    """Run only in the existing SDK-free, network-none passive image."""
    counts = block_execution()
    lexical(str(snapshot))
    checked_path(snapshot, snapshot.parent)
    raw = snapshot.read_bytes()
    decoded = decode(raw)
    if not isinstance(decoded, dict):
        raise ContractError("unsupported P4 snapshot")
    payload: dict[str, Any] = decoded
    validate_snapshot(payload)
    lexical(str(output))
    _require(output.is_absolute() and output.parent == Path("/out") and not output.exists(),
             "export needs a fresh direct child of /out")
    checked_path(output, Path("/out"), missing=True)
    # Inspect imports happen only after SDK, socket and model-constructor blocks.
    from inspect_ai.event import InfoEvent
    from inspect_ai.log import (
        EvalConfig,
        EvalDataset,
        EvalError,
        EvalLog,
        EvalSample,
        EvalSpec,
        EvalStats,
        bundle_log_dir,
        read_eval_log,
        write_eval_log,
    )
    from inspect_ai.model import ModelConfig, ModelOutput, ModelUsage

    from followups.phase3b_seq2_v1.inspect_adapter import _semantic

    def semantic(log):
        # Reuse the established view; Inspect's transient bookkeeping is not native evidence.
        value = _semantic(log, {sample.id: {} for sample in log.samples})
        return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False,
                                     default=lambda item: item.model_dump(mode="json")))

    snapshot_hash = hashlib.sha256(raw).hexdigest()
    exported_at = datetime.now(timezone.utc).isoformat()
    roles: dict[str, dict[str, list[dict]]] = {}
    samples = []
    for case in sorted(payload["cases"], key=lambda row: row["id"]):
        events = []
        for index, row in enumerate(case["events"]):
            events.append(InfoEvent(timestamp=_utc(row["timestamp"]), source=row["source"], data=row["data"],
                                    uuid=f"p4-import-{snapshot_hash}-{case['id']}-{index}"))
            role, model = row["data"].get("role"), row["data"].get("requested_model")
            if isinstance(role, str) and isinstance(model, str) and role and model:
                profiles = roles.setdefault(role, {}).setdefault(model, [])
                params = row["data"].get("requested_parameters")
                if isinstance(params, dict) and params not in profiles:
                    profiles.append(params)
        display = ModelOutput()
        if case["outputs"] is not None:
            display = ModelOutput.from_content(model="imported-native-portfolio",
                content=json.dumps(case["outputs"], ensure_ascii=False, indent=2))
            display.choices[0].message.id = f"p4-{snapshot_hash}-{case['id']}-display"
        samples.append(EvalSample(id=case["id"], epoch=1, input=case["prompt"], target=[], output=display,
            scores=None, events=events, started_at=case.get("started_at"), completed_at=case.get("completed_at"),
            model_usage={model: ModelUsage(**usage) for model, usage in case["model_usage"].items()},
            description=f"IMPORTED P4 {payload['status']}: {case['id']}; "
                        + ("missing output" if case["outputs"] is None else "saved output"),
            metadata={"fixture": payload["fixture"], "native_case": case, "snapshot_sha256": snapshot_hash,
                      "native_metrics_are_authoritative": True, "inspect_served_calls": 0,
                      "usage_is_imported_native": True, "activity_graph_available": False, "notice": NOTICE}))
    complete = payload["status"] == "complete"
    status = "success" if complete else "started" if payload["status"] in {"started", "running", "prepared"} else "error"
    message = "Imported native study is incomplete; this is not an Inspect execution failure."
    error = EvalError(message=message, traceback=message, traceback_ansi=message) if status == "error" else None
    starts = [_utc(row["started_at"]) for row in payload["cases"] if row.get("started_at") is not None]
    ends = [_utc(row["completed_at"]) for row in payload["cases"] if row.get("completed_at") is not None]
    log = EvalLog(status=status, error=error, results=None, samples=samples,
        stats=EvalStats(started_at=min(starts).isoformat() if starts else exported_at,
                       completed_at=max(ends).isoformat() if ends else exported_at,
                       model_usage={model: ModelUsage(**usage) for model, usage in aggregate_usage(payload["cases"]).items()}),
        eval=EvalSpec(created=exported_at, task="P4-CM1 imported native snapshot", task_version="1.0",
            task_id="p4-cm1-snapshot", eval_id=snapshot_hash, run_id=payload["study_sha256"], model="none",
            model_roles={"imported_native/" + role: [ModelConfig(model=model, args={
                "origin": "imported native; Inspect served zero calls", "requested_parameters": profiles or None})
                for model, profiles in sorted(models.items())] for role, models in sorted(roles.items())},
            dataset=EvalDataset(name="P4-CM1 prompt units; missing cases retained", samples=len(samples),
                                sample_ids=[row.id for row in samples]), config=EvalConfig(),
            tags=["IMPORTED", "NO_MODEL_CALLS", "ACTIVITY_INFO_ONLY", "SYNTHETIC" if payload["fixture"] else "NATIVE_EVIDENCE"],
            metadata={"snapshot": payload, "snapshot_sha256": snapshot_hash, "notice": NOTICE,
                      "usage_is_imported_native": True, "inspect_served_calls": 0,
                      "source_artifacts_are_references_only": True, "activity_graph_available": False,
                      "task_dates_basis": ("native source intervals" if starts and ends else
                          "export observation time; native source interval unavailable" )}))
    expected = semantic(log)
    output.mkdir()
    (output / "logs").mkdir()
    target = output / "logs/phase4.eval"
    write_eval_log(log, target)
    actual = semantic(read_eval_log(target, resolve_attachments=True))
    _require(actual == expected, "Inspect roundtrip changed imported P4 semantics")
    _require(not any(counts.values()), "passive export attempted model/network activity")
    bundle_log_dir(log_dir=str(output / "logs"), output_dir=str(output / "viewer"), overwrite=False)
    _require(not any(counts.values()), "passive viewer bundle attempted model/network activity")
    (output / "DISPLAY_NOTES.md").write_text(NOTICE + "\n", encoding="utf-8")
    (output / "native-audit.csv").write_text(audit_csv(payload), encoding="utf-8", newline="")
    (output / "semantic.json").write_bytes(canonical(actual) + b"\n")
    actual["eval"].pop("created")
    receipt: dict[str, Any] = {"kind": "phase4-cm1-inspect-export-v1", "study_sha256": payload["study_sha256"],
        "source_sha256": payload["source_sha256"], "snapshot_sha256": snapshot_hash,
        "fixture": payload["fixture"], "native_status": payload["status"], "visibility_status": "complete",
        "provider_calls": 0, "api_spend": 0, "model_network_attempts": counts, "roundtrip_equal": True,
        "semantic_sha256": hashlib.sha256(canonical(actual)).hexdigest(), "samples": len(samples),
        "missing_output_cases": sum(c["outputs"] is None for c in payload["cases"]),
        "imported_events": sum(len(c["events"]) for c in payload["cases"]), "actual_exported_at_utc": exported_at,
        "native_scores_are_imported_metadata": True, "usage_is_imported_native": True,
        "inspect_results_absent": True, "activity_graph_available": False, "model_tool_events_fabricated": False}
    with (output / "result.json").open("xb") as stream:
        stream.write(canonical(receipt) + b"\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export_snapshot(args.snapshot, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
