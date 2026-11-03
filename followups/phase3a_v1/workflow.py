"""Four paired Phase 3A procedures, sealed outputs and separate native assessment."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any, Callable

from buddha2.artifacts import ContractError, file_hash, write_bytes_once
from buddha2.phase2_dispatch import writer_lock

from . import accounting, strategy, support
from .support import (
    DEFINITION,
    LAUNCHER,
    RESULTS,
    ROOT,
    SPEC,
    authorization,
    checked_path,
    json_sha,
    read_json,
    require,
    runtime_identity,
    source_identity,
)

ARMS = ("fixed", "adaptive")
FIRST = "p3a-01"


def _seal(value: dict, field: str = "sha256") -> dict:
    return value | {field: json_sha(value)}


def _check_seal(value: Any, field: str = "sha256") -> None:
    require(isinstance(value, dict) and value.get(field) == json_sha(
        {k: v for k, v in value.items() if k != field}), "saved identity differs")


def _bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _read(path: Path) -> Any:
    # The maximum fixed branch contains six portfolios, parents and request
    # records; it can exceed the older two-MB single-artifact reader ceiling.
    require(path.is_file() and path.stat().st_size <= 32_000_000, "missing/oversized phase artifact")
    require(not any(p.is_symlink() for p in (path, *path.parents)), "linked phase artifact")
    value = json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda _: (_ for _ in ()).throw(
        ContractError("nonfinite phase artifact")))
    require(path.read_bytes() == _bytes(value), "phase artifact is not exact canonical saved bytes")
    return value


def _publish(path: Path, value: Any) -> None:
    write_bytes_once(path, _bytes(value))


def _paths(study: dict, fixture: bool) -> tuple[Path, Path]:
    run = checked_path(RESULTS / study["study_sha256"] / ("mock" if fixture else "live"))
    return run, run / "journal"


def _task(entry: dict) -> dict:
    return {"id": entry["parent_task_id"], "domain": "phase3a-development", "prompt": entry["prompt"],
            "source_context": entry["source_context"]}


def _fixed_id(study: dict, pilot: str) -> str:
    return f"{study['execution_tag']}:{pilot}:fixed"


def _native_tag(study: dict, pilot: str) -> str:
    return f"{study['execution_tag']}-{pilot}"


def _assessment_id(study: dict, pilot: str, arm: str, *, diagnostic: bool = False) -> str:
    return f"{study['execution_tag']}:{pilot}:{arm}:" + ("anchor" if diagnostic else "primary")


def _fixed_order(study: dict) -> dict:
    return {entry["pilot_id"]: sorted(
        [f"{_fixed_id(study, entry['pilot_id'])}/candidate-{i:02}" for i in range(1, 7)],
        key=lambda run_id: json_sha({"task_id": entry["parent_task_id"],
            "run_id": _fixed_id(study, entry["pilot_id"]), "candidate_run_id": run_id}))
        for entry in study["tasks"]}


def _plan_slots(study: dict) -> tuple[dict, list[dict]]:
    from .native import Phase3NativeAssessment, adaptive_run_ids

    slots, assessments = {}, []
    for entry in study["tasks"]:
        pilot, task = entry["pilot_id"], _task(entry)
        for arm in ARMS:
            cell = pilot + ":" + arm
            run_ids = ([f"{_fixed_id(study, pilot)}/candidate-{i:02}" for i in range(1, 7)] if arm == "fixed"
                       else list(adaptive_run_ids(task["id"], _native_tag(study, pilot)).values()))
            for run_id in run_ids:
                ids = strategy.slot_ids(run_id)
                for role, names in (("plan", [ids["plan"]]), ("answer", ids["answers"]), ("rank", [ids["rank"]])):
                    for slot in names:
                        slots[slot] = {"role": role, "cell": cell, "pair": pilot}
            if arm == "fixed":
                slots[strategy.slot_prefix(_fixed_id(study, pilot)) + ".selector"] = {
                    "role": "fixed_selector", "cell": cell, "pair": pilot}
            else:
                for stage in ("inv1", "dom1", "agg1"):
                    for attempt in (1, 2):
                        conversation = f"{cell}:{stage}.a{attempt}"
                        for turn in range(1, accounting.POLICY["editor_turns"] + 1):
                            slots[f"{pilot}.adaptive.editor.{stage}.a{attempt}.t{turn:02}"] = {
                                "role": "editor", "cell": cell, "pair": pilot,
                                "conversation": conversation, "turn": turn}
        for arm in entry["arm_order"]:
            assessments.append({"id": _assessment_id(study, pilot, arm), "pilot": pilot,
                                "arm": arm, "diagnostic": False})
        if pilot == FIRST:
            assessments.append({"id": _assessment_id(study, pilot, "fixed", diagnostic=True),
                                "pilot": pilot, "arm": "fixed", "diagnostic": True})
    for row in assessments:
        prefix = Phase3NativeAssessment.slot_prefix(row["id"])
        slots[prefix + ".group"] = {"role": "group", "cell": "assessment", "pair": row["pilot"]}
        for i in range(10):
            slots[f"{prefix}.quality.{i:02}"] = {"role": "quality", "cell": "assessment", "pair": row["pilot"]}
    accounting._slot_scope(slots)
    return slots, assessments


def _prior_episode(spec: dict) -> dict:
    accepted = authorization()
    expected = {"episodes": accepted["prior_episodes"], "known_requests": accepted["prior_known_requests"],
                "provider_calls": accepted["prior_requests"], "unknown_requests": accepted["prior_unknown_requests"],
                "known_spent_micro_usd": accepted["prior_spent_micro_usd"],
                "reserved_micro_usd": accepted["prior_reserved_micro_usd"],
                "results_reused": False, "historical_unknown_released": False,
                "new_max_attempts": 775, "cumulative_max_attempts": 952}
    require(spec.get("prior_live_episode") == expected, "prior episodes differ from accepted R2 authority")
    return expected


def prepare(output: Path, *, editor_tools: dict | None = None,
            source: dict | None = None, runtime: dict | None = None) -> dict:
    output = checked_path(output)
    spec, sources, environment = read_json(SPEC), source or source_identity(), runtime or runtime_identity()
    exact_tools = read_json(ROOT / "followups/phase3a_v1/editor-tools.json")
    require(editor_tools is None or editor_tools == exact_tools, "editor tool override differs from pinned runtime")
    require(spec["phase"]["proposed_cap_micro_usd"] == accounting.POLICY["phase_micro_usd"]
            and len(spec["task_selection"]["tasks"]) == 4,
            "phase definition differs")
    execution_tag = "phase3a-" + json_sha({"specification": file_hash(SPEC),
        "pilots": [t["pilot_id"] for t in spec["task_selection"]["tasks"]]})[:20]
    body = {"kind": "phase3a-study-v1", "specification_sha256": file_hash(SPEC),
            "definition_sha256": file_hash(DEFINITION),
            "source": sources, "source_sha256": sources["sha256"], "runtime": environment,
            "runtime_sha256": json_sha(environment), "tasks": spec["task_selection"]["tasks"],
            "execution_tag": execution_tag, "parent_decision_sha256": spec["parent_decision_sha256"],
            "seed_procedure_sha256": spec["seed_procedure_sha256"], "policy": accounting.POLICY,
            "policy_sha256": json_sha(accounting.POLICY), "editor_tools": exact_tools,
            "seed_tree": strategy.seed_tree(), "launcher_sha256": sources["files"].get(LAUNCHER.name, "0" * 64),
            "prior_live_episode": _prior_episode(spec)}
    body["slots"], body["assessment_plan"] = _plan_slots(body)
    body["fixed_candidate_order"] = _fixed_order(body)
    study = _seal(body, "study_sha256")
    _publish(output / "study.json", study)
    strategy.materialize_seed(output / "seed")
    for name, expected in sources["files"].items():
        path = ROOT / name
        require(file_hash(path) == expected, "source changed during preparation")
        write_bytes_once(output / "source" / name, path.read_bytes())
    return {"status": "prepared-offline", "study_sha256": study["study_sha256"],
            "slots": len(study["slots"]), "primary_finals": 8, "diagnostic_assessments": 1, "provider_calls": 0}


def load_study(study_path: Path) -> dict:
    path = checked_path(study_path)
    study = _read(path)
    _check_seal(study, "study_sha256")
    spec = read_json(SPEC)
    require(study["kind"] == "phase3a-study-v1" and study["source"] == source_identity()
            and study["runtime"] == runtime_identity() and study["runtime_sha256"] == json_sha(study["runtime"])
            and study["source_sha256"] == study["source"]["sha256"]
            and study["specification_sha256"] == file_hash(SPEC)
            and study["definition_sha256"] == file_hash(DEFINITION)
            and study["tasks"] == spec["task_selection"]["tasks"]
            and study["execution_tag"] == "phase3a-" + json_sha({"specification": file_hash(SPEC),
                "pilots": [t["pilot_id"] for t in spec["task_selection"]["tasks"]]})[:20]
            and study["parent_decision_sha256"] == spec["parent_decision_sha256"]
            and study["seed_procedure_sha256"] == spec["seed_procedure_sha256"]
            and study["policy"] == accounting.POLICY and study["policy_sha256"] == json_sha(accounting.POLICY)
            and study["editor_tools"] == read_json(ROOT / "followups/phase3a_v1/editor-tools.json")
            and study["launcher_sha256"] == study["source"]["files"].get(LAUNCHER.name, "0" * 64)
            and study["prior_live_episode"] == _prior_episode(spec)
            and study["seed_tree"] == strategy.seed_tree(), "frozen study/source/runtime differs")
    slots, assessment_plan = _plan_slots(study)
    require(study["slots"] == slots and study["assessment_plan"] == assessment_plan, "phase worklist differs")
    require(study["fixed_candidate_order"] == _fixed_order(study), "fixed selector candidate order differs")
    require(strategy.validate_harness(path.parent / "seed")["tree"] == study["seed_tree"], "seed tree changed")
    for name, expected in study["source"]["files"].items():
        require(file_hash(path.parent / "source" / name) == expected, "retained phase source differs")
    return study


def _grant(study: dict, path: Path, fixture: bool) -> dict:
    grant = _read(checked_path(path))
    _check_seal(grant, "grant_sha256")
    require(set(grant) == {"kind", "fixture", "study_sha256", "source_sha256", "policy_sha256",
                           "launcher_sha256", "authority", "grant_sha256"}
            and grant["kind"] == "phase3a-grant-v1" and grant["fixture"] is fixture,
            "phase grant shape or mode differs")
    require(all(grant[k] == study[k] for k in ("study_sha256", "source_sha256", "policy_sha256", "launcher_sha256")),
            "phase grant belongs to another frozen study")
    accounting.validate_authority(study["study_sha256"], grant["authority"], fixture=fixture)
    return grant


def _ledger(study: dict, grant: dict, transport: Any) -> accounting.Ledger:
    _, journal = _paths(study, grant["fixture"])
    return accounting.Ledger(journal, study_sha256=study["study_sha256"], slots=study["slots"],
        authority=grant["authority"], transport=transport,
        bindings={k: study[k] for k in ("source_sha256", "policy_sha256", "launcher_sha256")},
        editor_tools=study["editor_tools"])


def preflight(study_path: Path, grant_path: Path, fixture: bool) -> dict:
    require(type(fixture) is bool, "explicit fixture/provider mode required")
    study = load_study(study_path)
    grant = _grant(study, grant_path, fixture)
    if not fixture:
        support.validate_gate(study_path, study)
    run, journal = _paths(study, fixture)
    require(not any(p.is_symlink() for p in run.rglob("*")), "linked phase execution evidence")
    if (journal / "manifest.json").exists():
        state = accounting.replay(journal)
        inputs = read_json(journal / "manifest.json")["inputs"]
        require(inputs == {"study_sha256": study["study_sha256"], "slots": study["slots"],
            "authority": grant["authority"], "fixture": fixture,
            "bindings": {k: study[k] for k in ("source_sha256", "policy_sha256", "launcher_sha256")},
            "policy": accounting.POLICY, "editor_tools": study["editor_tools"]},
            "existing journal belongs to another source/study/authority")
        require(state["status"] == "ready" and state["reserved_micro_usd"] == 0,
                "unresolved phase liability blocks execution")
        _saved(study_path, study, run, state, fixture)
    else:
        require(not any(p.name != ".writer.lock" for p in journal.glob("*")), "unrecognized journal contents")
        require(not any((run / name).exists() for name in ("branches", "search", "seals", "assessments")),
                "execution evidence lacks its authoritative journal")
    return {"kind": "phase3a-preflight-v1", **{k: study[k] for k in (
        "study_sha256", "source_sha256", "policy_sha256", "launcher_sha256", "runtime_sha256")},
        "grant_sha256": grant["grant_sha256"], "fixture": fixture, "run": str(run), "journal": str(journal),
        "provider_calls": 0, "credentials_read": False}


def _native():
    from .native import Phase3NativeAssessment

    return Phase3NativeAssessment(ROOT / ".upstream/novelty-bench")


def _branch_path(run: Path, pilot: str, arm: str) -> Path:
    return run / "branches" / f"{pilot}-{arm}.json"


def _search_root(run: Path, pilot: str, arm: str) -> Path:
    return run / "search" / pilot / arm


def _branch(study_path: Path, study: dict, run: Path, entry: dict, arm: str,
            state: dict, fixture: bool) -> dict | None:
    from .native import validate_adaptation, validate_adaptive_partial

    pilot, task = entry["pilot_id"], _task(entry)
    seed, path = Path(study_path).parent / "seed", _branch_path(run, pilot, arm)
    # Every known partial candidate is checked even if an earlier candidate is
    # incomplete; a forged later request must not permit fresh earlier spending.
    if arm == "fixed":
        strategy.validate_fixed_partial(task, seed, study_sha256=study["study_sha256"],
            run_id=_fixed_id(study, pilot), fixture=fixture, results=state["results"])
    else:
        from .editor import validate_persisted_sessions

        validate_persisted_sessions(_search_root(run, pilot, arm) / "editor-audit",
            study_sha256=study["study_sha256"], pilot=pilot, fixture=fixture, results=state["results"],
            intents=state["intents"])
        validate_adaptive_partial(task, seed, study_sha256=study["study_sha256"],
            run_root=_search_root(run, pilot, arm), tag=_native_tag(study, pilot), fixture=fixture,
            results=state["results"])
    if not path.exists():
        return None
    record = _read(path)
    _check_seal(record)
    require(record["kind"] == "phase3a-branch-v1" and record["study_sha256"] == study["study_sha256"]
            and record["pilot"] == pilot and record["arm"] == arm and record["fixture"] is fixture,
            "branch belongs to a different paired procedure")
    result = record["result"]
    if result is not None:
        if arm == "fixed":
            strategy.validate_fixed(result, task, seed, study_sha256=study["study_sha256"],
                run_id=_fixed_id(study, pilot), fixture=fixture, results=state["results"],
                stopped=pilot + ":fixed" in state.get("stopped_cells", []))
        else:
            validate_adaptation(result, task, seed, study_sha256=study["study_sha256"],
                run_root=_search_root(run, pilot, arm), tag=_native_tag(study, pilot),
                fixture=fixture, results=state["results"])
    require(record["portfolio_sha256"] == (json_sha(result["portfolio"]) if result and result.get("portfolio") else None),
            "branch final identity differs")
    return record


def _saved(study_path: Path, study: dict, run: Path, state: dict, fixture: bool) -> dict:
    with strategy.validation_scope(readonly=True):
        return _saved_impl(study_path, study, run, state, fixture)


def _saved_impl(study_path: Path, study: dict, run: Path, state: dict, fixture: bool) -> dict:
    require(not any(p.is_symlink() for p in (run, *run.rglob("*"))), "phase run contains a link")
    branches, seals, assessments = {}, {}, {}
    allowed_branches = {f"{t['pilot_id']}-{arm}.json" for t in study["tasks"] for arm in ARMS}
    require(all(p.name in allowed_branches for p in (run / "branches").glob("*.json")), "undeclared branch")
    for entry in study["tasks"]:
        pilot = entry["pilot_id"]
        for arm in ARMS:
            record = _branch(study_path, study, run, entry, arm, state, fixture)
            if record is not None:
                branches[pilot, arm] = record
        path = run / "seals" / f"{pilot}.json"
        if path.exists():
            seal = _read(path)
            _check_seal(seal)
            require(all((pilot, arm) in branches for arm in ARMS), "pair sealed before both dispositions")
            require(seal == _pair_seal(study, pilot, branches, seal["journal_prefix"]), "paired final seal differs")
            _validate_seal_prefix(study, run / "journal", seal)
            seals[pilot] = seal
    native = _native()
    remaining = {s for s, r in state["results"].items() if r["role"] in ("group", "quality")}
    for row in study["assessment_plan"]:
        pilot, arm = row["pilot"], row["arm"]
        branch = branches.get((pilot, arm))
        portfolio = (branch["result"] or {}).get("portfolio") if branch else None
        prefix = native.slot_prefix(row["id"])
        group = state["results"].get(prefix + ".group")
        if group is not None:
            require(portfolio is not None and pilot in seals, "judgment precedes the immutable paired finals")
            expected = native.group_request(portfolio)
            require(group["request_sha256"] == json_sha(expected), "saved group request changed its paired final")
            remaining.remove(prefix + ".group")
            if group["status"] == "response":
                native._response(group, prefix + ".group", "group", expected, portfolio)
                try:
                    partition = native.fold_group(portfolio, group, assessment_id=row["id"])["partition"]
                except ValueError:
                    partition = None
                if partition is not None:
                    heads = native.modules["score"].heads(partition)
                    for i, request in zip(heads, native.quality_requests(portfolio, partition), strict=True):
                        slot = f"{prefix}.quality.{i:02}"
                        result = state["results"].get(slot)
                        if result is not None:
                            require(result["request_sha256"] == json_sha(request), "saved quality request changed its head")
                            if result["status"] == "response":
                                native._response(result, slot, "quality", request, portfolio)
                            remaining.remove(slot)
        path = run / "assessments" / (prefix + ".json")
        if path.exists():
            require(group is not None and portfolio is not None and pilot in seals, "assessment lacks sealed source")
            assessment = _read(path)
            requests = assessment["requests"]
            require(all(r == state["results"].get(r["slot_id"]) for r in requests), "assessment uses foreign results")
            expected = native.finalize(portfolio, requests[0], requests[1:], assessment_id=row["id"])
            require(assessment == expected, "native assessment does not replay exactly")
            assessments[row["id"]] = assessment
    require(not remaining, "quality evidence has no valid paired group/head")
    return {"branches": branches, "seals": seals, "assessments": assessments}


def _pair_seal(study: dict, pilot: str, branches: dict, prefix: dict) -> dict:
    return _seal({"kind": "phase3a-pair-seal-v1", "study_sha256": study["study_sha256"], "pilot": pilot,
        "branches": {arm: branches[pilot, arm]["sha256"] for arm in ARMS},
        "finals": {arm: branches[pilot, arm]["portfolio_sha256"] for arm in ARMS}, "journal_prefix": prefix})


def _validate_seal_prefix(study: dict, journal: Path, seal: dict) -> None:
    events = accounting.events(journal)
    prefix, pilot = seal["journal_prefix"], seal["pilot"]
    index = prefix["index"]
    require(type(index) is int and 0 <= index <= len(events) and set(prefix) == {"index", "event_sha256"},
            "invalid seal journal prefix")
    require(prefix["event_sha256"] == (events[index - 1]["event_sha256"] if index else None), "seal prefix changed")
    for event in events:
        if event["kind"] != "intent":
            continue
        meta = study["slots"][event["record"]["slot_id"]]
        if meta["pair"] == pilot:
            require((meta["cell"] == "assessment") == (event["index"] > index),
                    "judging preceded a paired final seal or inference followed it")


def _record_branch(study: dict, run: Path, pilot: str, arm: str, fixture: bool,
                   result: dict | None, failure: str | None) -> dict:
    portfolio = result.get("portfolio") if result else None
    record = _seal({"kind": "phase3a-branch-v1", "study_sha256": study["study_sha256"],
        "pilot": pilot, "arm": arm, "fixture": fixture, "result": result, "failure": failure,
        "portfolio_sha256": json_sha(portfolio) if portfolio else None})
    _publish(_branch_path(run, pilot, arm), record)
    return record


def _classify(exc: Exception) -> str:
    return type(exc).__name__


def run(study_path: Path, grant_path: Path, *, stage: str, transport: Any,
        proposer_factory: Callable[..., Any], cutoff: str | None = None) -> dict:
    from .native import run_adaptation

    require(stage in ("first", "remaining"), "unknown phase execution stage")
    preflight(study_path, grant_path, transport.fixture)
    study = load_study(study_path)
    grant = _grant(study, grant_path, transport.fixture)
    run_path, _ = _paths(study, transport.fixture)
    seed = Path(study_path).parent / "seed"
    evaluator = _native()
    with writer_lock(run_path / "owner"):
        ledger = _ledger(study, grant, transport)
        state = ledger.state()
        saved = _saved(study_path, study, run_path, state, transport.fixture)
        if stage == "remaining":
            require(state["engineering_review"] is not None, "first-pair engineering review required")
        global_stop: list[Exception] = []

        def finish() -> dict:
            current = snapshot(study_path, grant_path, transport.fixture, cutoff=cutoff, _locked=True)
            summary = current["summary"]
            _publish(run_path / "report-cutoffs" / f"{summary['evidence_sha256']}.json", {
                "evidence_sha256": summary["evidence_sha256"], "cutoff": summary["cutoff"]})
            return summary

        def dispatch_for(pilot: str, arm: str | None = None):
            cell = pilot + ":" + arm if arm else "assessment"

            def dispatch(slot: str, role: str, request: dict, **kwargs: Any) -> dict:
                if global_stop:
                    raise global_stop[0]
                require(slot in study["slots"] and study["slots"][slot]["cell"] == cell
                        and study["slots"][slot]["pair"] == pilot, "request escaped its paired resource cell")
                if hasattr(transport, "select"):
                    transport.select(role, slot)
                try:
                    return ledger.dispatch(slot, role, request, **kwargs)
                except (accounting.LiabilityStop, accounting.IntegrityStop, accounting.PhaseBudgetStop) as exc:
                    global_stop.append(exc)
                    raise
            return dispatch

        for entry in study["tasks"]:
            pilot, task = entry["pilot_id"], _task(entry)
            if stage == "first" and pilot != FIRST:
                break
            if pilot != FIRST and not ledger.state()["first_assessments_closed"]:
                break
            for arm in entry["arm_order"]:
                if (pilot, arm) in saved["branches"]:
                    continue
                result, failure = None, None
                try:
                    if arm == "fixed":
                        result = strategy.fixed_best6(task, seed, study_sha256=study["study_sha256"],
                            run_id=_fixed_id(study, pilot), dispatch=dispatch_for(pilot, arm), fixture=transport.fixture,
                            known_results=ledger.state()["results"])
                    else:
                        prop = proposer_factory(task=task, pilot=pilot, dispatch=dispatch_for(pilot, arm),
                            audit_dir=_search_root(run_path, pilot, arm) / "editor-audit", halt=ledger.halt,
                            study_sha256=study["study_sha256"], fixture=transport.fixture)
                        result = run_adaptation(task, seed, study_sha256=study["study_sha256"],
                            run_root=_search_root(run_path, pilot, arm), tag=_native_tag(study, pilot),
                            dispatch=dispatch_for(pilot, arm), fixture=transport.fixture, prop=prop,
                            known_results=ledger.state()["results"], result_snapshot=lambda: ledger.state()["results"],
                            halt=ledger.halt)
                except accounting.IntegrityStop as exc:
                    ledger.halt("component_provenance_or_profile_mismatch")
                    global_stop.append(exc)
                except ContractError as exc:
                    failure = _classify(exc)
                if global_stop or ledger.state()["status"] != "ready":
                    return finish()
                saved["branches"][pilot, arm] = _record_branch(study, run_path, pilot, arm, transport.fixture, result, failure)
            if not all((pilot, arm) in saved["branches"] for arm in ARMS):
                break
            if pilot not in saved["seals"]:
                events = accounting.events(run_path / "journal")
                prefix = {"index": len(events), "event_sha256": events[-1]["event_sha256"] if events else None}
                seal = _pair_seal(study, pilot, saved["branches"], prefix)
                _publish(run_path / "seals" / f"{pilot}.json", seal)
                saved["seals"][pilot] = seal
            for row in [r for r in study["assessment_plan"] if r["pilot"] == pilot]:
                if ledger.state()["assessment_stopped"]:
                    break
                if row["id"] in saved["assessments"]:
                    continue
                branch = saved["branches"][pilot, row["arm"]]
                portfolio = (branch["result"] or {}).get("portfolio")
                if portfolio is None:
                    continue
                try:
                    assessment = evaluator.assess(portfolio, dispatch_for(pilot), assessment_id=row["id"],
                        checkpoint="canary" if pilot == FIRST else "expansion")
                    _publish(run_path / "assessments" / (evaluator.slot_prefix(row["id"]) + ".json"), assessment)
                    saved["assessments"][row["id"]] = assessment
                except accounting.AssessmentBudgetStop:
                    break
                except (accounting.CheckpointStop, accounting.PhaseBudgetStop,
                        accounting.LiabilityStop, accounting.IntegrityStop):
                    return finish()
                except ContractError:
                    # The unchanged native bridge reports an unresolved reply
                    # with its base error type; the journal retains liability.
                    if ledger.state()["status"] != "ready":
                        return finish()
                    raise
            if pilot == FIRST and ledger.state()["engineering_review"] and not ledger.state()["first_assessments_closed"]:
                close_first_assessments(study_path, grant_path, transport.fixture, _locked=True)
        return finish()


def _cutoff(value: str | None) -> str:
    result = value or dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    require(dt.datetime.strptime(result, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%dT%H:%M:%SZ") == result,
            "cutoff must be canonical UTC")
    return result


def _coverage(study: dict, state: dict, saved: dict) -> dict:
    slots = dict.fromkeys(study["slots"], "not_attempted")
    for slot, meta in study["slots"].items():
        if meta["cell"] in state.get("stopped_cells", []):
            slots[slot] = "not_attempted_cell_budget"
        elif meta["cell"] == "assessment" and state.get("assessment_stopped"):
            slots[slot] = "not_attempted_assessment_budget"
    for slot, result in state["results"].items():
        if result["status"] != "response":
            slots[slot] = "unknown_liability"
            continue
        response = result["response"]
        content = response.get("content", (response.get("provider_response") or {}).get("content", []))
        tool_reply = result["role"] == "editor" and any(
            isinstance(block, dict) and block.get("type") == "tool_use" for block in content)
        slots[slot] = ("refused" if response.get("refusal") or response.get("stop_reason") in ("refusal", "content_filter")
                      else "truncated" if response.get("stop_reason") in ("max_tokens", "length")
                      else "known_tool_response" if tool_reply
                      else "empty" if not response.get("text", "").strip() else "known_response")
    native = _native()
    for row in study["assessment_plan"]:
        branch = saved["branches"].get((row["pilot"], row["arm"]))
        prefix = native.slot_prefix(row["id"])
        if branch is not None and not (branch["result"] or {}).get("portfolio"):
            for slot in study["slots"]:
                if slot.startswith(prefix + "."):
                    require(slot not in state["results"], "judge used a missing final")
                    slots[slot] = "skipped_missing_final"
        assessment = saved["assessments"].get(row["id"])
        fields = assessment["native"].get("partition_fields") if assessment else None
        invalid_group = bool(assessment and fields is None)
        group = state["results"].get(prefix + ".group")
        if not assessment and group and group["status"] == "response" and branch:
            portfolio = (branch["result"] or {}).get("portfolio")
            if portfolio:
                try:
                    fields = native.fold_group(portfolio, group, assessment_id=row["id"])
                except ValueError:
                    invalid_group = True
        if fields is not None:
            heads = set(native.modules["score"].heads(fields["partition"]))
            for i in range(10):
                slot = f"{prefix}.quality.{i:02}"
                if i not in heads:
                    require(slot not in state["results"], "nonhead quality was dispatched")
                    slots[slot] = "not_needed_nonhead"
        elif invalid_group:
            for i in range(10):
                slot = f"{prefix}.quality.{i:02}"
                if slot not in state["results"]:
                    slots[slot] = "skipped_invalid_group"
    from collections import Counter

    return {"slots": slots, "slot_counts": dict(Counter(slots.values())), "scheduled_slots": len(slots)}


def _first_done(study: dict, saved: dict, state: dict) -> bool:
    if FIRST not in saved["seals"]:
        return False
    for row in study["assessment_plan"]:
        if row["pilot"] != FIRST:
            continue
        branch = saved["branches"].get((FIRST, row["arm"]))
        if branch is None:
            return False
        if ((branch["result"] or {}).get("portfolio") is not None and row["id"] not in saved["assessments"]
                and not state.get("assessment_stopped")):
            return False
    return True


def _empty_state(study: dict, fixture: bool) -> dict:
    return {"study_sha256": study["study_sha256"], "fixture": fixture, "run_id": None,
            "status": "ready", "attempts": 0, "results": {}, "intents": {}, "spent_micro_usd": 0,
            "reserved_micro_usd": 0, "provider_calls": 0, "engineering_review": None,
            "first_assessments_closed": False, "cells": {}, "assessment": {}, "first_pair": {}}


def _historical_resources(study: dict, state: dict) -> dict:
    prior = study["prior_live_episode"]
    known, reserved = prior["known_spent_micro_usd"], prior["reserved_micro_usd"]
    fixture = state["fixture"]
    total_known = None if fixture else known + state["spent_micro_usd"]
    total_reserved = None if fixture else reserved + state["reserved_micro_usd"]
    return {"prior_real_phase3a_spent_micro_usd": known,
            "prior_real_phase3a_reserved_micro_usd": reserved,
            "prior_real_phase3a_provider_calls": prior["provider_calls"],
            "prior_real_phase3a_known_responses": prior["known_requests"],
            "prior_real_phase3a_unknown_responses": prior["unknown_requests"],
            "cumulative_real_phase3a_spent_micro_usd": total_known,
            "cumulative_real_phase3a_reserved_micro_usd": total_reserved,
            "cumulative_real_phase3a_max_exposure_micro_usd": None if fixture else
                known + reserved + state["spent_micro_usd"] + state["reserved_micro_usd"],
            "cumulative_real_phase3a_provider_calls": None if fixture else prior["provider_calls"] + state["provider_calls"],
            "historical_accounting_settled": reserved == 0,
            "historical_unknown_released": False}


def _resources(study: dict, state: dict) -> dict:
    """Authoritative usage totals remain separate from native action accounting."""
    profiles: dict[str, dict] = {}
    for slot, result in state["results"].items():
        request = state["intents"][slot]["request"]
        profile = {"role": result["role"], "model": request["model"],
                   "effort": request.get("output_config", {}).get("effort", request.get("reasoning_effort")),
                   "thinking": request.get("thinking"),
                   "max_tokens": request.get("max_tokens", request.get("max_completion_tokens"))}
        key = json_sha(profile)
        row = profiles.setdefault(key, profile | {"attempts": 0, "known": 0, "unknown": 0,
            "spent_micro_usd": 0, "reserved_micro_usd": 0, "uncached_input_tokens": 0,
            "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "output_tokens": 0,
            "reported_reasoning_tokens": 0, "reasoning_usage_reported_calls": 0})
        row["attempts"] += 1
        row["reserved_micro_usd"] += result["reserved_micro_usd"]
        if result["status"] != "response":
            row["unknown"] += 1
            continue
        row["known"] += 1
        row["spent_micro_usd"] += result["spent_micro_usd"]
        usage = result["response"]["usage"]
        for target, source in (("uncached_input_tokens", "input_tokens"),
                               ("cache_creation_input_tokens", "cache_creation_input_tokens"),
                               ("cache_read_input_tokens", "cache_read_input_tokens"), ("output_tokens", "output_tokens")):
            row[target] += usage.get(source, 0)
        reasoning = (usage.get("output_tokens_details") or {}).get(
            "reasoning_tokens" if result["role"] == "group" else "thinking_tokens")
        if reasoning is not None:
            row["reported_reasoning_tokens"] += reasoning
            row["reasoning_usage_reported_calls"] += 1
    utilization = {}
    for cell, values in state["cells"].items():
        utilization[cell] = {"spent_fraction": values["spent_micro_usd"] / accounting.POLICY["cell_micro_usd"],
            "http_fraction": values["attempts"] / accounting.POLICY["cell_http"],
            "input_fraction": values["input_tokens"] / accounting.POLICY["cell_input"],
            "output_fraction": values["output_tokens"] / accounting.POLICY["cell_output"]}
    return {"profiles": [profiles[key] for key in sorted(profiles)], "inference_allowance_utilization": utilization,
            **_historical_resources(study, state),
            "original_phase3a_cap_micro_usd": 220000000,
            "current_study_cap_micro_usd": accounting.POLICY["phase_micro_usd"],
            "assessment_allowance_micro_usd": accounting.POLICY["assessment_micro_usd"],
            "inference_allowance_micro_usd_per_cell": accounting.POLICY["cell_micro_usd"],
            "wall_time_seconds": None, "wall_time_basis": "Retain actual host launch/runtime records separately; not measured by the request journal.",
            "thinking_usage_note": "Reported reasoning is a subset of output, not an extra charge. Unreported thinking is not inferred as zero.",
            "cost_basis": accounting.POLICY["cost_basis"], "fixture": state["fixture"], "study_sha256": study["study_sha256"]}


def _untrusted_artifacts(run: Path) -> dict:
    """Hash ordinary held evidence without opening links or special entries."""
    inventory = {}
    for name in ("branches", "search", "seals", "assessments"):
        base = run / name
        if not base.exists() and not base.is_symlink():
            continue
        try:
            descriptor = os.open(base, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        except OSError:
            inventory[name] = {"status": "unread_nonordinary_or_unavailable"}
            continue
        try:
            for parent, directories, files, directory_fd in os.fwalk(".", dir_fd=descriptor, follow_symlinks=False):
                for child in sorted(directories + files):
                    relative = (Path(name) / parent / child).as_posix()
                    details = os.stat(child, dir_fd=directory_fd, follow_symlinks=False)
                    if stat.S_ISDIR(details.st_mode):
                        continue
                    if not stat.S_ISREG(details.st_mode):
                        inventory[relative] = {"status": "unread_nonordinary"}
                        continue
                    entry = os.open(child, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
                    with os.fdopen(entry, "rb") as stream:
                        opened = os.fstat(stream.fileno())
                        require(stat.S_ISREG(opened.st_mode) and (opened.st_dev, opened.st_ino) ==
                                (details.st_dev, details.st_ino), "held evidence changed during inspection")
                        inventory[relative] = {"status": "untrusted_ordinary_file", "sha256": hashlib.file_digest(stream, "sha256").hexdigest()}
        finally:
            os.close(descriptor)
    return inventory


def snapshot(study_path: Path, grant_path: Path, fixture: bool, *, cutoff: str | None = None,
             _locked: bool = False) -> dict:
    study = load_study(study_path)
    _grant(study, grant_path, fixture)
    run_path, journal = _paths(study, fixture)
    if not _locked:
        import fcntl

        lock = run_path / "owner/.writer.lock"
        if lock.exists():
            with lock.open("rb") as stream:
                try:
                    fcntl.flock(stream, fcntl.LOCK_SH | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise ContractError("another owner is executing this phase") from exc
                return snapshot(study_path, grant_path, fixture, cutoff=cutoff, _locked=True)
        return snapshot(study_path, grant_path, fixture, cutoff=cutoff, _locked=True)
    state = accounting.replay(journal) if (journal / "manifest.json").exists() else _empty_state(study, fixture)
    validation_failure = None
    try:
        saved = _saved(study_path, study, run_path, state, fixture)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        if state["status"] == "ready":
            raise
        saved = {"branches": {}, "seals": {}, "assessments": {}}
        validation_failure = {"kind": "phase3a-untrusted-held-evidence-v1", "exception_type": type(exc).__name__,
                              "artifacts": _untrusted_artifacts(run_path), "scientific_use": "disqualified"}
    rows = []
    for entry in study["tasks"]:
        for arm in ARMS:
            branch = saved["branches"].get((entry["pilot_id"], arm))
            portfolio = (branch["result"] or {}).get("portfolio") if branch else None
            assessment_id = _assessment_id(study, entry["pilot_id"], arm)
            assessment = saved["assessments"].get(assessment_id)
            result = (branch["result"] or {}) if branch else {}
            rows.append({"pilot": entry["pilot_id"], "parent_task_id": entry["parent_task_id"], "arm": arm,
                "branch_status": (branch["result"] or {}).get("status", branch["failure"]) if branch else "not_attempted",
                "final_sha256": json_sha(portfolio) if portfolio else None,
                "assessment_id": assessment_id, "assessment_sha256": json_sha(assessment) if assessment else None,
                "status": assessment["status"] if assessment else (
                    "assessment_budget_stop" if state.get("assessment_stopped") else "unscored") if portfolio else "missing_final",
                "metrics": assessment["metrics"] if assessment else {"utility": None, "distinct": None},
                "first_answer_quality": assessment["native"]["fields"]["generation_scores"][0] if assessment else None,
                "authentic": bool(arm == "adaptive" and result.get("authentic")),
                "inference_accounting": state["cells"].get(entry["pilot_id"] + ":" + arm, {}),
                "native_actions": result.get("native", {}).get("modes", {}).get("agg", {}).get("ledger")
                    if arm == "adaptive" else None,
                "native_action_cost_is_authoritative": False,
                "stage_dispositions": result.get("stage_dispositions") if arm == "adaptive" else None,
                "fixed_candidate_dispositions": [{"run_id": c["run_id"], "status": c["status"],
                    "reason": c.get("reason")} for c in result.get("candidates", [])] if arm == "fixed" else None})
            if validation_failure is not None:
                rows[-1].update(status="unvalidated_integrity_hold", branch_status="unvalidated_integrity_hold")
    scored = all(row["status"] == "scored" for row in rows)
    authentic = any(row["authentic"] for row in rows)
    complete = scored and state["status"] == "ready" and state["reserved_micro_usd"] == 0 and (fixture or authentic)
    pairs = []
    for entry in study["tasks"]:
        pair = {row["arm"]: row for row in rows if row["pilot"] == entry["pilot_id"]}
        difference = (pair["adaptive"]["metrics"]["utility"] - pair["fixed"]["metrics"]["utility"]
                      if all(pair[a]["status"] == "scored" for a in ARMS) else None)
        distinct = (pair["adaptive"]["metrics"]["distinct"] - pair["fixed"]["metrics"]["distinct"]
                    if all(pair[a]["status"] == "scored" for a in ARMS) else None)
        pairs.append({"pilot": entry["pilot_id"], "adaptive_minus_fixed": difference,
                      "adaptive_minus_fixed_distinct": distinct})
    mean = sum(row["adaptive_minus_fixed"] for row in pairs) / 4 if complete else None
    anchor_id = _assessment_id(study, FIRST, "fixed", diagnostic=True)
    anchor, primary = saved["assessments"].get(anchor_id), saved["assessments"].get(_assessment_id(study, FIRST, "fixed"))
    diagnostic: dict[str, Any] = {"assessment_id": anchor_id, "status": anchor["status"] if anchor else "missing",
                  "primary_unchanged": True, "partition_equal": None, "utility_difference": None,
                  "shared_head_positions": [], "shared_head_score_disagreements": None}
    if anchor and primary and anchor["status"] == primary["status"] == "scored":
        af, pf = anchor["native"]["fields"], primary["native"]["fields"]
        positions = [i for i in range(10) if af["generation_scores"][i] is not None and pf["generation_scores"][i] is not None]
        diagnostic.update(partition_equal=anchor["native"]["partition_fields"]["partition"] == primary["native"]["partition_fields"]["partition"],
            utility_difference=af["utility"] - pf["utility"], shared_head_positions=positions,
            shared_head_score_disagreements=sum(af["generation_scores"][i] != pf["generation_scores"][i] for i in positions))
    analysis = {"kind": "phase3a-paired-development-analysis-v1", "pairs": pairs, "independent_prompt_units": 4,
                "mean_adaptive_minus_fixed": mean, "complete_primary": complete, "authentic_live_path": authentic,
                "fixture": fixture, "selected_method": None, "diagnostic": diagnostic,
                "held_evidence_failure": validation_failure,
                "limits": ["Development feasibility only; no population or equal-realized-compute causal claim.",
                           "The duplicate is diagnostic and never replaces the original primary assessment."]}
    coverage = _coverage(study, state, saved)
    evidence_id = json_sha({"state": state, "branches": {f"{p}:{a}":r for (p,a),r in saved["branches"].items()},
                            "assessments": saved["assessments"], "analysis": analysis, "coverage": coverage})
    time_path = run_path / "report-cutoffs" / f"{evidence_id}.json"
    if cutoff is None and time_path.is_file():
        cutoff = _read(time_path)["cutoff"]
    summary = {"kind": "phase3a-summary-v1", "study_sha256": study["study_sha256"], "fixture": fixture,
        "status": "mock-complete" if complete and fixture else "complete" if complete else "incomplete",
        "attempts": state["attempts"], "provider_calls": state["provider_calls"],
        "spent_micro_usd": state["spent_micro_usd"], "reserved_micro_usd": state["reserved_micro_usd"],
        **_historical_resources(study, state),
        "journal_status": state["status"], "primary_scored": sum(row["status"] == "scored" for row in rows),
        "primary_scheduled": 8, "complete_primary": complete, "authentic_live_path": authentic,
        "engineering_review": state["engineering_review"], "first_assessments_closed": state["first_assessments_closed"],
        "first_assessments_done": _first_done(study, saved, state), "cutoff": _cutoff(cutoff), "evidence_sha256": evidence_id}
    return {"study": study, "state": state, "saved": saved, "rows": rows, "coverage": coverage,
            "analysis": analysis, "summary": summary}


def _review_evidence(study_path: Path, study: dict, run: Path, state: dict, record: dict) -> None:
    saved = _saved(study_path, study, run, state, state["fixture"])
    require(FIRST in saved["seals"] and all((FIRST, arm) in saved["branches"] for arm in ARMS),
            "first pair lacks complete inference dispositions and seal")
    require(state["status"] == "ready" and state["reserved_micro_usd"] == 0,
            "engineering review cannot override integrity or liability")
    require(record["first_assessments_closed"] == _first_done(study, saved, state),
            "first assessment closure is not supported by saved outcomes")
    for name, expected in record["evidence"].items():
        path = checked_path(Path(name))
        require(file_hash(path) == expected, "engineering review evidence changed")


def _publish_first_review(study_path: Path, grant_path: Path, fixture: bool, review_id: str,
                          *, closure: bool, _locked: bool = False) -> dict:
    study = load_study(study_path)
    _grant(study, grant_path, fixture)
    run_path, journal = _paths(study, fixture)
    if not _locked:
        with writer_lock(run_path / "owner"):
            return _publish_first_review(study_path, grant_path, fixture, review_id, closure=closure, _locked=True)
    state = accounting.replay(journal)
    saved = _saved(study_path, study, run_path, state, fixture)
    require(FIRST in saved["seals"], "first paired outputs were not sealed")
    files = [run_path / "seals" / f"{FIRST}.json",
             *[_branch_path(run_path, FIRST, arm) for arm in ARMS], journal / "manifest.json"]
    evaluator = _native()
    for row in study["assessment_plan"]:
        if row["pilot"] != FIRST:
            continue
        path = run_path / "assessments" / (evaluator.slot_prefix(row["id"]) + ".json")
        if path.exists():
            files.append(path)
    record = {"review_id": review_id, "study_sha256": study["study_sha256"], "run_id": state["run_id"],
              "state_sha256": json_sha(state), "checks": dict.fromkeys(accounting.CHECKS, True),
              "evidence": {str(path): file_hash(path) for path in files},
              "first_assessments_closed": _first_done(study, saved, state)}
    _review_evidence(study_path, study, run_path, state, record)
    def callback(prefix, value):
        _review_evidence(study_path, study, run_path, prefix, value)
    if closure:
        return accounting.close_first_assessments(journal, record, validate_evidence=callback)
    return accounting.publish_review(journal, record, validate_evidence=callback)


def review_first(study_path: Path, grant_path: Path, fixture: bool, *, review_id: str = "first-pair-engineering-001") -> dict:
    """Publish only saved engineering/accounting evidence, without reading utility as a gate."""
    return _publish_first_review(study_path, grant_path, fixture, review_id, closure=False)


def close_first_assessments(study_path: Path, grant_path: Path, fixture: bool, *, _locked: bool = False) -> dict:
    return _publish_first_review(study_path, grant_path, fixture, "first-pair-assessments-closed-001",
                                  closure=True, _locked=_locked)


def report(study_path: Path, grant_path: Path, output: Path, fixture: bool, *, cutoff: str | None = None) -> dict:
    saved = snapshot(study_path, grant_path, fixture, cutoff=cutoff)
    output = checked_path(output)
    for name in ("rows", "coverage", "analysis", "summary"):
        _publish(output / f"{name}.json", saved[name])
    state, study = saved["state"], saved["study"]
    _publish(output / "accounting.json", {k: v for k, v in state.items() if k not in ("results", "intents")}
             | {"resource_report": _resources(study, state)})
    _publish(output / "protocol.json", {"study_sha256": study["study_sha256"], "fixture": fixture,
        "specification_sha256": study["specification_sha256"], "source_sha256": study["source_sha256"],
        "runtime": study["runtime"], "policy": study["policy"], "task_manifest": study["tasks"],
        "slots": study["slots"], "assessment_plan": study["assessment_plan"],
        "fixed_candidate_order": study["fixed_candidate_order"],
        "requests": [{"slot_id": slot, "role": r["role"], "status": r["status"],
                      "request_sha256": r["request_sha256"], "result_sha256": json_sha(r),
                      "returned_model": (r.get("response") or {}).get("model"),
                      "failure": r.get("failure"),
                      "spent_micro_usd": r["spent_micro_usd"], "reserved_micro_usd": r["reserved_micro_usd"]}
                     for slot, r in state["results"].items()]})
    text = ("# Phase 3A paired development pilot\n\n"
        + ("Synthetic mock evidence; no real procedure effectiveness is established.\n\n" if fixture else "Development feasibility evidence; not held-out or equal-realized-compute causality.\n\n")
        + f"Status: {saved['summary']['status']}. Primary scores: {saved['summary']['primary_scored']}/8. "
        + f"Requests: {state['attempts']}; accounted micro-USD: {state['spent_micro_usd']}; "
        + f"unresolved reservation: {state['reserved_micro_usd']}.\n\n"
        + f"Prior real Phase3A episodes: {study['prior_live_episode']['known_spent_micro_usd']} accounted micro-USD; "
        + f"historical unresolved liability: {study['prior_live_episode']['reserved_micro_usd']} micro-USD, retained in full. "
        + ("Current values are synthetic; no combined real-spend total is inferred.\n\n" if fixture else
           f"Cumulative real Phase3A accounted micro-USD: {study['prior_live_episode']['known_spent_micro_usd'] + state['spent_micro_usd']}.\n\n")
        + "Scientific comparison completion does not settle historical engineering accounting.\n\n"
        + f"Complete-primary mean adaptive-minus-fixed: {saved['analysis']['mean_adaptive_minus_fixed']}. "
        + "Missing primary outcomes preclude a complete-case aggregate winner. Native fallback outcomes stay included and classified.\n\n"
        + "The fixed p3a-01 duplicate is diagnostic only; its first primary result remains unchanged. "
        + "All inference/probes/discarded candidates/editing/selection and separate judging costs remain charged once. "
        + "Equal resource ceilings are allowances, not equal realized spend or invoices.\n")
    write_bytes_once(output / "PHASE3A_REPORT.md", text.encode("utf-8"))
    return {**saved["summary"], "report_output": str(output), "reporting_provider_calls": 0}
