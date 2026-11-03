"""Pure public projection of validated P3A-HI records; no controller or provider access."""

from __future__ import annotations

import copy
import hashlib
import json
import stat
from pathlib import Path

from followups.inspect_visibility_i1.paths import checked_path, lexical

KIND = "p3a-hi-public-snapshot-v1"
MANIFEST = "p3a-hi-public-snapshot-manifest-v1"
CHECKPOINTS = {"first-pair", "closure"}
PILOTS = tuple(f"p3a-{i:02}" for i in range(1, 5))
ARMS = ("fixed", "adaptive")
ROLES = {"plan", "answer", "rank", "editor", "fixed_selector", "group", "quality"}
ROW_STATUSES = {"scored", "unscored", "missing_final", "assessment_budget_stop",
                "unvalidated_integrity_hold", "group_refused", "invalid_group",
                "quality_refused", "invalid_quality", "unvalidated_known_deadline_stop",
                "unvalidated_unknown_deadline_hold"}
ROOT = Path(__file__).resolve().parents[2]
SCOPES = (ROOT / "runs/phase3a-h1-integrated-v1", Path("/results/phase3a-h1-integrated-v1"))
ACCOUNTING = ("attempts", "provider_calls", "spent_micro_usd", "reserved_micro_usd",
              "input_tokens", "output_tokens", "reserved_input_tokens", "reserved_output_tokens",
              "known_results", "unknown_results", "durable_unknown_results", "pending_intents",
              "unknown_results_semantics", "unknown_cost_not_inferred_zero", "cells", "assessment",
              "resource_report", "fixture", "study_sha256", "status", "core_status")
ASSESSMENT = ("schema_version", "kind", "fixture", "evaluator", "portfolio_sha256", "task_id",
              "assessment_identity_sha256", "status", "failure", "metrics", "native")


class ProjectionError(ValueError):
    """Unsupported or damaged optional projection; does not grant or stop core execution."""


class CanonicalIntegrityError(ValueError):
    """Contradictory already-validated canonical identities; core must handle its integrity gate."""


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _require(condition: bool, message: str, *, canonical_error: bool = False) -> None:
    if not condition:
        raise (CanonicalIntegrityError if canonical_error else ProjectionError)(message)


