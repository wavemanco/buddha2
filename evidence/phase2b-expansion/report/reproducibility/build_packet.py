"""One-off stdlib-only packaging of closed, saved Phase 2B evidence; no inference."""
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sys
import zipfile


IMAGE = "sha256:585a5539c6091592258ec19d0bf8e216b189405f95766b167df0d2e88e251366"
STUDY = "38132ee3a935af4ac975c3fda84154d1a85b1bcb510925f409993a15d3103d8b"
ROOT, RESULTS = Path("/workspace"), Path("/results")
PUBLIC = RESULTS / "phase2-release-r018/reports/live-full"
REPLAY = RESULTS / "phase2-release-r018/reports/live-full-replay"
RUN = RESULTS / f"phase2-release-r018/{STUDY}/live"
OUTPUT = RESULTS / "phase2b-expansion/report"
LAUNCH = RESULTS / "phase2-release-r018/launcher"
STEM = "fb73008b1a264f3db04c1aa0cadb7c8b"
PUBLIC_NAMES = ("PHASE2_REPORT.md", "summary.json", "native_assessment.json",
                "execution.json", "decision.json", "coverage.json", "analysis.json")
SNAPSHOT_NAMES = ("analysis", "complete", "coverage", "decision", "execution", "failures",
                  "native_assessment", "recoverable_exports", "state", "summary")
OMITTED = ("temperature", "top_p", "top_k", "seed", "max_tokens", "max_completion_tokens",
           "reasoning_effort", "service_tier", "inference_geo", "thinking", "output_config")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def blocked(*args, **kwargs):
    raise RuntimeError("network construction forbidden in evidence packaging")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bounded(path):
    require(path.is_absolute() and (path.is_relative_to(ROOT) or path.is_relative_to(RESULTS)),
            "input outside fixed new-project mounts")
    require(not any(part.is_symlink() for part in (path, *path.parents)), "linked input")
    return path


def read(path):
    return json.loads(bounded(path).read_text(encoding="utf-8"))


def check_seal(value, key):
    require(value[key] == digest({k: v for k, v in value.items() if k != key}), "saved seal differs")


def credential_free(value):
    if isinstance(value, dict):
        require(not set(k.lower() for k in value).intersection({
            "api_key", "apikey", "anthropic_api_key", "openai_api_key", "authorization",
            "credential_fingerprints", "access_token", "refresh_token", "private_key"}),
            "credential field outside whitelist")
        for item in value.values():
            credential_free(item)
    elif isinstance(value, list):
        for item in value:
            credential_free(item)


