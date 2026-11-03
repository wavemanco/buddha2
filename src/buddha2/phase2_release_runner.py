"""Complete fixed-pilot execution and read-only evidence replay for P2-R.

The runner owns ordering and dependent work. Its injected release dispatcher
owns the full immutable worklist, stage authority and cumulative liabilities.
"""

from __future__ import annotations

import datetime
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .artifacts import ContractError, digest, read_json, write_once
from .phase2 import PROJECT, _object, _output, generate_order, parse_angles, parse_order, rank_order
from .phase2_contracts import export_native, slot_prefix, validate_portfolio
from .phase2_coverage import slot_coverage
from .phase2_decisions import _time, build_decision
from .phase2_dispatch import writer_lock
from .phase2_native import NativeAssessment
from .phase2_release_journal import (
    AuthorityError,
    BudgetStopError,
    LiabilityError,
    ReleaseDispatcher,
    _events,
    replay_journal,
)

_STAGES = {"first", "expansion"}
_FAILURE_KEYS = {"kind", "stage", "task_id", "repeat", "error", "attempts", "prefix_sha256",
                 "authority_sha256", "failed_slot"}


def _validate_release(study: dict) -> None:
    # Runtime import keeps preparation/CLI code separate from execution helpers.
    from .phase2_release import validate_release

    validate_release(study)


def _prefix_state(state: dict, attempts: Any) -> str:
    if type(attempts) is not int or not 0 <= attempts <= state["attempts"]:
        raise ContractError("failure record has an invalid journal prefix")
    ordered = list(state["results"].items())[:attempts]
    return digest({key: digest(value) for key, value in ordered})


def _failure_context(run: Path, state: dict, failed_slot: str | None = None) -> dict:
    attempts, authority = state["attempts"], state["authority_sha256"]
    if failed_slot is not None:
        # A cached malformed plan/rank remains the same outcome even after
        # independent work or a later grant extends the journal.
        events, _ = _events(run / "journal")
        intents = [event["record"] for event in events if event["kind"] == "intent"]
        matched = [(index, intent) for index, intent in enumerate(intents, 1)
                   if intent["slot_id"] == failed_slot]
        if (len(matched) != 1 or state["results"].get(failed_slot, {}).get("status") != "response"
                or state["results"][failed_slot]["intent_sha256"] != digest(matched[0][1])):
            raise ContractError("semantic failure lacks its original settled request")
        attempts, intent = matched[0]
        authority = intent["authority_sha256"]
    return {"attempts": attempts, "prefix_sha256": _prefix_state(state, attempts),
            "authority_sha256": authority, "failed_slot": failed_slot}


def _failure_name(row: dict) -> str:
    context = {key: row[key] for key in ("attempts", "prefix_sha256", "authority_sha256", "failed_slot")}
    return f"{slot_prefix(row['task_id'], 'A', row['repeat'])}.{row['stage']}.{digest(context)}.json"


def _failures(run: Path, study: dict, state: dict) -> list[dict]:
    tasks = {task["id"] for task in study["tasks"]}
    authorities = {row["authority_sha256"]: row for path in (run / "journal/authority").glob("*.grant.json")
                   for row in [read_json(path)]}
    failures = []
    for path in sorted((run / "failures").glob("*.json")):
        row = read_json(path)
        if (not isinstance(row, dict) or set(row) != _FAILURE_KEYS
                or row.get("kind") != "phase2-release-failure-v2"
                or row.get("task_id") not in tasks or type(row.get("repeat")) is not int
                or row["repeat"] not in (1, 2)
                or row.get("stage") not in ("generation-A", "generation-B", "rank", "assessment-A",
                                           "assessment-B", "assessment-C")
                or not isinstance(row.get("error"), str) or not row["error"]
                or row.get("prefix_sha256") != _prefix_state(state, row.get("attempts"))):
            raise ContractError("failure record differs from its immutable journal prefix")
        authority = row["authority_sha256"]
        if (not isinstance(authority, str) or authority not in authorities
                or authorities[authority]["attempts_at_grant"] > row["attempts"]):
            raise ContractError("failure record differs from its historical authority")
        if row["failed_slot"] is not None:
            method = "B" if row["stage"] == "generation-B" else "C" if row["stage"] == "rank" else None
            expected_slot = (slot_prefix(row["task_id"], method, row["repeat"])
                             + (".plan" if method == "B" else ".rank")) if method else None
            context = _failure_context(run, state, expected_slot) if expected_slot else None
            if (row["failed_slot"] != expected_slot or context is None
                    or any(row[key] != value for key, value in context.items())):
                raise ContractError("semantic failure differs from its original request")
        if path.name != _failure_name(row):
            raise ContractError("failure record path differs from its block/stage/attempt/authority")
        failures.append(row)
    return failures