def _hash(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def output_path(value: Path) -> Path:
    lexical(str(value))
    path = Path(value)
    scope = next((root for root in SCOPES if path.is_absolute()
                  and path != root and path.is_relative_to(root)), None)
    if scope is None:
        raise ProjectionError("visibility output outside new P3A-HI namespace")
    return checked_path(path, scope, missing=True)


def _copy_fields(value: dict, keys: tuple[str, ...]) -> dict:
    return {key: copy.deepcopy(value[key]) for key in keys if key in value}


def validate_projection(payload: dict) -> None:
    required = {"kind", "checkpoint", "study_sha256", "fixture", "source_identities", "tasks", "rows",
                "finals", "coverage", "analysis", "summary", "readiness", "accounting", "requests",
                "native_assessments", "checkpoint_dispositions", "projection_policy"}
    _require(isinstance(payload, dict) and required <= set(payload)
             and set(payload) <= required | {"role_profiles"}, "unsupported public projection fields")
    _require(payload["kind"] == KIND and payload["checkpoint"] in CHECKPOINTS
             and _hash(payload["study_sha256"]) and type(payload["fixture"]) is bool,
             "unsupported public projection identity")
    _require(isinstance(payload["summary"], dict) and "engineering_review" not in payload["summary"]
             and payload["summary"].get("study_sha256") == payload["study_sha256"]
             and payload["summary"].get("fixture") is payload["fixture"], "invalid projection summary")
    _require(isinstance(payload["accounting"], dict) and set(payload["accounting"]) <= set(ACCOUNTING),
             "unexpected accounting controls in public projection")
    tasks, rows, finals = payload["tasks"], payload["rows"], payload["finals"]
    _require(isinstance(tasks, list) and len(tasks) == 4
             and all(isinstance(t, dict) for t in tasks)
             and [t.get("pilot_id") for t in tasks] == list(PILOTS), "unknown projected tasks")
    expected = {(p, a) for p in PILOTS for a in ARMS}
    _require(isinstance(rows, list) and isinstance(finals, list) and len(rows) == len(finals) == 8
             and all(isinstance(r, dict) for r in rows + finals)
             and {(r.get("pilot"), r.get("arm")) for r in rows} == expected
             and {(r.get("pilot"), r.get("arm")) for r in finals} == expected
             and all(r.get("status") in ROW_STATUSES for r in rows), "unknown projected primary")
    indexed = {(r["pilot"], r["arm"]): r for r in rows}
    for final in finals:
        portfolio = final.get("portfolio")
        _require((sha(portfolio) if portfolio is not None else None)
                 == indexed[final["pilot"], final["arm"]].get("final_sha256"),
                 "projected selected portfolio changed")
        if portfolio is not None:
            responses = portfolio.get("responses") if isinstance(portfolio, dict) else None
            _require(isinstance(responses, list) and len(responses) == 10
                     and all(isinstance(r, dict) and isinstance(r.get("id"), str)
                             and isinstance(r.get("text"), str) for r in responses)
                     and len({r["id"] for r in responses}) == 10, "projected responses differ")
    requests = payload["requests"]
    _require(isinstance(requests, list), "missing origin requests")
    for request in requests:
        _require(isinstance(request, dict) and request.get("role") in ROLES
                 and isinstance(request.get("requested_parameters"), dict), "unknown projected role")
        expected_model = ("claude-sonnet-5-5" if request["role"] in {"plan", "answer", "rank"}
                          else "gpt-5.6-luna" if request["role"] == "group" else "claude-opus-5")
        _require(request["requested_parameters"].get("model") == expected_model, "unknown projected model")
    _require(isinstance(payload["native_assessments"], dict)
             and all(isinstance(v, dict) and set(v) <= set(ASSESSMENT)
                     for v in payload["native_assessments"].values()), "unexpected assessment content")
    canonical(payload)


def build_snapshot(study: dict, report_data: dict, saved_records: dict, checkpoint: str) -> dict:
    """Called only by the paused/ended core with its already-validated public records.

    No directory is read. Raw ledger intents/results, owner/review/grant controls and
    raw judge/provider messages are not part of this projection.
    """
    _require(checkpoint in CHECKPOINTS, "unknown visibility checkpoint")
    _require(all(isinstance(v, dict) for v in (study, report_data, saved_records)), "invalid snapshot inputs")
    study_sha = study.get("study_sha256")
    _require(_hash(study_sha), "invalid study identity")
    _require(all(name in report_data for name in
                 ("rows", "coverage", "analysis", "summary", "accounting", "protocol", "readiness")),
             "missing canonical public report component")
    summary, protocol = report_data["summary"], report_data["protocol"]
    _require(isinstance(summary, dict) and isinstance(protocol, dict), "invalid public report")
    _require(summary.get("study_sha256") == protocol.get("study_sha256") == study_sha,
             "canonical study identities disagree", canonical_error=True)
    fixture = summary.get("fixture")
    _require(type(fixture) is bool, "fixture flag must be explicit")
    tasks = study.get("tasks")
    _require(isinstance(tasks, list) and [t.get("pilot_id") for t in tasks] == list(PILOTS),
             "unsupported pilot population/order")
    if checkpoint == "first-pair":
        _require(summary.get("first_assessments_closed") is True and bool(summary.get("engineering_review")),
                 "first-pair checkpoint has not completed canonical review/assessment classification")
    rows = report_data["rows"]
    _require(isinstance(rows, list) and len(rows) == 8 and all(isinstance(r, dict) for r in rows),
             "eight native primary rows required")
    _require({(r.get("pilot"), r.get("arm")) for r in rows} == {(p, a) for p in PILOTS for a in ARMS},
             "unknown or duplicate pilot/arm")
    _require(all(r.get("status") in ROW_STATUSES for r in rows), "unsupported native primary status")
    _require(isinstance(saved_records.get("branches"), dict)
             and isinstance(saved_records.get("assessments"), dict), "invalid validated saved records")
    branches: dict = saved_records["branches"]
    assessments: dict = saved_records["assessments"]
    finals = []
    held = report_data["analysis"].get("held_evidence_failure") is not None
    for row in rows:
        branch = branches.get((row["pilot"], row["arm"])) if not held else None
        result = (branch.get("result") or {}) if branch else {}
        portfolio = result.get("portfolio")
        _require((sha(portfolio) if portfolio is not None else None) == row.get("final_sha256"),
                 "canonical selected portfolio hash disagrees with report", canonical_error=True)
        if branch:
            _require(branch.get("study_sha256") == study_sha and branch.get("pilot") == row["pilot"]
                     and branch.get("arm") == row["arm"] and branch.get("fixture") is fixture
                     and branch.get("portfolio_sha256") == row.get("final_sha256"),
                     "canonical selected branch identity differs", canonical_error=True)
        if portfolio is not None:
            _require(isinstance(portfolio, dict), "unsupported portfolio")
            responses = portfolio.get("responses")
            _require(isinstance(responses, list) and len(responses) == 10
                     and all(isinstance(r, dict) and isinstance(r.get("id"), str)
                             and isinstance(r.get("text"), str) for r in responses)
                     and len({r["id"] for r in responses}) == 10,
                     "unsupported ordered ten-response portfolio")
            _require(portfolio.get("fixture") is fixture, "canonical portfolio mode differs", canonical_error=True)
        finals.append({"pilot": row["pilot"], "arm": row["arm"], "portfolio": copy.deepcopy(portfolio)})
    declared = {entry["id"] for entry in study.get("assessment_plan", [])}
    native_assessments = {}
    if not held:
        for aid, assessment in assessments.items():
            _require(aid in declared and isinstance(assessment, dict), "undeclared canonical assessment",
                     canonical_error=True)
            native_assessments[aid] = _copy_fields(assessment, ASSESSMENT)
        for row in rows:
            assessment = assessments.get(row["assessment_id"])
            _require((sha(assessment) if assessment is not None else None) == row.get("assessment_sha256"),
                     "canonical assessment hash disagrees with report", canonical_error=True)
            if row["status"] == "scored":
                _require(assessment is not None and assessment.get("status") == "scored"
                         and assessment.get("metrics") == row.get("metrics"),
                         "canonical scored metrics disagree", canonical_error=True)
    requests = protocol.get("requests")
    _require(isinstance(requests, list), "public protocol lacks request metadata")
    for request in requests:
        _require(isinstance(request, dict) and request.get("role") in ROLES
                 and isinstance(request.get("requested_parameters"), dict), "unknown originating request role")
        model = request["requested_parameters"].get("model")
        expected = ("claude-sonnet-5-5" if request["role"] in {"plan", "answer", "rank"}
                    else "gpt-5.6-luna" if request["role"] == "group" else "claude-opus-5")
        _require(model == expected, "unknown originating model")
    _require(isinstance(report_data["accounting"], dict), "invalid public accounting")
    payload = {
        "kind": KIND, "checkpoint": checkpoint, "study_sha256": study_sha, "fixture": fixture,
        "source_identities": _copy_fields(protocol, ("definition_sha256", "specification_sha256",
                                                    "source_sha256", "runtime", "runtime_sha256")),
        "tasks": copy.deepcopy(tasks), "rows": copy.deepcopy(rows), "finals": finals,
        "coverage": copy.deepcopy(report_data["coverage"]), "analysis": copy.deepcopy(report_data["analysis"]),
        "summary": {key: copy.deepcopy(value) for key, value in summary.items() if key != "engineering_review"},
        "readiness": copy.deepcopy(report_data["readiness"]),
        "accounting": _copy_fields(report_data["accounting"], ACCOUNTING),
        "requests": copy.deepcopy(requests), "native_assessments": native_assessments,
        "checkpoint_dispositions": {"first-pair": "reached" if checkpoint == "first-pair"
                                     or summary.get("first_assessments_closed") is True else "not_reached",
                                     "closure": "reached" if checkpoint == "closure" else "not_reached"},
        "projection_policy": {"no_native_reexecution": True, "native_values_not_recomputed": True,
                              "raw_provider_messages_excluded": True, "grant_review_owner_controls_excluded": True,
                              "snapshot_bytes_are_public_projection_not_original_provider_transcript": True},
    }
    if "role_profiles" in protocol:
        payload["role_profiles"] = copy.deepcopy(protocol["role_profiles"])
    # Validate JSON without adding defaults, replacing nulls or accepting nonfinite numbers.
    validate_projection(payload)
    return payload


def publish_snapshot(payload: dict, output: Path) -> dict:
    validate_projection(payload)
    output = output_path(output)
    _require(not output.exists(), "snapshot output must be fresh")
    raw = canonical(payload) + b"\n"
    manifest = {"kind": MANIFEST, "study_sha256": payload["study_sha256"],
                "checkpoint": payload["checkpoint"], "fixture": payload["fixture"],
                "payload_file": "payload.json", "payload_sha256": hashlib.sha256(raw).hexdigest(),
                "snapshot_sha256": hashlib.sha256(raw).hexdigest(),
                "payload_bytes": len(raw)}
    output.mkdir(parents=True)
    for name, value in (("payload.json", raw), ("manifest.json", canonical(manifest) + b"\n")):
        with (output / name).open("xb") as stream:
            stream.write(value)
    return manifest


def _decode(raw: bytes) -> dict:
    def pairs(items: list[tuple]) -> dict:
        value = {}
        for key, item in items:
            _require(key not in value, "duplicate snapshot JSON key")
            value[key] = item
        return value
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ProjectionError("nonfinite snapshot JSON")))
    _require(isinstance(value, dict), "snapshot JSON must be an object")
    return value


