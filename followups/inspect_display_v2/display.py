#!/usr/bin/env python3
"""Presentation-only projection of a closed native log; never an inference route."""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from followups.inspect_visibility_i1.importer import block_execution, decode
from followups.inspect_visibility_i1.paths import checked_path, lexical

NOTICE = ("Imported native audit intervals, not Inspect execution. Times span controller admission "
          "through post-cleanup completion, not provider server latency or token speed. Inspect's "
          "Activity graph does not render InfoEvents; use the dated Info/Transcript records, "
          "native_audit metadata and native-audit.csv. No model/tool transcript was reconstructed.")
PRIVATE = {"credential-binding.json", ".writer.lock", ".env", "auth.json", "credentials.json"}


def require(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def utc(value):
    require(isinstance(value, str) and value.endswith(("Z", "+00:00")), "UTC timestamp required")
    result = datetime.fromisoformat(value)
    offset = result.utcoffset()
    if result.tzinfo is None or offset is None or offset.total_seconds() != 0:
        raise ValueError("UTC offset required")
    return result


def validate(log, provenance):
    """Validate supplied public facts without following any provenance path."""
    require(provenance["kind"] == "buddha2-inspect-display-provenance-v1", "wrong provenance kind")
    require(provenance["provider_calls_made_by_derivation"] == 0 and provenance["raw_messages_included"] is False,
            "derivation must be keyless and transcript-free")
    snapshot = log.eval.metadata["snapshot"]
    require(snapshot["checkpoint"] == "closure" and snapshot["fixture"] is False, "closed native log required")
    ids = provenance["source_identities"]
    require(ids["study_sha256"] == snapshot["study_sha256"] == log.eval.run_id, "foreign study")
    for key in ("source_sha256", "runtime_sha256"):
        require(ids[key] == snapshot["source_identities"][key], "foreign source/runtime")
    require(provenance["scientific_complete"] is snapshot["summary"]["scientific_complete"], "scientific status differs")

    def references(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key.endswith("sha256"):
                    require(isinstance(item, str) and len(item) == 64 and all(c in "0123456789abcdef" for c in item),
                            "invalid source hash")
                if key == "path":
                    path = PurePosixPath(item)
                    require(bool(path.parts) and item not in {"", "."} and not path.is_absolute()
                            and path.as_posix() == item and "\\" not in item and ":" not in item
                            and not any(p in {"..", "."} or p.casefold() in PRIVATE or "stdout" in p.casefold()
                                        or "stderr" in p.casefold() for p in path.parts), "private/foreign source reference")
                references(item)
        elif isinstance(value, list):
            for item in value:
                references(item)
    references(provenance)
    attachment = log.samples[0].attachments.get("payload.json")
    payload_bytes = attachment.encode() if attachment is not None else canonical(snapshot) + b"\n"
    require(sha(payload_bytes) == provenance["old_snapshots"]["closure"]["payload"]["file_sha256"],
            "old snapshot bytes differ")
    start, finish = (utc(provenance["controller"][key]) for key in ("started_at_utc", "finished_at_utc"))
    require(start <= finish, "controller dates reversed")
    native = {r["slot_id"]: r for r in snapshot["requests"]}
    rows = provenance["requests"]
    require(len(rows) == provenance["attempts"] == len(native) and len({r["slot_id"] for r in rows}) == len(rows),
            "request inventory differs or duplicates exist")
    require(sum(r["spent_micro_usd"] for r in rows) == provenance["spent_micro_usd"]
            == snapshot["accounting"]["spent_micro_usd"], "native cost differs")
    for row in rows:
        old = native[row["slot_id"]]
        require(all(type(row[k]) is int and row[k] >= 0 for k in ("input_tokens", "output_tokens", "spent_micro_usd")),
                "invalid native counts")
        require(start <= utc(row["started_at_utc"]) <= utc(row["finished_at_utc"]) <= finish,
                "request interval reversed or outside controller")
        require(row["pair"] + "/" + row["arm"] in {s.id for s in log.samples}, "foreign pair/arm")
        assessment = row["assessment"]
        if assessment is None:
            require(row["cell"] == row["pair"] + ":" + row["arm"] and row["diagnostic"] is False
                    and row["role"] not in {"group", "quality"}, "foreign inference cell")
        else:
            require(row["cell"] == "assessment" and row["role"] in {"group", "quality"}
                    and assessment["pilot"] == row["pair"] and assessment["arm"] == row["arm"]
                    and assessment["id"] in snapshot["native_assessments"], "foreign assessment cell")
            prefix = "p3a-assessment-" + sha(canonical(assessment["id"]))[:24]
            require(row["slot_id"].startswith(prefix + "."), "assessment slot identity differs")
            primary = next(r for r in snapshot["rows"] if r["pilot"] == row["pair"] and r["arm"] == row["arm"])
            require((not row["diagnostic"] and assessment["id"] == primary["assessment_id"])
                    or (row["diagnostic"] and row["pair"] == "p3a-01" and row["arm"] == "fixed"
                        and assessment["id"].endswith(":anchor")
                        and snapshot["native_assessments"][assessment["id"]]["portfolio_sha256"] == primary["final_sha256"]),
                    "primary/diagnostic assessment differs")
        require(row["requested_model"] == row["declared_config"]["model"], "model/config differs")
        require(row["declared_config"] == old["requested_parameters"] and all(row[key] == old[key]
                for key in ("role", "returned_model", "status", "spent_micro_usd")), "native request projection differs")
        require(row["source"]["request_sha256"] == old["request_sha256"]
                and row["source"]["result_record_sha256"] == old["result_sha256"], "native request/result hash differs")
        require(type(row["diagnostic"]) is bool and (row["assessment"] is None
                or row["diagnostic"] is row["assessment"]["diagnostic"]), "diagnostic classification differs")
    require(utc(provenance["activity"]["first_request_started_at_utc"]) == min(utc(r["started_at_utc"]) for r in rows)
            and utc(provenance["activity"]["last_request_finished_at_utc"]) == max(utc(r["finished_at_utc"]) for r in rows),
            "activity bounds differ")


def project(log, provenance: dict, imported_at: str):
    """Pure projection: return a copied EvalLog, preserving native evidence and usage absence."""
    from inspect_ai.event import InfoEvent
    from inspect_ai.model import ModelConfig

    validate(log, provenance)
    result = log.model_copy(deep=True)
    result.eval.created = utc(imported_at).isoformat()
    result.stats.started_at = utc(provenance["controller"]["started_at_utc"]).isoformat()
    result.stats.completed_at = utc(provenance["controller"]["finished_at_utc"]).isoformat()
    require(not log.stats.model_usage and not log.stats.role_usage, "unexpected original Inspect usage")
    rows = provenance["requests"]
    by_role_model = {}
    for role, model in sorted({(r["role"], r["requested_model"]) for r in rows}):
        profiles: dict[str, int] = {}
        for row in rows:
            if row["role"] == role and row["requested_model"] == model:
                key = canonical({"role": row["role"], "parameters": row["declared_config"],
                                 "returned_model": row["returned_model"]}).decode()
                profiles[key] = profiles.get(key, 0) + 1
        by_role_model[role, model] = {"origin": "IMPORTED native model configuration; Inspect made no calls",
                                     "profiles": [{**json.loads(k), "native_call_count": v} for k, v in profiles.items()],
                                     "inspect_usage_unavailable": True}
    result.eval.model_roles = {"imported_native/" + role: [ModelConfig(model=model, args=by_role_model[role, model])
        for model in sorted({r["requested_model"] for r in rows if r["role"] == role})]
        for role in sorted({r["role"] for r in rows})}
    result.eval.task = log.eval.task + " — imported audit; Activity graph unavailable"
    result.eval.tags = [*(log.eval.tags or []), "PRESENTATION_V2", "IMPORTED_NATIVE_CONFIGS", "ACTIVITY_INFO_ONLY"]
    display = {"notice": NOTICE, "exported_at_utc": imported_at, "task_dates_basis": "native controller lifetime",
               "controller": provenance["controller"], "api_activity": provenance["activity"],
               "source_identities": provenance["source_identities"], "native_request_count": len(rows),
               "native_spent_micro_usd": provenance["spent_micro_usd"], "inspect_served_calls": 0,
               "diagnostic_calls_are_not_extra_primary_samples": True}
    result.eval.metadata = {**(result.eval.metadata or {}), "presentation_v2": display,
                            "native_audit": copy.deepcopy(provenance)}
    # Inspect synchronizes the legacy EvalSpec and current top-level tags/metadata on read.
    result.tags = sorted(set(result.eval.tags))
    result.metadata = {**(result.metadata or {}), **result.eval.metadata}
    result.eval.metadata = copy.deepcopy(result.metadata)
    for sample in result.samples:
        calls = [r for r in rows if r["pair"] + "/" + r["arm"] == sample.id]
        sample.metadata = {**(sample.metadata or {}), "presentation_v2": display,
                           "native_audit": copy.deepcopy(calls)}
        if calls:
            sample.started_at = min(utc(r["started_at_utc"]) for r in calls).isoformat()
            sample.completed_at = max(utc(r["finished_at_utc"]) for r in calls).isoformat()
        for row in calls:
            sample.events.append(InfoEvent(source="IMPORTED native audit interval; not an Inspect call",
                timestamp=utc(row["started_at_utc"]), uuid="imported-audit-" + sha(canonical(row)),
                data={"notice": NOTICE, "native_audit": copy.deepcopy(row)}))
    return result


def audit_csv(provenance: dict) -> str:
    stream = io.StringIO(newline="")
    fields = ("slot_id", "pair", "arm", "cell", "role", "diagnostic", "requested_model", "returned_model",
              "status", "started_at_utc", "finished_at_utc", "input_tokens", "output_tokens", "spent_micro_usd")
    writer = csv.DictWriter(stream, fieldnames=[*fields, "audit_path", "audit_file_sha256"], lineterminator="\n")
    writer.writeheader()
    for row in provenance["requests"]:
        writer.writerow({**{key: row[key] for key in fields}, "audit_path": row["source"]["audit"]["path"],
                         "audit_file_sha256": row["source"]["audit"]["file_sha256"]})
    return stream.getvalue()


def export(log_path: Path, provenance_path: Path, output: Path):
    counts = block_execution()
    from inspect_ai.log import (
        bundle_log_dir,
        read_eval_log,
        resolve_sample_attachments,
        write_eval_log,
    )

    require(log_path == Path("/input/closure.eval") and provenance_path == Path("/input/provenance.json"),
            "only exact whitelisted display inputs are permitted")
    for path in (log_path, provenance_path):
        lexical(str(path))
        checked_path(path, Path("/input"))
    lexical(str(output))
    require(output.parent == Path("/out") and output.name == "export", "fresh /out/export required")
    checked_path(output, Path("/out"), missing=True)
    require(not output.exists(), "export exists")
    provenance = decode(provenance_path.read_bytes())
    if not isinstance(provenance, dict):
        raise TypeError("provenance must be an object")
    require(sha(log_path.read_bytes()) == provenance["old_closure_log"]["file_sha256"], "old closure log bytes differ")
    log = read_eval_log(log_path, resolve_attachments=False)
    projected = project(log, provenance, datetime.now(UTC).isoformat())
    output.mkdir()
    (output / "logs").mkdir()
    target = output / "logs/closure-v2.eval"
    write_eval_log(projected, target)
    restored = read_eval_log(target, resolve_attachments=False)
    for sample, original in zip(restored.samples, projected.samples, strict=True):
        require(all(sample.attachments.get(name) == value for name, value in original.attachments.items()),
                "original raw attachment key/value changed")
    for before, after in zip(log.samples, restored.samples, strict=True):
        require(before.output == after.output and before.scores == after.scores
                and before.error == after.error, "native sample evidence changed")
    require(log.status == restored.status and log.error == restored.error and log.results == restored.results,
            "native outcome changed")
    old_resolved = read_eval_log(log_path, resolve_attachments=True)
    new_resolved = read_eval_log(target, resolve_attachments=True)
    expected_resolved = projected.model_copy(deep=True)
    expected_resolved.samples = [resolve_sample_attachments(s, "full") for s in expected_resolved.samples]
    require(new_resolved.model_dump(mode="json") == expected_resolved.model_dump(mode="json"),
            "saved-log semantic roundtrip differs")
    for before, after in zip(old_resolved.samples, new_resolved.samples, strict=True):
        require(before.input == after.input and before.output == after.output
                and before.scores == after.scores and before.error == after.error, "resolved native evidence changed")
    (output / "native-audit.csv").write_text(audit_csv(provenance), encoding="utf-8", newline="")
    (output / "DISPLAY_NOTES.md").write_text(NOTICE + "\n", encoding="utf-8")
    bundle_log_dir(log_dir=str(output / "logs"), output_dir=str(output / "viewer"), overwrite=False)
    require(not any(counts.values()), "projection attempted a model or socket")
    proof = {"passed": True, "kind": "buddha2-inspect-display-v2", "old_closure_log_sha256": sha(log_path.read_bytes()),
             "provenance_sha256": sha(provenance_path.read_bytes()), "roundtrip_equal": True,
             "all_original_raw_attachment_values_preserved": True, "resolved_native_values_preserved": True,
             "native_evidence_preserved": True, "native_request_count": len(provenance["requests"]),
             "native_scientific_complete": provenance["scientific_complete"], "inspect_usage_absent": True,
             "model_network_attempts": counts, "provider_calls": 0, "api_spend": 0, "activity_graph_available": False}
    (output / "result.json").write_bytes(canonical(proof) + b"\n")
    return proof


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.log, args.provenance, args.output), sort_keys=True))
