"""S2 paired study: actual native successive refinement and checkpoint assessment."""

from __future__ import annotations

import copy
import json
import os
import re
import threading
import time
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from harness2.core.proposer import ProposerError

from buddha2 import phase2_am1_controls as am1
from buddha2.artifacts import ContractError, digest, file_hash, write_bytes_once
from buddha2.phase2_dispatch import writer_lock

from . import accounting, editor, native, rank_io, strategy, supervision
from .adapter import CompatibleProposer
from .deadline import CONVERSATION_POLICY
from .deadline import POLICY as DEADLINE_POLICY
from .snapshot import VISIBILITY_OWNER_KIND, VISIBILITY_REQUEST_KIND, VISIBILITY_RESULT_KIND
from .support import (
    AUTHORITY,
    DECLARED_DEFINITION_SHA256,
    LAUNCHER,
    NATIVE,
    PRIOR_CLOSED_ARTIFACT_ATTEMPT,
    PRIOR_CLOSED_ATTEMPT,
    PRIOR_CLOSED_REPEAT,
    READ_CONSUMPTION_POLICY,
    ROOT,
    checked,
    offline_readiness,
    path,
    publish,
    read,
    require,
    runtime_identity,
    safe,
    seal,
    source_identity,
    source_snapshot_policy,
    validate_authority,
)
from .support import BASE as BASE

STAGES = {"readiness", "first", "remaining", "all"}
ARMS = ("fixed", "adaptive")


class ReadinessProposer(CompatibleProposer):
    """Observe known unfinished sessions before native fallback/probe scheduling."""

    def __init__(self, *, observe: bool, known_stop, can_stop, **kwargs):
        self.observe, self.known_stop, self.can_stop = observe, known_stop, can_stop
        super().__init__(**kwargs)

    def call(self, mission, context_dir=None, label="", **kwargs):
        # Reuse the parent's existing editor lock, including this observation.
        # Other native branches cannot open another editor between return and latch.
        with editor._SERIAL:
            try:
                reply = super().call(mission, context_dir, label, **kwargs)
            except ProposerError:
                if self.observe and self.can_stop():
                    self.known_stop("unfinished_editor_session")
                raise
            if self.observe and self.can_stop():
                session = self.phase3a_evidence()["sessions"].get(label, {})
                if session.get("terminal_note_used") or (
                    session.get("status") not in {"valid", "invalid_harvest"}
                ):
                    self.known_stop("unfinished_editor_session")
                elif session.get("status") == "valid":
                    final = reply.text
                    if not label.startswith("select.") and (
                        not isinstance(final, str)
                        or not re.fullmatch(r"\s*<notes>\s*\S[\s\S]*</notes>\s*", final)
                        or final.count("<notes>") != 1
                        or final.count("</notes>") != 1
                    ):
                        self.known_stop("unfinished_editor_session")
            return reply


def _scientific_inputs() -> dict:
    value = read(ROOT / "configs/phase3b-development.json")
    hashes = ("parent_decision_sha256", "seed_procedure_sha256", "source_descriptor_file_sha256", "source_study_sha256")
    require(set(value) == {"kind", "tasks", *hashes}
        and value.get("kind") == "buddha2-development-inputs-v1"
        and isinstance(value.get("tasks"), list) and len(value["tasks"]) == 4
        and all(isinstance(task, dict) and isinstance(task.get("parent_task_id"), str)
            and bool(task["parent_task_id"].strip()) for task in value["tasks"])
        and len({task["parent_task_id"] for task in value["tasks"]}) == 4
        and all(isinstance(value.get(key), str) and len(value[key]) == 64
            and all(char in "0123456789abcdef" for char in value[key]) for key in hashes),
        "invalid portable development inputs")
    return value


def frozen_tasks() -> list[dict]:
    tasks = copy.deepcopy(_scientific_inputs()["tasks"])
    for index, task in enumerate(tasks, 1):
        task["pilot_id"] = f"p3b-{index:02}"
    tasks[0]["arm_order"] = ["adaptive", "fixed"]
    return tasks


def _task(entry: dict) -> dict:
    return {
        "id": entry["parent_task_id"],
        "domain": "phase3b-development",
        "prompt": entry["prompt"],
        "source_context": entry["source_context"],
    }


def _fixed_id(study: dict, pilot: str) -> str:
    return f"{study['execution_tag']}:{pilot}:fixed"


def _native_tag(study: dict, pilot: str) -> str:
    return f"{study['execution_tag']}-{pilot}"


def _assessment_id(study: dict, pilot: str, target: str) -> str:
    return f"{study['execution_tag']}:{pilot}:{target}:candidate"


def _fixed_order(study: dict) -> dict:
    return {
        entry["pilot_id"]: sorted(
            [f"{_fixed_id(study, entry['pilot_id'])}/candidate-{i:02}" for i in range(1, 13)],
            key=lambda rid: digest(
                {
                    "task_id": entry["parent_task_id"],
                    "run_id": _fixed_id(study, entry["pilot_id"]),
                    "candidate_run_id": rid,
                }
            ),
        )
        for entry in study["tasks"]
    }


def _target_portfolio(branch: dict | None, target: str) -> dict | None:
    result = (branch or {}).get("result") or {}
    return (
        result.get("portfolio") if target == "fixed" else result.get("checkpoints", {}).get(target)
    )


def _pair_seal(study: dict, pilot: str, branches: dict, prefix: dict) -> dict:
    native_result = branches[pilot, "adaptive"].get("result") or {}
    return seal(
        {
            "kind": "phase3b-seq2-pair-seal-v1",
            "study_sha256": study["study_sha256"],
            "pilot": pilot,
            "branches": {arm: branches[pilot, arm]["sha256"] for arm in ARMS},
            "finals": {arm: branches[pilot, arm]["portfolio_sha256"] for arm in ARMS},
            "checkpoints": {
                key: digest(value) for key, value in native_result.get("checkpoints", {}).items()
            },
            "selected_checkpoint": native_result.get("selected_checkpoint"),
            "journal_prefix": prefix,
        }
    )


def _first_done(study: dict, saved: dict, state: dict) -> bool:
    first = study["tasks"][0]["pilot_id"]
    rows = [row for row in study["assessment_plan"] if row["pilot"] == first]
    return (
        first in saved["seals"]
        and len(rows) == 3
        and all(saved["assessments"].get(row["id"], {}).get("status") == "scored" for row in rows)
    )


def _empty_state(study: dict, fixture: bool) -> dict:
    return accounting.core._start(
        {"run_id": None, "inputs": {"study_sha256": study["study_sha256"], "fixture": fixture}}
    )


def paths(study: dict, fixture: bool) -> tuple[Path, Path]:
    return NATIVE / study["study_sha256"] / (
        "mock" if fixture else "live"
    ), accounting.canonical_journal(study["study_sha256"], fixture)


