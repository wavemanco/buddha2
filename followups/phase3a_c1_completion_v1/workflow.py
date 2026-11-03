"""One fresh paired study; actual engine, strategy, scoring and ledger are reused."""
from __future__ import annotations

import copy
import json
import re
import threading
import time
from pathlib import Path
from typing import Any

from harness2.core.proposer import ProposerError

from buddha2 import phase2_am1_controls as am1
from buddha2.artifacts import ContractError, digest, file_hash, write_bytes_once
from buddha2.phase2_dispatch import writer_lock
from followups.phase3a_compat_c1_v1.adapter import CompatibleProposer
from followups.phase3a_compat_c1_v1.support import runtime_identity
from followups.phase3a_v1 import editor, native, strategy
from followups.phase3a_v1 import workflow as parent

from . import accounting
from .support import (
    AUTHORITY,
    DEFINITION,
    LAUNCHER,
    NATIVE,
    ROOT,
    checked,
    path,
    publish,
    read,
    require,
    seal,
    source_identity,
    validate_authority,
)
from .support import BASE as BASE

STAGES = {"readiness", "first", "remaining", "all"}
ARMS = ("fixed", "adaptive")


class ReadinessProposer(CompatibleProposer):
    """Observe known unfinished sessions before native fallback/probe scheduling."""
    def __init__(self, *, observe: bool, known_stop, can_stop, final_response=None, **kwargs):
        self.observe, self.known_stop, self.can_stop = observe, known_stop, can_stop
        self.final_response = final_response
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
                if session.get("terminal_note_used") or (session.get("status") not in {"valid", "invalid_harvest"}):
                    self.known_stop("unfinished_editor_session")
                elif session.get("status") == "valid":
                    final = self.final_response(session) if self.final_response else reply.text
                    if (not isinstance(final, str) or not re.fullmatch(r"\s*<notes>\s*\S[\s\S]*</notes>\s*", final)
                            or final.count("<notes>") != 1 or final.count("</notes>") != 1
                            or final.strip() != reply.text.strip()):
                        self.known_stop("unfinished_editor_session")
            return reply


def frozen_tasks() -> list[dict]:
    tasks = copy.deepcopy(read(ROOT / "runs/phase3a-r2-v1/release-v1/study.json")["tasks"])
    tasks[0]["arm_order"] = ["adaptive", "fixed"]
    return tasks


def paths(study: dict, fixture: bool) -> tuple[Path, Path]:
    return NATIVE / study["study_sha256"] / ("mock" if fixture else "live"), accounting.canonical_journal(study["study_sha256"], fixture)


def prepare(output: Path, *, source: dict | None = None, runtime: dict | None = None) -> dict:
    output = path(output)
    authority = validate_authority()
    sources, environment = source or source_identity(), runtime or runtime_identity()
    old = read(ROOT / "runs/phase3a-r2-v1/release-v1/study.json")
    tasks = frozen_tasks()
    body = {"kind": "phase3a-c1-completion-study-v1", "source": sources,
        "source_sha256": sources["sha256"], "runtime": environment, "runtime_sha256": digest(environment),
        "definition_sha256": file_hash(DEFINITION), "authorization_sha256": file_hash(AUTHORITY),
        "specification_sha256": file_hash(DEFINITION), "launcher_sha256": file_hash(LAUNCHER),
        "policy": accounting.POLICY, "policy_sha256": digest(accounting.POLICY), "tasks": tasks,
        "execution_tag": "phase3a-c1-" + digest({"source": sources["sha256"], "tasks": tasks})[:20],
        "editor_tools": read(ROOT / "followups/phase3a_v1/editor-tools.json"),
        "seed_tree": strategy.seed_tree(), "parent_decision_sha256": old["parent_decision_sha256"],
        "seed_procedure_sha256": old["seed_procedure_sha256"], "authority": authority,
        "prior_live_episode": {"known_spent_micro_usd": 10487885, "reserved_micro_usd": 11440000,
            "provider_calls": 842, "known_requests": 841, "unknown_requests": 1},
        "readiness_is_primary": "p3a-01:adaptive", "readiness_max_micro_usd": 20000000}
    body["slots"], body["assessment_plan"] = parent._plan_slots(body)
    body["fixed_candidate_order"] = parent._fixed_order(body)
    study = {**body, "study_sha256": digest(body)}
    publish(output / "study.json", study)
    strategy.materialize_seed(output / "seed")
    for name, expected in sources["files"].items():
        source_path = ROOT / name
        require(file_hash(source_path) == expected, "source changed while freezing the new study")
        write_bytes_once(output / "source" / name, source_path.read_bytes())
    return study