def read_snapshot(directory: Path, *, scope: Path | None = None) -> tuple[dict, dict, dict[str, bytes]]:
    """Only these two named files are opened; referenced native paths are never followed."""
    directory = Path(directory)
    lexical(str(directory))
    if scope is None:
        scope = Path("/snapshot") if directory == Path("/snapshot") else next(
            (root for root in SCOPES if directory.is_absolute() and directory.is_relative_to(root)), None)
    if scope is None:
        raise ProjectionError("snapshot input outside explicit scope")
    _require(scope == Path("/snapshot") or scope in SCOPES, "snapshot input outside explicit scope")
    checked_path(directory, scope)
    raw = {}
    for name in ("manifest.json", "payload.json"):
        path = checked_path(directory / name, scope)
        info = path.lstat()
        _require(stat.S_ISREG(info.st_mode) and info.st_size <= 32_000_000, "snapshot file type/size invalid")
        raw[name] = path.read_bytes()
    manifest, payload = _decode(raw["manifest.json"]), _decode(raw["payload.json"])
    _require(set(manifest) == {"kind", "study_sha256", "checkpoint", "fixture", "payload_file",
                               "payload_sha256", "snapshot_sha256", "payload_bytes"}, "snapshot manifest shape differs")
    _require(manifest.get("kind") == MANIFEST and manifest.get("payload_file") == "payload.json"
             and manifest.get("payload_sha256") == hashlib.sha256(raw["payload.json"]).hexdigest()
             and manifest.get("snapshot_sha256") == manifest.get("payload_sha256")
             and manifest.get("payload_bytes") == len(raw["payload.json"]), "projected snapshot checksum differs")
    _require(payload.get("kind") == KIND and payload.get("checkpoint") in CHECKPOINTS
             and _hash(payload.get("study_sha256"))
             and all(manifest.get(key) == payload.get(key) for key in ("study_sha256", "checkpoint", "fixture")),
             "projected snapshot identity differs")
    validate_projection(payload)
    return payload, manifest, raw
