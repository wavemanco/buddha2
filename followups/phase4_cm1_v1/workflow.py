"""One P4-CM1 controller; existing native execution, ledger and transport do the work."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from buddha2.artifacts import (
    ContractError,
    digest,
    file_hash,
    read_json,
    write_bytes_once,
    write_once,
)
from followups.phase3b_seq2_v1 import accounting, editor, native, strategy
from followups.phase3b_seq2_v1 import ledger_core as core
from followups.phase3b_seq2_v1.adapter import CompatibleProposer
from followups.phase3b_seq2_v1.support import (
    NATIVE,
    ROOT,
    checked,
    offline_readiness,
    require,
    seal,
)

from . import assessment, control, eligibility, policy, release
from .release import claim as claim
from .release import load_study, make_grant, paths, prepare


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _freeze(study):
    return {"accepted": True, "method_sha256": study["method_sha256"],
            "source_sha256": study["confirmation_source_sha256"],
            "exposure_inventory_sha256": study["exposure_inventory_sha256"],
            "eligibility_proof_sha256": study["eligibility_proof_sha256"]}


def _ids(study: dict, pair: str) -> tuple[str, str, dict[str, str]]:
    return (f"{study['execution_tag']}/{pair}/fixed", f"{study['execution_tag']}-{pair}",
            {target: f"{study['study_sha256']}/{pair}/assessment/{target}" for target in assessment.TARGETS})


def worklist(study: dict, kind: str, pair: str, task: dict) -> dict:
    fixed, tag, targets = _ids(study, pair)
    slots: dict[str, dict] = {}
    if kind == "inference":
        for run_id in native.adaptive_run_ids(task["id"], tag).values():
            ids = strategy.slot_ids(run_id)
            for role, names in (("plan", [ids["plan"]]), ("answer", ids["answers"]), ("rank", [ids["rank"]])):
                slots.update({name: {"role": role, "cell": pair + ":adaptive", "pair": pair} for name in names})
        labels = [(f"{stage}.a{attempt}", "editor") for stage in native.STAGES for attempt in (1, 2)]
        for label, role in [*labels, ("select.seq2", "native_selector")]:
            for turn in range(1, 25):
                slots[f"{pair}.adaptive.editor.{label}.t{turn:02}"] = {
                    "role": role, "cell": pair + ":adaptive", "pair": pair,
                    "conversation": pair + ":adaptive:" + label, "turn": turn}
    if kind in {"dev", "inference"}:
        for pool in control.fixed_run_ids(fixed):
            for ordinal in range(1, 13):
                ids = strategy.slot_ids(f"{pool}/candidate-{ordinal:02d}")
                for role, names in (("plan", [ids["plan"]]), ("answer", ids["answers"]), ("rank", [ids["rank"]])):
                    slots.update({name: {"role": role, "cell": pair + ":fixed", "pair": pair} for name in names})
            slots[strategy.slot_ids(pool)["selector"]] = {"role": "fixed_selector", "cell": pair + ":fixed", "pair": pair}
        slots[strategy.slot_ids(fixed)["selector"]] = {"role": "fixed_selector", "cell": pair + ":fixed", "pair": pair}
    else:
        evaluator = native.Phase3NativeAssessment(ROOT / ".upstream/novelty-bench")
        for target_id in targets.values():
            slots.update({slot: {"role": role, "cell": "assessment", "pair": pair}
                          for slot, role in assessment.target_slots(evaluator, target_id).items()})
    policy._slot_scope(slots, kind, pair)
    return slots


def intake(study_path: Path) -> dict:
    """Content-hidden overlap/selection after acceptance, before keys or generation."""
    study = load_study(study_path)
    offline_readiness(study_path, {key: study[key] for key in release.READINESS_BINDINGS})
    manifest = eligibility.intake(eligibility.SOURCE_PATH, freeze=_freeze(study),
        exposure_audit_path=ROOT / release.RECORDS["exposure"], eligibility_proof=study["eligibility_proof"])
    write_once(study_path.parent / "confirmation-manifest.json", manifest)
    return {"passed": manifest["eligibility_passed"], "eligible_units": manifest["eligible_prompt_units"],
            "selected_source_ids": [row["source_task_id"] for row in manifest["selected"]], "provider_calls": 0}


def _manifest(study_path: Path, study: dict, *, verify_derivation: bool = True) -> dict:
    value = read_json(study_path.parent / "confirmation-manifest.json")
    require(value.get("manifest_sha256") == digest({k: v for k, v in value.items() if k != "manifest_sha256"})
        and value.get("frozen_method_sha256") == study["method_sha256"]
        and value.get("source_sha256") == study["confirmation_source_sha256"]
        and value.get("exposure_inventory_sha256") == study["exposure_inventory_sha256"]
        and value.get("eligibility_passed") is True and len(value.get("selected", [])) == 24,
        "accepted content-hidden confirmation manifest required")
    if verify_derivation:
        expected = eligibility.intake(eligibility.SOURCE_PATH, freeze=_freeze(study),
            exposure_audit_path=ROOT / release.RECORDS["exposure"], eligibility_proof=study["eligibility_proof"])
        require(value == expected, "confirmation manifest differs from its frozen deterministic derivation")
    return value


def _tasks(study_path: Path, study: dict, *, fixture: bool = False) -> list[dict]:
    if fixture:
        return [{"id": f"synthetic-p4-{i:02d}", "prompt": f"Give varied ways to arrange fictional reading room {i}.",
            "domain": "synthetic", "source_context": {"dataset": "synthetic", "revision": "0" * 40,
                "source_sha256": "0" * 64, "source_task_id": f"synthetic-p4-{i:02d}"}} for i in range(1, 25)]
    manifest = _manifest(study_path, study)
    raw = eligibility.SOURCE_PATH.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == study["confirmation_source_sha256"],
            "confirmation corpus changed after intake")
    rows = {row["id"]: row for row in (json.loads(line) for line in raw.decode("utf-8").splitlines())}
    selected = {row["source_task_id"]: row for row in manifest["selected"]}
    tasks = []
    for entry in manifest["selected"]:
        source_id = entry["source_task_id"]
        prompt = rows[source_id]["prompt"]
        require(digest(prompt) == selected[source_id]["prompt_sha256"], "selected prompt bytes differ")
        tasks.append({"id": source_id, "prompt": prompt, "domain": "nb-wildchat-confirmation",
            "source_context": {"dataset": "noveltybench/wildchat-1k",
                "revision": "64a23be6b18ec1dacc298830aab276061b6e143c",
                "source_sha256": study["confirmation_source_sha256"], "source_task_id": source_id}})
    return tasks


def preflight(study_path, grant_path, stage, mode, *, supervisor_agent=None, host=None):
    value = release.preflight(study_path, grant_path, stage, mode,
                              supervisor_agent=supervisor_agent, host=host)
    if mode == "provider":
        _manifest(study_path, load_study(study_path))
    return value


class Coordinator:
    """Serial child allowances; never duplicate the parent budget into another child."""

    def __init__(self, study: dict, run: Path, transport):
        self.study, self.run, self.transport = study, run, transport
        self.closed: list[dict] = []
        self.spent = dict.fromkeys(policy.ALLOCATIONS, 0)
        self.held = dict.fromkeys(policy.ALLOCATIONS, 0)
        self.reserved = 0
        self.attempts = 0
        self.active: tuple[str, str, str, Path, dict] | None = None
        self.active_ledger: accounting.Ledger | None = None
        self.active_profile: dict | None = None
        self.blocked = False
        self.qualification = False
        self.generation_seal: dict | None = None
        self.inference_hashes: list[str] = []

    def _generation_barrier(self):
        require(self.generation_seal is not None, "all generation must be sealed before any judge call")
        saved = checked(read_json(self.run / "generation-seal.json"))
        count = len(self.inference_hashes)
        require(saved == self.generation_seal and saved.get("study_sha256") == self.study["study_sha256"]
            and saved.get("count") == count and saved.get("generation_sha256") == self.inference_hashes
            and (1 <= count <= 24 if self.transport.fixture else count == 24),
            "the immutable generation barrier does not cover every planned task")

    def _source_guard(self):
        require(release.source_identity()["sha256"] == self.study["source_sha256"],
                "accepted implementation changed before provider admission")

    def progress(self, label: str, **fields) -> None:
        directory = self.run / "progress"
        index = len(list(directory.glob("*.json"))) + 1 if directory.exists() else 1
        write_once(directory / f"{index:03d}-{label}.json", seal({"kind": "phase4-cm1-progress-v1",
            "study_sha256": self.study["study_sha256"], "observed_at_utc": _now(), "stage": label,
            "settled_micro_usd": sum(self.spent.values()), "reserved_micro_usd": self.reserved,
            "attempts": self.attempts, **fields}))

    def open(self, kind: str, pair: str, task: dict, *, generation_study_sha256=None):
        require(not self.blocked and self.active is None and self.reserved == 0,
                "another child, integrity stop or unresolved liability is active")
        require(kind == "dev" or self.qualification, "qualification must pass before confirmation calls")
        if kind == "assessment":
            self._generation_barrier()
        require(not any(row["kind"] == kind and row["pair"] == pair for row in self.closed),
                "a completed or failed child cannot be repeated")
        self._source_guard()
        allocation = seal({"kind": "phase4-cm1-child-allocation-v1", "parent_sha256": self.study["study_sha256"],
            "ordinal": len(self.closed) + 1, "child_kind": kind, "pair": pair, "task_sha256": digest(task),
            "remaining_total_micro_usd": 1_200_000_000 - sum(self.spent.values()),
            "remaining_allocation_micro_usd": policy.ALLOCATIONS[kind] - self.spent[kind],
            "prior_closures": [row["sha256"] for row in self.closed]})
        slots = worklist(self.study, kind, pair, task)
        profile = policy.make(kind, pair, slots=slots, parent_sha256=self.study["study_sha256"],
            authorization_sha256=self.study["authorization_sha256"], allocation_sha256=digest(allocation),
            remaining_total_micro_usd=allocation["remaining_total_micro_usd"],
            remaining_allocation_micro_usd=allocation["remaining_allocation_micro_usd"],
            generation_study_sha256=generation_study_sha256)
        child = digest({"parent": self.study["study_sha256"], "allocation": allocation,
                        "profile": profile, "task_sha256": digest(task)})
        authority = {"study_sha256": child, "authorization_id": "P4-CM1/" + self.study["study_sha256"],
            "authorized": not self.transport.fixture, "expansion_authorized": False,
            "cap_micro_usd": profile["phase_micro_usd"], "canary_cap_micro_usd": profile["first_micro_usd"],
            "control_policy_sha256": core.am1.CONTROL_SHA256, "billing_profile": core.am1.BILLING_PROFILE}
        bindings = {"source_sha256": self.study["source_sha256"], "policy_sha256": digest(profile),
                    "launcher_sha256": self.study["launcher_sha256"]}
        target = self.run / "children" / f"{len(self.closed) + 1:03d}-{kind}-{pair}"
        opened = seal({"kind": "phase4-cm1-child-open-v1", "allocation": allocation,
            "child_sha256": child, "profile": profile, "slots": slots, "authority": authority,
            "bindings": bindings, "task": task, "generation_study_sha256": generation_study_sha256})
        core._publish(target / "open.json", opened)
        self.active = (kind, pair, child, target, opened)
        self.active_profile = profile

        def guard(state):
            # The ledger calls this after an operator wait and before the durable intent.
            self._source_guard()
            require(self.active == (kind, pair, child, target, opened)
                and checked(read_json(target / "open.json")) == opened, "parent active-child binding changed")
            require(sum(self.spent.values()) + state["spent_micro_usd"] + state["reserved_micro_usd"]
                    <= 1_200_000_000 and self.spent[kind] + state["spent_micro_usd"]
                    + state["reserved_micro_usd"] <= policy.ALLOCATIONS[kind]
                    and self.attempts + state["attempts"] <= 40914, "parent allocation exceeded")
            if kind == "assessment":
                self._generation_barrier()

        ledger = accounting.Ledger(accounting.canonical_journal(child, self.transport.fixture),
            study_sha256=child, slots=slots, authority=authority, transport=self.transport,
            bindings=bindings, editor_tools=self.study["editor_tools"], stage="p4",
            admission_guard=guard, profile=profile)
        self.active_ledger = ledger
        self.progress("child-open", child_sha256=child, pair=pair, child_kind=kind)
        return ledger, profile, target

    def close(self, ledger, result: dict) -> dict:
        require(self.active is not None, "no active child to reconcile")
        kind, pair, child, target, opened = cast(tuple[str, str, str, Path, dict], self.active)
        state = ledger.state()
        body = seal({"kind": "phase4-cm1-child-close-v1", "parent_sha256": self.study["study_sha256"],
            "child_sha256": child, "child_kind": kind, "pair": pair, "open_sha256": opened["sha256"],
            "journal": str(ledger.journal), "status": state["status"], "result_sha256": digest(result),
            "spent_micro_usd": state["spent_micro_usd"], "reserved_micro_usd": state["reserved_micro_usd"],
            "attempts": state["attempts"], "transport_audit_summary": state["transport_audit_summary"]})
        core._publish(target / "result.json", result)
        core._publish(target / "closure.json", body)
        self.spent[kind] += state["spent_micro_usd"]
        self.reserved += state["reserved_micro_usd"]
        self.held[kind] += state["reserved_micro_usd"]
        self.attempts += state["attempts"]
        self.closed.append({"kind": kind, "pair": pair, "sha256": body["sha256"], "path": str(target)})
        if kind == "inference":
            self.inference_hashes.append(digest(result))
        self.active = None
        self.active_ledger = None
        self.active_profile = None
        self.progress("child-closed", child_sha256=child, pair=pair, child_kind=kind,
                      child_status=state["status"])
        self.blocked = (state["status"] != "ready" or self.reserved != 0
            or bool(state["active_unsettled_intents"]) or state["durable_unknown_results"] != 0
            or bool(state["transport_audit_summary"]["missing_or_invalid_slots"]))
        require(self.reserved == 0 and not state["active_unsettled_intents"]
                and state["durable_unknown_results"] == 0, "unknown child liability blocks every later admission")
        require(not state["transport_audit_summary"]["missing_or_invalid_slots"], "child transport audit incomplete")
        if state["status"] in {"stopped-by-operator", "stopped-timing-review", "stopped-known-deadline"}:
            raise core.IntegrityStop("operator/timing decision closed the active execution")
        require(state["status"] == "ready", "a genuine child integrity halt blocks further spending")
        return body

    def accounting_view(self) -> dict:
        """An interrupted active child still contributes spending and held liability."""
        spent, reserved, attempts = sum(self.spent.values()), self.reserved, self.attempts
        by_kind, held_by_kind = dict(self.spent), dict(self.held)
        active = None
        if self.active is not None:
            try:
                require(self.active_ledger is not None, "active child ledger unavailable")
                state = cast(accounting.Ledger, self.active_ledger).state()
                active = {"spent_micro_usd": state["spent_micro_usd"],
                          "reserved_micro_usd": state["reserved_micro_usd"], "attempts": state["attempts"],
                          "accounting_status": state["status"], "known": True}
                spent += active["spent_micro_usd"]
                reserved += active["reserved_micro_usd"]
                attempts += active["attempts"]
                by_kind[self.active[0]] += active["spent_micro_usd"]
                held_by_kind[self.active[0]] += active["reserved_micro_usd"]
            except (ContractError, OSError, ValueError, TypeError, KeyError):
                # No release is inferred when the admitted child's accounting cannot be verified.
                amount = self.active_profile["phase_micro_usd"] if self.active_profile else 0
                reserved += amount
                held_by_kind[self.active[0]] += amount
                active = {"known": False, "conservative_held_micro_usd": amount}
        return {"spent_micro_usd": spent, "reserved_micro_usd": reserved, "attempts": attempts,
                "spent_by_allocation_micro_usd": by_kind, "reserved_by_allocation_micro_usd": held_by_kind,
                "active_child_accounting": active}


def _fixed(book: Coordinator, ledger, profile: dict, pair: str, task: dict, target: int, seed: Path) -> dict:
    return control.run_fixed(task, seed, study_sha256=ledger.manifest["inputs"]["study_sha256"],
        run_id=_ids(book.study, pair)[0], target_micro_usd=target, dispatch=ledger.dispatch,
        spent=lambda: ledger.state()["cells"][pair + ":fixed"]["spent_micro_usd"],
        fixture=book.transport.fixture, request_policy=profile)


def _retained_native(task: dict, seed: Path, *, child_sha: str, search: Path, tag: str,
                     fixture: bool, profile: dict, state: dict) -> dict | None:
    """Preserve validated checkpoint outputs after a known incomplete native run."""
    require(state.get("study_sha256") == child_sha and state.get("fixture") is fixture
        and isinstance(state.get("results"), dict), "partial native accounting origin differs")
    results = state["results"]
    partial = native.validate_adaptive_partial(task, seed, study_sha256=child_sha,
        run_root=search, tag=tag, fixture=fixture, results=results, request_policy=profile)
    ids = native.adaptive_run_ids(task["id"], tag)
    checkpoints, rollouts = dict.fromkeys(("c1", "c2")), {}
    for label in checkpoints:
        directory = search / "rollouts" / label
        saved = directory / "rollout.json"
        if partial[label]["status"] != "complete" or not saved.exists():
            continue
        record = strategy.validate_rollout(native.read_artifact(saved, request_policy=profile), task, directory / "harness",
            study_sha256=child_sha, fixture=fixture, run_id=ids[label], arm="adaptive",
            results=results, request_policy=profile)
        require(record["status"] == "complete" and record.get("portfolio") is not None,
                "complete partial checkpoint lacks its validated portfolio")
        checkpoints[label], rollouts[label] = record["portfolio"], record
    if not rollouts:
        return None
    return {"kind": "phase4-cm1-partial-native-v1", "status": "incomplete", "fixture": fixture,
        "arm": "adaptive", "study_sha256": child_sha, "task_id": task["id"], "tag": tag,
        "authentic": False, "selected_checkpoint": None, "portfolio": None,
        "checkpoints": checkpoints, "rollouts": rollouts, "partial_validation": partial,
        "stage_dispositions": []}


def _generation(book: Coordinator, pair: str, task: dict, seed: Path) -> dict:
    ledger, profile, _ = book.open("inference", pair, task)
    child = ledger.manifest["inputs"]["study_sha256"]
    search = NATIVE / child / ("mock" if book.transport.fixture else "live") / pair / "adaptive" / "search"
    failures: list[dict] = []
    register = getattr(book.transport, "register_contract", None)
    prop = CompatibleProposer(pilot=pair, study_sha256=child, dispatch=ledger.dispatch,
        audit_dir=search / "editor-audit", fixture=book.transport.fixture, halt=ledger.halt,
        source_sha256=book.study["source_sha256"], register_deadline=book.transport.register_conversation,
        register_contract=(lambda label, prepared: register(pair, label, prepared)) if callable(register) else None,
        request_policy=profile)
    adaptive = fixed = None
    failure = None
    try:
        adaptive = native.run_adaptation(task, seed, study_sha256=child, run_root=search,
            tag=_ids(book.study, pair)[1], dispatch=ledger.dispatch, fixture=book.transport.fixture,
            prop=prop, known_results=ledger.state()["results"], result_snapshot=lambda: ledger.state()["results"],
            halt=ledger.halt, on_required_failure=failures.append, request_policy=profile)
        if adaptive["status"] == "complete" and (book.transport.fixture or adaptive["authentic"]):
            fixed = _fixed(book, ledger, profile, pair, task,
                ledger.state()["cells"][pair + ":adaptive"]["spent_micro_usd"], seed)
    except (strategy.KnownOutcomeError, native.RequiredCheckpointStop, editor.KnownProviderTerminalStop, core.CellBudgetStop,
            core.PhaseBudgetStop, core.CheckpointStop) as exc:
        failure = type(exc).__name__
    state = ledger.state()
    if adaptive is None and failure is not None:
        adaptive = _retained_native(task, seed, child_sha=child, search=search,
            tag=_ids(book.study, pair)[1], fixture=book.transport.fixture, profile=profile, state=state)
    result = {"kind": "phase4-cm1-generation-v1", "task": task, "pair": pair,
        "generation_study_sha256": child, "adaptive": adaptive, "fixed": fixed,
        "failure": failure, "required_failures": failures,
        "native_micro_usd": state["cells"][pair + ":adaptive"]["spent_micro_usd"],
        "fixed_micro_usd": state["cells"][pair + ":fixed"]["spent_micro_usd"]}
    book.close(ledger, result)
    return result


def _assessment(book: Coordinator, generation: dict) -> dict:
    pair, task = generation["pair"], generation["task"]
    ledger, _, _ = book.open("assessment", pair, task,
        generation_study_sha256=generation["generation_study_sha256"])
    evaluator = native.Phase3NativeAssessment(ROOT / ".upstream/novelty-bench")
    adaptive, fixed = generation.get("adaptive") or {}, generation.get("fixed") or {}
    portfolios = {"fixed": fixed.get("portfolio"), **{key: adaptive.get("checkpoints", {}).get(key)
                                                       for key in ("c1", "c2")}}
    targets = dict.fromkeys(assessment.TARGETS)
    failure = None
    try:
        for target, portfolio in portfolios.items():
            if portfolio is not None:
                targets[target] = assessment.assess_target(evaluator, portfolio,
                    _ids(book.study, pair)[2][target], ledger.dispatch)
    except (core.AssessmentBudgetStop, core.PhaseBudgetStop, core.CheckpointStop) as exc:
        failure = type(exc).__name__
    row = {"prompt_id": task["id"], "pair": pair, "targets": targets,
        "selected_checkpoint": adaptive.get("selected_checkpoint"),
        "stage_dispositions": adaptive.get("stage_dispositions", []),
        "native_micro_usd": generation["native_micro_usd"], "fixed_micro_usd": generation["fixed_micro_usd"],
        "failure": failure}
    book.close(ledger, row)
    return row


def _qualification(rows: list[dict]) -> dict:
    complete = len(rows) == 2 and all(row["status"] == "complete" for row in rows)
    per_pair = [0.8 <= row["spent_micro_usd"] / row["target_micro_usd"] <= 1.2 for row in rows]
    ratio = sum(row["spent_micro_usd"] for row in rows) / sum(row["target_micro_usd"] for row in rows) if rows else None
    compact = [{key: row[key] for key in ("status", "spent_micro_usd", "target_micro_usd")}
               | {"result_sha256": digest(row), "pool_count": len(row.get("pools", [])),
                  "selected_run_id": row.get("selected_run_id")} for row in rows]
    return seal({"kind": "phase4-cm1-cost-qualification-v1", "results": compact,
        "passed": complete and all(per_pair) and ratio is not None and 0.9 <= ratio <= 1.1,
        "aggregate_ratio": ratio, "individual_matches": per_pair, "benchmark_calls": 0})


def _snapshot(book: Coordinator, label: str, status: str) -> None:
    """A display failure is recorded without changing authoritative study outputs."""
    try:
        from .snapshot import build_snapshot

        payload = build_snapshot(book.study, book.run, fixture=book.transport.fixture, status=status)
        write_once(book.run / "snapshots" / label / "snapshot.json", payload)
    except Exception as exc:
        book.progress("snapshot-unavailable", checkpoint=label, error_type=type(exc).__name__)


def run(study_path: Path, grant_path: Path, *, stage: str, transport) -> dict:
    study = load_study(study_path)
    release.grant_for(study_path, grant_path, transport.fixture)
    require(stage == "all", "P4 is one complete bounded block")
    if not transport.fixture:
        offline_readiness(study_path, {key: study[key] for key in release.READINESS_BINDINGS})
        _manifest(study_path, study)
    run_path, _ = paths(study, transport.fixture)
    book = Coordinator(study, run_path, transport)
    status, error = "incomplete", None
    with core.writer_lock(run_path / "controller-owner"):
        require(not (run_path / "started.json").exists(), "P4 execution already started; no automatic repetition")
        if not transport.fixture:
            write_bytes_once(run_path / "confirmation-manifest.json",
                             (study_path.parent / "confirmation-manifest.json").read_bytes())
        core._publish(run_path / "started.json", {"study_sha256": study["study_sha256"], "started_at": _now(),
            "confirmation_manifest_sha256": None if transport.fixture else
                file_hash(study_path.parent / "confirmation-manifest.json")})
        try:
            qualifications = []
            for entry in study["development"]:
                pair, task = entry["pilot_id"], entry["task"]
                ledger, profile, _ = book.open("dev", pair, task)
                result = _fixed(book, ledger, profile, pair, task, entry["target_micro_usd"], study_path.parent / "seed")
                book.close(ledger, result)
                qualifications.append(result)
                if result["status"] != "complete":
                    break
            qualification = _qualification(qualifications)
            core._publish(run_path / "qualification.json", qualification)
            book.qualification = qualification["passed"]
            if not book.qualification:
                status = "qualification-change-required"
            else:
                book._source_guard()
                if not transport.fixture:
                    offline_readiness(study_path, {key: study[key] for key in release.READINESS_BINDINGS})
                generations = []
                for index, task in enumerate(_tasks(study_path, study, fixture=transport.fixture), 1):
                    row = _generation(book, f"p4-{index:02d}", task, study_path.parent / "seed")
                    generations.append(row)
                    if index == 1:
                        # No benchmark result exists at this review; source and usage remain authoritative.
                        require(release.source_identity() == study["source"], "source changed at first-pair review")
                        core._publish(run_path / "first-pair-review.json", seal({"kind": "phase4-cm1-first-pair-review-v1",
                            "passed": True, "generation_sha256": digest(row), "grading_calls": 0,
                            "engineering_only": True, "spent_micro_usd": sum(book.spent.values())}))
                        _snapshot(book, "first-pair", "running")
                book.generation_seal = seal({"kind": "phase4-cm1-all-generation-closed-v1",
                    "study_sha256": study["study_sha256"], "count": len(generations),
                    "generation_sha256": [digest(row) for row in generations]})
                core._publish(run_path / "generation-seal.json", book.generation_seal)
                rows = [_assessment(book, row) for row in generations]
                analysis = assessment.analyze_pairs(rows)
                core._publish(run_path / "analysis.json", analysis)
                status = ("mock-complete" if transport.fixture else "complete") if analysis.get("scientific_complete") else "incomplete"
        except Exception as exc:
            error = type(exc).__name__
            status = "paused-integrity-or-liability"
        accounted = book.accounting_view()
        outcome = seal({"kind": "phase4-cm1-outcome-v1", "study_sha256": study["study_sha256"],
            "fixture": transport.fixture, "status": status, "error_type": error,
            "closed_children": book.closed, "active_child": book.active[2] if book.active else None,
            **accounted,
            "provider_calls": 0 if transport.fixture else accounted["attempts"], "historical_held_micro_usd": 22_880_000,
            "closed_at": _now(), "automatic_repeat": False})
        core._publish(run_path / "outcome.json", outcome)
        _snapshot(book, "closure", status)
        return outcome


def _report_read(value: Path, observed: dict) -> dict:
    """Only named P4 saved artifacts may use the larger, bounded delivery envelope."""
    value = release.path(value)
    limit = policy.artifact_limits()["saved_artifact_bytes"]
    require(value.stat().st_size <= limit, "P4 saved artifact exceeds delivery byte capacity")
    raw = value.read_bytes()
    require(len(raw) <= limit, "P4 saved artifact exceeds delivery byte capacity")
    observed[value] = hashlib.sha256(raw).hexdigest()
    try:
        result = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        raise ContractError("P4 saved artifact is not valid JSON") from None
    require(isinstance(result, dict), "P4 saved artifact must be an object")
    return result


def _report_task(study_path, study, pair, task, fixture, manifest):
    development = {row["pilot_id"]: row["task"] for row in study["development"]}
    if pair in development:
        expected = development[pair]
    elif fixture:
        expected = _tasks(study_path, study, fixture=True)[int(pair[3:]) - 1]
    else:
        entry = manifest["selected"][int(pair[3:]) - 1]
        require(digest(task["prompt"]) == entry["prompt_sha256"], "saved confirmation task hash differs")
        expected = {"id": entry["source_task_id"], "prompt": task["prompt"], "domain": "nb-wildchat-confirmation",
            "source_context": {"dataset": "noveltybench/wildchat-1k",
                "revision": "64a23be6b18ec1dacc298830aab276061b6e143c",
                "source_sha256": study["confirmation_source_sha256"], "source_task_id": entry["source_task_id"]}}
    require(task == expected, "saved child task differs from the frozen prompt unit")


def _report_dispatch(state: dict):
    def replay(slot, role, request, **kwargs):
        require(slot in state["results"] and slot in state["intents"], "saved replay lacks its original request")
        intent, result = state["intents"][slot], state["results"][slot]
        require(intent["role"] == result["role"] == role and intent["request"] == request
            and result["request_sha256"] == digest(request), "saved replay request/role differs")
        return result
    return replay


def _report_fixed(study, pair, task, child, profile, state, value, target, seed):
    require(isinstance(value, dict) and value.get("kind") == "phase4-cm1-hierarchical-fixed-v1"
        and value.get("study_sha256") == child and value.get("task_id") == task["id"]
        and value.get("run_id") == _ids(study, pair)[0] and value.get("fixture") is state["fixture"]
        and value.get("request_policy_sha256") == digest(profile)
        and value.get("target_micro_usd") == target
        and value.get("spent_micro_usd") == state["cells"][pair + ":fixed"]["spent_micro_usd"],
        "fixed hierarchy identity, matching target or spending differs")
    if value.get("status") == "complete":
        rebuilt = control.run_fixed(task, seed, study_sha256=child, run_id=_ids(study, pair)[0],
            target_micro_usd=target, dispatch=_report_dispatch(state),
            spent=lambda: state["cells"][pair + ":fixed"]["spent_micro_usd"],
            fixture=state["fixture"], request_policy=profile)
        require(rebuilt == value, "saved fixed hierarchy does not replay exactly")
    else:
        require(value.get("portfolio") is None, "incomplete fixed hierarchy has an eligible final portfolio")


def _report_generation(study, pair, task, child, profile, state, value, seed):
    require(value.get("kind") == "phase4-cm1-generation-v1" and value.get("task") == task
        and value.get("pair") == pair and value.get("generation_study_sha256") == child
        and value.get("native_micro_usd") == state["cells"][pair + ":adaptive"]["spent_micro_usd"]
        and value.get("fixed_micro_usd") == state["cells"][pair + ":fixed"]["spent_micro_usd"],
        "generation identity or arm costs differ")
    adaptive, fixed = value.get("adaptive"), value.get("fixed")
    if adaptive is not None:
        search = NATIVE / child / ("mock" if state["fixture"] else "live") / pair / "adaptive/search"
        if adaptive.get("kind") == "phase4-cm1-partial-native-v1":
            require(fixed is None and value["fixed_micro_usd"] == 0
                and adaptive.get("selected_checkpoint") is None and adaptive.get("portfolio") is None
                and adaptive.get("authentic") is False
                and not any(intent.get("cell") == pair + ":fixed" for intent in state.get("intents", {}).values()),
                "partial native evidence cannot supply a selection or fixed matching budget")
            require(adaptive == _retained_native(task, seed, child_sha=child, search=search,
                tag=_ids(study, pair)[1], fixture=state["fixture"], profile=profile, state=state),
                "partial native checkpoints do not replay exactly")
        else:
            native.validate_adaptation(adaptive, task, seed, study_sha256=child, run_root=search,
                tag=_ids(study, pair)[1], fixture=state["fixture"], results=state["results"], request_policy=profile)
    if fixed is not None:
        require(adaptive is not None and adaptive.get("status") == "complete"
            and (state["fixture"] or adaptive.get("authentic") is True),
            "fixed matching target lacks completed authentic native inference")
        _report_fixed(study, pair, task, child, profile, state, fixed,
                      value["native_micro_usd"], seed)


def _report_assessment(study, pair, task, state, value, generation):
    require(value.get("prompt_id") == task["id"] and value.get("pair") == pair
        and value.get("native_micro_usd") == generation["native_micro_usd"]
        and value.get("fixed_micro_usd") == generation["fixed_micro_usd"], "assessment prompt/cost scope differs")
    adaptive, fixed = generation.get("adaptive") or {}, generation.get("fixed") or {}
    require(value.get("selected_checkpoint") == adaptive.get("selected_checkpoint")
        and value.get("stage_dispositions") == adaptive.get("stage_dispositions", []),
        "assessment changed the blind native choice or edit history")
    portfolios = {"fixed": fixed.get("portfolio"),
                  **{key: adaptive.get("checkpoints", {}).get(key) for key in ("c1", "c2")}}
    require(isinstance(value.get("targets"), dict) and set(value["targets"]) == set(assessment.TARGETS),
            "assessment target inventory differs")
    evaluator = native.Phase3NativeAssessment(ROOT / ".upstream/novelty-bench")
    used = set()
    for target, bundle in value["targets"].items():
        if bundle is None:
            continue  # Missing targets stay missing; no replacement judgments or invented scores.
        portfolio = portfolios[target]
        identity = _ids(study, pair)[2][target]
        require(portfolio is not None and bundle.get("assessment_id") == identity,
                "saved assessment lacks its eligible original portfolio")
        for record in bundle["requests"]:
            slot = record["slot_id"]
            require(record == state["results"].get(slot), "saved judgment differs from its journal result")
            used.add(slot)
        rebuilt = assessment.assess_target(evaluator, portfolio, identity, _report_dispatch(state),
                                          official=bundle["official"])
        require(rebuilt == bundle, "saved primary/supplemental assessment does not replay exactly")
    if value.get("failure") is None:
        require(used == set(state["results"]), "assessment journal has unreachable judgment results")


def report(study_path: Path, grant_path: Path) -> dict:
    """Reconstruct saved accounting and results without opening the corpus or dispatching."""
    from followups.phase3b_seq2_v1.core_view import _blocked

    study = load_study(study_path)
    proposed = read_json(grant_path)
    release.grant_for(study_path, grant_path, proposed["fixture"])
    fixture = proposed["fixture"]
    run_path, _ = paths(study, fixture)
    observed: dict = {}
    with _blocked(), strategy.validation_scope(readonly=True):
        outcome = checked(_report_read(run_path / "outcome.json", observed))
        require(outcome.get("kind") == "phase4-cm1-outcome-v1"
            and outcome.get("study_sha256") == study["study_sha256"] and outcome.get("fixture") is fixture
            and outcome.get("automatic_repeat") is False, "saved outcome belongs to another parent/mode")
        started = _report_read(run_path / "started.json", observed)
        require(started.get("study_sha256") == study["study_sha256"], "saved start has another parent")
        manifest = None
        if not fixture:
            source = study_path.parent / "confirmation-manifest.json"
            require(started.get("confirmation_manifest_sha256") == file_hash(source), "selected manifest changed after startup")
            _report_read(source, observed)
            manifest = _manifest(study_path, study, verify_derivation=False)
        else:
            require(started.get("confirmation_manifest_sha256") is None, "fixture imported a live frame")
        expected_order = [("dev", row["pilot_id"]) for row in study["development"]]
        expected_order += [(kind, f"p4-{index:02d}") for kind in ("inference", "assessment") for index in range(1, 25)]
        closed = outcome.get("closed_children")
        require(isinstance(closed, list) and len(closed) <= len(expected_order), "invalid closed child inventory")
        closed = cast(list[dict], closed)
        spent, held = dict.fromkeys(policy.ALLOCATIONS, 0), dict.fromkeys(policy.ALLOCATIONS, 0)
        attempts = 0
        closures: list[dict] = []
        generations: dict[str, dict] = {}
        assessment_rows: list[dict] = []
        dev_results: list[dict] = []
        active_accounting = None
        entries = [(row, False) for row in closed]
        if outcome.get("active_child") is not None:
            require(len(closed) < len(expected_order), "extra active child after the finite study")
            kind, pair = expected_order[len(closed)]
            entries.append(({"kind": kind, "pair": pair, "path": str(run_path / "children" /
                f"{len(closed) + 1:03d}-{kind}-{pair}")}, True))
        for ordinal, (entry, active) in enumerate(entries, 1):
            require(sum(held.values()) == 0 and (entry["kind"], entry["pair"]) == expected_order[ordinal - 1],
                    "children are repeated/reordered or follow unresolved liability")
            kind, pair = entry["kind"], entry["pair"]
            folder = run_path / "children" / f"{ordinal:03d}-{kind}-{pair}"
            require(release.path(Path(entry["path"])) == folder, "child path escaped its exact parent ordinal")
            opened = checked(_report_read(folder / "open.json", observed))
            task, profile = opened["task"], opened["profile"]
            _report_task(study_path, study, pair, task, fixture, manifest)
            allocation = seal({"kind": "phase4-cm1-child-allocation-v1", "parent_sha256": study["study_sha256"],
                "ordinal": ordinal, "child_kind": kind, "pair": pair, "task_sha256": digest(task),
                "remaining_total_micro_usd": 1_200_000_000 - sum(spent.values()),
                "remaining_allocation_micro_usd": policy.ALLOCATIONS[kind] - spent[kind],
                "prior_closures": closures})
            require(opened["allocation"] == allocation, "child allocation does not follow settled parent accounting")
            expected_profile = policy.make(kind, pair, slots=worklist(study, kind, pair, task),
                parent_sha256=study["study_sha256"], authorization_sha256=study["authorization_sha256"],
                allocation_sha256=digest(allocation), remaining_total_micro_usd=allocation["remaining_total_micro_usd"],
                remaining_allocation_micro_usd=allocation["remaining_allocation_micro_usd"],
                generation_study_sha256=opened.get("generation_study_sha256"))
            child = digest({"parent": study["study_sha256"], "allocation": allocation,
                            "profile": expected_profile, "task_sha256": digest(task)})
            require(profile == expected_profile and opened.get("kind") == "phase4-cm1-child-open-v1"
                and opened["child_sha256"] == child and opened["slots"] == worklist(study, kind, pair, task),
                "child profile/worklist/execution identity differs")
            if kind == "assessment":
                require(pair in generations and profile["phase4_child"]["generation_study_sha256"]
                    == generations[pair]["generation_study_sha256"], "assessment imported another generation child")
            bindings = {"source_sha256": study["source_sha256"], "policy_sha256": digest(profile),
                        "launcher_sha256": study["launcher_sha256"]}
            authority = {"study_sha256": child, "authorization_id": "P4-CM1/" + study["study_sha256"],
                "authorized": not fixture, "expansion_authorized": False,
                "cap_micro_usd": profile["phase_micro_usd"], "canary_cap_micro_usd": profile["first_micro_usd"],
                "control_policy_sha256": core.am1.CONTROL_SHA256, "billing_profile": core.am1.BILLING_PROFILE}
            require(opened["bindings"] == bindings and opened["authority"] == authority,
                    "child source/authority differs from the accepted parent")
            journal = accounting.canonical_journal(child, fixture)
            for name in ("manifest.json", "events.jsonl", "deadline-stop.json", "transport-audit-failure.json"):
                item = journal / name
                observed[item] = file_hash(item) if item.exists() else None
            try:
                state = accounting.replay(journal)
                ledger_manifest = accounting._manifest(journal)
                require(ledger_manifest["inputs"] == {"study_sha256": child, "slots": opened["slots"],
                    "authority": authority, "fixture": fixture, "bindings": bindings, "policy": profile,
                    "editor_tools": study["editor_tools"]}, "child journal is not the declared execution")
            except (ContractError, OSError, ValueError, TypeError, KeyError):
                require(active, "closed child journal cannot be verified")
                held[kind] += profile["phase_micro_usd"]
                active_accounting = {"known": False, "conservative_held_micro_usd": profile["phase_micro_usd"]}
                require(outcome["active_child"] == child, "unknown active child identity differs")
                continue
            spent[kind] += state["spent_micro_usd"]
            held[kind] += state["reserved_micro_usd"]
            attempts += state["attempts"]
            if active:
                require(outcome["active_child"] == child, "active child identity differs")
                active_accounting = {"spent_micro_usd": state["spent_micro_usd"],
                    "reserved_micro_usd": state["reserved_micro_usd"], "attempts": state["attempts"],
                    "accounting_status": state["status"], "known": True}
                continue
            closure = checked(_report_read(folder / "closure.json", observed))
            value = _report_read(folder / "result.json", observed)
            require(closure.get("kind") == "phase4-cm1-child-close-v1"
                and closure["parent_sha256"] == study["study_sha256"] and closure["child_sha256"] == child
                and closure["child_kind"] == kind and closure["pair"] == pair and closure["open_sha256"] == opened["sha256"]
                and closure["journal"] == str(journal) and closure["sha256"] == entry["sha256"]
                and closure["result_sha256"] == digest(value) and closure["status"] == state["status"]
                and closure["transport_audit_summary"] == state["transport_audit_summary"]
                and all(closure[key] == state[key] for key in ("spent_micro_usd", "reserved_micro_usd", "attempts")),
                "closed child artifacts/accounting differ")
            closures.append(closure["sha256"])
            if kind == "dev":
                target = next(row["target_micro_usd"] for row in study["development"] if row["pilot_id"] == pair)
                _report_fixed(study, pair, task, child, profile, state, value, target, study_path.parent / "seed")
                dev_results.append(value)
            elif kind == "inference":
                _report_generation(study, pair, task, child, profile, state, value, study_path.parent / "seed")
                generations[pair] = value
            else:
                _report_assessment(study, pair, task, state, value, generations[pair])
                assessment_rows.append(value)
        expected_accounting = {"spent_micro_usd": sum(spent.values()), "reserved_micro_usd": sum(held.values()),
            "attempts": attempts, "spent_by_allocation_micro_usd": spent, "reserved_by_allocation_micro_usd": held,
            "active_child_accounting": active_accounting}
        require(all(outcome.get(key) == value for key, value in expected_accounting.items())
            and outcome.get("provider_calls") == (0 if fixture else attempts)
            and outcome.get("historical_held_micro_usd") == 22_880_000
            and sum(spent.values()) + sum(held.values()) <= 1_200_000_000 and attempts <= 40914
            and all(spent[key] + held[key] <= policy.ALLOCATIONS[key] for key in spent),
            "saved parent totals omit/duplicate child cost, attempts or held liability")
        qualification_path = run_path / "qualification.json"
        if qualification_path.exists():
            qualification = checked(_report_read(qualification_path, observed))
            require(qualification == _qualification(dev_results), "saved cost qualification changed")
        else:
            qualification = None
        if generations:
            require(qualification is not None and qualification["passed"] is True,
                    "confirmation generation preceded successful cost qualification")
        generation_seal = run_path / "generation-seal.json"
        if assessment_rows or any(entry[0]["kind"] == "assessment" for entry in entries):
            require(len(generations) == 24 and checked(_report_read(generation_seal, observed)) == seal({
                "kind": "phase4-cm1-all-generation-closed-v1", "study_sha256": study["study_sha256"], "count": 24,
                "generation_sha256": [digest(value) for value in generations.values()]}),
                "judging preceded the complete sealed generation inventory")
        analysis_path = run_path / "analysis.json"
        analysis = assessment.analyze_pairs(assessment_rows)
        if analysis_path.exists():
            require(_report_read(analysis_path, observed) == analysis, "saved metrics do not reconstruct from judgments")
        if outcome.get("status") in {"complete", "mock-complete"}:
            require(analysis_path.exists() and analysis["scientific_complete"] is True
                and outcome["status"] == ("mock-complete" if fixture else "complete")
                and outcome.get("active_child") is None, "completion exceeds verified scientific coverage")
        require(release.source_identity() == study["source"], "source changed during saved replay")
        require(all((file_hash(item) if item.exists() else None) == expected for item, expected in observed.items()),
                "saved report replay changed its journals or source artifacts")
    return outcome


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("prepare")
    create.add_argument("--output", required=True, type=Path)
    for command in ("grant", "intake", "report", "snapshot"):
        part = commands.add_parser(command)
        part.add_argument("--study", required=True, type=Path)
        if command == "grant":
            part.add_argument("--fixture", action="store_true")
            part.add_argument("--output", required=True, type=Path)
        elif command in {"report", "snapshot"}:
            part.add_argument("--grant", required=True, type=Path)
            if command == "snapshot":
                part.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        value = prepare(args.output)
    elif args.command == "grant":
        value = make_grant(args.study, args.fixture)
        write_once(release.path(args.output), value)
    elif args.command == "intake":
        value = intake(args.study)
    elif args.command == "snapshot":
        from .snapshot import publish_snapshot

        study = load_study(args.study)
        proposed = read_json(release.path(args.grant))
        grant = release.grant_for(args.study, args.grant, proposed["fixture"])
        run_path, _ = paths(study, grant["fixture"])
        outcome = read_json(run_path / "outcome.json")
        value = publish_snapshot(study, run_path, args.output, fixture=grant["fixture"], status=outcome["status"])
    else:
        value = report(args.study, args.grant)
    print(json.dumps(value, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