def load_study(study_path: Path) -> dict:
    study_path = path(study_path)
    study = read(study_path)
    require(study.get("kind") == "phase3a-c1-completion-study-v1"
        and study["study_sha256"] == digest({k: v for k, v in study.items() if k != "study_sha256"}), "completion study seal differs")
    require(study["source"] == source_identity() and study["source_sha256"] == study["source"]["sha256"]
        and study["runtime"] == runtime_identity() and study["runtime_sha256"] == digest(study["runtime"])
        and study["definition_sha256"] == file_hash(DEFINITION)
        and study["authorization_sha256"] == file_hash(AUTHORITY)
        and study["authority"] == validate_authority(), "completion source/runtime/authority changed")
    old = read(ROOT / "runs/phase3a-r2-v1/release-v1/study.json")
    require(study["tasks"] == frozen_tasks() and study["execution_tag"] == "phase3a-c1-" + digest({
        "source": study["source_sha256"], "tasks": study["tasks"]})[:20]
        and study["parent_decision_sha256"] == old["parent_decision_sha256"]
        and study["seed_procedure_sha256"] == old["seed_procedure_sha256"]
        and study["seed_tree"] == strategy.seed_tree()
        and study["editor_tools"] == read(ROOT / "followups/phase3a_v1/editor-tools.json")
        and study["launcher_sha256"] == file_hash(LAUNCHER)
        and study["prior_live_episode"] == {"known_spent_micro_usd": 10487885, "reserved_micro_usd": 11440000,
            "provider_calls": 842, "known_requests": 841, "unknown_requests": 1}
        and study["readiness_is_primary"] == "p3a-01:adaptive" and study["readiness_max_micro_usd"] == 20000000,
        "completion method/tasks/history differ from the frozen definition")
    require((study["slots"], study["assessment_plan"]) == parent._plan_slots(study)
        and study["fixed_candidate_order"] == parent._fixed_order(study)
        and study["policy"] == accounting.POLICY and study["policy_sha256"] == digest(accounting.POLICY), "completion worklist/policy changed")
    require(strategy.validate_harness(study_path.parent / "seed")["tree"] == study["seed_tree"], "seed changed")
    require(all(file_hash(study_path.parent / "source" / name) == sha for name, sha in study["source"]["files"].items()),
            "retained completion source changed")
    return study


def make_grant(study_path: Path, fixture: bool) -> dict:
    study = load_study(study_path)
    authority = {"study_sha256": study["study_sha256"], "authorization_id": "phase3a-c1-completion-user-goal",
        "authorized": not fixture, "cap_micro_usd": 205860000, "canary_cap_micro_usd": 50860000,
        "expansion_authorized": False, "control_policy_sha256": am1.CONTROL_SHA256, "billing_profile": am1.BILLING_PROFILE}
    result = {"kind": "phase3a-c1-completion-grant-v1", "fixture": fixture, "authority": authority,
        **{key: study[key] for key in ("study_sha256", "source_sha256", "policy_sha256", "runtime_sha256", "launcher_sha256")}}
    return {**result, "grant_sha256": digest(result)}


