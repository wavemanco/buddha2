"""Presentation-only dates, imported model roles and audit table for frozen RP1 snapshots."""
from __future__ import annotations

import copy
import csv
import io

from .snapshot import canonical, sha, utc, validate_projection

NOTICE = ("FROZEN imported native evidence; Inspect made no model calls. Task dates describe the observed "
          "native API admission-through-cleanup interval, not controller completion or provider server latency. "
          "When no interval exists, dates mark the recorded snapshot observation only. "
          "The unfinished controller end is absent. Inspect Activity does not render InfoEvents: "
          "use dated Info records, native_audit metadata and native-audit.csv. "
          "No model/tool transcript was reconstructed.")


def audit_rows(payload: dict) -> list[dict]:
    requests = {r["slot_id"]: r for r in payload["requests"]}
    return [{**copy.deepcopy(r), "request": copy.deepcopy(requests[r["slot_id"]])}
            for r in payload["native_audit"]["requests"]]


def project(log, payload: dict, imported_at: str):
    """Copy only presentation fields; native attachments/results/errors remain unchanged."""
    validate_projection(payload)
    exported_at = utc(imported_at).isoformat()
    from inspect_ai.event import InfoEvent
    from inspect_ai.model import ModelConfig

    result = log.model_copy(deep=True)
    rows = audit_rows(payload)
    intervals = [r["interval"] for r in rows if r["interval"] is not None]
    observed = payload["native_audit"]["observed_at_utc"]
    start = min((utc(r["started_at_utc"]) for r in intervals), default=utc(observed)).isoformat()
    finish = max((utc(r["finished_at_utc"]) for r in intervals), default=utc(observed)).isoformat()
    result.eval.created = exported_at
    result.stats.started_at, result.stats.completed_at = start, finish
    if result.stats.model_usage or result.stats.role_usage:
        raise ValueError("Inspect usage must remain absent for an imported snapshot")
    roles = {}
    for role in sorted({r["role"] for r in payload["requests"]}):
        models = sorted({r["requested_parameters"]["model"] for r in payload["requests"] if r["role"] == role})
        configs = []
        for model in models:
            profiles: dict[str, int] = {}
            for request in payload["requests"]:
                if request["role"] == role and request["requested_parameters"]["model"] == model:
                    key = canonical({"requested_parameters": request["requested_parameters"],
                                     "returned_model": request.get("returned_model"),
                                     "status": request.get("status")}).decode()
                    profiles[key] = profiles.get(key, 0) + 1
            import json
            args = {"origin": "IMPORTED native configuration; Inspect served no calls",
                    "profiles": [{**json.loads(key), "native_admitted_request_count": count}
                                 for key, count in sorted(profiles.items())],
                    "inspect_usage_unavailable": True}
            configs.append(ModelConfig(model=model, args=args))
        roles["imported_native/" + role] = configs
    result.eval.model_roles = roles
    result.eval.task += " â€” imported audit; Activity graph unavailable"
    result.eval.tags = sorted(set([*(result.eval.tags or []), "IMPORTED_NATIVE_CONFIGS", "ACTIVITY_INFO_ONLY"]))
    display = {"notice": NOTICE, "task_dates_basis": "observed native API interval" if intervals
               else "recorded snapshot observation; no native audit interval available",
               "checkpoint": payload["checkpoint"], "controller_completion_recorded": False,
               "api_interval": {"started_at_utc": start, "finished_at_utc": finish} if intervals else None,
               "snapshot_observed_at_utc": observed, "native_admitted_request_count": len(rows),
               "native_audit_interval_count": len(intervals),
               "missing_interval_slots": [r["slot_id"] for r in rows if r["interval"] is None],
               "inspect_served_calls": 0, "activity_graph_available": False}
    result.eval.metadata = {**(result.eval.metadata or {}), "presentation": display,
                            "native_audit": copy.deepcopy(payload["native_audit"])}
    result.tags = sorted(set(result.eval.tags))
    result.metadata = {**(result.metadata or {}), **result.eval.metadata}
    result.eval.metadata = copy.deepcopy(result.metadata)
    for sample in result.samples:
        calls = [r for r in rows if r["pair"] + "/" + r["arm"] == sample.id]
        available = [r for r in calls if r["interval"] is not None]
        sample.metadata = {**(sample.metadata or {}), "presentation": display, "native_audit": calls}
        if available:
            sample.started_at = min(utc(r["interval"]["started_at_utc"]) for r in available).isoformat()
            sample.completed_at = max(utc(r["interval"]["finished_at_utc"]) for r in available).isoformat()
        for row in available:
            sample.events.append(InfoEvent(source="IMPORTED native audit interval; not an Inspect call",
                timestamp=utc(row["interval"]["started_at_utc"]), uuid="imported-audit-" + sha(row),
                data={"notice": NOTICE, "native_audit": row}))
    return result


def audit_csv(payload: dict) -> str:
    """One row per admitted request; missing native values remain empty, never zero-filled."""
    stream = io.StringIO(newline="")
    fields = ("slot_id", "pair", "arm", "cell", "diagnostic", "assessment_id", "role", "requested_model",
              "returned_model", "status", "started_at_utc", "finished_at_utc", "input_tokens", "output_tokens",
              "spent_micro_usd", "reserved_micro_usd", "request_sha256", "result_sha256", "audit_file_sha256")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in audit_rows(payload):
        request, interval = row["request"], row["interval"] or {}
        item = {k: row[k] for k in ("slot_id", "pair", "arm", "cell", "diagnostic", "assessment_id")}
        item.update({k: request[k] for k in ("role", "returned_model", "status", "spent_micro_usd",
                    "reserved_micro_usd", "request_sha256", "result_sha256") if k in request})
        item.update({k: interval[k] for k in ("started_at_utc", "finished_at_utc", "input_tokens",
                    "output_tokens", "audit_file_sha256") if k in interval})
        item["requested_model"] = request["requested_parameters"]["model"]
        writer.writerow(item)
    return stream.getvalue()