def _plan_slots(study: dict) -> tuple[dict, list[dict]]:
    slots, assessments = {}, []
    for entry in study["tasks"]:
        pilot, task = entry["pilot_id"], _task(entry)
        for arm in ARMS:
            cell = pilot + ":" + arm
            run_ids = (
                [f"{_fixed_id(study, pilot)}/candidate-{i:02}" for i in range(1, 13)]
                if arm == "fixed"
                else list(native.adaptive_run_ids(task["id"], _native_tag(study, pilot)).values())
            )
            require(
                len(run_ids) == (12 if arm == "fixed" else 8),
                "native/fixed rollout population differs",
            )
            for run_id in run_ids:
                ids = strategy.slot_ids(run_id)
                for role, names in (
                    ("plan", [ids["plan"]]),
                    ("answer", ids["answers"]),
                    ("rank", [ids["rank"]]),
                ):
                    for name in names:
                        slots[name] = {"role": role, "cell": cell, "pair": pilot}
            if arm == "fixed":
                slots[strategy.slot_prefix(_fixed_id(study, pilot)) + ".selector"] = {
                    "role": "fixed_selector",
                    "cell": cell,
                    "pair": pilot,
                }
            else:
                conversations = [
                    (f"{stage}.a{attempt}", "editor")
                    for stage in ("inv1", "dom1", "c1", "inv2", "dom2", "c2")
                    for attempt in (1, 2)
                ]
                conversations.append(("select.seq2", "native_selector"))
                for label, role in conversations:
                    for turn in range(1, 25):
                        slots[f"{pilot}.adaptive.editor.{label}.t{turn:02}"] = {
                            "role": role,
                            "cell": cell,
                            "pair": pilot,
                            "conversation": cell + ":" + label,
                            "turn": turn,
                        }
        for target in ("fixed", "c1", "c2"):
            assessments.append(
                {
                    "id": _assessment_id(study, pilot, target),
                    "pilot": pilot,
                    "arm": "fixed" if target == "fixed" else "adaptive",
                    "target": target,
                    "diagnostic": False,
                }
            )
    for row in assessments:
        prefix = native.Phase3NativeAssessment.slot_prefix(row["id"])
        slots[prefix + ".group"] = {"role": "group", "cell": "assessment", "pair": row["pilot"]}
        for index in range(10):
            slots[f"{prefix}.quality.{index:02}"] = {
                "role": "quality",
                "cell": "assessment",
                "pair": row["pilot"],
            }
    accounting._slot_scope(slots)
    return slots, assessments


def _validate_seal_prefix(study: dict, journal: Path, seal_record: dict) -> None:
    """Same seal ordering invariant, reading the explicitly versioned HI journal."""
    events = accounting.events(journal)
    prefix, pilot = seal_record["journal_prefix"], seal_record["pilot"]
    index = prefix["index"]
    require(
        type(index) is int
        and 0 <= index <= len(events)
        and set(prefix) == {"index", "event_sha256"},
        "invalid seal journal prefix",
    )
    require(
        prefix["event_sha256"] == (events[index - 1]["event_sha256"] if index else None),
        "seal prefix changed",
    )
    for event in events:
        if event["kind"] == "intent":
            meta = study["slots"][event["record"]["slot_id"]]
            if meta["pair"] == pilot:
                require(
                    (meta["cell"] == "assessment") == (event["index"] > index),
                    "judging preceded a paired final seal or inference followed it",
                )


def prepare(
    output: Path,
    *,
    source: dict | None = None,
    runtime: dict | None = None,
    supervised_fixture: bool = False,
    boundary_fixture: bool = False,
) -> dict:
    output = path(output)
    require(type(supervised_fixture) is bool, "supervised fixture flag must be boolean")
    require(type(boundary_fixture) is bool and (not boundary_fixture or supervised_fixture),
            "boundary-only fixture requires the supervised, generation-free route")
    authority = validate_authority()
    sources, environment = source or source_identity(), runtime or runtime_identity()
    snapshot_policy = source_snapshot_policy(sources["files"])
    old = _scientific_inputs()
    tasks = frozen_tasks()
    body = {
        "kind": "buddha2-effective-seq2-study-v2",
        "source": sources,
        "source_sha256": sources["sha256"],
        "source_snapshot_policy": snapshot_policy,
        "runtime": environment,
        "runtime_sha256": digest(environment),
        "definition_sha256": DECLARED_DEFINITION_SHA256,
        "authorization_sha256": file_hash(AUTHORITY),
        "specification_sha256": DECLARED_DEFINITION_SHA256,
        "launcher_sha256": file_hash(LAUNCHER),
        "policy": accounting.POLICY,
        "policy_sha256": digest(accounting.POLICY),
        "tasks": tasks,
        "execution_tag": "phase3b-seq2-"
        + digest({"source": sources["sha256"], "tasks": tasks})[:20],
        "transport_deadline_policy": asdict(DEADLINE_POLICY),
        "conversation_timing_policy": copy.deepcopy(CONVERSATION_POLICY),
        "editor_tools": read(ROOT / "followups/phase3a_v1/editor-tools.json"),
        "seed_tree": strategy.seed_tree(),
        "parent_decision_sha256": old["parent_decision_sha256"],
        "rank_io_profile": rank_io.profile(),
        "startup_supervision_profile": supervision.profile(),
        "read_consumption_policy": READ_CONSUMPTION_POLICY,
        "fixture_supervision_rehearsal": supervised_fixture,
        "fixture_boundary_contract": boundary_fixture,
        "seed_procedure_sha256": old["seed_procedure_sha256"],
        "authority": authority,
        "prior_live_episode": {
            "known_spent_micro_usd": 46044365,
            "reserved_micro_usd": 22880000,
            "provider_calls": 1997,
            "known_requests": 1995,
            "unknown_requests": 2,
        },
        "prior_closed_attempt": copy.deepcopy(PRIOR_CLOSED_ATTEMPT),
        "prior_closed_repeat": copy.deepcopy(PRIOR_CLOSED_REPEAT),
        "prior_closed_artifact_attempt": copy.deepcopy(PRIOR_CLOSED_ARTIFACT_ATTEMPT),
        "readiness_is_primary": "p3b-01:adaptive",
        "readiness_max_micro_usd": 35000000,
        "potential_slot_count": accounting.WORKLIST_PROFILE["potential_request_slots"],
        "maximum_admitted_attempts": accounting.WORKLIST_PROFILE["maximum_admitted_attempts"],
        "editor_steps": 24,
    }
    body["slots"], body["assessment_plan"] = _plan_slots(body)
    body["fixed_candidate_order"] = _fixed_order(body)
    study = {**body, "study_sha256": digest(body)}
    publish(output / "study.json", study)
    strategy.materialize_seed(output / "seed")
    for name, expected in sources["files"].items():
        if name in snapshot_policy["canonical_originals"]:
            continue
        source_path = safe(ROOT / name)
        require(file_hash(source_path) == expected, "source changed while freezing the new study")
        write_bytes_once(safe(output / "source" / name), source_path.read_bytes())
    return study


