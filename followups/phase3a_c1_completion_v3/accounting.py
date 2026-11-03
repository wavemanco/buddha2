"""Fresh completion scope around the unchanged, durable Phase 3A ledger core.

The live journal retains the core's literal storage prefix with a NEW study SHA.
This does not reuse any stopped R2 journal, authority, claim or result identity.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Callable

from buddha2.artifacts import ContractError, digest
from followups.phase3a_v1 import accounting as core

from . import transport as bounded
from .deadline import Budget, KnownDeadlineStop, OwnerStopRequired

PREFIX = "phase3a-c1-completion-v3"
POLICY = copy.deepcopy(core.POLICY)
PAIRS, ROLES, CHECKS, IMAGE_ID = core.PAIRS, core.ROLES, core.CHECKS, core.IMAGE_ID
AuthorityError, IntegrityStop, LiabilityStop = core.AuthorityError, core.IntegrityStop, core.LiabilityStop
CellBudgetStop, CheckpointStop = core.CellBudgetStop, core.CheckpointStop
AssessmentBudgetStop, PhaseBudgetStop = core.AssessmentBudgetStop, core.PhaseBudgetStop
validate_request, runtime_guard = core.validate_request, core.runtime_guard
RETIRED_STUDIES = frozenset({
    "1628a958477de938f55bd925cfa08150a1067ef8233ae937ae79e9bcbbcfe42a",
    "44d12d6ff196a9481bd6106541ad62d8161fff50fa7a1fd6eef899df4f627012",
    "17f35cf72cad95351e726cd9f02824be78db35a0a16c3f83db9e7bae9d762032",
    "1e7edf24a9ac3dff4735c8d7af2b5843d86278830d697b2b8260a6da8528de57",
    "28519e20cf71fbf599f6f21a5c2c3b275fbc9c24ffedf4df2041d49816e8eb62",
})
HISTORICAL = {"known_micro_usd": 12_231_444, "reserved_micro_usd": 22_880_000,
              "provider_calls": 885, "known_responses": 883, "unknown_responses": 2}
Validator = Callable[[dict], None]


class ReadinessStop(ContractError):
    """A known, durably recorded readiness failure; no request was admitted."""


def _require(condition: Any, message: str) -> None:
    if not condition:
        raise ContractError(message)


def canonical_journal(study_sha256: str, fixture: bool) -> Path:
    _require(core._hash(study_sha256) and study_sha256 not in RETIRED_STUDIES and type(fixture) is bool,
             "completion requires a fresh exact study identity and explicit mode")
    prefix = PREFIX if fixture else "phase3a-r2-v1"
    return Path("/results") / prefix / study_sha256 / ("mock" if fixture else "live") / "journal"


def _journal(path: Path) -> Path:
    path = Path(path)
    _require(len(path.parts) == 6 and path.parts[:2] == ("/", "results")
             and path.parts[-1] == "journal" and path.parts[-2] in {"mock", "live"},
             "completion journal does not have its exact canonical path")
    _require(path == canonical_journal(path.parts[-3], path.parts[-2] == "mock"),
             "completion journal escaped its declared fresh study/mode")
    return path


def validate_authority(study_sha256: str, authority: dict, fixture: bool = False,
                       bindings: dict | None = None) -> None:
    canonical_journal(study_sha256, fixture)
    if not isinstance(bindings, dict):
        raise ContractError("completion authority requires complete source/policy/launcher bindings")
    core.validate_authority(study_sha256, authority, fixture=fixture, bindings=bindings)
    _require(bindings["policy_sha256"] == digest(POLICY), "completion policy binding differs from the delegated core")
    _require(bindings["source_sha256"] not in {
        "a3b9403d6bc0a144d0bb74e74a330ccf057850da0d23dcb2d9059d94a20883e3",
        "e2471ad9e38171cabc2d32615bac797739f378c3f6c7ebc64f8b95f8632d9d26",
        "33cc36cb56fa75b6b427add09934a943515dd40e57cccfb4d4cfcb92a8b4bc1c",
    }, "a closed R2/completion source cannot authorize this fresh study")


def journal_identity(*, study_sha256: str, slots: dict, authority: dict, fixture: bool,
                     bindings: dict, editor_tools: dict | None = None) -> str:
    validate_authority(study_sha256, authority, fixture, bindings)
    return core.journal_identity(study_sha256=study_sha256, slots=slots, authority=authority,
        fixture=fixture, bindings=bindings, editor_tools=editor_tools)


def _bindings(manifest: dict) -> dict:
    return {"study_sha256": manifest["inputs"]["study_sha256"], **manifest["inputs"]["bindings"]}


def _stop(journal: Path, manifest: dict, state: dict, events: list) -> dict | None:
    target = journal / "deadline-stop.json"
    if not target.exists():
        return None
    record = core.read_json(target)
    _require(isinstance(record, dict) and record.get("sha256") == digest({k: v for k, v in record.items() if k != "sha256"})
             and record.get("kind") == "phase3a-r2-deadline-stop-v1" and record.get("bindings") == _bindings(manifest)
             and record.get("fixture") is manifest["inputs"]["fixture"]
             and record.get("reason") in {"pre_intent_deadline", "known_late_response", "known_cleanup_failed", "unknown_terminal"},
             "foreign/invalid durable deadline stop")
    slot = record["slot_id"]
    _require(slot in manifest["inputs"]["slots"], "deadline stop names an undeclared slot")
    intent = state["intents"].get(slot)
    if record["intent_sha256"] is not None:
        _require(intent is not None and record["intent_sha256"] == digest(intent), "deadline stop intent differs")
    result = state["results"].get(slot)
    durable = any(e["kind"] == "result" and e["record"]["slot_id"] == slot for e in events)
    if durable and result is not None and record["candidate_result_sha256"] is not None:
        _require(record["candidate_result_sha256"] == digest(result), "deadline result differs from its prior stop latch")
    return record


def _audit(journal: Path, manifest: dict, state: dict, *, strict: bool) -> dict:
    rows, failures = {}, []
    for slot, result in state["results"].items():
        intent = state["intents"][slot]
        try:
            rows[slot] = bounded.read_audit(manifest["inputs"]["study_sha256"], manifest["inputs"]["fixture"], slot,
                intent=intent, result=result, bindings=_bindings(manifest))
        except (ContractError, OSError, ValueError, TypeError, KeyError):
            failures.append(slot)
    if strict:
        _require(not failures, "missing/invalid committed transport audit blocks continuation")
    return {"validated_audits": len(rows), "missing_or_invalid_slots": sorted(failures),
        "SDK_invoked": sum(r["sdk_invoked"] is True for r in rows.values()) if not failures else None,
        "SDK_invocation_unknown": sum(r["sdk_invoked"] is None for r in rows.values()) if not failures else None,
        "late_known": sum(bool(r["late_known"]) for r in rows.values()) if not failures else None,
        "owner_stop_required": sum(bool(r["owner_stop_required"]) for r in rows.values()) if not failures else None,
        "audit_sha256": {slot: digest(row) for slot, row in sorted(rows.items())}}


def replay(journal: Path) -> dict:
    journal = _journal(journal)
    state, records, manifest = core._replay(journal)
    stop = _stop(journal, manifest, state, records)
    audit = _audit(journal, manifest, state, strict=False)
    state["core_status"] = state["status"]
    state["deadline_stop"] = stop
    state["transport_audit_summary"] = audit
    durable = {e["record"]["slot_id"] for e in records if e["kind"] == "result"}
    state["active_unsettled_intents"] = sorted(set(state["intents"]) - durable)
    state["durable_unknown_results"] = sum(state["results"][s]["status"] != "response" for s in durable)
    if stop is not None and state["status"] != "blocked-unknown":
        state["status"] = "stopped-known-deadline"
    elif audit["missing_or_invalid_slots"] and state["status"] == "ready":
        state["status"] = "halted-transport-audit"
    return state


def raw_state(state: dict) -> dict:
    """Keep frozen state-hash/event arithmetic independent of new report metadata."""
    result = {k: copy.deepcopy(v) for k, v in state.items() if k not in {
        "core_status", "deadline_stop", "transport_audit_summary", "active_unsettled_intents", "durable_unknown_results"}}
    if "core_status" in state:
        result["status"] = state["core_status"]
    return result


def events(journal: Path) -> list[dict]:
    return core.events(_journal(journal))


def publish_review(journal: Path, record: dict, *, validate_evidence: Callable[[dict, dict], None]) -> dict:
    return core.publish_review(_journal(journal), record, validate_evidence=validate_evidence)


def close_first_assessments(journal: Path, record: dict, *, validate_evidence: Callable[[dict, dict], None]) -> dict:
    return core.close_first_assessments(_journal(journal), record, validate_evidence=validate_evidence)


def historical_totals(state: dict) -> dict:
    """Carry closed real costs/liability once; mock costs never become real spend."""
    fixture = state.get("fixture")
    _require(type(fixture) is bool, "historical accounting requires an explicit journal mode")
    return {"historical": copy.deepcopy(HISTORICAL), "historical_unknown_released": False,
        "cumulative_known_micro_usd": None if fixture else HISTORICAL["known_micro_usd"] + state["spent_micro_usd"],
        "cumulative_reserved_micro_usd": None if fixture else HISTORICAL["reserved_micro_usd"] + state["reserved_micro_usd"],
        "cumulative_max_exposure_micro_usd": None if fixture else HISTORICAL["known_micro_usd"] + HISTORICAL["reserved_micro_usd"]
            + state["spent_micro_usd"] + state["reserved_micro_usd"],
        "cumulative_provider_calls": None if fixture else HISTORICAL["provider_calls"] + state["attempts"]}


class _DeadlineCore(core.Ledger):
    """Frozen dispatch transaction with explicit post-lock/terminal hooks only."""
    def __init__(self, *args, hooks, **kwargs):
        self.hooks = hooks
        super().__init__(*args, **kwargs)
        with self._lock, core.writer_lock(self.journal):
            state, events, manifest = core._replay(self.journal)
            if _stop(self.journal, manifest, state, events) is None and state["status"] == "ready":
                _audit(self.journal, manifest, state, strict=True)

    def dispatch(self, slot_id: str, role: str, request: dict, *, checkpoint: str | None = None) -> dict:
        # The original transaction is retained in phase3a_v1.accounting.Ledger.dispatch.
        # All original validation/reservation/result/event functions remain delegated.
        request = copy.deepcopy(request)
        with self._lock, core.writer_lock(self.journal):
            state, events, manifest = core._replay(self.journal)
            if _stop(self.journal, manifest, state, events) is not None:
                raise KnownDeadlineStop("durable deadline stop forbids any continuation or response forwarding")
            if state["status"] == "blocked-unknown":
                raise LiabilityStop("unknown request must never be resent")
            if state["status"] != "ready":
                raise IntegrityStop("phase is durably halted")
            try:
                meta = manifest["inputs"]["slots"].get(slot_id)
                _require(meta is not None and meta["role"] == role and (checkpoint is None or checkpoint == (
                    "canary" if meta["pair"] == PAIRS[0] else "expansion")), "undeclared request slot/role/checkpoint")
                validate_request(role, request, editor_tools=manifest["inputs"]["editor_tools"])
                self.hooks.check_scope(state, events, meta)
                if slot_id in state["results"]:
                    _require(state["results"][slot_id]["request_sha256"] == digest(request), "settled request changed on replay")
                    bounded.read_audit(manifest["inputs"]["study_sha256"], manifest["inputs"]["fixture"], slot_id,
                        intent=state["intents"][slot_id], result=state["results"][slot_id], bindings=_bindings(manifest))
                    return state["results"][slot_id]
                if role == "editor" and meta["turn"] > 1:
                    previous = next(name for name, row in manifest["inputs"]["slots"].items() if
                        row.get("conversation") == meta["conversation"] and row.get("turn") == meta["turn"] - 1)
                    _require(previous in state["results"], "editor cannot skip or restart its provider-turn sequence")
            except AuthorityError:
                raise
            except (ValueError, TypeError, KeyError, StopIteration) as exc:
                core._append_event(self.journal, "halt", {"state_sha256": digest(state), "reason": str(exc)}, events)
                raise IntegrityStop(str(exc)) from exc
            try:
                core._admit(state, meta, core._reservation(role))
            except (CellBudgetStop, AssessmentBudgetStop, CheckpointStop, PhaseBudgetStop) as exc:
                scope = ("cell" if isinstance(exc, CellBudgetStop) else "assessment" if isinstance(exc, AssessmentBudgetStop)
                         else "checkpoint" if isinstance(exc, CheckpointStop) else "phase")
                already = (meta["cell"] in state["stopped_cells"] if scope == "cell" else
                           state["assessment_stopped"] if scope == "assessment" else state["checkpoint_stopped"])
                if not already:
                    core._append_event(self.journal, "budget_stop", {"state_sha256": digest(state), "scope": scope,
                        "cell": meta["cell"], "slot_id": slot_id, "reason": str(exc)}, events)
                raise
            # Both serialization locks are held. No earlier queue-time estimate is used.
            allocation = self.hooks.before_intent(state, events, manifest, slot_id, role, meta)
            intent = core._intent(manifest, slot_id, request, state["attempts"] + 1)
            core._append_event(self.journal, "intent", intent, events)
            returned = response = None
            stage = "transport_select"
            try:
                self.transport.bind_intent(intent, allocation)
                if hasattr(self.transport, "select"):
                    self.transport.select(role, slot_id)
                stage = "provider_call"
                returned = self.transport.create(role, request)
                stage = "response_copy"
                response = json.loads(core._wire(returned))
                stage = "accounting"
                result = core._result(intent, response)
                stage = "serialization"
                core._wire(result)
                _require(len(core._result_event_bytes(result, events)) <= 2_000_000,
                         "single result event exceeds the artifact profile")
            except core.TransportFailure as error:
                result = core._bounded_failure_result(intent, error.response, error.failure, events)
            except Exception as error:
                candidate = response if response is not None else returned
                available_id = core.provider_request_id(candidate.get("request_id")) if isinstance(candidate, dict) else None
                kept = core.retain_response(candidate)
                result = core._bounded_failure_result(intent, kept, core.failure_from_exception(error, stage,
                    request_id=available_id), events)
            _require(len(core._result_event_bytes(result, events)) <= 2_000_000,
                     "single result event exceeds the artifact profile")
            disposition = self.transport.disposition(slot_id)
            reason = ("unknown_terminal" if result["status"] != "response" else
                      "known_late_response" if disposition.get("late_known") else
                      "known_cleanup_failed" if disposition.get("cleanup_failed") or disposition.get("owner_stop_required") else None)
            if reason:
                _require(result["status"] != "response" or result.get("failure") is None, "late known latch requires validated ordinary accounting")
                self.hooks.latch(manifest, slot_id, reason, intent=intent, result=result, disposition=disposition)
            core._append_event(self.journal, "result", result, events)
            try:
                audit = self.transport.commit(slot_id, result)
                bounded.validate_audit(audit, intent=intent, result=result, bindings=_bindings(manifest))
                core._publish(bounded.audit_path(manifest["inputs"]["study_sha256"], manifest["inputs"]["fixture"], slot_id), audit)
            except Exception as exc:
                try:
                    after, current_events, _ = core._replay(self.journal)
                    if after["status"] == "ready":
                        core._append_event(self.journal, "halt", {"state_sha256": digest(after),
                            "reason": "transport_audit_commit_failed"}, current_events)
                    failure = {"kind": "phase3a-r2-transport-audit-failure-v1", "slot_id": slot_id,
                        "bindings": _bindings(manifest), "fixture": manifest["inputs"]["fixture"],
                        "intent_sha256": digest(intent), "terminal_result_sha256": digest(result),
                        "error_category": type(exc).__name__, "automatic_release_or_resume": False}
                    failure["sha256"] = digest(failure)
                    core._publish(self.journal / "transport-audit-failure.json", failure)
                finally:
                    # An unavailable audit cannot permit an uncertain worker/owner to continue.
                    if result["status"] != "response" or disposition.get("owner_stop_required"):
                        self.hooks.stop_owner(result, disposition)
                    else:
                        self.transport.close()
                raise IntegrityStop("terminal accounting retained; transport audit commitment failed") from exc
            if reason:
                if result["status"] == "response":
                    after, current_events, _ = core._replay(self.journal)
                    core._append_event(self.journal, "halt", {"state_sha256": digest(after),
                        "reason": "known_deadline_stop:" + reason}, current_events)
                if result["status"] != "response" or disposition.get("owner_stop_required"):
                    self.hooks.stop_owner(result, disposition)
                raise KnownDeadlineStop("settled known deadline outcome is not forwarded")
            return result


class Ledger:
    """Delegate requests/accounting; add only immutable stage admission scope.

    The controller must hold its study workflow-owner lock for the whole stage;
    all concurrent native workers share this one wrapper. The core file lock
    serializes accounting, while this instance lock orders external stop checks.
    """
    def __init__(self, journal: Path, *, study_sha256: str, slots: dict, authority: dict,
                 transport: Any, bindings: dict, editor_tools: dict | None = None,
                 stage: str = "readiness", readiness_validator: Validator | None = None,
                 admission_guard: Validator | None = None, fixture_owner_exit: Callable | None = None):
        _require(stage in {"readiness", "first", "remaining"}, "unknown completion stage")
        _require(readiness_validator is None or callable(readiness_validator), "invalid readiness validator")
        _require(admission_guard is None or callable(admission_guard), "invalid admission guard")
        _require(stage == "readiness" or readiness_validator is not None,
                 "comparison admission requires the bound readiness-review validator")
        validate_authority(study_sha256, authority, transport.fixture, bindings)
        _require(Path(journal) == canonical_journal(study_sha256, transport.fixture),
                 "completion must use its single new canonical journal")
        _require(isinstance(transport, bounded.Transport), "R2 requires its source-bound owned-worker transport")
        _require(fixture_owner_exit is None or transport.fixture and callable(fixture_owner_exit), "owner-exit injection is fixture-only")
        self.stage, self.readiness_validator, self.admission_guard = stage, readiness_validator, admission_guard
        self.fixture_owner_exit = fixture_owner_exit
        self._slots = copy.deepcopy(slots)
        self._core = _DeadlineCore(journal, hooks=self, study_sha256=study_sha256, slots=slots, authority=authority,
                                transport=transport, bindings=bindings, editor_tools=editor_tools)
        self.journal, self.transport, self.manifest = self._core.journal, self._core.transport, self._core.manifest

    def state(self) -> dict:
        with self._core._lock:
            return replay(self.journal)

    def halt(self, reason: str, evidence_sha256: str | None = None) -> dict:
        return self._core.halt(reason, evidence_sha256)

    def dispatch(self, slot_id: str, role: str, request: dict, *, checkpoint: str | None = None) -> dict:
        return self._core.dispatch(slot_id, role, request, checkpoint=checkpoint)

    def check_scope(self, state: dict, events: list, meta: dict) -> None:
        if ((self.stage == "readiness" and meta["cell"] != "p3a-01:adaptive")
                or (self.stage == "first" and meta["pair"] != "p3a-01")):
            core._append_event(self.journal, "halt", {"state_sha256": digest(state), "reason": "completion_stage_scope_violation"}, events)
            raise AuthorityError("request is outside this completion stage")
        if self.stage == "remaining" and not state["engineering_review"]:
            raise AuthorityError("remaining completion work requires the first-pair engineering review")

    def before_intent(self, state: dict, events: list, manifest: dict, slot: str, role: str, meta: dict) -> Budget:
        for validator in (self.readiness_validator, self.admission_guard):
            if validator is None:
                continue
            try:
                _require(validator(copy.deepcopy(state)) is None, "completion admission validator did not finish")
            except ReadinessStop:
                raise
            except Exception as exc:
                core._append_event(self.journal, "halt", {"state_sha256": digest(state), "reason": "completion_admission_evidence_rejected"}, events)
                raise IntegrityStop("completion admission evidence failed validation") from exc
        try:
            return self.transport.prepare(slot, role, meta, _bindings(manifest))
        except KnownDeadlineStop:
            self.latch(manifest, slot, "pre_intent_deadline")
            core._append_event(self.journal, "halt", {"state_sha256": digest(state), "reason": "known_deadline_stop:pre_intent_deadline"}, events)
            raise
        except Exception as exc:
            core._append_event(self.journal, "halt", {"state_sha256": digest(state),
                "reason": "deadline_admission_integrity_failure"}, events)
            raise IntegrityStop("post-lock deadline admission rejected") from exc

    def latch(self, manifest: dict, slot: str, reason: str, *, intent=None, result=None, disposition=None) -> None:
        record = {"kind": "phase3a-r2-deadline-stop-v1", "reason": reason, "bindings": _bindings(manifest),
            "fixture": manifest["inputs"]["fixture"], "slot_id": slot,
            "intent_sha256": digest(intent) if intent else None,
            "candidate_result_sha256": digest(result) if result else None,
            "disposition": copy.deepcopy(disposition or {}), "automatic_release_or_resume": False}
        record["sha256"] = digest(record)
        core._publish(self.journal / "deadline-stop.json", record)

    def stop_owner(self, result: dict, disposition: dict) -> None:
        # close() retains the original absolute cleanup deadline; it never renews it.
        try:
            self.transport.close()
        finally:
            if self.transport.fixture:
                if self.fixture_owner_exit is not None:
                    self.fixture_owner_exit(copy.deepcopy(result), copy.deepcopy(disposition))
                raise OwnerStopRequired("fixture terminal hold reached the owned-controller exit boundary")
            runtime_guard()
            _require(os.getpid() == 1, "owner stop requires the inspected contained PID1; hold remains")
            os._exit(82)  # source-bound PID1 only, after terminal durability, including audit-failure handling