def _record_failure(run: Path, stage: str, task: dict, repeat: int,
                    error: ContractError, state: dict, *, failed_slot: str | None = None) -> None:
    row = {"kind": "phase2-release-failure-v2", "stage": stage, "task_id": task["id"],
           "repeat": repeat, "error": str(error), **_failure_context(run, state, failed_slot)}
    write_once(run / "failures" / _failure_name(row), row)


def _artifacts(study: dict, run: Path, native: Any, state: dict) -> tuple[list[dict], list[dict], dict]:
    if any(path.is_symlink() for path in run.rglob("*")):
        raise ContractError("release artifacts cannot traverse links")
    declared = {row["order_id"]: row for row in study["worklist"]["outputs"]}
    portfolios, indexed, assessments = [], {}, []
    for path in sorted((run / "portfolios").glob("*.json")):
        row = read_json(path)
        validate_portfolio(row)
        provenance = row["provenance"]
        prefix = slot_prefix(row["task"]["id"], provenance["method"], provenance["repeat"])
        if path.stem != prefix or prefix not in declared:
            raise ContractError("saved portfolio is outside the frozen worklist")
        # A finalized portfolio always has its lossless native exchange beside it.
        if native.load_export(run / "native" / prefix) != row:
            raise ContractError("saved native export differs from its portfolio")
        portfolios.append(row)
        indexed[prefix] = row
    assessment_paths = list((run / "assessments").glob("*.json"))
    recoverable: dict[str, dict] = {}
    native_root = run / "native"
    if native_root.exists():
        paths = list(native_root.iterdir())
        if any(not path.is_dir() or path.name not in declared for path in paths):
            raise ContractError("native exchange contains an undeclared order")
        pending = {path.name: path for path in paths if path.name not in indexed}
        tasks = {task["id"]: task for task in study["tasks"]}

        def saved(slot: str, role: str, request: dict, **_: Any) -> dict:
            result = state["results"].get(slot)
            if (not result or result.get("role") != role
                    or result.get("request_sha256") != digest(request)):
                raise ContractError("orphan exchange lacks complete saved generation evidence")
            return result

        # Recover only the export-before-portfolio publication window. A saved
        # assessment proves its portfolio was already published; absence then
        # is corruption, not an interrupted publication to repair silently.
        for method in ("A", "B", "C"):
            for prefix, directory in pending.items():
                definition = declared[prefix]
                if definition["method"] != method:
                    continue
                if any(path.stem == prefix for path in assessment_paths):
                    raise ContractError("saved assessment is missing its published portfolio")
                if set(path.name for path in directory.iterdir()).difference({"generations.jsonl", "identities.json"}):
                    raise ContractError("native exchange contains an unexpected artifact")
                task, repeat = tasks[definition["task_id"]], definition["repeat"]
                if method == "C":
                    parent_prefix = slot_prefix(task["id"], "B", repeat)
                    parent = indexed.get(parent_prefix, recoverable.get(parent_prefix))
                    if parent is None:
                        raise ContractError("orphan permutation lacks its planner parent")
                    row = rank_order(study, parent, saved, checkpoint=definition["checkpoint"])
                else:
                    row = generate_order(study, task, repeat, method, saved,
                                         checkpoint=definition["checkpoint"], fixture=state["fixture"])
                generations, identities = directory / "generations.jsonl", directory / "identities.json"
                if identities.exists():
                    if not generations.exists() or native.load_export(directory) != row:
                        raise ContractError("orphan exchange differs from saved generation replay")
                elif generations.exists():
                    try:
                        if generations.stat().st_size > 2_000_000:
                            raise ValueError("native generation is too large")
                        lines = generations.read_text(encoding="utf-8").splitlines()
                        matches = len(lines) == 1 and json.loads(lines[0]) == native._instance(row)
                    except (OSError, ValueError, UnicodeError) as exc:
                        raise ContractError("partial native generation is unreadable") from exc
                    if not matches:
                        raise ContractError("partial native generation differs from saved replay")
                recoverable[prefix] = row
    for path in sorted(assessment_paths):
        portfolio = indexed.get(path.stem)
        if portfolio is None:
            raise ContractError("saved assessment lacks its frozen portfolio")
        provenance = portfolio["provenance"]
        assessments.append({**read_json(path), "method": provenance["method"],
                            "repeat": provenance["repeat"], "order_id": path.stem,
                            "study_sha256": study["study_sha256"]})
    # A complete saved generation can also prove a missing planner parent for
    # an already-published permutation. Recovery stays visible until resume
    # republishes the exact missing primary/export files.
    return [*portfolios, *recoverable.values()], assessments, recoverable