def grant_for(study: dict, grant_path: Path, fixture: bool) -> dict:
    grant = read(path(grant_path))
    require(grant.get("kind") == "phase3a-c1-completion-grant-v1" and grant.get("fixture") is fixture
        and grant["grant_sha256"] == digest({k: v for k, v in grant.items() if k != "grant_sha256"})
        and all(grant.get(k) == study[k] for k in ("study_sha256", "source_sha256", "policy_sha256", "runtime_sha256", "launcher_sha256")), "completion grant identity differs")
    accounting.validate_authority(study["study_sha256"], grant["authority"], fixture,
        {k: study[k] for k in ("source_sha256", "policy_sha256", "launcher_sha256")})
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
            pilot, task = entry["pilot_id"], parent._task(entry)
            for arm in ARMS:
                search = _search(run, pilot, arm)
                if arm == "fixed":
                    strategy.validate_fixed_partial(task, seed, study_sha256=study["study_sha256"],
                        run_id=parent._fixed_id(study, pilot), fixture=fixture, results=state["results"])
                else:
                    editor.validate_persisted_sessions(search / "editor-audit", study_sha256=study["study_sha256"],
                        pilot=pilot, fixture=fixture, results=state["results"], intents=state["intents"])
                    native.validate_adaptive_partial(task, seed, study_sha256=study["study_sha256"],
                        run_root=search, tag=parent._native_tag(study, pilot), fixture=fixture, results=state["results"])
                target = _branch_path(run, pilot, arm)
                if not target.exists():
                    continue
                record = checked(read(target))
                require(record["study_sha256"] == study["study_sha256"] and record["fixture"] is fixture
                    and record["pilot"] == pilot and record["arm"] == arm, "foreign saved branch")
                result = record["result"]
                if result is not None:
                    if arm == "fixed":
                        strategy.validate_fixed(result, task, seed, study_sha256=study["study_sha256"],
                            run_id=parent._fixed_id(study, pilot), fixture=fixture, results=state["results"],
                            stopped=pilot + ":fixed" in state.get("stopped_cells", []))
                    else:
                        native.validate_adaptation(result, task, seed, study_sha256=study["study_sha256"],
                            run_root=search, tag=parent._native_tag(study, pilot), fixture=fixture, results=state["results"])
                portfolio = result.get("portfolio") if result else None
                require(record["portfolio_sha256"] == (digest(portfolio) if portfolio else None), "saved final changed")
                branches[pilot, arm] = record
            target = run / "seals" / f"{pilot}.json"
            if target.exists():
                seal_record = checked(read(target))
                require(all((pilot, arm) in branches for arm in ARMS)
                    and seal_record == parent._pair_seal(study, pilot, branches, seal_record["journal_prefix"]), "pair seal changed")
                parent._validate_seal_prefix(study, journal, seal_record)
                seals[pilot] = seal_record
    evaluator = native.Phase3NativeAssessment(ROOT / ".upstream/novelty-bench")
    remaining = {slot for slot, result in state["results"].items() if result["role"] in {"group", "quality"}}
    for row in study["assessment_plan"]:
        branch = branches.get((row["pilot"], row["arm"]))
        portfolio = (branch["result"] or {}).get("portfolio") if branch else None
        prefix = evaluator.slot_prefix(row["id"])
        group = state["results"].get(prefix + ".group")
        if group is not None:
            if not isinstance(portfolio, dict) or row["pilot"] not in seals:
                raise ContractError("judgment lacks both sealed finals")
            require(group["request_sha256"] == digest(evaluator.group_request(portfolio)), "saved group body changed")
            remaining.remove(prefix + ".group")
            try:
                partition = evaluator.fold_group(portfolio, group, assessment_id=row["id"])["partition"]
            except ValueError:
                partition = None
            if partition is not None:
                heads = evaluator.modules["score"].heads(partition)
                for head, request in zip(heads, evaluator.quality_requests(portfolio, partition), strict=True):
                    slot = f"{prefix}.quality.{head:02}"
                    if slot in state["results"]:
                        require(state["results"][slot]["request_sha256"] == digest(request), "saved quality body changed")
                        remaining.remove(slot)
        target = run / "assessments" / (prefix + ".json")
        if target.exists():
            assessment = read(target)
            if not isinstance(portfolio, dict) or row["pilot"] not in seals or group is None:
                raise ContractError("saved assessment lacks sealed portfolio")
            require(all(record == state["results"].get(record["slot_id"]) for record in assessment["requests"]), "foreign assessment result")
            require(assessment == evaluator.finalize(portfolio, assessment["requests"][0],
                assessment["requests"][1:], assessment_id=row["id"]), "assessment does not exactly replay")
            assessments[row["id"]] = assessment
    require(not remaining, "undeclared/foreign judge results")
    readiness = checked(read(run / "readiness-review.json")) if (run / "readiness-review.json").exists() else None
    return {"branches": branches, "seals": seals, "assessments": assessments, "readiness": readiness}


def _state(study: dict, fixture: bool) -> dict:
    _, journal = paths(study, fixture)
    return accounting.replay(journal) if (journal / "manifest.json").exists() else parent._empty_state(study, fixture)


