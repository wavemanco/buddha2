"""Prepare an immutable assessment supplement; never dispatch or reopen a ledger."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from buddha2.artifacts import digest, public_path_parts, write_once

from . import ledger_core, native, support
from .support import BASE, ROOT, checked, file_hash, read, require, safe, seal

PARENT_STUDY = "237db1d3b85408696a945ede1220c99c61ae80ae4e3e32b23065089a13596623"
PARENT_OUTCOME_SHA = "5def145eda347de9d321eba93ecbce072838c2c941f60400b3eeaa67161b6f92"
PAIR_SEAL_SHA = "ef12bd486b184a978e8e7c84fdb212e95862f7dbdb3a5c93bea875613903286b"
READINESS_SHA = "0d49531225d2444c1136a399e9516a7d501e9d4a2acbdaaa83cc9b2a15b470dd"
KIND = "buddha2-assessment-reuse-plan-v1"


def _ordinary(value: Path) -> Path:
    value = Path(value)
    public_path_parts(value.parts)
    return safe(value if value.is_absolute() else ROOT / value)


def _build(study_path: Path) -> dict:
    inputs: dict[str, str] = {}

    def load(value: Path) -> dict:
        value = _ordinary(value)
        inputs[value.relative_to(ROOT).as_posix()] = file_hash(value)
        return read(value)

    study_path = _ordinary(study_path)
    study = load(study_path)
    require(study.get("study_sha256") == PARENT_STUDY
            == digest({k: v for k, v in study.items() if k != "study_sha256"}),
            "reuse requires the approved closed generation study")
    outcome_path = ROOT / "evidence/phase3b-seq2-v1/timing-continuation-live-outcome-v1.json"
    outcome = load(outcome_path)
    require(file_hash(outcome_path) == PARENT_OUTCOME_SHA
            and outcome["study_sha256"] == PARENT_STUDY
            and outcome["outcome"]["status"] == "incomplete",
            "closed outcome identity differs")
    certificate_path = ROOT / "runs/phase3b-seq2-v1/timing-continuation-v1/forensic-replay-v1/independent-outcome-review-v1.json"
    certificate = load(certificate_path)
    require(file_hash(certificate_path) == outcome["evidence_receipt_sha256"]["independent_outcome_review"],
            "parent data certificate differs")
    journal = ROOT / "runs/phase3b-seq2-v1" / PARENT_STUDY / "live/journal"
    for name, expected in certificate["actual_journal_sha256"].items():
        require(name in {"events.jsonl", "manifest.json"}, "foreign journal reference")
        target = _ordinary(journal / name)
        require(file_hash(target) == expected, "original journal changed")
        inputs[target.relative_to(ROOT).as_posix()] = expected
    manifest = read(journal / "manifest.json")
    require(manifest["run_id"] == digest(manifest["inputs"])
            and manifest["inputs"]["study_sha256"] == PARENT_STUDY
            and manifest["inputs"]["fixture"] is False, "parent manifest differs")
    for name in ("src/buddha2/phase2_native.py", "followups/phase3a_v1/native.py"):
        require(file_hash(ROOT / name) == study["source"]["files"][name],
                "evaluator replay compatibility needs review")
    events, tail = ledger_core._read_events(journal)
    require(not tail and events[-1]["kind"] == "halt"
            and events[-1]["record"]["reason"] == "strategy/native request exceeds preserved payload admission",
            "parent is not the closed evaluator-admission failure")
    intents, results, intent_indices = {}, {}, {}
    for event in events:
        row = event["record"]
        if event["kind"] == "intent":
            require(row["slot_id"] not in intents, "duplicate original intent")
            intents[row["slot_id"]] = row
            intent_indices[row["slot_id"]] = event["index"]
        elif event["kind"] == "result":
            slot = row["slot_id"]
            require(slot in intents and slot not in results
                    and row["intent_sha256"] == digest(intents[slot])
                    and row["status"] == "response", "unresolved or foreign original result")
            results[slot] = row
    require(len(intents) == len(results) == 353, "parent request inventory differs")
    run = ROOT / "runs/phase3b-seq2-v1/native" / PARENT_STUDY / "live"
    pair = checked(load(run / "seals/p3b-01.json"))
    require(pair["sha256"] == PAIR_SEAL_SHA and pair["study_sha256"] == PARENT_STUDY,
            "original pair seal differs")
    prefix = pair["journal_prefix"]
    require(events[prefix["index"] - 1]["event_sha256"] == prefix["event_sha256"],
            "generation was not sealed at its original journal prefix")
    branches = {arm: checked(load(run / f"branches/p3b-01-{arm}.json"))
                for arm in ("fixed", "adaptive")}
    for arm, branch in branches.items():
        require(branch["sha256"] == pair["branches"][arm]
                and branch["fixture"] is False and branch["result"]["status"] == "complete"
                and digest(branch["result"]["portfolio"]) == pair["finals"][arm],
                "original sealed generation differs")
    readiness = checked(load(run / "readiness-review.json"))
    require(readiness["sha256"] == READINESS_SHA and readiness["passed"] is True
            and readiness["fixture"] is False
            and readiness["branch_sha256"] == branches["adaptive"]["sha256"],
            "original native readiness differs")
    portfolios = {"fixed": branches["fixed"]["result"]["portfolio"],
                  **branches["adaptive"]["result"]["checkpoints"]}
    require(set(portfolios) == {"fixed", "c1", "c2"}
            and all(digest(portfolios[t]) == pair["checkpoints"][t] for t in ("c1", "c2")),
            "original checkpoint identities differ")
    evaluator = native.Phase3NativeAssessment(ROOT / ".upstream/novelty-bench")
    worklist, targets, complete, consumed = [], [], {}, set()
    for row in (r for r in study["assessment_plan"] if r["pilot"] == "p3b-01"):
        label, assessment_id = row["target"], row["id"]
        portfolio = portfolios[label]
        native_prefix = evaluator.slot_prefix(assessment_id)
        group_slot = native_prefix + ".group"
        grouped = results[group_slot]
        partition = evaluator.fold_group(portfolio, grouped, assessment_id=assessment_id)["partition"]
        requests = [(group_slot, "group", evaluator.group_request(portfolio))]
        requests.extend((f"{native_prefix}.quality.{head:02d}", "quality", body)
                        for head, body in zip(evaluator.modules["score"].heads(partition),
                                             evaluator.quality_requests(portfolio, partition), strict=True))
        retained = []
        for slot, role, body in requests:
            ledger_core.validate_request(role, body)
            item = {"slot_id": slot, "role": role, "target": label,
                    "request_sha256": digest(body)}
            if slot in results:
                intent, result = intents[slot], results[slot]
                require(intent_indices[slot] > prefix["index"] and intent["request"] == body
                        and intent["request_sha256"] == digest(body)
                        and ledger_core._result(intent, result["response"], failure=result["failure"]) == result,
                        "saved judgment request or accounting differs")
                response = evaluator._response(result, slot, role, body, portfolio)
                if role == "quality":
                    message = SimpleNamespace(stop_reason=response.get("stop_reason"),
                        content=[SimpleNamespace(type="text", text=response["text"])])
                    evaluator.modules["judge"].parse_message(message, evaluator.modules["score"].Score)
                    parsed = evaluator._strict_object(response["text"], evaluator.modules["score"].Score)
                    require(1 <= parsed.score <= 10, "cached quality is out of range")
                item.update(disposition="reuse", result_sha256=digest(result))
                retained.append(result)
                consumed.add(slot)
            else:
                item.update(disposition="pending", request=body)
            worklist.append(item)
        if len(retained) == len(requests):
            previous = load(run / "assessments" / (native_prefix + ".json"))
            require(previous == evaluator.finalize(portfolio, retained[0], retained[1:],
                                                   assessment_id=assessment_id),
                    "complete cached assessment does not replay exactly")
            complete[label] = digest(previous)
        targets.append({"target": label, "assessment_id": assessment_id,
                        "portfolio_sha256": digest(portfolio)})
    expected = {slot for slot, row in results.items() if row["role"] in {"group", "quality"}}
    pending = [r for r in worklist if r["disposition"] == "pending"]
    require(consumed == expected and len(consumed) == 25 and len(pending) == 8
            and set(complete) == {"fixed", "c1"}
            and all(r["role"] == "quality" and r["target"] == "c2" for r in pending),
            "assessment-only reuse inventory differs")
    require(all(file_hash(ROOT / name) == expected for name, expected in inputs.items()),
            "parent inputs changed during preparation")
    return {"kind": KIND, "parent_study_path": study_path.relative_to(ROOT).as_posix(),
            "generation_study_sha256": PARENT_STUDY, "source_sha256": support.source_identity()["sha256"],
            "native_evaluator_sha256": digest(evaluator.identity), "parent_status": "incomplete",
            "selected_checkpoint": pair["selected_checkpoint"], "inputs": inputs, "targets": targets,
            "worklist": worklist, "complete_cached_assessments": complete,
            "reused_results": 25, "pending_requests": 8, "live_execution_allowed": False,
            "generation_calls_required": 0, "provider_calls": 0}


def _summary(packet: dict, path: Path) -> dict:
    return {"packet_sha256": packet["sha256"], "packet_path": str(path),
            "reused_results": packet["reused_results"], "pending_requests": packet["pending_requests"],
            "complete_cached_assessments": len(packet["complete_cached_assessments"]),
            "provider_calls": 0, "live_execution_allowed": False}


def prepare(study_path: Path, output: Path) -> dict:
    support.runtime_guard()
    output = _ordinary(output)
    require(output.parent == BASE / "assessment-reuse" and not output.exists(),
            "reuse preparation requires a fresh assessment-reuse output directory")
    packet = seal(_build(study_path))
    output.mkdir(parents=True, exist_ok=False)
    target = output / "assessment-reuse.json"
    write_once(target, packet)
    return _summary(packet, target)


def verify(packet_path: Path) -> dict:
    support.runtime_guard()
    target = _ordinary(packet_path)
    require(target.name == "assessment-reuse.json" and target.parent.parent == BASE / "assessment-reuse",
            "foreign reuse packet path")
    packet = checked(read(target))
    require(packet.get("kind") == KIND and packet.get("source_sha256") == support.source_identity()["sha256"],
            "reuse packet source or kind differs")
    require(packet == seal(_build(_ordinary(Path(packet["parent_study_path"])))),
            "reuse packet differs from its unchanged original evidence")
    return _summary(packet, target)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--study", type=Path)
    source.add_argument("--packet", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    require((args.study is not None) == (args.output is not None), "preparation requires --output; verification does not")
    result = prepare(args.study, args.output) if args.study is not None else verify(args.packet)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0