def load_study(study_path: Path) -> dict:
    study_path = path(study_path)
    study = read(study_path)
    require(
        study.get("kind") == "buddha2-effective-seq2-study-v2"
        and isinstance(study.get("source"), dict)
        and study["source"].get("kind") == "buddha2-effective-source-v2"
        and study["study_sha256"]
        == digest({k: v for k, v in study.items() if k != "study_sha256"}),
        "completion study seal differs",
    )
    require(study.get("source_snapshot_policy") == source_snapshot_policy(study["source"]["files"]),
            "completion source snapshot policy differs")
    require(
        study["source"] == source_identity()
        and study["source_sha256"] == study["source"]["sha256"]
        and study["runtime"] == runtime_identity()
        and study["runtime_sha256"] == digest(study["runtime"])
        and study["definition_sha256"] == DECLARED_DEFINITION_SHA256
        and study["specification_sha256"] == DECLARED_DEFINITION_SHA256
        and study["authorization_sha256"] == file_hash(AUTHORITY)
        and study["authority"] == validate_authority(),
        "completion source/runtime/authority changed",
    )
    old = _scientific_inputs()
    require(
        study["tasks"] == frozen_tasks()
        and study["execution_tag"]
        == "phase3b-seq2-"
        + digest({"source": study["source_sha256"], "tasks": study["tasks"]})[:20]
        and study["parent_decision_sha256"] == old["parent_decision_sha256"]
        and study["seed_procedure_sha256"] == old["seed_procedure_sha256"]
        and study["seed_tree"] == strategy.seed_tree()
        and study["rank_io_profile"] == rank_io.profile()
        and study["startup_supervision_profile"] == supervision.profile()
        and study["read_consumption_policy"] == READ_CONSUMPTION_POLICY
        and type(study["fixture_supervision_rehearsal"]) is bool
        and type(study["fixture_boundary_contract"]) is bool
        and (not study["fixture_boundary_contract"] or study["fixture_supervision_rehearsal"])
        and study["editor_tools"] == read(ROOT / "followups/phase3a_v1/editor-tools.json")
        and study["launcher_sha256"] == file_hash(LAUNCHER)
        and study["prior_live_episode"]
        == {
            "known_spent_micro_usd": 46044365,
            "reserved_micro_usd": 22880000,
            "provider_calls": 1997,
            "known_requests": 1995,
            "unknown_requests": 2,
        }
        and study["prior_closed_attempt"] == PRIOR_CLOSED_ATTEMPT
        and study["prior_closed_repeat"] == PRIOR_CLOSED_REPEAT
        and study["prior_closed_artifact_attempt"] == PRIOR_CLOSED_ARTIFACT_ATTEMPT
        and study["transport_deadline_policy"] == asdict(DEADLINE_POLICY)
        and study["conversation_timing_policy"] == CONVERSATION_POLICY
        and study["readiness_is_primary"] == "p3b-01:adaptive"
        and study["readiness_max_micro_usd"] == 35000000
        and study["potential_slot_count"] == accounting.WORKLIST_PROFILE["potential_request_slots"]
        and study["maximum_admitted_attempts"] == accounting.WORKLIST_PROFILE["maximum_admitted_attempts"]
        and study["editor_steps"] == 24,
        "completion method/tasks/history differ from the frozen definition",
    )
    require(
        (study["slots"], study["assessment_plan"]) == _plan_slots(study)
        and study["fixed_candidate_order"] == _fixed_order(study)
        and study["policy"] == accounting.POLICY
        and study["policy_sha256"] == digest(accounting.POLICY),
        "completion worklist/policy changed",
    )
    require(
        strategy.validate_harness(study_path.parent / "seed")["tree"] == study["seed_tree"],
        "seed changed",
    )
    require(
        all(
            file_hash(safe(study_path.parent / "source" / name)) == sha
            for name, sha in study["source"]["files"].items()
            if name not in study["source_snapshot_policy"]["canonical_originals"]
        ),
        "retained completion source changed",
    )
    return study


def make_grant(study_path: Path, fixture: bool) -> dict:
    study = load_study(study_path)
    require(
        type(fixture) is bool and (fixture or not study["fixture_supervision_rehearsal"])
        and (fixture or not study["fixture_boundary_contract"]),
        "supervised fixture study cannot receive a provider grant",
    )
    authority = {
        "study_sha256": study["study_sha256"],
        "authorization_id": "phase3b-continuation-user-approval",
        "authorized": not fixture,
        "cap_micro_usd": accounting.POLICY["phase_micro_usd"],
        "canary_cap_micro_usd": accounting.POLICY["first_micro_usd"],
        "expansion_authorized": False,
        "control_policy_sha256": am1.CONTROL_SHA256,
        "billing_profile": am1.BILLING_PROFILE,
    }
    result = {
        "kind": "phase3b-seq2-grant-v1",
        "fixture": fixture,
        "authority": authority,
        **{
            key: study[key]
            for key in (
                "study_sha256",
                "source_sha256",
                "policy_sha256",
                "runtime_sha256",
                "launcher_sha256",
            )
        },
    }
    return {**result, "grant_sha256": digest(result)}


def grant_for(study: dict, grant_path: Path, fixture: bool) -> dict:
    require(
        type(fixture) is bool and (fixture or not study["fixture_supervision_rehearsal"]),
        "supervised fixture study cannot dispatch providers",
    )
    grant = read(path(grant_path))
    require(
        grant.get("kind") == "phase3b-seq2-grant-v1"
        and grant.get("fixture") is fixture
        and grant["grant_sha256"] == digest({k: v for k, v in grant.items() if k != "grant_sha256"})
        and all(
            grant.get(k) == study[k]
            for k in (
                "study_sha256",
                "source_sha256",
                "policy_sha256",
                "runtime_sha256",
                "launcher_sha256",
            )
        ),
        "completion grant identity differs",
    )
    accounting.validate_authority(
        study["study_sha256"],
        grant["authority"],
        fixture,
        {k: study[k] for k in ("source_sha256", "policy_sha256", "launcher_sha256")},
    )
    return grant


def _branch_path(run: Path, pilot: str, arm: str) -> Path:
    return run / "branches" / f"{pilot}-{arm}.json"


def _search(run: Path, pilot: str, arm: str) -> Path:
    return run / "search" / pilot / arm


def saved(study_path: Path, study: dict, state: dict, fixture: bool) -> dict:
    run, journal = paths(study, fixture)
    seed = study_path.parent / "seed"
    branches, seals, assessments = {}, {}, {}
    with strategy.validation_scope(readonly=True):
        for entry in study["tasks"]:
            pilot, task = entry["pilot_id"], _task(entry)
            for arm in ARMS:
                search = _search(run, pilot, arm)
                if arm == "fixed":
                    strategy.validate_fixed_partial(
                        task,
                        seed,
                        study_sha256=study["study_sha256"],
                        run_id=_fixed_id(study, pilot),
                        fixture=fixture,
                        results=state["results"],
                    )
                else:
                    editor.validate_persisted_sessions(
                        search / "editor-audit",
                        study_sha256=study["study_sha256"],
                        pilot=pilot,
                        fixture=fixture,
                        results=state["results"],
                        intents=state["intents"],
                    )
                    native.validate_adaptive_partial(
                        task,
                        seed,
                        study_sha256=study["study_sha256"],
                        run_root=search,
                        tag=_native_tag(study, pilot),
                        fixture=fixture,
                        results=state["results"],
                    )
                target = _branch_path(run, pilot, arm)
                if not target.exists():
                    continue
                record = checked(read(target))
                require(
                    record["study_sha256"] == study["study_sha256"]
                    and record["fixture"] is fixture
                    and record["pilot"] == pilot
                    and record["arm"] == arm,
                    "foreign saved branch",
                )
                result = record["result"]
                if result is not None:
                    if arm == "fixed":
                        strategy.validate_fixed(
                            result,
                            task,
                            seed,
                            study_sha256=study["study_sha256"],
                            run_id=_fixed_id(study, pilot),
                            fixture=fixture,
                            results=state["results"],
                            stopped=pilot + ":fixed" in state.get("stopped_cells", []),
                        )
                    else:
                        native.validate_adaptation(
                            result,
                            task,
                            seed,
                            study_sha256=study["study_sha256"],
                            run_root=search,
                            tag=_native_tag(study, pilot),
                            fixture=fixture,
                            results=state["results"],
                        )
                portfolio = result.get("portfolio") if result else None
                require(
                    record["portfolio_sha256"] == (digest(portfolio) if portfolio else None),
                    "saved final changed",
                )
                branches[pilot, arm] = record
            target = run / "seals" / f"{pilot}.json"
            if target.exists():
                seal_record = checked(read(target))
                require(
                    all((pilot, arm) in branches for arm in ARMS)
                    and seal_record
                    == _pair_seal(study, pilot, branches, seal_record["journal_prefix"]),
                    "pair seal changed",
                )
                _validate_seal_prefix(study, journal, seal_record)
                seals[pilot] = seal_record
    evaluator = native.Phase3NativeAssessment(ROOT / ".upstream/novelty-bench")
    remaining = {
        slot for slot, result in state["results"].items() if result["role"] in {"group", "quality"}
    }
    for row in study["assessment_plan"]:
        branch = branches.get((row["pilot"], row["arm"]))
        portfolio = _target_portfolio(branch, row["target"])
        prefix = evaluator.slot_prefix(row["id"])
        group = state["results"].get(prefix + ".group")
        if group is not None:
            if not isinstance(portfolio, dict) or row["pilot"] not in seals:
                raise ContractError("judgment lacks both sealed finals")
            require(
                group["request_sha256"] == digest(evaluator.group_request(portfolio)),
                "saved group body changed",
            )
            remaining.remove(prefix + ".group")
            try:
                partition = evaluator.fold_group(portfolio, group, assessment_id=row["id"])[
                    "partition"
                ]
            except ValueError:
                partition = None
            if partition is not None:
                heads = evaluator.modules["score"].heads(partition)
                for head, request in zip(
                    heads, evaluator.quality_requests(portfolio, partition), strict=True
                ):
                    slot = f"{prefix}.quality.{head:02}"
                    if slot in state["results"]:
                        require(
                            state["results"][slot]["request_sha256"] == digest(request),
                            "saved quality body changed",
                        )
                        remaining.remove(slot)
        target = run / "assessments" / (prefix + ".json")
        if target.exists():
            assessment = read(target)
            if not isinstance(portfolio, dict) or row["pilot"] not in seals or group is None:
                raise ContractError("saved assessment lacks sealed portfolio")
            require(
                all(
                    record == state["results"].get(record["slot_id"])
                    for record in assessment["requests"]
                ),
                "foreign assessment result",
            )
            require(
                assessment
                == evaluator.finalize(
                    portfolio,
                    assessment["requests"][0],
                    assessment["requests"][1:],
                    assessment_id=row["id"],
                ),
                "assessment does not exactly replay",
            )
            assessments[row["id"]] = assessment
    require(not remaining, "undeclared/foreign judge results")
    readiness = (
        checked(read(run / "readiness-review.json"))
        if (run / "readiness-review.json").exists()
        else None
    )
    return {
        "branches": branches,
        "seals": seals,
        "assessments": assessments,
        "readiness": readiness,
    }