def preflight(study_path: Path, grant_path: Path, fixture: bool, stage: str = "all", *,
              require_offline_gate: bool = True) -> dict:
    require(stage in STAGES and type(fixture) is bool, "unknown completion invocation")
    require(type(require_offline_gate) is bool, "offline-gate selector must be explicit")
    study = load_study(study_path)
    grant = grant_for(study, grant_path, fixture)
    run, journal = paths(study, fixture)
    if not fixture and require_offline_gate:
        gate = checked(read(study_path.parent / "offline-gate.json"))
        require(gate["passed"] is True and gate["study_sha256"] == study["study_sha256"]
            and gate["source_sha256"] == study["source_sha256"] and gate["runtime_sha256"] == study["runtime_sha256"],
            "whole-scope offline gate required")
        require(set(gate["checks"]) == {"tests", "static", "matrix", "replay", "launcher", "preservation"}, "whole-scope gate groups differ")
        for ref in gate["checks"].values():
            target = path(Path(ref["path"]))
            record = read(target)
            require(file_hash(target) == ref["sha256"] and record.get("passed") is True
                and record.get("study_sha256") == study["study_sha256"]
                and record.get("source_sha256") == study["source_sha256"], "offline check evidence is stale or incomplete")
    state = _state(study, fixture)
    require(state["status"] == "ready" and state["reserved_micro_usd"] == 0, "unresolved completion accounting blocks dispatch")
    require(not (run / "readiness-failure.json").exists(), "known readiness failure prevents further calls")
    records = saved(study_path, study, state, fixture)
    if stage in {"first", "remaining"} or records["readiness"] is not None:
        validate_readiness_review(study, run, state, records, fixture)
    if stage == "remaining":
        require(state["engineering_review"] is not None, "first-pair engineering review required")
    return {"kind": "phase3a-c1-completion-preflight-v1", **{k: study[k] for k in (
        "study_sha256", "source_sha256", "policy_sha256", "runtime_sha256", "launcher_sha256")},
        "grant_sha256": grant["grant_sha256"], "fixture": fixture, "run": str(run), "journal": str(journal),
        "provider_calls": 0, "credentials_read": False}


def _readiness_check(study: dict, run: Path, state: dict, records: dict, fixture: bool) -> dict:
    from .evidence import verify_readiness
    branch = records["branches"].get(("p3a-01", "adaptive"))
    require(branch is not None, "counted native readiness branch missing")
    return verify_readiness(study, run, state, branch, fixture)


def validate_readiness_review(study: dict, run: Path, state: dict, records: dict, fixture: bool) -> dict:
    record = records["readiness"]
    require(record is not None and record.get("passed") is True
        and record.get("kind") == "phase3a-c1-counted-readiness-review-v1"
        and record.get("study_sha256") == study["study_sha256"]
        and record.get("source_sha256") == study["source_sha256"] and record.get("fixture") is fixture,
        "counted readiness review has another source/study/mode")
    proof = _readiness_check(study, run, state, records, fixture)
    require(record["proof"] == proof and record["inspection"]["evidence_sha256"] == digest(proof)
        and record["inspection"]["evidence_grounded_decisions"] is True
        and record["branch_sha256"] == records["branches"]["p3a-01", "adaptive"]["sha256"],
        "readiness review is unsupported by actual native evidence")
    return record


def _review_readiness(study_path: Path, study: dict, state: dict, records: dict, fixture: bool, audit: dict) -> dict:
    run, _ = paths(study, fixture)
    proof = _readiness_check(study, run, state, records, fixture)
    require(audit.get("study_sha256") == study["study_sha256"] and audit.get("evidence_sha256") == digest(proof)
        and audit.get("evidence_grounded_decisions") is True and audit.get("no_quality_continuation_gate") is True
        and audit.get("fixture") is fixture and isinstance(audit.get("notes"), str) and bool(audit["notes"].strip()), "trusted readiness inspection differs")
    record = seal({"kind": "phase3a-c1-counted-readiness-review-v1", "passed": True,
        "study_sha256": study["study_sha256"], "source_sha256": study["source_sha256"],
        "proof": proof, "inspection": audit, "fixture": fixture,
        "branch_sha256": records["branches"]["p3a-01", "adaptive"]["sha256"]})
    publish(run / "readiness-review.json", record)
    return record


