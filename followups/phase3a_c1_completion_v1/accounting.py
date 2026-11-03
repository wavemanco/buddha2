"""Fresh completion scope around the unchanged, durable Phase 3A ledger core.

The live journal retains the core's literal storage prefix with a NEW study SHA.
This does not reuse any stopped R2 journal, authority, claim or result identity.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Callable

from buddha2.artifacts import ContractError, digest
from followups.phase3a_v1 import accounting as core

PREFIX = "phase3a-c1-completion-v1"
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
})
HISTORICAL = {"known_micro_usd": 10_487_885, "reserved_micro_usd": 11_440_000,
              "provider_calls": 842, "known_responses": 841, "unknown_responses": 1}
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
    _require(bindings["source_sha256"] != "a3b9403d6bc0a144d0bb74e74a330ccf057850da0d23dcb2d9059d94a20883e3",
             "the closed R2 source cannot authorize completion")


def journal_identity(*, study_sha256: str, slots: dict, authority: dict, fixture: bool,
                     bindings: dict, editor_tools: dict | None = None) -> str:
    validate_authority(study_sha256, authority, fixture, bindings)
    return core.journal_identity(study_sha256=study_sha256, slots=slots, authority=authority,
        fixture=fixture, bindings=bindings, editor_tools=editor_tools)


def replay(journal: Path) -> dict:
    return core.replay(_journal(journal))


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


class Ledger:
    """Delegate requests/accounting; add only immutable stage admission scope.

    The controller must hold its study workflow-owner lock for the whole stage;
    all concurrent native workers share this one wrapper. The core file lock
    serializes accounting, while this instance lock orders external stop checks.
    """
    def __init__(self, journal: Path, *, study_sha256: str, slots: dict, authority: dict,
                 transport: Any, bindings: dict, editor_tools: dict | None = None,
                 stage: str = "readiness", readiness_validator: Validator | None = None,
                 admission_guard: Validator | None = None):
        _require(stage in {"readiness", "first", "remaining"}, "unknown completion stage")
        _require(readiness_validator is None or callable(readiness_validator), "invalid readiness validator")
        _require(admission_guard is None or callable(admission_guard), "invalid admission guard")
        _require(stage == "readiness" or readiness_validator is not None,
                 "comparison admission requires the bound readiness-review validator")
        validate_authority(study_sha256, authority, transport.fixture, bindings)
        _require(Path(journal) == canonical_journal(study_sha256, transport.fixture),
                 "completion must use its single new canonical journal")
        self.stage, self.readiness_validator, self.admission_guard = stage, readiness_validator, admission_guard
        self._slots = copy.deepcopy(slots)
        self._core = core.Ledger(journal, study_sha256=study_sha256, slots=slots, authority=authority,
                                transport=transport, bindings=bindings, editor_tools=editor_tools)
        self.journal, self.transport, self.manifest = self._core.journal, self._core.transport, self._core.manifest

    def state(self) -> dict:
        return self._core.state()

    def halt(self, reason: str, evidence_sha256: str | None = None) -> dict:
        return self._core.halt(reason, evidence_sha256)

    def dispatch(self, slot_id: str, role: str, request: dict, *, checkpoint: str | None = None) -> dict:
        # Use the core instance's existing reentrant lock; its file lock still
        # serializes every actual provider call across instances/processes.
        with self._core._lock:
            state = self._core.state()
            if state["status"] == "blocked-unknown":
                raise LiabilityStop("unresolved completion request must not be resent")
            if state["status"] != "ready":
                raise IntegrityStop("completion is durably halted")
            meta = self._slots.get(slot_id)
            allowed = (meta is not None and meta["role"] == role
                and (self.stage != "readiness" or meta["cell"] == "p3a-01:adaptive")
                and (self.stage != "first" or meta["pair"] == "p3a-01"))
            if not allowed:
                self._core.halt("completion_stage_scope_violation")
                raise AuthorityError("request is outside this completion stage")
            if self.stage == "remaining" and not state["engineering_review"]:
                raise AuthorityError("remaining completion work requires the first-pair engineering review")
            for validator in (self.readiness_validator, self.admission_guard):
                if validator is None:
                    continue
                try:
                    _require(validator(copy.deepcopy(state)) is None, "completion admission validator did not finish")
                except ReadinessStop:
                    raise
                except Exception as exc:
                    self._core.halt("completion_admission_evidence_rejected")
                    raise IntegrityStop("completion admission evidence failed validation") from exc
            return self._core.dispatch(slot_id, role, request, checkpoint=checkpoint)