@contextmanager
def _reader_lock(run: Path) -> Iterator[None]:
    """Reject a concurrent active owner without creating any inspection files."""
    import fcntl

    lock = run / "owner/.writer.lock"
    if lock.is_symlink() or lock.parent.is_symlink():
        raise ContractError("release ownership lock cannot traverse a link")
    if not lock.exists():
        yield
        return
    with lock.open("rb") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ContractError("another concurrent writer owns the phase journal") from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def _evidence(study: dict, run: Path, native: Any) -> dict:
    state = replay_journal(run / "journal")
    portfolios, assessments, recoverable = _artifacts(study, run, native, state)
    failures = _failures(run, study, state)
    coverage = slot_coverage(study, state["results"], portfolios, assessments)
    return {"state": state, "portfolios": portfolios, "assessments": assessments,
            "failures": failures, "coverage": coverage, "recoverable_exports": recoverable}


def _cutoff(run: Path, evidence_id: str, supplied: str | None, *, publish: bool) -> str:
    path = run / "report-cutoffs" / f"{evidence_id}.json"
    prior = read_json(path) if path.exists() else None
    if prior is not None and (not isinstance(prior, dict) or set(prior) != {"evidence_sha256", "cutoff"}
                              or prior["evidence_sha256"] != evidence_id):
        raise ContractError("report cutoff record differs from its evidence")
    cutoff = supplied or (prior["cutoff"] if prior else datetime.datetime.now(
        datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    _time(cutoff)
    if publish and prior is None:
        write_once(path, {"evidence_sha256": evidence_id, "cutoff": cutoff})
    return cutoff


def _snapshot(study: dict, run: Path, *, cutoff: str | None, native: Any,
              publish: bool = False) -> dict:
    evidence = _evidence(study, run, native)
    evidence_id = digest(evidence)
    actual_cutoff = _cutoff(run, evidence_id, cutoff, publish=publish)
    state = evidence["state"]
    bundle = build_decision(study, evidence["portfolios"], evidence["assessments"], state, native,
                            track="benchmark", cutoff=actual_cutoff, fixture=state["fixture"])
    first_orders = {row["order_id"] for row in study["worklist"]["outputs"]
                    if row["checkpoint"] == "canary"}
    first = [row for row in evidence["assessments"] if row["order_id"] in first_orders]
    first_complete = (not evidence["recoverable_exports"] and len(first) == 3
                      and all(row["status"] == "scored" for row in first)
                      and state["status"] == "ready" and state["reserved_micro_usd"] == 0)
    complete = bundle["decision"]["native_complete"]
    status = ("mock-pilot-complete" if state["fixture"] else "pilot-complete") if complete else (
        "first-block-complete" if first_complete else "partial")
    frozen = {**evidence, "bundle": bundle}
    snapshot_id = digest(frozen)
    destination = run / "snapshots" / snapshot_id
    summary = {"status": status, "fixture": state["fixture"], "study_sha256": study["study_sha256"],
               "snapshot_sha256": snapshot_id, "snapshot": str(destination), "cutoff": actual_cutoff,
               "attempts": state["attempts"], "orders": len(evidence["assessments"]),
               "portfolios": len(evidence["portfolios"]), "spent_micro_usd": state["spent_micro_usd"],
               "recoverable_export_orders": len(evidence["recoverable_exports"]),
               "reserved_micro_usd": state["reserved_micro_usd"], "provider_calls": state["provider_calls"],
               "experiment_api_spend_micro_usd": 0 if state["fixture"] else None,
               "first_block_ready_for_review": first_complete,
               "missing_assessments": bundle["native_assessment"]["coverage"]["missing_assessments"],
               "decision_status": bundle["decision"]["status"],
               "selected_method": bundle["decision"]["selected_method"],
               "synthetic_selected_method": bundle["decision"]["synthetic_selected_method"]}
    records = {"coverage": evidence["coverage"], "state": state, "failures": evidence["failures"],
               "recoverable_exports": evidence["recoverable_exports"], "summary": summary, **bundle}
    complete_record = {"snapshot_sha256": snapshot_id,
                       "record_hashes": {name: digest(value) for name, value in records.items()}}
    completion = destination / "complete.json"
    if completion.exists() and read_json(completion) != complete_record:
        raise ContractError("published report completion differs from exact replay")
    for name, value in records.items():
        path = destination / f"{name}.json"
        if path.exists():
            raw = (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2)
                   + "\n").encode("utf-8")
            if path.stat().st_size != len(raw) or path.read_bytes() != raw:
                raise ContractError("published report differs from exact saved-evidence replay")
        elif completion.exists():
            raise ContractError("completed report is missing a required record")
        if publish:
            write_once(path, value)
    if publish:
        write_once(completion, complete_record)
    return {**evidence, "bundle": bundle, "summary": summary}


def snapshot(study: dict, run: Path, *, cutoff: str | None = None, native: Any = None) -> dict:
    """Replay all saved evidence; no dispatch, SDK construction, key read or write."""
    _validate_release(study)
    run = _output(run)
    native = native or NativeAssessment(PROJECT / ".upstream/novelty-bench")
    with _reader_lock(run):
        return _snapshot(study, run, cutoff=cutoff, native=native)


def _invalid_plan(study: dict, task: dict, repeat: int, state: dict) -> bool:
    result = state["results"].get(slot_prefix(task["id"], "B", repeat) + ".plan")
    if not result or result.get("status") != "response":
        return False
    raw = result["response"]
    if raw.get("stop_reason") in ("refusal", "max_tokens"):
        return True
    if raw.get("stop_reason") != "end_turn":
        return False
    try:
        parse_angles(_object(raw["text"]))
    except (ValueError, TypeError, KeyError):
        return True
    return False


def _invalid_rank(parent: dict, state: dict) -> bool:
    provenance = parent["provenance"]
    slot = slot_prefix(parent["task"]["id"], "C", provenance["repeat"]) + ".rank"
    result = state["results"].get(slot)
    if not result or result.get("status") != "response":
        return False
    raw = result["response"]
    if raw.get("stop_reason") in ("refusal", "max_tokens"):
        return True
    if raw.get("stop_reason") != "end_turn":
        return False
    try:
        parse_order(_object(raw["text"]), [row["id"] for row in parent["responses"]])
    except (ValueError, TypeError, KeyError):
        return True
    return False


def run_stage(study: dict, run: Path, *, stage: str, transport: Any,
              cutoff: str | None = None) -> dict:
    """Run the first block or the reviewed remainder in the same phase journal."""
    if not isinstance(stage, str) or stage not in _STAGES:
        raise ContractError("release stage must be first or expansion")
    _validate_release(study)
    run = _output(run)
    native = NativeAssessment(PROJECT / ".upstream/novelty-bench")
    with writer_lock(run / "owner"):
        dispatcher = ReleaseDispatcher(run / "journal", study=study, transport=transport)
        try:
            dispatcher.require_stage(stage)
        except LiabilityError:
            return _snapshot(study, run, cutoff=cutoff, native=native, publish=True)["summary"]
        before = _snapshot(study, run, cutoff=cutoff, native=native)
        if before["state"]["fixture"] is not transport.fixture:
            raise ContractError("release transport differs from the immutable fixture/live journal")
        return _run_locked(study, run, stage, transport, dispatcher, native, cutoff, before)


def _run_locked(study: dict, run: Path, stage: str, transport: Any, dispatcher: Any,
                native: Any, cutoff: str | None, before: dict) -> dict:
    indexed = {slot_prefix(row["task"]["id"], row["provenance"]["method"], row["provenance"]["repeat"]): row
               for row in before["portfolios"]}
    for prefix, portfolio in before["recoverable_exports"].items():
        export_native(portfolio, run / "native" / prefix)
        write_once(run / "portfolios" / f"{prefix}.json", portfolio)
        indexed[prefix] = portfolio
    assessed = {row["order_id"] for row in before["assessments"]}
    blocks = [row for row in study["worklist"]["blocks"]
              if (row["checkpoint"] == "canary") is (stage == "first")]
    tasks = {row["id"]: row for row in study["tasks"]}
    halt = False

    def dispatch(slot: str, role: str, request: dict, **kwargs: Any) -> dict:
        if hasattr(transport, "select"):
            transport.select(role, slot)
        return dispatcher.dispatch(slot, role, request, **kwargs)

    for block in blocks:
        task, repeat, checkpoint = tasks[block["task_id"]], block["repeat"], block["checkpoint"]
        saved = {method: indexed[prefix] for method in ("A", "B", "C")
                 if (prefix := slot_prefix(task["id"], method, repeat)) in indexed}
        for method in block["generation_order"]:
            if method in saved:
                continue
            try:
                saved[method] = generate_order(study, task, repeat, method, dispatch,
                                               checkpoint=checkpoint, fixture=transport.fixture)
                prefix = slot_prefix(task["id"], method, repeat)
                export_native(saved[method], run / "native" / prefix)
                write_once(run / "portfolios" / f"{prefix}.json", saved[method])
                indexed[prefix] = saved[method]
            except AuthorityError:
                raise
            except ContractError as exc:
                state = dispatcher.state()
                halt = (isinstance(exc, (BudgetStopError, LiabilityError)) or state["status"] != "ready"
                        or method != "B" or not _invalid_plan(study, task, repeat, state))
                failed_slot = None if halt else slot_prefix(task["id"], "B", repeat) + ".plan"
                _record_failure(run, "generation-" + method, task, repeat, exc, state, failed_slot=failed_slot)
                if halt:
                    break
        if not halt and "B" in saved and "C" not in saved:
            try:
                saved["C"] = rank_order(study, saved["B"], dispatch, checkpoint=checkpoint)
                prefix = slot_prefix(task["id"], "C", repeat)
                export_native(saved["C"], run / "native" / prefix)
                write_once(run / "portfolios" / f"{prefix}.json", saved["C"])
                indexed[prefix] = saved["C"]
            except AuthorityError:
                raise
            except ContractError as exc:
                state = dispatcher.state()
                halt = (isinstance(exc, (BudgetStopError, LiabilityError)) or state["status"] != "ready"
                        or not _invalid_rank(saved["B"], state))
                failed_slot = None if halt else slot_prefix(task["id"], "C", repeat) + ".rank"
                _record_failure(run, "rank", task, repeat, exc, state, failed_slot=failed_slot)
        if not halt:
            for method in ("A", "B", "C"):
                prefix = slot_prefix(task["id"], method, repeat)
                if method not in saved or prefix in assessed:
                    continue
                try:
                    portfolio = native.load_export(run / "native" / prefix)
                    if portfolio != saved[method]:
                        raise ContractError("native export/import changed the saved portfolio")
                    assessment = native.assess(portfolio, dispatch, checkpoint=checkpoint)
                    write_once(run / "assessments" / f"{prefix}.json", assessment)
                    assessed.add(prefix)
                except AuthorityError:
                    raise
                except ContractError as exc:
                    _record_failure(run, "assessment-" + method, task, repeat, exc, dispatcher.state())
                    halt = True
                    break
        if halt:
            break
    result = _snapshot(study, run, cutoff=cutoff, native=native, publish=True)
    return result["summary"]