def _first_review(study_path: Path, study: dict, state: dict, records: dict, fixture: bool, *, closure=False) -> None:
    run, journal = paths(study, fixture)
    require("p3a-01" in records["seals"] and state["status"] == "ready" and not state["reserved_micro_usd"], "first pair not reviewable")
    files = [run / "seals/p3a-01.json", *[_branch_path(run, "p3a-01", arm) for arm in ARMS], journal / "manifest.json"]
    record = {"review_id": "c1-completion-first-closed" if closure else "c1-completion-first-engineering",
        "study_sha256": study["study_sha256"], "run_id": state["run_id"], "state_sha256": digest(state),
        "checks": dict.fromkeys(accounting.CHECKS, True), "evidence": {str(p): file_hash(p) for p in files},
        "first_assessments_closed": parent._first_done(study, records, state)}
    def validate(prefix, value):
        require(value == record and all(file_hash(Path(name)) == sha for name, sha in value["evidence"].items()), "first review evidence changed")
        current = saved(study_path, study, prefix, fixture)
        require("p3a-01" in current["seals"] and value["first_assessments_closed"] == parent._first_done(study, current, prefix), "unsupported first-assessment closure")
    if closure:
        accounting.close_first_assessments(journal, record, validate_evidence=validate)
    else:
        accounting.publish_review(journal, record, validate_evidence=validate)


def snapshot(study_path: Path, grant_path: Path, fixture: bool) -> dict:
    from .report import build
    study = load_study(study_path)
    grant_for(study, grant_path, fixture)
    state = _state(study, fixture)
    run, _ = paths(study, fixture)
    try:
        records = saved(study_path, study, state, fixture)
        if records["readiness"] is not None:
            validate_readiness_review(study, run, state, records, fixture)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        if state["status"] == "ready" and not (run / "readiness-failure.json").exists():
            raise
        records = {"branches": {}, "seals": {}, "assessments": {}, "readiness": None,
            "validation_failure": {"exception_type": type(exc).__name__, "scientific_use": "disqualified"}}
    return build(study, state, records, fixture)


def _barrier(study_path: Path, study: dict, grant_path: Path, fixture: bool, name: str) -> None:
    run, _ = paths(study, fixture)
    state = _state(study, fixture)
    records = saved(study_path, study, state, fixture)
    proof = _readiness_check(study, run, state, records, fixture) if name == "readiness" else {
        "study_sha256": study["study_sha256"], "pair_seal": records["seals"]["p3a-01"], "state_sha256": digest(state)}
    publish(run / f"barrier-{name}.json", seal({"kind": "phase3a-c1-review-barrier-v1", "stage": name,
        "study_sha256": study["study_sha256"], "proof": proof, "evidence_sha256": digest(proof), "fixture": fixture}))
    audit_path = run / f"inspection-{name}.json"
    if fixture:
        publish(audit_path, {"study_sha256": study["study_sha256"], "evidence_sha256": digest(proof),
            "fixture": True, "evidence_grounded_decisions": True, "no_quality_continuation_gate": True,
            "engineering_checks_passed": True, "notes": "Scripted offline structural inspection only; not actual model readiness."})
    deadline = time.monotonic() + 1800
    while not audit_path.exists():
        require(time.monotonic() < deadline, "review barrier timed out with no additional dispatch")
        time.sleep(1)
    audit = read(audit_path)
    require(audit.get("study_sha256") == study["study_sha256"] and audit.get("evidence_sha256") == digest(proof)
        and audit.get("fixture") is fixture and audit.get("no_quality_continuation_gate") is True, "review audit has another identity")
    if name == "readiness":
        _review_readiness(study_path, study, state, records, fixture, audit)
    else:
        require(audit.get("engineering_checks_passed") is True and bool(audit.get("notes")), "first-pair engineering audit incomplete")
        publish(run / "first-review.json", seal({"kind": "phase3a-c1-first-review-v1", "study_sha256": study["study_sha256"], "inspection": audit}))
        _first_review(study_path, study, state, records, fixture)