def safe_bytes(name, value):
    require(not re.search(rb"(?<![A-Za-z0-9_])sk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}", value),
            "recognizable credential token outside whitelist")
    require(not re.search(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", value),
            "private-key pattern outside whitelist")
    if name.endswith(".json"):
        credential_free(json.loads(value))
    elif name.endswith(".jsonl"):
        for line in value.decode("utf-8").splitlines():
            if line:
                credential_free(json.loads(line))


def write_bytes(name, value):
    path = OUTPUT / name
    require(path.is_relative_to(OUTPUT) and ".." not in Path(name).parts, "invalid member")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(value)


def main():
    require(len(sys.argv) == 2, "supply this attempt's sanitized runtime inspection path")
    require(sys.version_info[:3] == (3, 12, 15) and os.environ.get("BUDDHA2_IMAGE_ID") == IMAGE,
            "requires pinned runtime")
    require({p.name for p in Path("/sys/class/net").iterdir()} == {"lo"}, "requires network none")
    socket.socket = blocked
    socket.create_connection = blocked
    require(not any(name.split(".")[0] in {"anthropic", "openai", "buddha2"}
                    for name in sys.modules), "unexpected SDK/project import")
    require(not bounded(OUTPUT).exists(), "fresh output namespace required")
    study_path = RESULTS / "phase2-release-r018/release/study.json"
    study, summary, coverage = read(study_path), read(PUBLIC / "summary.json"), read(PUBLIC / "coverage.json")
    require(study["study_sha256"] == summary["study_sha256"] == STUDY and not summary["fixture"],
            "wrong saved study or fixture")
    require(summary["attempts"] == 991 and summary["spent_micro_usd"] == 5983504
            and summary["reserved_micro_usd"] == 0 and summary["missing_assessments"] == 4,
            "closed outcome differs from this report recipe")
    public = {name: bounded(PUBLIC / name).read_bytes() for name in PUBLIC_NAMES}
    require(all(bounded(REPLAY / name).read_bytes() == value for name, value in public.items()),
            "native full/replay report differs")
    raw, originals = {}, {}

    def include(path, name):
        value = bounded(path).read_bytes()
        require(name not in raw, "duplicate archive member")
        safe_bytes(name, value)
        raw[name], originals[path] = value, value

    include(study_path, "raw/study.json")
    include(Path(__file__), "reproducibility/build_packet.py")
    runtime_path = bounded(Path(sys.argv[1]))
    runtime = read(runtime_path)
    require(runtime["image"] == IMAGE and runtime["network_mode"] == "none"
            and runtime["read_only_rootfs"] is True, "packaging runtime inspection differs")
    include(runtime_path, "reproducibility/runtime-inspection.json")
    for name in PUBLIC_NAMES:
        include(PUBLIC / name, "public-report/" + name)
    for name in ("manifest.json", "study.json", "events.jsonl"):
        include(RUN / "journal" / name, "raw/run/journal/" + name)
    for directory, pattern in (("journal/authority", "*.grant.json"), ("journal/reviews", "*.json"),
                               ("failures", "*.json"), ("portfolios", "*.json"), ("assessments", "*.json")):
        for path in sorted((RUN / directory).glob(pattern)):
            include(path, "raw/run/" + path.relative_to(RUN).as_posix())
    for definition in study["worklist"]["outputs"]:
        for name in ("generations.jsonl", "identities.json"):
            path = RUN / "native" / definition["order_id"] / name
            if path.is_file():
                include(path, "raw/run/" + path.relative_to(RUN).as_posix())
    snapshot = RUN / "snapshots" / summary["snapshot_sha256"]
    for name in SNAPSHOT_NAMES:
        include(snapshot / (name + ".json"), "raw/run/snapshots/" + summary["snapshot_sha256"] + "/" + name + ".json")
    for name in ("preflight-container", "preflight", "inspection-draft", "inspection", "result"):
        include(LAUNCH / f"{STEM}.{name}.json", f"launch-records/{name}.json")
    host = read(LAUNCH / f"{STEM}.result.json")
    require(host["stage"] == "expansion" and host["action"] == "provider" and host["exit_code"] == 0,
            "wrong sanitized launch result")
    grant_path = RESULTS / Path(host["preflight"]["grant_path"]).relative_to("/results")
    include(grant_path, "launch-records/grant.json")
    events_bytes = originals[RUN / "journal/events.jsonl"]
    require(events_bytes.endswith(b"\n"), "partial saved journal tail")
    events = [json.loads(line) for line in events_bytes.decode("utf-8").splitlines()]
    intents, results, previous = {}, {}, None
    for position, event in enumerate(events, 1):
        check_seal(event, "event_sha256")
        require(event["index"] == position and event["previous_event_sha256"] == previous
                and event["kind"] == ("intent" if position % 2 else "result"), "journal chain differs")
        previous = event["event_sha256"]
        target = intents if event["kind"] == "intent" else results
        slot = event["record"]["slot_id"]
        require(slot not in target, "duplicate saved slot")
        target[slot] = event
    require(len(intents) == len(results) == 991, "unresolved or different attempt count")
    slots, settings = [], {}
    costs, counts = collections.Counter(), collections.Counter()
    for position, (slot, definition) in enumerate(study["worklist"]["slots"].items(), 1):
        intent, result = intents.get(slot), results.get(slot)
        row = {"worklist_position": position, "slot_id": slot, **definition,
               "coverage": coverage["slots"][slot], "attempt": None,
               "intent": None, "result": None}
        if intent is not None:
            i, r = intent["record"], result["record"]
            require(r["intent_sha256"] == digest(i) and r["status"] == "response"
                    and r["reserved_micro_usd"] == 0, "unknown/nonaccounted saved result")
            role, request, response = i["role"], i["request"], r["response"]
            for kind, event in (("intent", intent), ("result", result)):
                row[kind] = {"path": "raw/run/journal/events.jsonl", "line": event["index"],
                             "event_sha256": event["event_sha256"], "record_sha256": digest(event["record"])}
            row.update(attempt=(intent["index"] + 1) // 2, returned_model=response["model"],
                       result_status=r["status"], spent_micro_usd=r["spent_micro_usd"],
                       reserved_micro_usd=r["reserved_micro_usd"])
            controls = {k: v for k, v in request.items() if k not in ("messages", "system")}
            key = digest({"role": role, "controls": controls})
            group = settings.setdefault(key, {"role": role, "requested_settings": controls,
                "omitted_controls": [name for name in OMITTED if name not in request],
                "attempts": 0, "returned_models": set(), "returned_stop_reasons": set()})
            group["attempts"] += 1
            group["returned_models"].add(response["model"])
            group["returned_stop_reasons"].add(response["stop_reason"])
            counts[role] += 1
            costs[role] += r["spent_micro_usd"]
        slots.append(row)
    require(len(slots) == 1320 and len(settings) == 5 and sum(costs.values()) == 5983504,
            "slot/settings/cost coverage differs")
    settings = [{**value, "returned_models": sorted(value["returned_models"]),
                 "returned_stop_reasons": sorted(value["returned_stop_reasons"])}
                for value in settings.values()]
    portfolio_index = {}
    for definition in study["worklist"]["outputs"]:
        path = RUN / definition["portfolio_path"]
        if path.is_file():
            portfolio_index[(definition["task_id"], definition["repeat"], definition["method"])] = read(path)
    failures = [read(path) for path in sorted((RUN / "failures").glob("*.json"))]
    orders = []
    for definition in study["worklist"]["outputs"]:
        key = definition["task_id"], definition["repeat"], definition["method"]
        portfolio = portfolio_index.get(key)
        assessment_path = RUN / definition["assessment_path"]
        assessment = read(assessment_path) if assessment_path.is_file() else None
        order = {**definition, "status": coverage["orders"][definition["order_id"]],
                 "portfolio": None, "assessment": None, "metrics": None,
                 "partition": None, "generation_scores": None, "response_ids": None,
                 "original_B_positions_1_based": None,
                 "failure_records": [row for row in failures if row["task_id"] == key[0]
                                     and row["repeat"] == key[1] and key[2] == "C"]}
        if portfolio is not None:
            order["portfolio"] = "raw/run/" + definition["portfolio_path"]
            order["response_ids"] = [r["id"] for r in portfolio["responses"]]
            if key[2] == "C":
                parent = portfolio_index[(key[0], key[1], "B")]["responses"]
                require({r["id"]: r for r in parent} == {r["id"]: r for r in portfolio["responses"]},
                        "C changed its saved B texts")
                positions = {r["id"]: i for i, r in enumerate(parent, 1)}
                order["original_B_positions_1_based"] = [positions[r["id"]] for r in portfolio["responses"]]
        if assessment is not None:
            order.update(assessment="raw/run/" + definition["assessment_path"], metrics=assessment["metrics"],
                         partition=assessment["native"]["partition_fields"]["partition"],
                         generation_scores=assessment["native"]["fields"]["generation_scores"])
        orders.append(order)
    require(len(orders) == 72 and len(portfolio_index) == 68 and len(failures) == 4,
            "saved order inventory differs")
    state = read(snapshot / "state.json")
    require(state["status"] == "ready" and state["reserved_micro_usd"] == 0 and state["retries"] == 0,
            "unreconciled saved accounting")
    index = {"kind": "phase2b-full-pilot-evidence-index-v1", "study_sha256": STUDY,
             "fixture": False, "cutoff": summary["cutoff"], "summary": summary,
             "slot_coverage": dict(collections.Counter(r["coverage"] for r in slots)),
             "order_coverage": dict(collections.Counter(r["status"] for r in orders)),
             "actual_request_counts": dict(counts), "unique_cost_micro_usd_by_role": dict(costs),
             "slots": "slot-outcomes.json", "orders": "orders.json", "settings": "settings.json",
             "raw_journal": "raw/run/journal/events.jsonl", "public_report": "public-report/",
             "snapshot_sha256": summary["snapshot_sha256"], "new_provider_calls": 0,
             "new_sdk_constructions": 0, "new_credential_reads": 0,
             "limitations": ["Saved visible canonical records are not full SDK objects or thinking blocks.",
                 "Missing C outcomes stay missing; no repair, replacement, replay inference or new calls.",
                 "Whole-study decision remains inconclusive; package creates no new scientific selection.",
                 "Conservative public-price accounting is not independent invoice reconciliation.",
                 "Frozen summary.status is first-block-complete; full-run coverage is indexed explicitly."]}
    derived = {"pilot-data.json": index, "slot-outcomes.json": slots, "orders.json": orders,
               "settings.json": settings}
    for name, value in derived.items():
        raw[name] = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode("utf-8") + b"\n"
    raw["README.md"] = ("# Phase 2B saved full-pilot evidence\n\n"
        "991 known accounted requests; 68 scored orders and four invalid-rank C orders. "
        "The frozen whole-study decision is inconclusive; no seed is selected.\n\n"
        "Start with pilot-data.json, slot-outcomes.json, orders.json and settings.json. "
        "Each attempted slot links to exact journal line/event/record hashes; requests, visible outputs, "
        "usage and accounting remain in raw/run/journal/events.jsonl. Complete text orders and "
        "native exchanges/assessments, four failures, final snapshot, staged authority/review, "
        "sanitized expansion launch records and native public reports are retained byte-for-byte.\n\n"
        "Reporting uses only stdlib, blocked sockets and the pinned network-none image. No inference, "
        "SDK construction, credential lookup, repair or changed scoring occurs. Credential-binding "
        "material, fingerprints, host environment values, provider streams and locks are excluded.\n").encode("utf-8")
    for name, value in raw.items():
        safe_bytes(name, value)
    ready = read(RESULTS / "phase2-release-r018/release/release-readiness.json")
    frozen = {ROOT / name: expected for name, expected in ready["evidence"].items()}
    frozen.update({ROOT / "src/buddha2" / name: expected for name, expected in study["package_files"].items()})
    frozen[ROOT / "phase2-release.ps1"] = study["launcher_sha256"]
    require(all(file_hash(bounded(path)) == expected for path, expected in frozen.items()), "frozen source differs")
    OUTPUT.mkdir(parents=True, exist_ok=False)
    for name, value in raw.items():
        write_bytes(name, value)
    manifest = {"kind": "phase2b-full-report-manifest-v1", "study_sha256": STUDY,
                "recipe_sha256": file_hash(Path(__file__)),
                "files": {name: hashlib.sha256(value).hexdigest() for name, value in sorted(raw.items())},
                "raw_scope": "whitelisted saved canonical visible evidence; no credentials/fingerprints/env/streams/locks",
                "new_provider_calls": 0, "new_sdk_constructions": 0, "new_credential_reads": 0}
    write_bytes("manifest.json", json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n")
    members = {name: (OUTPUT / name).read_bytes() for name in (*raw, "manifest.json")}
    archive_path = OUTPUT / "phase2b-report.zip"
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, value in sorted(members.items()):
            archive.writestr(name, value)
    with zipfile.ZipFile(archive_path) as archive:
        require(archive.testzip() is None and len(archive.namelist()) == len(members)
                and set(archive.namelist()) == set(members)
                and all(archive.read(name) == value for name, value in members.items()), "ZIP inventory/bytes/CRC differ")
    require(all(path.read_bytes() == value for path, value in originals.items())
            and all(file_hash(path) == expected for path, expected in frozen.items()), "source evidence changed")
    require(not any(name.split(".")[0] in {"anthropic", "openai", "buddha2"} for name in sys.modules),
            "unexpected SDK/project import")
    check = {"kind": "phase2b-full-report-package-check-v1", "status": "pass", "members": len(members),
             "archive_sha256": file_hash(archive_path), "manifest_sha256": file_hash(OUTPUT / "manifest.json"),
             "source_evidence_unchanged": True, "public_full_replay_byte_exact": True,
             "frozen_source_hashes_checked": len(frozen), "slots": len(slots), "orders": len(orders),
             "attempts": len(intents), "known_results": len(results), "scored_orders": 68,
             "missing_invalid_rank_orders": 4, "cost_micro_usd": sum(costs.values()),
             "reserved_micro_usd": 0, "unknown_outcomes": 0,
             "bounded_secret_check": "structured credential fields and recognizable token prefixes only",
             "provider_calls": 0, "sdk_constructions": 0, "credential_reads": 0,
             "runtime_image": IMAGE, "network": "none", "sockets_blocked": True}
    write_bytes("package-check.json", json.dumps(check, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n")
    print(json.dumps(check, ensure_ascii=False))


if __name__ == "__main__":
    main()
