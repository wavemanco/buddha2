"""Display-only public provenance; no native replay, provider construction or inferred times."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from buddha2.artifacts import digest, file_hash
from followups.inspect_visibility_i1.paths import checked_path, lexical
from followups.phase3a_h1_integrated_v1.transport import audit_path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "runs/phase3a-h1-integrated-v1"
STUDY = BASE / "verification-v4/release/study.json"
CONTROLLER = BASE / "launcher/41ee14d9027344938abe33743d5d3bfe.result.json"
OUTPUT = ROOT / "runs/inspect-display-v2/inputs-v1/provenance.json"
BINDINGS = ("study_sha256", "source_sha256", "runtime_sha256", "policy_sha256", "launcher_sha256")
REPORTS = ("rows.json", "coverage.json", "analysis.json", "summary.json", "accounting.json",
           "protocol.json", "readiness.json", "PHASE3A_REPORT.md")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def public(path: Path, *, missing: bool = False) -> Path:
    lexical(str(path))
    require(not any("stdout" in p.casefold() or "stderr" in p.casefold() for p in path.parts),
            "stream path rejected before metadata")
    return checked_path(path, ROOT, missing=missing)


def read(path: Path) -> dict:
    value = json.loads(public(path).read_bytes())
    require(isinstance(value, dict), "public provenance input must be an object")
    return value


def reference(path: Path) -> dict:
    return {"path": public(path).relative_to(ROOT).as_posix(), "file_sha256": file_hash(path)}


def aware(raw: str) -> datetime:
    value = datetime.fromisoformat(raw)
    require(value.tzinfo is not None and value.utcoffset() is not None, "timestamp must have an explicit timezone")
    return value


def interval(start: str, finish: str) -> None:
    require(aware(start) <= aware(finish), "reversed provenance interval")


def derive(study_path: Path = STUDY, controller_path: Path = CONTROLLER) -> dict:
    study = read(study_path)
    require(study["study_sha256"] == digest({k: v for k, v in study.items() if k != "study_sha256"}), "study seal changed")
    sid = study["study_sha256"]
    run, journal = BASE / "native" / sid / "live", BASE / sid / "live/journal/events.jsonl"
    reports = {name: read(run / "reports/final" / name) for name in ("summary.json", "accounting.json", "protocol.json")}
    summary, accounting, protocol = (reports[name] for name in ("summary.json", "accounting.json", "protocol.json"))
    require(all(reports[name].get("study_sha256", sid) == sid for name in reports), "foreign canonical report")
    canonical_files = {name: reference(run / "reports/final" / name) for name in REPORTS}
    journal_ref = reference(journal)
    events: dict[str, dict] = {"intent": {}, "result": {}}
    previous = None
    with public(journal).open("r", encoding="utf-8") as stream:
        for index, line in enumerate(stream, 1):
            event = json.loads(line)
            require(event["index"] == index and event["previous_event_sha256"] == previous
                    and event["event_sha256"] == digest({k: v for k, v in event.items() if k != "event_sha256"}), "journal chain changed")
            previous = event["event_sha256"]
            if event["kind"] in events:
                slot = event["record"]["slot_id"]
                require(slot not in events[event["kind"]], "duplicate request event")
                events[event["kind"]][slot] = event
    require(set(events["intent"]) == set(events["result"]), "unsettled requests cannot acquire completed display spans")
    rows = []
    assessment_map = {"p3a-assessment-" + digest(item["id"])[:24]: item for item in protocol["assessment_plan"]}
    for parameters in protocol["requests"]:
        slot = parameters["slot_id"]
        intent_event, result_event = events["intent"][slot], events["result"][slot]
        intent, result = intent_event["record"], result_event["record"]
        raw = audit_path(sid, False, slot).as_posix()
        require(raw.startswith("/results/phase3a-h1-integrated-v1/"), "foreign bounded audit path")
        path = ROOT / "runs" / raw.removeprefix("/results/")
        audit = read(path)
        require(digest(audit) == summary["transport_audit_summary"]["audit_sha256"][slot]
                and audit["sha256"] == digest({k: v for k, v in audit.items() if k != "sha256"})
                and audit["terminal_result_sha256"] == parameters["result_sha256"] == digest(result)
                and audit["intent_sha256"] == result["intent_sha256"] == digest(intent)
                and audit["request_sha256"] == parameters["request_sha256"] == intent["request_sha256"] == digest(intent["request"])
                and all(audit[key] == study[key] for key in ("study_sha256", "source_sha256", "policy_sha256", "launcher_sha256")),
                "request/audit/canonical provenance changed")
        require(result["status"] == "response" and result["reserved_micro_usd"] == 0
                and result["response"]["model"] == parameters["returned_model"]
                and all(intent["request"].get(k) == v for k, v in parameters["requested_parameters"].items()),
                "unproved request parameters or known result")
        start, finish = audit["budget"]["started_utc"], audit["finished_utc"]
        interval(start, finish)
        assessment = None
        if result["cell"] == "assessment":
            matches = [item for prefix, item in assessment_map.items() if slot == prefix + ".group" or slot.startswith(prefix + ".quality.")]
            require(len(matches) == 1 and matches[0]["pilot"] == result["pair"], "unmapped native assessment")
            assessment = matches[0]
        rows.append({"slot_id": slot, "pair": result["pair"], "cell": result["cell"], "role": result["role"],
            "arm": assessment["arm"] if assessment else result["cell"].split(":")[1],
            "assessment": assessment, "diagnostic": assessment["diagnostic"] if assessment else False,
            "requested_model": intent["request"]["model"], "returned_model": result["response"]["model"],
            "declared_config": parameters["requested_parameters"], "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"], "spent_micro_usd": result["spent_micro_usd"], "status": result["status"],
            "started_at_utc": start, "finished_at_utc": finish,
            "source": {"audit": reference(path), "audit_record_sha256": digest(audit), "journal": journal_ref,
                "intent_event_index": intent_event["index"], "intent_event_sha256": intent_event["event_sha256"],
                "result_event_index": result_event["index"], "result_event_sha256": result_event["event_sha256"],
                "request_sha256": intent["request_sha256"], "result_record_sha256": digest(result)}})
    require(len(rows) == len(events["result"]) == summary["attempts"] == accounting["known_results"] == 256
            and sum(r["spent_micro_usd"] for r in rows) == summary["spent_micro_usd"] == accounting["spent_micro_usd"] == 7882971
            and sum(r["input_tokens"] for r in rows) == accounting["input_tokens"]
            and sum(r["output_tokens"] for r in rows) == accounting["output_tokens"], "display totals disagree with canonical evidence")
    controller = read(controller_path)
    require(controller["action"] == "provider" and controller["state"] == "exited" and controller["exit_code"] == 0
            and all(controller["preflight"][key] == study[key] for key in BINDINGS), "foreign/incomplete sanitized controller record")
    interval(controller["started_at_utc"], controller["finished_at_utc"])
    require(all(aware(controller["started_at_utc"]) <= aware(row["started_at_utc"])
                and aware(row["finished_at_utc"]) <= aware(controller["finished_at_utc"]) for row in rows), "request outside controller lifetime")
    snapshots = {}
    for checkpoint in ("first-pair", "closure"):
        folder = run / "visibility" / checkpoint / "snapshot"
        manifest = read(folder / "manifest.json")
        payload = reference(folder / "payload.json")
        require(manifest["study_sha256"] == sid and manifest["payload_sha256"] == payload["file_sha256"], "old snapshot changed")
        snapshots[checkpoint] = {"manifest": reference(folder / "manifest.json"), "payload": payload}
    require(canonical_files == {name: reference(run / "reports/final" / name) for name in REPORTS}
            and reference(journal) == journal_ref, "canonical evidence changed while deriving")
    return {"kind": "buddha2-inspect-display-provenance-v1", "source_identities": {k: study[k] for k in BINDINGS},
        "study": reference(study_path), "canonical_files": canonical_files, "old_snapshots": snapshots,
        "old_closure_log": reference(BASE / "visibility-exports" / sid / "live/closure/export-v1/export/logs/closure.eval"),
        "controller": {"source": reference(controller_path), **{k: controller[k] for k in ("started_at_utc", "finished_at_utc", "elapsed_wall_seconds")}},
        "activity": {"first_request_started_at_utc": min(rows, key=lambda row: aware(row["started_at_utc"]))["started_at_utc"],
            "last_request_finished_at_utc": max(rows, key=lambda row: aware(row["finished_at_utc"]))["finished_at_utc"]},
        "requests": rows, "attempts": len(rows), "spent_micro_usd": sum(r["spent_micro_usd"] for r in rows),
        "scientific_complete": summary["scientific_complete"], "timing_basis": "Recorded post-lock admission start and post-cleanup transport finish; not provider server times or file mtimes. Controller lifetime includes setup/key wait/reviews/export.",
        "provider_calls_made_by_derivation": 0, "raw_messages_included": False}


def main() -> None:
    value = derive()
    output = public(OUTPUT, missing=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