def _state(study: dict, fixture: bool) -> dict:
    _, journal = paths(study, fixture)
    return (
        accounting.replay(journal)
        if (journal / "manifest.json").exists()
        else _empty_state(study, fixture)
    )


def preflight(
    study_path: Path,
    grant_path: Path,
    fixture: bool,
    stage: str = "all",
    *,
    require_offline_gate: bool = True,
) -> dict:
    require(stage in STAGES and type(fixture) is bool, "unknown completion invocation")
    require(type(require_offline_gate) is bool, "offline-gate selector must be explicit")
    study = load_study(study_path)
    grant = grant_for(study, grant_path, fixture)
    require(not study["fixture_boundary_contract"], "boundary-only fixture cannot admit model work")
    run, journal = paths(study, fixture)
    require(
        not path(run / "canonical-stop.json").exists(),
        "canonical checkpoint stop prevents all later calls",
    )
    if not fixture and require_offline_gate:
        offline_readiness(study_path, {key: study[key] for key in (
            "study_sha256", "source_sha256", "runtime_sha256", "policy_sha256", "launcher_sha256"
        )})
    state = _state(study, fixture)
    require(
        state["status"] == "ready" and state["reserved_micro_usd"] == 0,
        "unresolved completion accounting blocks dispatch",
    )
    require(
        not (run / "readiness-failure.json").exists(),
        "known readiness failure prevents further calls",
    )
    require(
        not (run / "primary-stop.json").exists(), "irrecoverable primary prevents further calls"
    )
    records = saved(study_path, study, state, fixture)
    if stage in {"first", "remaining"} or records["readiness"] is not None:
        validate_readiness_review(study, run, state, records, fixture)
    if stage == "remaining":
        require(state["engineering_review"] is not None, "first-pair engineering review required")
    return {
        "kind": "phase3b-seq2-preflight-v1",
        **{
            k: study[k]
            for k in (
                "study_sha256",
                "source_sha256",
                "policy_sha256",
                "runtime_sha256",
                "launcher_sha256",
            )
        },
        "grant_sha256": grant["grant_sha256"],
        "fixture": fixture,
        "run": str(run),
        "journal": str(journal),
        "provider_calls": 0,
        "credentials_read": False,
    }


def _readiness_check(study: dict, run: Path, state: dict, records: dict, fixture: bool) -> dict:
    from .evidence import verify_readiness

    branch = records["branches"].get(("p3b-01", "adaptive"))
    require(branch is not None, "counted native readiness branch missing")
    return verify_readiness(study, run, state, branch, fixture)


def validate_readiness_review(
    study: dict, run: Path, state: dict, records: dict, fixture: bool
) -> dict:
    record = records["readiness"]
    require(
        record is not None
        and record.get("passed") is True
        and record.get("kind") == "phase3b-seq2-counted-readiness-review-v1"
        and record.get("study_sha256") == study["study_sha256"]
        and record.get("source_sha256") == study["source_sha256"]
        and record.get("fixture") is fixture,
        "counted readiness review has another source/study/mode",
    )
    proof = _readiness_check(study, run, state, records, fixture)
    require(
        record["proof"] == proof
        and record["inspection"]["evidence_sha256"] == digest(proof)
        and record["inspection"]["hard_engineering_checks_passed"] is True
        and record["inspection"]["read_diagnostics_reviewed"] is True
        and record["branch_sha256"] == records["branches"]["p3b-01", "adaptive"]["sha256"],
        "readiness review is unsupported by actual native evidence",
    )
    return record


def _review_readiness(
    study_path: Path, study: dict, state: dict, records: dict, fixture: bool, audit: dict
) -> dict:
    run, _ = paths(study, fixture)
    proof = _readiness_check(study, run, state, records, fixture)
    require(
        audit.get("study_sha256") == study["study_sha256"]
        and audit.get("evidence_sha256") == digest(proof)
        and audit.get("hard_engineering_checks_passed") is True
        and audit.get("read_diagnostics_reviewed") is True
        and audit.get("no_quality_continuation_gate") is True
        and audit.get("fixture") is fixture
        and isinstance(audit.get("notes"), str)
        and bool(audit["notes"].strip()),
        "trusted readiness inspection differs",
    )
    record = seal(
        {
            "kind": "phase3b-seq2-counted-readiness-review-v1",
            "passed": True,
            "study_sha256": study["study_sha256"],
            "source_sha256": study["source_sha256"],
            "proof": proof,
            "inspection": audit,
            "fixture": fixture,
            "branch_sha256": records["branches"]["p3b-01", "adaptive"]["sha256"],
        }
    )
    publish(run / "readiness-review.json", record)
    return record


def _first_review(
    study_path: Path, study: dict, state: dict, records: dict, fixture: bool, *, closure=False
) -> None:
    run, journal = paths(study, fixture)
    require(
        "p3b-01" in records["seals"]
        and state["status"] == "ready"
        and not state["reserved_micro_usd"],
        "first pair not reviewable",
    )
    files = [
        run / "seals/p3b-01.json",
        *[_branch_path(run, "p3b-01", arm) for arm in ARMS],
        journal / "manifest.json",
    ]
    record = {
        "review_id": "c1-completion-first-closed" if closure else "c1-completion-first-engineering",
        "study_sha256": study["study_sha256"],
        "run_id": state["run_id"],
        "state_sha256": digest(accounting.raw_state(state)),
        "checks": dict.fromkeys(accounting.CHECKS, True),
        "evidence": {str(p): file_hash(p) for p in files},
        "first_assessments_closed": _first_done(study, records, state),
    }

    def validate(prefix, value):
        require(
            value == record
            and all(file_hash(Path(name)) == sha for name, sha in value["evidence"].items()),
            "first review evidence changed",
        )
        current = saved(study_path, study, prefix, fixture)
        require(
            "p3b-01" in current["seals"]
            and value["first_assessments_closed"] == _first_done(study, current, prefix),
            "unsupported first-assessment closure",
        )

    if closure:
        accounting.close_first_assessments(journal, record, validate_evidence=validate)
    else:
        accounting.publish_review(journal, record, validate_evidence=validate)