def _run_stage(study_path: Path, study: dict, grant: dict, stage: str, transport: Any,
               grant_path: Path) -> dict:
    run, journal = paths(study, transport.fixture)
    fixture = transport.fixture
    records = saved(study_path, study, _state(study, fixture), fixture)
    stop = threading.Event()
    failure_path = run / "readiness-failure.json"
    def known_stop(reason):
        stop.set()
        publish(failure_path, seal({"kind": "phase3a-c1-readiness-known-stop-v1", "study_sha256": study["study_sha256"], "reason": reason,
            "fixture": fixture, "unknown_charge_inferred": False}))
    def guard(state):
        if stop.is_set() or failure_path.exists():
            raise accounting.ReadinessStop("known readiness failure; no further admission")
        if stage != "readiness":
            review = checked(read(run / "readiness-review.json"))
            require(review["passed"] is True and review["study_sha256"] == study["study_sha256"]
                and review["branch_sha256"] == records["branches"]["p3a-01", "adaptive"]["sha256"], "readiness review changed")
    ledger = accounting.Ledger(journal, study_sha256=study["study_sha256"], slots=study["slots"],
        authority=grant["authority"], transport=transport, editor_tools=study["editor_tools"],
        bindings={k: study[k] for k in ("source_sha256", "policy_sha256", "launcher_sha256")},
        stage=stage, readiness_validator=guard)
    def halt(reason, evidence_sha256=None):
        if not stop.is_set():
            ledger.halt(reason, evidence_sha256)
    def dispatch_for(pilot, arm=None):
        cell = pilot + ":" + arm if arm else "assessment"
        def dispatch(slot, role, request, **kwargs):
            require(slot in study["slots"] and study["slots"][slot]["cell"] == cell
                    and study["slots"][slot]["pair"] == pilot, "request escaped paired cell")
            if stage == "readiness" and role == "editor" and slot.endswith(".t08"):
                accounting.validate_request(role, request, editor_tools=study["editor_tools"])
                require(request.get("messages") and editor._terminal_shape(request["messages"][-1]),
                        "unexpected eighth readiness request is not the pinned terminal control")
                known_stop("forced_terminal_control_before_dispatch")
                raise accounting.ReadinessStop("normal readiness window exhausted")
            return ledger.dispatch(slot, role, request, **kwargs)
        return dispatch
    evaluator = native.Phase3NativeAssessment(ROOT / ".upstream/novelty-bench")
    for entry in study["tasks"]:
        pilot, task = entry["pilot_id"], parent._task(entry)
        if stage in {"readiness", "first"} and pilot != "p3a-01":
            break
        if pilot != "p3a-01" and not ledger.state()["first_assessments_closed"]:
            break
        for arm in (["adaptive"] if stage == "readiness" else entry["arm_order"]):
            if (pilot, arm) in records["branches"]:
                continue
            result, failure, c1_evidence = None, None, None
            try:
                if arm == "fixed":
                    result = strategy.fixed_best6(task, study_path.parent / "seed", study_sha256=study["study_sha256"],
                        run_id=parent._fixed_id(study, pilot), fixture=fixture, dispatch=dispatch_for(pilot, arm), known_results=ledger.state()["results"])
                else:
                    callback = getattr(transport, "register_contract", None)
                    prop = ReadinessProposer(observe=stage == "readiness", known_stop=known_stop,
                        can_stop=lambda: ledger.state()["status"] == "ready" and not stop.is_set(),
                        final_response=lambda session: ledger.state()["results"].get(
                            (session.get("result_slots") or [None])[-1], {}).get("response", {}).get("text"),
                        pilot=pilot, study_sha256=study["study_sha256"],
                        dispatch=dispatch_for(pilot, arm), audit_dir=_search(run, pilot, arm) / "editor-audit",
                        fixture=fixture, halt=halt, source_sha256=study["source_sha256"],
                        register_contract=(lambda label, prepared: callback(pilot, label, prepared)) if callback else None)
                    result = native.run_adaptation(task, study_path.parent / "seed", study_sha256=study["study_sha256"],
                        run_root=_search(run, pilot, arm), tag=parent._native_tag(study, pilot), dispatch=dispatch_for(pilot, arm),
                        fixture=fixture, prop=prop, known_results=ledger.state()["results"], result_snapshot=lambda: ledger.state()["results"], halt=halt)
                    c1_evidence = prop.c1_evidence()
            except accounting.IntegrityStop:
                halt("completion_component_integrity_failure")
            except (ContractError, accounting.CellBudgetStop, accounting.CheckpointStop, accounting.PhaseBudgetStop) as exc:
                failure = type(exc).__name__
            if ledger.state()["status"] != "ready":
                break
            portfolio = result.get("portfolio") if result else None
            branch = seal({"kind": "phase3a-branch-v1", "study_sha256": study["study_sha256"],
                "pilot": pilot, "arm": arm, "fixture": fixture, "result": result, "failure": failure,
                "portfolio_sha256": digest(portfolio) if portfolio else None, "c1_evidence": c1_evidence})
            publish(_branch_path(run, pilot, arm), branch)
            records["branches"][pilot, arm] = branch
            if stop.is_set():
                break
        if stop.is_set() or ledger.state()["status"] != "ready" or stage == "readiness":
            break
        if not all((pilot, arm) in records["branches"] for arm in ARMS):
            break
        if pilot not in records["seals"]:
            events = accounting.events(journal)
            prefix = {"index": len(events), "event_sha256": events[-1]["event_sha256"] if events else None}
            pair_seal = parent._pair_seal(study, pilot, records["branches"], prefix)
            publish(run / "seals" / f"{pilot}.json", pair_seal)
            records["seals"][pilot] = pair_seal
        for row in [row for row in study["assessment_plan"] if row["pilot"] == pilot]:
            if row["id"] in records["assessments"] or ledger.state()["assessment_stopped"]:
                continue
            portfolio = (records["branches"][pilot, row["arm"]]["result"] or {}).get("portfolio")
            if portfolio is None:
                continue
            try:
                assessment = evaluator.assess(portfolio, dispatch_for(pilot), assessment_id=row["id"])
                publish(run / "assessments" / (evaluator.slot_prefix(row["id"]) + ".json"), assessment)
                records["assessments"][row["id"]] = assessment
            except (accounting.AssessmentBudgetStop, accounting.CheckpointStop, accounting.PhaseBudgetStop, accounting.LiabilityStop, accounting.IntegrityStop):
                return snapshot(study_path, grant_path, fixture)["summary"]
        if pilot == "p3a-01" and ledger.state()["engineering_review"] and not ledger.state()["first_assessments_closed"]:
            current = ledger.state()
            _first_review(study_path, study, current, saved(study_path, study, current, fixture), fixture, closure=True)
    return snapshot(study_path, grant_path, fixture)["summary"]


