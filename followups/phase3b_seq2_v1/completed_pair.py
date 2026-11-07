"""Read-only certificate for the one completed pair and its assessment supplement."""
from __future__ import annotations

import copy

from buddha2.artifacts import ContractError, digest

from . import accounting, ledger_core, native, transport
from . import assessment_reuse as reuse
from .support import ROOT, checked, file_hash, read, require, seal

KIND = "phase3b-completed-first-pair-v1"
GENERATION = reuse.PARENT_STUDY
EXECUTION = "cac569074f96ac1cd016ab9428f45722ad6818913f255d50408729686bb6a265"
COMPLETION_RECEIPT = "evidence/phase3b-seq2-v1/assessment-only-execution-live-outcome-v1.json"
COMPLETION_RECEIPT_SHA = "08562a4e31ebdbeaba1c37753e88d9684f08709dfbaccf7d1b5dd8935075271f"
PARENT_PATH = "runs/phase3b-seq2-v1/timing-continuation-v1/phase3b-seq2-v1/release/study.json"


def _load() -> tuple[dict, dict]:
    # Reuse the narrow data verifier, never the old source/policy-bound runner.
    plan = reuse._build(ROOT / PARENT_PATH)
    inputs = dict(plan["inputs"])

    def load(name: str) -> dict:
        path = reuse._ordinary(ROOT / name)
        inputs[name] = file_hash(path)
        return read(path)

    receipt = load(COMPLETION_RECEIPT)
    require(inputs[COMPLETION_RECEIPT] == COMPLETION_RECEIPT_SHA
            and receipt["status"] == "assessed"
            and receipt["generation_study_sha256"] == GENERATION
            and receipt["assessment_execution_sha256"] == EXECUTION,
            "completed first-pair receipt differs")
    parent = read(ROOT / PARENT_PATH)
    parent_manifest = read(ROOT / "runs/phase3b-seq2-v1" / GENERATION / "live/journal/manifest.json")
    old_run = f"runs/phase3b-seq2-v1/native/{GENERATION}/live"
    branches = {("p3b-01", arm): checked(load(f"{old_run}/branches/p3b-01-{arm}.json"))
                for arm in ("fixed", "adaptive")}
    pair = checked(load(f"{old_run}/seals/p3b-01.json"))
    readiness = checked(load(f"{old_run}/readiness-review.json"))
    root = f"runs/phase3b-seq2-v1/{EXECUTION}/live/journal"
    manifest = load(root + "/manifest.json")
    event_path = reuse._ordinary(ROOT / root / "events.jsonl")
    inputs[root + "/events.jsonl"] = file_hash(event_path)
    require(inputs[root + "/manifest.json"] == receipt["journal_manifest_file_sha256"]
            and inputs[root + "/events.jsonl"] == receipt["journal_events_file_sha256"]
            and manifest["run_id"] == digest(manifest["inputs"])
            and manifest["inputs"]["study_sha256"] == GENERATION
            and manifest["inputs"]["assessment_execution_sha256"] == EXECUTION
            and manifest["inputs"]["fixture"] is False,
            "completed supplement journal identity differs")
    outcome_path = f"runs/phase3b-seq2-v1/native/{EXECUTION}/live/outcome.json"
    outcome = checked(load(outcome_path))
    require(inputs[outcome_path] == receipt["outcome_file_sha256"]
            and outcome["sha256"] == receipt["outcome_sha256"]
            and outcome["status"] == "assessed" and outcome["fixture"] is False
            and outcome["generation_study_sha256"] == GENERATION
            and outcome["assessment_execution_sha256"] == EXECUTION
            and outcome["generation_calls"] == 0 and outcome["reserved_micro_usd"] == 0
            and outcome["selected_checkpoint"] == pair["selected_checkpoint"] == "c1",
            "completed supplement outcome differs")
    events, tail = ledger_core._read_events(ROOT / root)
    require(not tail and len(events) == 16, "supplement event inventory differs")
    pending = {r["slot_id"]: r for r in plan["worklist"] if r["disposition"] == "pending"}
    old_events, old_tail = ledger_core._read_events(ROOT / "runs/phase3b-seq2-v1" / GENERATION / "live/journal")
    require(not old_tail, "original journal has an incomplete tail")
    intents = {e["record"]["slot_id"]: e["record"] for e in old_events if e["kind"] == "intent"}
    results = {e["record"]["slot_id"]: e["record"] for e in old_events if e["kind"] == "result"}
    for number in range(8):
        intent_event, result_event = events[number * 2:number * 2 + 2]
        intent, result = intent_event["record"], result_event["record"]
        slot = intent["slot_id"]
        require(intent_event["kind"] == "intent" and result_event["kind"] == "result"
                and slot in pending and slot not in intents and slot not in results
                and intent["request"] == pending[slot]["request"]
                and intent == ledger_core._intent(manifest, slot, intent["request"], number + 1)
                and result["status"] == "response"
                and result == ledger_core._result(intent, result["response"], failure=result["failure"]),
                "supplement request, response or accounting differs")
        intents[slot], results[slot] = intent, result
    portfolios = {"fixed": branches["p3b-01", "fixed"]["result"]["portfolio"],
                  **branches["p3b-01", "adaptive"]["result"]["checkpoints"]}
    evaluator = native.Phase3NativeAssessment(ROOT / ".upstream/novelty-bench")
    assessments = {}
    for target in plan["targets"]:
        label, aid = target["target"], target["assessment_id"]
        prefix = evaluator.slot_prefix(aid)
        quality = [results[r["slot_id"]] for r in plan["worklist"]
                   if r["target"] == label and r["role"] == "quality"]
        assessed = evaluator.finalize(portfolios[label], results[prefix + ".group"], quality,
                                      assessment_id=aid)
        require(assessed == outcome["assessments"][label], "completed assessment does not replay exactly")
        assessments[aid] = assessed
    intervals = {}
    slots = {slot: copy.deepcopy(parent["slots"][slot]) for slot in results}
    for slot, result in results.items():
        origin = GENERATION if slot not in pending else EXECUTION
        name = (f"runs/phase3b-seq2-v1/{GENERATION}/live/transport-audit/" if origin == GENERATION
                else f"runs/phase3b-seq2-v1/native/{EXECUTION}/live/transport-audit/")
        name += digest({"slot_id": slot}) + ".json"
        audit = transport.validate_audit(load(name), intent=intents[slot], result=result,
            bindings=manifest["inputs"]["bindings"] if origin == EXECUTION
                else accounting._bindings(parent_manifest))
        require(audit["sdk_invoked"] is True and audit["worker_stopped"] is True
                and not any(audit[key] for key in ("late_known", "cleanup_failed", "owner_stop_required")),
                "completed pair has a non-normal transport disposition")
        intervals[slot] = {"started_at_utc": audit["budget"]["started_utc"],
                           "finished_at_utc": audit["finished_utc"], "audit_file_sha256": inputs[name],
                           **{key: result[key] for key in ("input_tokens", "output_tokens") if key in result}}
    require(len(results) == len(intents) == 361
            and sum(r["spent_micro_usd"] for r in results.values()) == 11_239_856
            and all(r["reserved_micro_usd"] == 0 for r in results.values()),
            "completed first-pair accounting differs")
    buckets: dict[str, dict[str, int]] = {}
    for result in results.values():
        bucket = buckets.setdefault(result["cell"], {"attempts": 0, "spent_micro_usd": 0,
            "reserved_micro_usd": 0, "input_tokens": 0, "output_tokens": 0})
        bucket["attempts"] += 1
        for name in ("spent_micro_usd", "input_tokens", "output_tokens"):
            bucket[name] += result[name]
    record = seal({"kind": KIND, "pilot": "p3b-01", "generation_study_sha256": GENERATION,
        "assessment_execution_study_sha256": EXECUTION,
        "native_evaluator_sha256": digest(evaluator.identity), "inputs": inputs,
        "pair_seal_sha256": pair["sha256"], "outcome_sha256": outcome["sha256"],
        "selected_checkpoint": pair["selected_checkpoint"],
        "assessment_plan": [copy.deepcopy(r) for r in parent["assessment_plan"] if r["pilot"] == "p3b-01"],
        "frozen_original_fixed_candidate_order": copy.deepcopy(parent["fixed_candidate_order"]),
        "accounting": {"provider_calls": 361, "known_spent_micro_usd": 11_239_856,
                       "reserved_micro_usd": 0,
                       "cells": {key: value for key, value in buckets.items() if key != "assessment"},
                       "assessment": buckets["assessment"]},
        "historical_accounting": {"provider_calls": 3189, "known_spent_micro_usd": 90_848_979,
                                  "reserved_micro_usd": 22_880_000},
        "fixture": False, "new_calls_authorized": False})
    require(all(file_hash(ROOT / name) == expected for name, expected in inputs.items()),
            "completed first-pair evidence changed during verification")
    views = {"record": record, "branches": branches, "seals": {"p3b-01": pair},
             "assessments": assessments, "results": results, "intents": intents, "slots": slots,
             "audit_intervals": intervals, "readiness": readiness,
             "supplement_slots": list(pending),
             "accounting": record["accounting"], "origin": {key: record[key] for key in (
                 "generation_study_sha256", "assessment_execution_study_sha256", "native_evaluator_sha256")}}
    return record, views


def certificate() -> dict:
    """Return metadata only; neither the old runner nor a provider is constructed."""
    return _load()[0]


def verify_certificate(record: dict) -> dict:
    require(checked(record).get("kind") == KIND, "unknown completed-pair certificate")
    actual, views = _load()
    require(record == actual, "completed-pair certificate differs from original evidence")
    return views


def join(study: dict, saved: dict) -> dict:
    """Join already-verified report evidence without rebinding any original record."""
    imported = saved.get("completed_first_pair")
    if "imported_first_pair" not in study:
        require(imported is None, "undeclared completed first pair")
        return saved
    if not isinstance(imported, dict):
        raise ContractError("missing verified completed first pair")
    require(imported.get("record") == study["imported_first_pair"]
            and checked(imported["record"])["kind"] == KIND, "missing verified completed first pair")
    result = dict(saved)
    for name in ("branches", "seals", "assessments", "audit_intervals"):
        current = saved.get(name, {})
        require(not set(current).intersection(imported[name]), "new evidence replaces the completed first pair")
        result[name] = {**imported[name], **current}
    return result