def _snapshot_records(study_path: Path, study: dict, state: dict, fixture: bool) -> dict:
    """Keep report and visibility views on the same validated/held evidence rule."""
    run, _ = paths(study, fixture)
    stop_path = path(run / "canonical-stop.json")
    if stop_path.exists():
        stop = checked(read(stop_path))
        require(
            stop.get("study_sha256") == study["study_sha256"]
            and stop.get("source_sha256") == study["source_sha256"]
            and stop.get("fixture") is fixture,
            "foreign canonical stop marker",
        )
        return {
            "branches": {},
            "seals": {},
            "assessments": {},
            "readiness": None,
            "snapshot_observed_at_utc": datetime.now(timezone.utc).isoformat(),
            "audit_intervals": {},
            "validation_failure": {
                "exception_type": "CanonicalCheckpointStop",
                "scientific_use": "disqualified",
                "classification": "integrity_hold",
                "canonical_stop": stop,
            },
            "deadline_stop": state.get("deadline_stop"),
        }
    try:
        records = saved(study_path, study, state, fixture)
        if records["readiness"] is not None:
            validate_readiness_review(study, run, state, records, fixture)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        if state["status"] == "ready" and not (run / "readiness-failure.json").exists():
            raise
        records = {
            "branches": {},
            "seals": {},
            "assessments": {},
            "readiness": None,
            "validation_failure": {
                "exception_type": type(exc).__name__,
                "scientific_use": "disqualified",
                "classification": "known_deadline_stop"
                if state.get("deadline_stop") is not None
                else "integrity_hold",
            },
            "deadline_stop": state.get("deadline_stop"),
        }
    records["audit_intervals"] = {}
    records["snapshot_observed_at_utc"] = datetime.now(timezone.utc).isoformat()
    if "validation_failure" not in records:
        from .transport import audit_path, read_audit

        for slot, result in state["results"].items():
            audit = read_audit(
                study["study_sha256"],
                fixture,
                slot,
                intent=state["intents"][slot],
                result=result,
                bindings={
                    key: study[key] for key in ("source_sha256", "policy_sha256", "launcher_sha256")
                },
            )
            records["audit_intervals"][slot] = {
                "started_at_utc": audit["budget"]["started_utc"],
                "finished_at_utc": audit["finished_utc"],
                "audit_file_sha256": file_hash(audit_path(study["study_sha256"], fixture, slot)),
                **{key: result[key] for key in ("input_tokens", "output_tokens") if key in result},
            }
    return records


def _fold_view(study: dict, state: dict, records: dict, fixture: bool) -> dict:
    from .report import build

    run, _ = paths(study, fixture)
    data = build(study, state, records, fixture)
    data["protocol"]["rank_io_profile"] = rank_io.profile()
    stop_file = run / "primary-stop.json"
    if stop_file.exists():
        primary_stop = checked(read(stop_file))
        require(
            primary_stop.get("study_sha256") == study["study_sha256"]
            and primary_stop.get("fixture") is fixture,
            "foreign primary stop",
        )
        for key in ("summary", "analysis", "protocol", "coverage"):
            data[key]["primary_stop"] = primary_stop
        data["summary"].update(
            status="incomplete", complete_primary=False, scientific_complete=False
        )
        data["analysis"].update(
            complete_primary=False,
            scientific_complete=False,
            mean_adaptive_minus_fixed=None,
            selected_method=None,
            descriptive_direction=None,
        )
        for slot, classification in data["coverage"]["slots"].items():
            if classification.startswith("not_attempted"):
                data["coverage"]["slots"][slot] = "not_attempted_primary_failfast"
        from collections import Counter

        data["coverage"]["slot_counts"] = dict(Counter(data["coverage"]["slots"].values()))
        data["summary"].pop("evidence_sha256", None)
        data["summary"]["evidence_sha256"] = digest(data)
    data["summary"].pop("evidence_sha256", None)
    data["summary"]["evidence_sha256"] = digest(data)
    return data


def snapshot(study_path: Path, grant_path: Path, fixture: bool) -> dict:
    study = load_study(study_path)
    grant_for(study, grant_path, fixture)
    state = _state(study, fixture)
    records = _snapshot_records(study_path, study, state, fixture)
    return _fold_view(study, state, records, fixture)


def _barrier(study_path: Path, study: dict, grant_path: Path, fixture: bool, name: str) -> None:
    run, _ = paths(study, fixture)
    state = _state(study, fixture)
    records = saved(study_path, study, state, fixture)
    proof = (
        _readiness_check(study, run, state, records, fixture)
        if name == "readiness"
        else {
            "study_sha256": study["study_sha256"],
            "pair_seal": records["seals"]["p3b-01"],
            "state_sha256": digest(state),
        }
    )
    publish(
        run / f"barrier-{name}.json",
        seal(
            {
                "kind": "phase3b-seq2-review-barrier-v1",
                "stage": name,
                "study_sha256": study["study_sha256"],
                "proof": proof,
                "evidence_sha256": digest(proof),
                "fixture": fixture,
            }
        ),
    )
    audit_path = run / f"inspection-{name}.json"
    if fixture and not study["fixture_supervision_rehearsal"]:
        publish(
            audit_path,
            {
                "study_sha256": study["study_sha256"],
                "evidence_sha256": digest(proof),
                "fixture": True,
                "hard_engineering_checks_passed": True,
                "read_diagnostics_reviewed": True,
                "no_quality_continuation_gate": True,
                "engineering_checks_passed": True,
                "notes": "Scripted offline structural inspection only; not actual model readiness.",
            },
        )
    deadline = time.monotonic() + 1800
    while not audit_path.exists():
        require(time.monotonic() < deadline, "review barrier timed out with no additional dispatch")
        time.sleep(1)
    audit = read(audit_path)
    require(
        audit.get("study_sha256") == study["study_sha256"]
        and audit.get("evidence_sha256") == digest(proof)
        and audit.get("fixture") is fixture
        and audit.get("no_quality_continuation_gate") is True,
        "review audit has another identity",
    )
    if name == "readiness":
        _review_readiness(study_path, study, state, records, fixture, audit)
    else:
        require(
            audit.get("engineering_checks_passed") is True and bool(audit.get("notes")),
            "first-pair engineering audit incomplete",
        )
        publish(
            run / "first-review.json",
            seal(
                {
                    "kind": "phase3a-c1-first-review-v1",
                    "study_sha256": study["study_sha256"],
                    "inspection": audit,
                }
            ),
        )
        _first_review(study_path, study, state, records, fixture)


