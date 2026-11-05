"""Versioned HI worklist and replay around immutable request/accounting helpers.

The 2344 potential slots are not a 2344-call allowance. All old economic guards
remain delegated, with a separate 2344-admission ceiling and sixteen-round scope.
No frozen module globals or manifests are modified or projected.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import threading
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from buddha2.artifacts import ContractError, digest
from followups.phase3a_c1_completion_v3 import accounting as parent
from followups.phase3a_c1_completion_v3.deadline import Budget as Budget

from . import ledger_core as core
from . import transport as bounded
from .deadline import KnownDeadlineStop
from .support import IMAGE_ID as IMAGE_ID
from .support import NATIVE, checked, read, runtime_guard, safe

PREFIX = "phase3b-seq2-v1"
POLICY = copy.deepcopy(core.POLICY)
POLICY.update(id="phase3b-seq2-continuation-accounting-v1",
              phase_micro_usd=152_313_066, first_micro_usd=31_971_901)
WORKLIST_PROFILE = {
    "id": "phase3b-seq2-continuation-worklist-v1",
    "potential_request_slots": 2344,
    "maximum_admitted_attempts": 1674,
    "editor_stages_per_cell": 6,
    "shape_attempts_per_stage": 2,
    "editor_turns_per_conversation": 24,
    "native_selector_sessions_per_cell": 1,
    "adaptive_potential_per_cell": 408,
    "fixed_potential_per_cell": 145,
    "assessment_potential": 132,
}
PAIRS, ROLES, CHECKS = core.PAIRS, core.ROLES, core.CHECKS
AuthorityError, IntegrityStop, LiabilityStop = (
    core.AuthorityError,
    core.IntegrityStop,
    core.LiabilityStop,
)
CellBudgetStop, CheckpointStop = core.CellBudgetStop, core.CheckpointStop
AssessmentBudgetStop, PhaseBudgetStop = core.AssessmentBudgetStop, core.PhaseBudgetStop
validate_request = core.validate_request
ReadinessStop = parent.ReadinessStop
Validator = Callable[[dict], None]
OwnerStopRequired = parent.OwnerStopRequired
RETIRED_STUDIES = parent.RETIRED_STUDIES | frozenset(
    {
        "bc86391000266d413276de0f9ca8fb7f4f5b65632aa509d650f8236a48735be8",
        "a233fbc5ed3fedaa21e6b364ecfbfdd15496e25c005897067eb2cc7aed90d28a",
        "080c6ec2bbc1477002a83f7bb91bf0c3f86799ffa1fddd693ced2bdbbccc4f34",
        "544d83fbfd8154466aefa04d4adc39ece204c8331d920adb08562bb1edb97da4",
        "8889603f3720753e0543b0c8dd714c384fc173822d0d3899d8131506121c20bc",
        "e2fd01fab453fdbe4a30297f282301738a42484f238d6a52afe1105f93f62cca",
    }
)
RETIRED_SOURCES = frozenset(
    {
        "517b8efcdfc68bbb3e6ac6d260dc2e7e0541fdb02ea46784afc4ca5e2d300ed8",
        "2440535e5274c106a44efb28cf9533308b7dbea8fd8768649a089145cbc150a3",
        "5c592fdf7724fe7371491ab3b2ec2c5d223bcaf7bede091485789d5050a5ecfb",
        "a3b9403d6bc0a144d0bb74e74a330ccf057850da0d23dcb2d9059d94a20883e3",
        "e2471ad9e38171cabc2d32615bac797739f378c3f6c7ebc64f8b95f8632d9d26",
        "33cc36cb56fa75b6b427add09934a943515dd40e57cccfb4d4cfcb92a8b4bc1c",
        "b17f977af8c893989870216aa8e92e09a4538f7d63555cceae73095998b37e9d",
        "59a5f129f51da661aee20f9939141bef1a6af683ef68148300586a2344c5b5a89",
        "64b839d569e3ddefa3d56e06fc5b431760aef15cdfb3fd38256e04f8565f519a",
    }
)
_require, _bindings, _stop = core._require, parent._bindings, parent._stop


def canonical_journal(study_sha256: str, fixture: bool) -> Path:
    _require(
        core._hash(study_sha256) and study_sha256 not in RETIRED_STUDIES and type(fixture) is bool,
        "HI requires a fresh study identity and explicit mode",
    )
    return Path("/results") / PREFIX / study_sha256 / ("mock" if fixture else "live") / "journal"


def _journal(path: Path) -> Path:
    path = Path(path)
    _require(
        len(path.parts) == 6
        and path.parts[:2] == ("/", "results")
        and path.parts[-1] == "journal"
        and path.parts[-2] in {"mock", "live"},
        "HI journal does not have its exact canonical path",
    )
    _require(
        path == canonical_journal(path.parts[-3], path.parts[-2] == "mock"),
        "HI journal escaped its fresh study/mode",
    )
    for filename in (
        "manifest.json",
        "events.jsonl",
        "deadline-stop.json",
        "transport-audit-failure.json",
    ):
        safe(path / filename)
    return safe(path)


def validate_authority(
    study_sha256: str, authority: dict, fixture: bool = False, bindings: dict | None = None
) -> None:
    canonical_journal(study_sha256, fixture)
    if not isinstance(bindings, dict):
        raise ContractError("HI requires source/policy/launcher bindings")
    _require(
        core._hash(study_sha256) and type(fixture) is bool, "exact study/mode binding required"
    )
    core._validate_auth(authority, study_sha256, core.am1.CONTROL_POLICY)
    _require(
        authority["cap_micro_usd"] == POLICY["phase_micro_usd"]
        and authority["canary_cap_micro_usd"] == POLICY["first_micro_usd"]
        and authority["expansion_authorized"] is False
        and (fixture or authority["authorized"] is True),
        "S2 authority differs; a legacy ceiling is not this grant",
    )
    _require(
        set(bindings) == {"source_sha256", "policy_sha256", "launcher_sha256"}
        and all(core._hash(v) for v in bindings.values()),
        "S2 source bindings are incomplete",
    )
    _require(bindings["policy_sha256"] == digest(POLICY), "HI policy identity differs")
    _require(bindings["source_sha256"] not in RETIRED_SOURCES, "retired source cannot authorize HI")


def _slot_scope(slots: Any) -> None:
    _require(
        isinstance(slots, dict) and len(slots) == 2344, "complete2344-slot S2 worklist required"
    )
    counts: Counter = Counter()
    conversations: dict[str, set[int]] = {}
    for name, row in slots.items():
        _require(
            isinstance(name, str)
            and re.fullmatch(r"[A-Za-z0-9_.:/-]{1,240}", name) is not None
            and isinstance(row, dict),
            "invalid frozen slot identity",
        )
        role, cell, pair = row.get("role"), row.get("cell"), row.get("pair")
        _require(
            role in ROLES
            and pair in PAIRS
            and cell in (pair + ":fixed", pair + ":adaptive", "assessment"),
            "invalid role/cell/pair",
        )
        extras = {"checkpoint"} if "checkpoint" in row else set()
        if extras:
            _require(
                row["checkpoint"] == ("canary" if pair == PAIRS[0] else "expansion"),
                "checkpoint differs",
            )
        _require(
            (cell == "assessment") == (role in {"group", "quality"}),
            "assessment/inference pool mismatch",
        )
        if role in {"editor", "native_selector"}:
            pattern = (
                r":(?:inv1|dom1|c1|inv2|dom2|c2)\.a[12]" if role == "editor" else r":select\.seq2"
            )
            _require(
                set(row) == {"role", "cell", "pair", "conversation", "turn"} | extras
                and cell == pair + ":adaptive"
                and isinstance(row["conversation"], str)
                and re.fullmatch(re.escape(cell) + pattern, row["conversation"])
                and type(row["turn"]) is int
                and 1 <= row["turn"] <= 24,
                "invalid native conversation/turn",
            )
            _require(
                name
                == f"{pair}.adaptive.editor.{row['conversation'].removeprefix(cell + ':')}.t{row['turn']:02}",
                "native slot name differs from its conversation",
            )
            conversations.setdefault(row["conversation"], set()).add(row["turn"])
        else:
            _require(set(row) == {"role", "cell", "pair"} | extras, "unexpected slot metadata")
        counts[cell, pair, role] += 1
    expected: Counter = Counter()
    for pair in PAIRS:
        for arm, population in (
            (
                "adaptive",
                {"answer": 80, "plan": 8, "rank": 8, "editor": 288, "native_selector": 24},
            ),
            ("fixed", {"answer": 120, "plan": 12, "rank": 12, "fixed_selector": 1}),
        ):
            for role, number in population.items():
                expected[pair + ":" + arm, pair, role] = number
        expected["assessment", pair, "group"] = 3
        expected["assessment", pair, "quality"] = 30
    _require(
        counts == expected
        and len(conversations) == 52
        and all(turns == set(range(1, 25)) for turns in conversations.values()),
        "S2 frozen scope differs",
    )


def _editor_tools(value: Any) -> None:
    _require(
        isinstance(value, dict)
        and set(value).issubset({"read", "write", "edit"})
        and all(
            isinstance(k, str) and isinstance(v, dict) and v.get("name") == k
            for k, v in value.items()
        ),
        "editor allowlist contains unbounded/invalid tools",
    )


def journal_identity(
    *,
    study_sha256: str,
    slots: dict,
    authority: dict,
    fixture: bool,
    bindings: dict,
    editor_tools: dict | None = None,
) -> str:
    validate_authority(study_sha256, authority, fixture, bindings)
    _slot_scope(slots)
    _editor_tools(editor_tools or {})
    return digest(
        {
            "study_sha256": study_sha256,
            "slots": slots,
            "authority": authority,
            "fixture": fixture,
            "bindings": bindings,
            "policy": POLICY,
            "editor_tools": editor_tools or {},
        }
    )


def _manifest(path: Path) -> dict:
    path = safe(_journal(path))
    value = core.read_json(path / "manifest.json")
    _require(
        isinstance(value, dict)
        and set(value) == {"kind", "inputs", "run_id"}
        and value["kind"] == "phase3b-seq2-ledger-v1"
        and value["run_id"] == digest(value["inputs"]),
        "invalid HI manifest",
    )
    inputs = value["inputs"]
    _require(
        isinstance(inputs, dict)
        and set(inputs)
        == {"study_sha256", "slots", "authority", "fixture", "bindings", "policy", "editor_tools"}
        and core._hash(inputs["study_sha256"]),
        "HI ledger inputs differ",
    )
    _require(
        inputs["policy"] == POLICY and digest(inputs["policy"]) == digest(POLICY),
        "HI ledger policy differs",
    )
    _slot_scope(inputs["slots"])
    _editor_tools(inputs["editor_tools"])
    validate_authority(
        inputs["study_sha256"], inputs["authority"], inputs["fixture"], inputs["bindings"]
    )
    _require(
        path == canonical_journal(inputs["study_sha256"], inputs["fixture"]),
        "HI journal identity differs",
    )
    if not inputs["fixture"]:
        runtime_guard()
    return value


def _admit(state: dict, meta: dict, reservation: dict) -> None:
    if state["status"] == "ready" and (
        state["spent_micro_usd"] + state["reserved_micro_usd"] + reservation["micro_usd"]
        > POLICY["phase_micro_usd"]
    ):
        raise PhaseBudgetStop("remaining S2 exposure ceiling reached")
    if (state["status"] == "ready" and meta["pair"] == PAIRS[0]
            and state["first_pair"]["spent_micro_usd"] + reservation["micro_usd"]
            > POLICY["first_micro_usd"]):
        raise CheckpointStop("remaining included first-pair exposure ceiling reached")
    core._admit(state, meta, reservation)
    if state["attempts"] + 1 > WORKLIST_PROFILE["maximum_admitted_attempts"]:
        raise PhaseBudgetStop("remaining S2 admitted-attempt ceiling reached")


def _replay(path: Path) -> tuple[dict, list[dict], dict]:
    manifest = _manifest(path)
    state, pending = core._start(manifest), None
    events, tail = core._read_events(path)
    for event in events:
        kind, record = event["kind"], event["record"]
        if kind == "intent":
            _require(
                pending is None
                and record.get("slot_id") in manifest["inputs"]["slots"]
                and record["slot_id"] not in state["results"],
                "duplicate/out-of-order ledger intent",
            )
            slot, request = record["slot_id"], record["request"]
            meta = manifest["inputs"]["slots"][slot]
            core.validate_request(
                meta["role"], request, editor_tools=manifest["inputs"]["editor_tools"]
            )
            _require(
                record == core._intent(manifest, slot, request, state["attempts"] + 1),
                "request intent differs",
            )
            _admit(state, meta, record["reservation"])
            if meta["role"] in {"editor", "native_selector"} and meta["turn"] > 1:
                previous = next(
                    name
                    for name, row in manifest["inputs"]["slots"].items()
                    if row.get("conversation") == meta["conversation"]
                    and row.get("turn") == meta["turn"] - 1
                )
                _require(
                    previous in state["results"]
                    and state["results"][previous]["status"] == "response",
                    "editor continuation lacks its preceding settled turn",
                )
            for bucket in core._buckets(state, meta):
                bucket["attempts"] += 1
                bucket["reserved_micro_usd"] += record["reservation"]["micro_usd"]
                bucket["reserved_input_tokens"] += record["reservation"]["input"]
                bucket["reserved_output_tokens"] += record["reservation"]["output"]
            state["intents"][slot] = record
            state["provider_calls"] = 0 if state["fixture"] else state["attempts"]
            pending = record
        elif kind == "result":
            if pending is None:
                raise IntegrityStop("result lacks its pending intent")
            _require(
                record
                == core._result(pending, record.get("response"), failure=record.get("failure")),
                "result differs from pending intent/accounting",
            )
            meta = manifest["inputs"]["slots"][pending["slot_id"]]
            if record["status"] == "response":
                for bucket in core._buckets(state, meta):
                    bucket["reserved_micro_usd"] -= pending["reservation"]["micro_usd"]
                    bucket["reserved_input_tokens"] -= pending["reservation"]["input"]
                    bucket["reserved_output_tokens"] -= pending["reservation"]["output"]
                    bucket["spent_micro_usd"] += record["spent_micro_usd"]
                    bucket["input_tokens"] += record["input_tokens"]
                    bucket["output_tokens"] += record["output_tokens"]
            else:
                state["status"] = "blocked-unknown"
            state["results"][record["slot_id"]] = record
            pending = None
        else:
            _require(
                pending is None and state["status"] == "ready",
                "control record follows pending/unknown/terminal halt",
            )
            if kind in {"review", "first_assessments_closed"}:
                core._review(state, record, closure=kind == "first_assessments_closed")
                if kind == "review":
                    state["engineering_review"] = digest(record)
                    state["checkpoint_stopped"] = False
                state["first_assessments_closed"] = record["first_assessments_closed"]
            elif kind == "halt":
                _require(record.get("state_sha256") == digest(state), "halt prefix differs")
                state["status"] = "halted-integrity"
            elif kind == "budget_stop":
                _require(
                    record.get("state_sha256") == digest(state)
                    and record.get("scope") in {"cell", "assessment", "checkpoint", "phase"},
                    "budget-stop prefix differs",
                )
                if record["scope"] == "cell":
                    _require(
                        record.get("cell") in state["cells"]
                        and record["cell"] not in state["stopped_cells"],
                        "invalid stopped cell",
                    )
                    state["stopped_cells"].append(record["cell"])
                elif record["scope"] == "assessment":
                    state["assessment_stopped"] = True
                elif record["scope"] == "checkpoint":
                    state["checkpoint_stopped"] = True
                else:
                    state["status"] = "halted-budget"
    if pending is not None:
        state["results"][pending["slot_id"]] = core._result(
            pending, None, failure=core.make_failure("unresolved_intent", "journal_replay")
        )
        state["status"] = "blocked-unknown"
    _require(not tail or pending is not None, "truncated result lacks its durable pending intent")
    if tail:
        state["stream_tail_sha256"] = hashlib.sha256(tail).hexdigest()
    state["provider_calls"] = 0 if state["fixture"] else state["attempts"]
    return state, events, manifest


def _audit(journal: Path, manifest: dict, state: dict, *, strict: bool) -> dict:
    rows, failures = {}, []
    for slot, result in state["results"].items():
        intent = state["intents"][slot]
        try:
            rows[slot] = bounded.read_audit(
                manifest["inputs"]["study_sha256"],
                manifest["inputs"]["fixture"],
                slot,
                intent=intent,
                result=result,
                bindings=_bindings(manifest),
            )
        except (ContractError, OSError, ValueError, TypeError, KeyError):
            failures.append(slot)
    if strict:
        _require(not failures, "missing/invalid committed transport audit blocks continuation")
    return {
        "validated_audits": len(rows),
        "missing_or_invalid_slots": sorted(failures),
        "SDK_invoked": sum(r["sdk_invoked"] is True for r in rows.values())
        if not failures
        else None,
        "SDK_invocation_unknown": sum(r["sdk_invoked"] is None for r in rows.values())
        if not failures
        else None,
        "late_known": sum(bool(r["late_known"]) for r in rows.values()) if not failures else None,
        "owner_stop_required": sum(bool(r["owner_stop_required"]) for r in rows.values())
        if not failures
        else None,
        "audit_sha256": {slot: digest(row) for slot, row in sorted(rows.items())},
    }


def replay(journal: Path) -> dict:
    journal = _journal(journal)
    state, records, manifest = _replay(journal)
    stop = _stop(journal, manifest, state, records)
    audit = _audit(journal, manifest, state, strict=False)
    state["core_status"] = state["status"]
    state["deadline_stop"] = stop
    state["transport_audit_summary"] = audit
    durable = {e["record"]["slot_id"] for e in records if e["kind"] == "result"}
    state["active_unsettled_intents"] = sorted(set(state["intents"]) - durable)
    state["durable_unknown_results"] = sum(
        state["results"][s]["status"] != "response" for s in durable
    )
    if stop is not None and state["status"] != "blocked-unknown":
        state["status"] = "stopped-known-deadline"
    elif audit["missing_or_invalid_slots"] and state["status"] == "ready":
        state["status"] = "halted-transport-audit"
    target = safe(
        NATIVE
        / state["study_sha256"]
        / ("mock" if state["fixture"] else "live")
        / "canonical-stop.json"
    )
    if target.exists():
        state["canonical_checkpoint_stop"] = checked(read(target))
        state["admission_status"] = "blocked-canonical-checkpoint"
    return state


def raw_state(state: dict) -> dict:
    """Keep frozen state-hash/event arithmetic independent of new report metadata."""
    result = {
        k: copy.deepcopy(v)
        for k, v in state.items()
        if k
        not in {
            "core_status",
            "deadline_stop",
            "transport_audit_summary",
            "active_unsettled_intents",
            "durable_unknown_results",
            "canonical_checkpoint_stop",
            "admission_status",
        }
    }
    if "core_status" in state:
        result["status"] = state["core_status"]
    return result


def events(journal: Path) -> list[dict]:
    return copy.deepcopy(_replay(_journal(journal))[1])


def _publish_review(
    journal: Path, record: dict, validate_evidence: Callable, *, closure: bool
) -> dict:
    journal = safe(_journal(journal))
    with core.writer_lock(journal):
        state, records, _ = _replay(journal)
        kind = "first_assessments_closed" if closure else "review"
        existing = [e["record"] for e in records if e["kind"] == kind]
        if existing:
            _require(
                len(existing) == 1 and existing[0] == record,
                "conflicting/replayed-as-new HI review",
            )
            return state
        core._review(state, record, closure=closure)
        _require(
            validate_evidence(copy.deepcopy(state), copy.deepcopy(record)) is None,
            "engineering evidence validator must complete without rejection",
        )
        core._append_event(journal, kind, record, records)
        return _replay(journal)[0]


def publish_review(
    journal: Path, record: dict, *, validate_evidence: Callable[[dict, dict], None]
) -> dict:
    return _publish_review(journal, record, validate_evidence, closure=False)


def close_first_assessments(
    journal: Path, record: dict, *, validate_evidence: Callable[[dict, dict], None]
) -> dict:
    return _publish_review(journal, record, validate_evidence, closure=True)


class _DeadlineCore:
    """HI manifest/replay seam; the R2 transaction ordering and helpers are retained."""

    def __init__(
        self,
        journal: Path,
        *,
        hooks,
        study_sha256: str,
        slots: dict,
        authority: dict,
        transport: Any,
        bindings: dict,
        editor_tools: dict | None = None,
    ):
        self.hooks = hooks
        validate_authority(study_sha256, authority, transport.fixture, bindings)
        _slot_scope(slots)
        if not transport.fixture:
            runtime_guard()
            _require(
                isinstance(transport, core.DirectSDKTransport)
                and transport.control_policy == core.am1.CONTROL_POLICY,
                "live HI requires its pinned explicit-key SDK boundary",
            )
        self.journal, self.transport, self._lock = (
            safe(_journal(journal)),
            transport,
            threading.RLock(),
        )
        inputs = {
            "study_sha256": study_sha256,
            "slots": copy.deepcopy(slots),
            "authority": copy.deepcopy(authority),
            "fixture": transport.fixture,
            "bindings": copy.deepcopy(bindings),
            "policy": copy.deepcopy(POLICY),
            "editor_tools": copy.deepcopy(editor_tools or {}),
        }
        _editor_tools(inputs["editor_tools"])
        self.manifest = {
            "kind": "phase3b-seq2-ledger-v1",
            "inputs": inputs,
            "run_id": journal_identity(
                study_sha256=study_sha256,
                slots=slots,
                authority=authority,
                fixture=transport.fixture,
                bindings=bindings,
                editor_tools=editor_tools,
            ),
        }
        with core.writer_lock(self.journal):
            if (self.journal / "manifest.json").exists():
                _require(
                    core.read_json(self.journal / "manifest.json") == self.manifest,
                    "another source/study/profile/authority owns this HI journal",
                )
            else:
                _require(
                    not any(p.name != ".writer.lock" for p in self.journal.iterdir()),
                    "unrecognized HI journal contents",
                )
                core._publish(self.journal / "manifest.json", self.manifest)
            _manifest(self.journal)
            state, records, manifest = _replay(self.journal)
            if _stop(self.journal, manifest, state, records) is None and state["status"] == "ready":
                _audit(self.journal, manifest, state, strict=True)

    def state(self) -> dict:
        with self._lock:
            return replay(self.journal)

    def halt(self, reason: str, evidence_sha256: str | None = None) -> dict:
        _require(
            isinstance(reason, str)
            and 0 < len(reason) <= 1000
            and (evidence_sha256 is None or core._hash(evidence_sha256)),
            "invalid integrity halt",
        )
        with self._lock, core.writer_lock(self.journal):
            state, records, _ = _replay(self.journal)
            if state["status"] == "ready":
                core._append_event(
                    self.journal,
                    "halt",
                    {
                        "state_sha256": digest(state),
                        "reason": reason,
                        "evidence_sha256": evidence_sha256,
                    },
                    records,
                )
                return replay(self.journal)
            return state

    def dispatch(
        self, slot_id: str, role: str, request: dict, *, checkpoint: str | None = None
    ) -> dict:
        # The original transaction is retained in phase3a_v1.accounting.Ledger.dispatch.
        # All original validation/reservation/result/event functions remain delegated.
        request = copy.deepcopy(request)
        with self._lock, core.writer_lock(self.journal):
            state, events, manifest = _replay(self.journal)
            stop_path = safe(
                NATIVE
                / manifest["inputs"]["study_sha256"]
                / ("mock" if manifest["inputs"]["fixture"] else "live")
                / "canonical-stop.json"
            )
            if stop_path.exists():
                raise IntegrityStop("canonical checkpoint stop forbids any further admission")
            if _stop(self.journal, manifest, state, events) is not None:
                raise KnownDeadlineStop(
                    "durable deadline stop forbids any continuation or response forwarding"
                )
            if state["status"] == "blocked-unknown":
                raise LiabilityStop("unknown request must never be resent")
            if state["status"] != "ready":
                raise IntegrityStop("phase is durably halted")
            try:
                meta = manifest["inputs"]["slots"].get(slot_id)
                _require(
                    meta is not None
                    and meta["role"] == role
                    and (
                        checkpoint is None
                        or checkpoint == ("canary" if meta["pair"] == PAIRS[0] else "expansion")
                    ),
                    "undeclared request slot/role/checkpoint",
                )
                validate_request(role, request, editor_tools=manifest["inputs"]["editor_tools"])
                self.hooks.check_scope(state, events, meta)
                if slot_id in state["results"]:
                    _require(
                        state["results"][slot_id]["request_sha256"] == digest(request),
                        "settled request changed on replay",
                    )
                    bounded.read_audit(
                        manifest["inputs"]["study_sha256"],
                        manifest["inputs"]["fixture"],
                        slot_id,
                        intent=state["intents"][slot_id],
                        result=state["results"][slot_id],
                        bindings=_bindings(manifest),
                    )
                    return state["results"][slot_id]
                if role in {"editor", "native_selector"} and meta["turn"] > 1:
                    previous = next(
                        name
                        for name, row in manifest["inputs"]["slots"].items()
                        if row.get("conversation") == meta["conversation"]
                        and row.get("turn") == meta["turn"] - 1
                    )
                    _require(
                        previous in state["results"],
                        "editor cannot skip or restart its provider-turn sequence",
                    )
            except AuthorityError:
                raise
            except (ValueError, TypeError, KeyError, StopIteration) as exc:
                core._append_event(
                    self.journal,
                    "halt",
                    {"state_sha256": digest(state), "reason": str(exc)},
                    events,
                )
                raise IntegrityStop(str(exc)) from exc
            try:
                _admit(state, meta, core._reservation(role))
            except (CellBudgetStop, AssessmentBudgetStop, CheckpointStop, PhaseBudgetStop) as exc:
                scope = (
                    "cell"
                    if isinstance(exc, CellBudgetStop)
                    else "assessment"
                    if isinstance(exc, AssessmentBudgetStop)
                    else "checkpoint"
                    if isinstance(exc, CheckpointStop)
                    else "phase"
                )
                already = (
                    meta["cell"] in state["stopped_cells"]
                    if scope == "cell"
                    else state["assessment_stopped"]
                    if scope == "assessment"
                    else state["checkpoint_stopped"]
                )
                if not already:
                    core._append_event(
                        self.journal,
                        "budget_stop",
                        {
                            "state_sha256": digest(state),
                            "scope": scope,
                            "cell": meta["cell"],
                            "slot_id": slot_id,
                            "reason": str(exc),
                        },
                        events,
                    )
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
                _require(
                    len(core._result_event_bytes(result, events)) <= 2_000_000,
                    "single result event exceeds the artifact profile",
                )
            except core.TransportFailure as error:
                result = core._bounded_failure_result(intent, error.response, error.failure, events)
            except Exception as error:
                candidate = response if response is not None else returned
                available_id = (
                    core.provider_request_id(candidate.get("request_id"))
                    if isinstance(candidate, dict)
                    else None
                )
                kept = core.retain_response(candidate)
                result = core._bounded_failure_result(
                    intent,
                    kept,
                    core.failure_from_exception(error, stage, request_id=available_id),
                    events,
                )
            _require(
                len(core._result_event_bytes(result, events)) <= 2_000_000,
                "single result event exceeds the artifact profile",
            )
            disposition = self.transport.disposition(slot_id)
            reason = (
                "unknown_terminal"
                if result["status"] != "response"
                else "known_late_response"
                if disposition.get("late_known")
                else "known_cleanup_failed"
                if disposition.get("cleanup_failed") or disposition.get("owner_stop_required")
                else None
            )
            if reason:
                _require(
                    result["status"] != "response" or result.get("failure") is None,
                    "late known latch requires validated ordinary accounting",
                )
                self.hooks.latch(
                    manifest, slot_id, reason, intent=intent, result=result, disposition=disposition
                )
            core._append_event(self.journal, "result", result, events)
            try:
                audit = self.transport.commit(slot_id, result)
                bounded.validate_audit(
                    audit, intent=intent, result=result, bindings=_bindings(manifest)
                )
                core._publish(
                    bounded.audit_path(
                        manifest["inputs"]["study_sha256"], manifest["inputs"]["fixture"], slot_id
                    ),
                    audit,
                )
            except Exception as exc:
                try:
                    after, current_events, _ = _replay(self.journal)
                    if after["status"] == "ready":
                        core._append_event(
                            self.journal,
                            "halt",
                            {
                                "state_sha256": digest(after),
                                "reason": "transport_audit_commit_failed",
                            },
                            current_events,
                        )
                    failure = {
                        "kind": "phase3a-r2-transport-audit-failure-v1",
                        "slot_id": slot_id,
                        "bindings": _bindings(manifest),
                        "fixture": manifest["inputs"]["fixture"],
                        "intent_sha256": digest(intent),
                        "terminal_result_sha256": digest(result),
                        "error_category": type(exc).__name__,
                        "automatic_release_or_resume": False,
                    }
                    failure["sha256"] = digest(failure)
                    core._publish(self.journal / "transport-audit-failure.json", failure)
                finally:
                    # An unavailable audit cannot permit an uncertain worker/owner to continue.
                    if result["status"] != "response" or disposition.get("owner_stop_required"):
                        self.hooks.stop_owner(result, disposition)
                    else:
                        self.transport.close()
                raise IntegrityStop(
                    "terminal accounting retained; transport audit commitment failed"
                ) from exc
            if reason:
                if result["status"] == "response":
                    after, current_events, _ = _replay(self.journal)
                    core._append_event(
                        self.journal,
                        "halt",
                        {"state_sha256": digest(after), "reason": "known_deadline_stop:" + reason},
                        current_events,
                    )
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

    def __init__(
        self,
        journal: Path,
        *,
        study_sha256: str,
        slots: dict,
        authority: dict,
        transport: Any,
        bindings: dict,
        editor_tools: dict | None = None,
        stage: str = "readiness",
        readiness_validator: Validator | None = None,
        admission_guard: Validator | None = None,
        fixture_owner_exit: Callable | None = None,
    ):
        _require(stage in {"readiness", "first", "remaining"}, "unknown completion stage")
        _require(
            readiness_validator is None or callable(readiness_validator),
            "invalid readiness validator",
        )
        _require(admission_guard is None or callable(admission_guard), "invalid admission guard")
        _require(
            stage == "readiness" or readiness_validator is not None,
            "comparison admission requires the bound readiness-review validator",
        )
        validate_authority(study_sha256, authority, transport.fixture, bindings)
        _require(
            Path(journal) == canonical_journal(study_sha256, transport.fixture),
            "completion must use its single new canonical journal",
        )
        _require(
            isinstance(transport, bounded.Transport),
            "HI requires its source-bound owned-worker transport",
        )
        _require(
            fixture_owner_exit is None or transport.fixture and callable(fixture_owner_exit),
            "owner-exit injection is fixture-only",
        )
        self.stage, self.readiness_validator, self.admission_guard = (
            stage,
            readiness_validator,
            admission_guard,
        )
        self.fixture_owner_exit = fixture_owner_exit
        self._slots = copy.deepcopy(slots)
        self._core = _DeadlineCore(
            journal,
            hooks=self,
            study_sha256=study_sha256,
            slots=slots,
            authority=authority,
            transport=transport,
            bindings=bindings,
            editor_tools=editor_tools,
        )
        self.journal, self.transport, self.manifest = (
            self._core.journal,
            self._core.transport,
            self._core.manifest,
        )

    def state(self) -> dict:
        with self._core._lock:
            return replay(self.journal)

    def halt(self, reason: str, evidence_sha256: str | None = None) -> dict:
        return self._core.halt(reason, evidence_sha256)

    def dispatch(
        self, slot_id: str, role: str, request: dict, *, checkpoint: str | None = None
    ) -> dict:
        return self._core.dispatch(slot_id, role, request, checkpoint=checkpoint)

    def check_scope(self, state: dict, events: list, meta: dict) -> None:
        if (self.stage == "readiness" and meta["cell"] != "p3b-01:adaptive") or (
            self.stage == "first" and meta["pair"] != "p3b-01"
        ):
            core._append_event(
                self.journal,
                "halt",
                {"state_sha256": digest(state), "reason": "completion_stage_scope_violation"},
                events,
            )
            raise AuthorityError("request is outside this completion stage")
        if self.stage == "remaining" and not state["engineering_review"]:
            raise AuthorityError(
                "remaining completion work requires the first-pair engineering review"
            )

    def before_intent(
        self, state: dict, events: list, manifest: dict, slot: str, role: str, meta: dict
    ) -> Budget:
        for validator in (self.readiness_validator, self.admission_guard):
            if validator is None:
                continue
            try:
                _require(
                    validator(copy.deepcopy(state)) is None,
                    "completion admission validator did not finish",
                )
            except ReadinessStop:
                raise
            except Exception as exc:
                core._append_event(
                    self.journal,
                    "halt",
                    {
                        "state_sha256": digest(state),
                        "reason": "completion_admission_evidence_rejected",
                    },
                    events,
                )
                raise IntegrityStop("completion admission evidence failed validation") from exc
        try:
            return self.transport.prepare(slot, role, meta, _bindings(manifest))
        except KnownDeadlineStop:
            self.latch(manifest, slot, "pre_intent_deadline")
            core._append_event(
                self.journal,
                "halt",
                {
                    "state_sha256": digest(state),
                    "reason": "known_deadline_stop:pre_intent_deadline",
                },
                events,
            )
            raise
        except Exception as exc:
            core._append_event(
                self.journal,
                "halt",
                {"state_sha256": digest(state), "reason": "deadline_admission_integrity_failure"},
                events,
            )
            raise IntegrityStop("post-lock deadline admission rejected") from exc

    def latch(
        self, manifest: dict, slot: str, reason: str, *, intent=None, result=None, disposition=None
    ) -> None:
        record = {
            "kind": "phase3a-r2-deadline-stop-v1",
            "reason": reason,
            "bindings": _bindings(manifest),
            "fixture": manifest["inputs"]["fixture"],
            "slot_id": slot,
            "intent_sha256": digest(intent) if intent else None,
            "candidate_result_sha256": digest(result) if result else None,
            "disposition": copy.deepcopy(disposition or {}),
            "automatic_release_or_resume": False,
        }
        record["sha256"] = digest(record)
        core._publish(self.journal / "deadline-stop.json", record)

    def stop_owner(self, result: dict, disposition: dict) -> None:
        # Same owned PID1 cleanup contract, checked against the actual H1 image.
        try:
            self.transport.close()
        finally:
            if self.transport.fixture:
                if self.fixture_owner_exit is not None:
                    self.fixture_owner_exit(copy.deepcopy(result), copy.deepcopy(disposition))
                raise OwnerStopRequired(
                    "fixture terminal hold reached the owned-controller exit boundary"
                )
            runtime_guard()
            _require(
                os.getpid() == 1, "owner stop requires the inspected contained PID1; hold remains"
            )
            os._exit(82)