def run(study_path: Path, grant_path: Path, *, stage: str, transport: Any) -> dict:
    preflight(study_path, grant_path, transport.fixture, stage)
    study = load_study(study_path)
    grant = grant_for(study, grant_path, transport.fixture)
    run_path, _ = paths(study, transport.fixture)
    with writer_lock(run_path / "owner"):
        if stage != "all":
            return _run_stage(study_path, study, grant, stage, transport, grant_path)
        records = saved(study_path, study, _state(study, transport.fixture), transport.fixture)
        if records["readiness"] is None:
            _run_stage(study_path, study, grant, "readiness", transport, grant_path)
            state = _state(study, transport.fixture)
            if state["status"] != "ready" or (run_path / "readiness-failure.json").exists():
                return snapshot(study_path, grant_path, transport.fixture)["summary"]
            _barrier(study_path, study, grant_path, transport.fixture, "readiness")
        state = _state(study, transport.fixture)
        if not state["engineering_review"]:
            _run_stage(study_path, study, grant, "first", transport, grant_path)
            if _state(study, transport.fixture)["status"] != "ready":
                return snapshot(study_path, grant_path, transport.fixture)["summary"]
            _barrier(study_path, study, grant_path, transport.fixture, "first")
        _run_stage(study_path, study, grant, "remaining", transport, grant_path)
        from .report import write_report
        data = snapshot(study_path, grant_path, transport.fixture)
        write_report(data, run_path / "reports/final")
        return data["summary"]


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "grant", "report"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--study", type=Path)
    parser.add_argument("--grant", type=Path)
    parser.add_argument("--fixture", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        require(args.output is not None, "prepare requires output")
        result = prepare(args.output)
    elif args.command == "grant":
        require(args.study is not None and args.output is not None, "grant requires study/output")
        result = make_grant(args.study, args.fixture)
        publish(args.output, result)
    else:
        require(args.study is not None and args.grant is not None and args.output is not None, "report requires study/grant/output")
        from .report import write_report
        result = snapshot(args.study, args.grant, args.fixture)
        write_report(result, path(args.output))
    print(json.dumps({key: result[key] for key in ("study_sha256", "status") if key in result}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