def _run_stage(
    study_path: Path,
    study: dict,
    grant: dict,
    stage: str,
    transport: Any,
    grant_path: Path,
    *,
    _summary: bool = True,
) -> dict | None:
    run, journal = paths(study, transport.fixture)
    fixture = transport.fixture
    records = saved(study_path, study, _state(study, fixture), fixture)
    stop = threading.Event()
    failure_path = run / "readiness-failure.json"
    primary_stop_path = run / "primary-stop.json"
    canonical_stop_path = path(run / "canonical-stop.json")

    def primary_stop(pilot, arm, reason):
        stop.set()
        current = _state(study, fixture)
        require(
            current["status"] in {"ready", "halted-budget"} and current["reserved_micro_usd"] == 0,
            "primary stop cannot settle an uncertain provider outcome",
        )
        publish(
            primary_stop_path,
            seal(
                {
                    "kind": "p3b-hi-primary-failfast-v1",
                    "study_sha256": study["study_sha256"],
                    "source_sha256": study["source_sha256"],
                    "fixture": fixture,
                    "pilot": pilot,
                    "arm": arm,
                    "reason": reason,
                    "attempts": current["attempts"],
                    "spent_micro_usd": current["spent_micro_usd"],
                    "remaining_slots_are_unattempted": True,
                }
            ),
        )

    def known_stop(reason):
        stop.set()
        publish(
            failure_path,
            seal(
                {
                    "kind": "phase3a-c1-readiness-known-stop-v1",
                    "study_sha256": study["study_sha256"],
                    "reason": reason,
                    "fixture": fixture,
                    "unknown_charge_inferred": False,
                }
            ),
        )

    def guard(state):
        if (
            stop.is_set()
            or failure_path.exists()
            or primary_stop_path.exists()
            or canonical_stop_path.exists()
        ):
            raise accounting.ReadinessStop("known readiness failure; no further admission")
        if stage != "readiness":
            review = checked(read(run / "readiness-review.json"))
            require(
                review["passed"] is True
                and review["study_sha256"] == study["study_sha256"]
                and review["branch_sha256"] == records["branches"]["p3b-01", "adaptive"]["sha256"],
                "readiness review changed",
            )

    ledger = accounting.Ledger(
        journal,
        study_sha256=study["study_sha256"],
        slots=study["slots"],
        authority=grant["authority"],
        transport=transport,
        editor_tools=study["editor_tools"],
        bindings={k: study[k] for k in ("source_sha256", "policy_sha256", "launcher_sha256")},
        stage=stage,
        readiness_validator=guard,
    )
    if ledger.state()["assessment_stopped"]:
        # A full-pool stop is irreversible, including one reached by the duplicate.
        # Never enter another native/fixed generation stage on a resumed owner.
        primary_stop("assessment", None, "primary_assessment_pool_exhausted")
        return snapshot(study_path, grant_path, fixture)["summary"] if _summary else None

    def halt(reason, evidence_sha256=None):
        if not stop.is_set():
            ledger.halt(reason, evidence_sha256)

    def dispatch_for(pilot, arm=None):
        cell = pilot + ":" + arm if arm else "assessment"

        def dispatch(slot, role, request, **kwargs):
            require(
                slot in study["slots"]
                and study["slots"][slot]["cell"] == cell
                and study["slots"][slot]["pair"] == pilot,
                "request escaped paired cell",
            )
            if (
                stage == "readiness"
                and role in {"editor", "native_selector"}
                and slot.endswith(".t24")
            ):
                accounting.validate_request(role, request, editor_tools=study["editor_tools"])
                require(
                    request.get("messages") and editor._terminal_shape(request["messages"][-1]),
                    "unexpected twenty-fourth readiness request is not the pinned terminal control",
                )
                known_stop("forced_terminal_control_before_dispatch")
                raise accounting.ReadinessStop("normal readiness window exhausted")
            return ledger.dispatch(slot, role, request, **kwargs)

        return dispatch

    evaluator = native.Phase3NativeAssessment(ROOT / ".upstream/novelty-bench")
    for entry in study["tasks"]:
        pilot, task = entry["pilot_id"], _task(entry)
        if stage in {"readiness", "first"} and pilot != "p3b-01":
            break
        if pilot != "p3b-01" and not ledger.state()["first_assessments_closed"]:
            break
        for arm in ["adaptive"] if stage == "readiness" else entry["arm_order"]:
            if (pilot, arm) in records["branches"]:
                continue
            result, failure, c1_evidence = None, None, None
            try:
                if arm == "fixed":
                    result = strategy.fixed_best12(
                        task,
                        study_path.parent / "seed",
                        study_sha256=study["study_sha256"],
                        run_id=_fixed_id(study, pilot),
                        fixture=fixture,
                        dispatch=dispatch_for(pilot, arm),
                        known_results=ledger.state()["results"],
                    )
                else:
                    callback = getattr(transport, "register_contract", None)
                    prop = ReadinessProposer(
                        observe=stage == "readiness",
                        known_stop=known_stop,
                        can_stop=lambda: ledger.state()["status"] == "ready" and not stop.is_set(),
                        pilot=pilot,
                        study_sha256=study["study_sha256"],
                        dispatch=dispatch_for(pilot, arm),
                        audit_dir=_search(run, pilot, arm) / "editor-audit",
                        fixture=fixture,
                        halt=halt,
                        source_sha256=study["source_sha256"],
                        register_deadline=transport.register_conversation,
                        register_contract=(lambda label, prepared: callback(pilot, label, prepared))
                        if callback
                        else None,
                    )
                    result = native.run_adaptation(
                        task,
                        study_path.parent / "seed",
                        study_sha256=study["study_sha256"],
                        run_root=_search(run, pilot, arm),
                        tag=_native_tag(study, pilot),
                        dispatch=dispatch_for(pilot, arm),
                        fixture=fixture,
                        prop=prop,
                        known_results=ledger.state()["results"],
                        result_snapshot=lambda: ledger.state()["results"],
                        halt=halt,
                        on_required_failure=lambda event: primary_stop(pilot, "adaptive",
                            "required_checkpoint_" + event["checkpoint"] + "_" + event["category"]),
                    )
                    c1_evidence = prop.c1_evidence()
            except accounting.IntegrityStop:
                halt("completion_component_integrity_failure")
            except (
                ContractError,
                accounting.CellBudgetStop,
                accounting.CheckpointStop,
                accounting.PhaseBudgetStop,
            ) as exc:
                failure = type(exc).__name__
            if ledger.state()["status"] != "ready":
                break
            portfolio = result.get("portfolio") if result else None
            branch = seal(
                {
                    "kind": "phase3a-branch-v1",
                    "study_sha256": study["study_sha256"],
                    "pilot": pilot,
                    "arm": arm,
                    "fixture": fixture,
                    "result": result,
                    "failure": failure,
                    "portfolio_sha256": digest(portfolio) if portfolio else None,
                    "c1_evidence": c1_evidence,
                }
            )
            publish(_branch_path(run, pilot, arm), branch)
            records["branches"][pilot, arm] = branch
            from .report import fixed_pool_complete, native_selection_normal
            current_results = ledger.state()["results"]
            method_missing = (not fixed_pool_complete(result or {}, current_results) if arm == "fixed"
                else not native_selection_normal(result or {}, current_results))
            if (
                portfolio is None
                or method_missing
                or arm == "adaptive"
                and (not result or set(result.get("checkpoints", {})) != {"c1", "c2"}
                    or any(not isinstance(value, dict) for value in result.get("checkpoints", {}).values()))
            ) and not stop.is_set():
                primary_stop(pilot, arm, "missing_required_final_or_checkpoint")
            if stop.is_set():
                break
        if stop.is_set() or ledger.state()["status"] != "ready" or stage == "readiness":
            break
        if not all((pilot, arm) in records["branches"] for arm in ARMS):
            break
        if pilot not in records["seals"]:
            events = accounting.events(journal)
            prefix = {
                "index": len(events),
                "event_sha256": events[-1]["event_sha256"] if events else None,
            }
            pair_seal = _pair_seal(study, pilot, records["branches"], prefix)
            publish(run / "seals" / f"{pilot}.json", pair_seal)
            records["seals"][pilot] = pair_seal
        for row in [row for row in study["assessment_plan"] if row["pilot"] == pilot]:
            if row["id"] in records["assessments"] or ledger.state()["assessment_stopped"]:
                continue
            portfolio = _target_portfolio(records["branches"][pilot, row["arm"]], row["target"])
            if portfolio is None:
                continue
            try:
                assessment = evaluator.assess(
                    portfolio, dispatch_for(pilot), assessment_id=row["id"]
                )
                publish(
                    run / "assessments" / (evaluator.slot_prefix(row["id"]) + ".json"), assessment
                )
                records["assessments"][row["id"]] = assessment
                if not row.get("diagnostic") and assessment.get("status") != "scored":
                    primary_stop(pilot, row["arm"], "unscorable_primary_assessment")
                    return (
                        snapshot(study_path, grant_path, fixture)["summary"] if _summary else None
                    )
            except (accounting.AssessmentBudgetStop, accounting.PhaseBudgetStop, accounting.CheckpointStop):
                # These pools cannot reopen after the counted engineering review.
                # The included first-prompt/assessment ceilings also stay binding after review.
                primary_stop(pilot, row["arm"], "primary_assessment_pool_exhausted")
                return snapshot(study_path, grant_path, fixture)["summary"] if _summary else None
            except (accounting.LiabilityStop, accounting.IntegrityStop):
                return snapshot(study_path, grant_path, fixture)["summary"] if _summary else None
        if (
            pilot == "p3b-01"
            and ledger.state()["engineering_review"]
            and not ledger.state()["first_assessments_closed"]
        ):
            current = ledger.state()
            _first_review(
                study_path,
                study,
                current,
                saved(study_path, study, current, fixture),
                fixture,
                closure=True,
            )
    return snapshot(study_path, grant_path, fixture)["summary"] if _summary else None


def _canonical_halt(study, fixture, reason):
    """Durable admission stop without another unbounded parent financial replay."""
    run, _ = paths(study, fixture)
    target = path(run / "canonical-stop.json")
    if target.exists():
        prior = checked(read(target))
        require(
            prior.get("study_sha256") == study["study_sha256"]
            and prior.get("source_sha256") == study["source_sha256"]
            and prior.get("fixture") is fixture,
            "foreign canonical stop",
        )
        return
    publish(
        target,
        seal(
            {
                "kind": "p3b-hi-canonical-stop-v1",
                **{
                    key: study[key]
                    for key in (
                        "study_sha256",
                        "source_sha256",
                        "runtime_sha256",
                        "policy_sha256",
                        "launcher_sha256",
                    )
                },
                "fixture": fixture,
                "reason": reason,
                "new_admissions_forbidden": True,
                "financial_state_inferred": False,
                "automatic_resume": False,
            }
        ),
    )


def _export_owner_settled(request: dict, owner: dict | None, ack: dict | None) -> bool:
    """A started exporter must prove stop; display success is never required."""
    if not isinstance(owner, dict):
        raise ContractError("visibility ownership window was not atomically closed")
    require(
        owner.get("kind") == VISIBILITY_OWNER_KIND
        and all(
            owner.get(key) == request[key]
            for key in ("study_sha256", "checkpoint", "snapshot_sha256", "deadline_at_utc")
        ),
        "visibility child ownership has another identity",
    )
    if owner.get("exporter_started") is False and owner.get("state") == "closed_without_export":
        return True
    require(
        owner.get("exporter_started") is True and owner.get("state") == "claimed",
        "visibility child ownership is unclassified",
    )
    require(
        isinstance(ack, dict)
        and ack.get("kind") == VISIBILITY_RESULT_KIND
        and all(
            ack.get(key) == request[key]
            for key in ("study_sha256", "checkpoint", "snapshot_sha256")
        )
        and ack.get("provider_calls") == 0
        and ack.get("exporter_stopped") is True,
        "visibility child stop is unconfirmed",
    )
    return True


def _visibility_checkpoint(study_path, study, grant_path, fixture, checkpoint, *, fixture_ack=None):
    """Core owns a <=600s public snapshot/visibility window, never an admission grant."""
    from .core_view import BINDINGS, collect, publish_reports

    require(
        checkpoint in {"first-pair", "closure"} and (fixture_ack is None or fixture),
        "unknown visibility checkpoint or live callback injection",
    )
    run_path, _ = paths(study, fixture)
    directory = path(run_path / "visibility" / checkpoint)
    status_path = directory / "status.json"
    if status_path.exists():
        prior = checked(read(status_path))
        require(
            all(prior.get(key) == study[key] for key in BINDINGS)
            and prior["checkpoint"] == checkpoint
            and prior["fixture"] is fixture
            and prior.get("canonical_status") == "complete"
            and prior.get("worker_stopped") is True
            and isinstance(prior.get("canonical_summary"), dict),
            "foreign or unvalidated visibility receipt",
        )
        return prior
    started = time.monotonic()
    deadline = started + 600
    started_utc = datetime.now(timezone.utc)
    result = {
        "kind": "p3b-hi-visibility-status-v1",
        **{key: study[key] for key in BINDINGS},
        "checkpoint": checkpoint,
        "fixture": fixture,
        "provider_calls": 0,
        "visibility_status": "failed",
        "snapshot_sha256": None,
        "core_review_is_authoritative": True,
    }
    publish(
        directory / "core-started.json",
        seal(
            {
                "kind": "p3b-hi-canonical-view-started-v1",
                **{key: study[key] for key in BINDINGS},
                "checkpoint": checkpoint,
                "fixture": fixture,
                "started_at_utc": started_utc.isoformat(),
                "deadline_at_utc": (started_utc + timedelta(seconds=600)).isoformat(),
                "provider_calls": 0,
            }
        ),
    )
    canonical_failure = True
    request = ack = built = None
    try:
        spec = {
            "study_path": str(study_path),
            "bindings": {key: study[key] for key in BINDINGS},
            "checkpoint": checkpoint,
            "fixture": fixture,
            "reports_path": str(
                run_path / "reports" / ("final" if checkpoint == "closure" else "first-pair")
            ),
            "reports_staging_path": str(directory / "reports-staging"),
            "reports_held_staging_path": str(directory / "reports-held-staging"),
            "snapshot_path": str(directory / "snapshot"),
        }
        built = collect(spec, deadline=deadline)
        if built["canonical_status"] != "complete" and built["worker_stopped"]:
            publish_reports(spec, built)
        result.update(
            canonical_status=built["canonical_status"],
            report_status=built["report_status"],
            report_variant=built.get("report_variant"),
            reports_published=built.get("reports_published", False),
            worker_stopped=built["worker_stopped"],
            canonical_summary=built.get("summary"),
            visibility_status=built["visibility_status"],
            canonical_error_type=built.get("canonical_error_type"),
            projection_error_type=built.get("projection_error_type"),
        )
        if built["canonical_status"] != "complete" or not built["worker_stopped"]:
            canonical_failure = True
            result["elapsed_seconds"] = time.monotonic() - started
            publish(status_path, seal(result))
            _canonical_halt(study, fixture, "canonical_view_validation_or_ownership_failed")
            if not built["worker_stopped"]:
                if fixture:
                    raise accounting.OwnerStopRequired(
                        "canonical worker ownership stop is unproved"
                    )
                accounting.runtime_guard()
                require(os.getpid() == 1, "canonical worker cleanup requires inspected owned PID1")
                os._exit(82)
            raise ContractError("canonical checkpoint validation failed; no later admission")
        require(
            isinstance(result["canonical_summary"], dict)
            and result["canonical_summary"].get("study_sha256") == study["study_sha256"]
            and result["canonical_summary"].get("fixture") is fixture,
            "validated checkpoint lacks bound summary",
        )
        canonical_failure = False
        if built["visibility_status"] == "prepared":
            manifest = {"snapshot_sha256": built["snapshot_sha256"]}
            result["snapshot_sha256"] = manifest["snapshot_sha256"]
            request = {
                "kind": VISIBILITY_REQUEST_KIND,
                "study_sha256": study["study_sha256"],
                "checkpoint": checkpoint,
                "snapshot_sha256": manifest["snapshot_sha256"],
                "snapshot_dir": str(directory / "snapshot"),
                "result_path": str(directory / "result.json"),
                "fixture": fixture,
                "timeout_seconds": 600,
                "started_at_utc": started_utc.isoformat(),
                "deadline_at_utc": (started_utc + timedelta(seconds=600)).isoformat(),
                "cleanup_reserve_seconds": 15,
            }
            request_path = directory / "request.json"
            if request_path.exists():
                require(read(request_path) == request, "visibility request changed")
            else:
                publish(request_path, request)
            if fixture and not study["fixture_supervision_rehearsal"]:
                ack = (
                    fixture_ack(request)
                    if fixture_ack
                    else {
                        "kind": VISIBILITY_RESULT_KIND,
                        "study_sha256": study["study_sha256"],
                        "checkpoint": checkpoint,
                        "snapshot_sha256": request["snapshot_sha256"],
                        "visibility_status": "complete",
                        "provider_calls": 0,
                        "fixture": True,
                        "structural_callback_only": True,
                        "exporter_stopped": True,
                    }
                )
                publish(directory / "result.json", ack)
            response_path = directory / "result.json"
            # The source-bound host refuses to create a child with <=15s
            # remaining. Five final seconds settle its public ownership proof.
            while not response_path.exists() and time.monotonic() < deadline - 5:
                time.sleep(min(1, max(0, deadline - time.monotonic() - 5)))
            ack = None
            if response_path.exists():
                ack = read(response_path)
                valid = (
                    ack.get("kind") == VISIBILITY_RESULT_KIND
                    and ack.get("study_sha256") == study["study_sha256"]
                    and ack.get("checkpoint") == checkpoint
                    and ack.get("snapshot_sha256") == request["snapshot_sha256"]
                    and ack.get("provider_calls") == 0
                    and ack.get("visibility_status") in {"complete", "failed", "timeout"}
                )
                result["visibility_status"] = ack["visibility_status"] if valid else "failed"
                result["result_sha256"] = digest(ack)
            else:
                result["visibility_status"] = "timeout"
    except Exception as exc:
        if canonical_failure:
            _canonical_halt(study, fixture, "canonical_checkpoint_infrastructure_failure")
            raise
        result["visibility_status"] = "failed"
        result["error_type"] = type(exc).__name__
    finally:
        if request is not None:
            owner_path = directory / "ownership.json"
            try:
                closed = {
                    "kind": VISIBILITY_OWNER_KIND,
                    **{
                        key: request[key]
                        for key in (
                            "study_sha256",
                            "checkpoint",
                            "snapshot_sha256",
                            "deadline_at_utc",
                        )
                    },
                    "exporter_started": False,
                    "state": "closed_without_export",
                }
                try:
                    # write_once uses an exclusive atomic hard-link publish.
                    # Either host claim or this tombstone wins; no late child.
                    publish(owner_path, closed)
                except ContractError:
                    if not owner_path.exists():
                        raise
                owner = read(owner_path)
                _export_owner_settled(request, owner, ack)
            except (ContractError, ValueError, KeyError, TypeError, OSError):
                canonical_failure = True
                _canonical_halt(study, fixture, "visibility_child_ownership_unconfirmed")
                raise
        result["elapsed_seconds"] = time.monotonic() - started
    if not canonical_failure and built is not None:
        publish_reports(spec, built)
        result["reports_published"] = built.get("reports_published", False)
    publish(status_path, seal(result))
    return result


def _close_run(study_path, study, grant_path, fixture, run_path, prior_error=None):
    """The closure worker independently attempts all eight reports before projection."""
    try:
        closed = _visibility_checkpoint(study_path, study, grant_path, fixture, "closure")
        return closed["canonical_summary"]
    except Exception:
        if prior_error is None:
            raise
        return None


def _run_all(study_path, study, grant_path, grant, transport, run_path):
    records = saved(study_path, study, _state(study, transport.fixture), transport.fixture)
    if records["readiness"] is None:
        _run_stage(study_path, study, grant, "readiness", transport, grant_path, _summary=False)
        state = _state(study, transport.fixture)
        if (
            state["status"] != "ready"
            or (run_path / "readiness-failure.json").exists()
            or (run_path / "primary-stop.json").exists()
        ):
            return
        _barrier(study_path, study, grant_path, transport.fixture, "readiness")
    state = _state(study, transport.fixture)
    if not state["engineering_review"]:
        _run_stage(study_path, study, grant, "first", transport, grant_path, _summary=False)
        if (
            _state(study, transport.fixture)["status"] != "ready"
            or (run_path / "primary-stop.json").exists()
        ):
            return
        _barrier(study_path, study, grant_path, transport.fixture, "first")
    if not _state(study, transport.fixture)["first_assessments_closed"]:
        _run_stage(study_path, study, grant, "first", transport, grant_path, _summary=False)
    state = _state(study, transport.fixture)
    if state["status"] != "ready" or (run_path / "primary-stop.json").exists():
        return
    require(state["first_assessments_closed"], "original first assessments remain unclassified")
    _visibility_checkpoint(study_path, study, grant_path, transport.fixture, "first-pair")
    _run_stage(study_path, study, grant, "remaining", transport, grant_path, _summary=False)


def run(study_path: Path, grant_path: Path, *, stage: str, transport: Any) -> dict:
    study = load_study(study_path)
    require(not study["fixture_boundary_contract"], "boundary-only fixture cannot run generation")
    grant = grant_for(study, grant_path, transport.fixture)
    if not transport.fixture or study["fixture_supervision_rehearsal"]:
        supervision.require_attached(study, grant, transport.fixture)
    preflight(study_path, grant_path, transport.fixture, stage)
    run_path, _ = paths(study, transport.fixture)
    with writer_lock(run_path / "owner"):
        if stage != "all":
            result = _run_stage(study_path, study, grant, stage, transport, grant_path)
            if not isinstance(result, dict):
                raise ContractError("single-stage summary missing")
            return result
        prior_error = None
        try:
            _run_all(study_path, study, grant_path, grant, transport, run_path)
        except BaseException as exc:
            prior_error = exc
            raise
        finally:
            summary = _close_run(
                study_path, study, grant_path, transport.fixture, run_path, prior_error
            )
        if not isinstance(summary, dict):
            raise ContractError("validated closure summary missing")
        return summary


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "grant", "report"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--study", type=Path)
    parser.add_argument("--grant", type=Path)
    parser.add_argument("--fixture", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "prepare":
        require(args.output is not None, "prepare requires output")
        result = prepare(args.output)
    elif args.command == "grant":
        require(args.study is not None and args.output is not None, "grant requires study/output")
        result = make_grant(args.study, args.fixture)
        publish(args.output, result)
    else:
        require(
            args.study is not None and args.grant is not None and args.output is not None,
            "report requires study/grant/output",
        )
        from .report import write_report

        result = snapshot(args.study, args.grant, args.fixture)
        write_report(result, path(args.output))
    print(json.dumps({key: result[key] for key in ("study_sha256", "status") if key in result}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
