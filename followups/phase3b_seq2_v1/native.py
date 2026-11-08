"""HI channel-profile entrypoint; execute the actual pinned Harness2 scheduler."""
from __future__ import annotations

import copy
import json
import os
import re
import stat
from pathlib import Path
from typing import Any

from buddha2 import phase2_contracts as portfolio_contract
from buddha2.artifacts import (
    ContractError,
    digest,
    file_hash,
    write_bytes_once,
    write_once,
)
from followups.phase3a_v1 import native as frozen

from . import contract, editor, ledger_core, strategy
from .deadline import NATIVE_TIMEOUT
from .support import PRIVATE, ROOT, safe
from .support import read as read_json

Phase3NativeAssessment = frozen.Phase3NativeAssessment
_modules = frozen._modules
BENCHMARK, SUBSTRATE = "noveltybench-phase3b", frozen.SUBSTRATE
LABELS = ("base1", "base2", "inv1", "dom1", "c1", "inv2", "dom2", "c2")
STAGES = ("inv1", "dom1", "c1", "inv2", "dom2", "c2")


def read_artifact(path: Path, *, request_policy: dict | None = None) -> dict:
    """Keep legacy reads unchanged; a P4 grant binds its larger saved-artifact envelope."""
    if request_policy is None:
        return read_json(path)
    from followups.phase4_cm1_v1.policy import context_limits

    limits = context_limits(request_policy)
    limit = limits["rollout_bytes" if Path(path).name in {"rollout.json", "failure.json"} else "saved_artifact_bytes"]
    return read_json(path, max_bytes=limit)


def validate_evaluator_capacity(task: dict) -> dict[str, int]:
    """Exercise current producer maxima through real builders, without dispatch."""
    task = copy.deepcopy(task)
    # This valid character takes six bytes in canonical JSON: the worst UTF-8 expansion.
    task["prompt"] = "\x01" * portfolio_contract.MAX_PROMPT_CHARS
    slots = [f"capacity-answer-{i}" for i in range(10)]
    portfolio = portfolio_contract.make_portfolio(task, [
        {"id": f"capacity-{i}", "text": "\x01" * portfolio_contract.MAX_RESPONSE_CHARS,
         "status": "ok", "request_id": slot} for i, slot in enumerate(slots)
    ], method="A", repeat=1, model={"requested": "fixture-no-model", "returned": "fixture-no-model"},
        settings_sha256="0" * 64, procedure_sha256="0" * 64,
        request_ids=slots, study_sha256="0" * 64, fixture=True)
    evaluator = Phase3NativeAssessment(ROOT / ".upstream/novelty-bench")
    requests = {"group": [evaluator.group_request(portfolio)],
                "quality": evaluator.quality_requests(portfolio, list(range(len(slots))))}
    sizes = {}
    for role, bodies in requests.items():
        for body in bodies:
            ledger_core.validate_request(role, body)
        sizes[role] = max(len(ledger_core._wire(body)) for body in bodies)
    return sizes


class RequiredCheckpointStop(ContractError):
    """Known missing mandatory checkpoint; not a transport or integrity failure."""


@strategy.scoped
def adaptive_run_ids(task_id: str, tag: str) -> dict[str, str]:
    modules = _modules()
    base = modules["schedule"].Namespace(BENCHMARK, SUBSTRATE, "agg", 2, None, tag)
    seq = modules["schedule"].Namespace(BENCHMARK, SUBSTRATE, "seq", 2, None, tag)
    return {label: (base if label.startswith("base") else seq).run_id(task_id, label) for label in LABELS}


class PortfolioSubstrate(frozen.PortfolioSubstrate):
    def surface(self):
        with strategy.validation_scope():
            return strategy._public_surface()


class PortfolioAdapter(frozen.PortfolioAdapter):
    def __init__(self, task: dict, harness_dir: Path, *, study_sha256: str, run_root: Path,
                 tag: str, dispatch: strategy.Dispatch, fixture: bool, channel: Any,
                 known_results: dict | None = None, halt: Any = None,
                 on_required_failure: Any = None, request_policy: dict | None = None):
        strategy._task(task)
        strategy._require(on_required_failure is None or callable(on_required_failure),
            "required-checkpoint observer must be callable")
        strategy._require(fixture or callable(on_required_failure),
            "live native execution requires its mandatory-coverage observer")
        with strategy.validation_scope():
            strategy.precheck_harness(harness_dir)
            for label in LABELS:
                strategy.precheck_harness(run_root / "rollouts" / label / "harness")
        self.task, self.harness_dir = copy.deepcopy(task), strategy._path(harness_dir)
        self.study_sha256, self.run_root, self.tag = study_sha256, strategy._path(run_root, existing=False), tag
        self.dispatch, self.fixture, self.halt = dispatch, fixture, halt
        self.request_policy = request_policy
        self.on_required_failure = on_required_failure
        self.required_failure: dict | None = None
        self.known_results = copy.deepcopy(known_results or {})
        self.ids = adaptive_run_ids(task["id"], tag)
        self.substrate = PortfolioSubstrate()
        modules = _modules()
        self.spec = modules["spec"].BenchSpec(name=BENCHMARK, runs_root=self.run_root / "native",
            install_mode="workspace_config", prompts=contract.benchmark_prompts(),
            channels={"proposer": channel, "selector": channel}, allow_subagents=False,
            leak_globs=("assessment*.json", "scores.json", "partitions.json", "decision.json", "analysis.json"),
            proposer_deliverables="contents", state_deliverable=False, obs_trunc=50_000)
        identity = {"kind": "phase3b-native-input-v1", "task": task, "study_sha256": study_sha256,
            "fixture": fixture, "tag": tag, "run_ids": self.ids,
            "seed": strategy.validate_harness(self.harness_dir),
            "native_sources": {name: file_hash(Path(module.__file__))
                               for name, module in modules.items() if name != "surface"}}
        write_once(self.run_root / "identity.json", identity)
        self._validate_existing(known_results)

    def _read(self, path: Path) -> dict:
        return read_artifact(path, request_policy=self.request_policy)

    def delivered(self, run_dir: Path) -> bool:
        if self.request_policy is None:
            return super().delivered(run_dir)
        try:
            record = self._read(Path(run_dir) / "rollout.json")
            portfolio_contract.validate_portfolio(record["portfolio"])
            return record["status"] == "complete"
        except (ContractError, KeyError, OSError):
            return False

    def deliverable_text(self, run_dir: Path) -> str:
        if self.request_policy is None:
            return super().deliverable_text(run_dir)
        record = self._read(Path(run_dir) / "rollout.json")
        portfolio_contract.validate_portfolio(record["portfolio"])
        return json.dumps([row["text"] for row in record["portfolio"]["responses"]], ensure_ascii=False)

    def deliverable_files(self, run_dir: Path) -> dict[str, str]:
        return {"answers.json": self.deliverable_text(run_dir)}

    def _validate_existing(self, known_results: dict | None) -> None:
        from .accounting import LiabilityStop

        root = self.run_root / "rollouts"
        strategy._require(known_results is not None or not root.exists() or not any(root.iterdir()),
                          "resume requires authoritative journal results")
        checked = validate_adaptive_partial(self.task, self.harness_dir, study_sha256=self.study_sha256,
            run_root=self.run_root, tag=self.tag, fixture=self.fixture, results=self.known_results,
            request_policy=self.request_policy)
        if any(row["status"] == "unresolved" for row in checked.values()):
            raise LiabilityStop("unresolved native request blocks further execution")
        for label in ("c1", "c2"):
            halt_path = root / label / "halt.json"
            budget_stopped = halt_path.exists() and self._read(halt_path).get("category") == "known_checkpoint_budget"
            if checked[label]["status"] == "failed" or budget_stopped:
                self._required_failure(label, "saved_known_failure" if not budget_stopped else "saved_known_budget_stop")
                raise RequiredCheckpointStop("saved mandatory checkpoint cannot produce complete coverage")

    def _required_failure(self, label: str, category: str) -> None:
        """Latch once before upstream can swallow a required-rollout exception."""
        if label not in {"c1", "c2"} or self.required_failure is not None:
            return
        self.required_failure = {"checkpoint": label, "category": category, "run_id": self.ids[label]}
        if self.on_required_failure is not None:
            self.on_required_failure(copy.deepcopy(self.required_failure))


    def _execute(self, task_id: str, harness_dir: Path | None, run_id: str,
                *, timeout: int | None = None) -> Path:
        self._task_id(task_id)
        strategy._integrity(run_id in self.ids.values(), "undeclared native rollout identity")
        label = next(key for key, value in self.ids.items() if value == run_id)
        source = strategy._path(harness_dir or self.harness_dir)
        checked = strategy.validate_harness(source)
        path = self.run_root / "rollouts" / label
        for relative in checked["raw_files_sha256"]:
            write_bytes_once(path / "harness" / relative, (source / relative).read_bytes())
        strategy.validate_harness(path / "harness")
        if (path / "rollout.json").exists():
            saved = strategy.validate_rollout(self._read(path / "rollout.json"), self.task, path / "harness",
                study_sha256=self.study_sha256, fixture=self.fixture, run_id=run_id,
                arm="adaptive", results=self.known_results, request_policy=self.request_policy)
            if label in {"c1", "c2"} and (saved.get("status") != "complete" or saved.get("portfolio") is None):
                self._required_failure(label, "saved_missing_portfolio")
                raise RequiredCheckpointStop("saved mandatory checkpoint lacks its required portfolio")
            return path

        def dispatch(slot: str, role: str, request: dict) -> dict:
            if self.required_failure is not None:
                raise RequiredCheckpointStop("known mandatory checkpoint failure forbids further solver admission")
            result = self.dispatch(slot, role, request)
            self.known_results[slot] = copy.deepcopy(result)
            return result

        try:
            record = strategy.execute_cn(self.task, path / "harness", study_sha256=self.study_sha256,
                run_id=run_id, dispatch=dispatch, fixture=self.fixture, arm="adaptive",
                request_policy=self.request_policy)
        except editor.KnownProviderTerminalStop:
            raise
        except strategy.KnownOutcomeError as exc:
            try:
                self._required_failure(label, "known_solver_failure")
            finally:
                write_once(path / "failure.json", exc.evidence)
            raise
        except ContractError as exc:
            from .accounting import CellBudgetStop, CheckpointStop, PhaseBudgetStop
            budget_stop = isinstance(exc, (CellBudgetStop, CheckpointStop, PhaseBudgetStop))
            try:
                if budget_stop:
                    self._required_failure(label, "known_budget_stop")
            finally:
                write_once(path / "halt.json", {"kind": "phase3a-execution-halt-v1",
                    "study_sha256": self.study_sha256, "run_id": run_id, "reason": str(exc),
                    **({"category": "known_checkpoint_budget"} if budget_stop and label in {"c1", "c2"} else {})})
            raise
        write_once(path / "rollout.json", record)
        return path

    @strategy.scoped
    def execute(self, *args, **kwargs):
        harness = args[1] if len(args) > 1 else kwargs.get("harness_dir")
        strategy.precheck_harness(harness or self.harness_dir)
        for label in LABELS:
            strategy.precheck_harness(self.run_root / "rollouts" / label / "harness")
        return super().execute(*args, **kwargs)

    @strategy.scoped
    def validate_tree(self, value):
        return super().validate_tree(value)

    def trajectory(self, run_dir: Path, *, obs_trunc: int) -> str:
        path = Path(run_dir)
        if not (path / "rollout.json").exists():
            return "[ERROR] This execution produced no completed portfolio."
        record = self._read(path / "rollout.json")
        blocks = []
        for result in record["requests"]:
            block = "[ACTION] " + result["role"]
            if result["role"] == "rank":
                parent = record["parent_B"]
                current = strategy.validate_harness(path / "harness")["strategy"]
                context = {"study_sha256": record["study_sha256"], "run_id": record["run_id"],
                    "slot_id": result["slot_id"], "arm": record["arm"], "fixture": record["fixture"]}
                prepared = strategy.rank_io.prepare(parent, parent["task"], current, context)
                block += "\n[INPUT] " + prepared["request"]["messages"][0]["content"]
            blocks.append(block + "\n[OBSERVATION] " + result["response"]["text"])
        return "\n\n".join(blocks)


@strategy.scoped
def validate_adaptive_partial(task: dict, harness_dir: Path, *, study_sha256: str,
                              run_root: Path, tag: str, fixture: bool, results: dict,
                              request_policy: dict | None = None) -> dict:
    """Verify all saved native inputs before any other missing arm may make a call."""
    def read(path):
        return read_artifact(path, request_policy=request_policy)

    run_root = strategy._path(run_root, existing=False)
    ids = adaptive_run_ids(task["id"], tag)
    root = run_root / "rollouts"
    if root.exists():
        names = os.listdir(root)
        strategy._require(all(name in LABELS for name in names), "undeclared native rollout directory")
        strategy._require(all(safe(root / name).is_dir() for name in names), "nonordinary native rollout directory")
    identity_path = run_root / "identity.json"
    if identity_path.exists():
        identity = read(identity_path)
        strategy._require(identity.get("task") == task and identity.get("study_sha256") == study_sha256
            and identity.get("fixture") is fixture and identity.get("tag") == tag
            and identity.get("run_ids") == ids and identity.get("seed") == strategy.validate_harness(harness_dir),
            "saved native execution has foreign inputs")
    checked = {}
    for label, run_id in ids.items():
        path = root / label
        slots = strategy.slot_ids(run_id)
        relevant = {slots["plan"], slots["rank"], *slots["answers"]}
        if not path.exists():
            strategy._require(not relevant.intersection(results),
                              "partial journal lacks its exact materialized native harness")
            checked[label] = {"status": "not_started", "validated_slots": []}
            continue
        strategy._require(identity_path.exists(), "saved native rollout lacks its execution identity")
        harness = path / "harness"
        strategy.validate_harness(harness)
        checked[label] = strategy.validate_partial(task, harness, study_sha256=study_sha256,
            run_id=run_id, fixture=fixture, arm="adaptive", results=results,
            request_policy=request_policy)
        for name in ("rollout.json", "failure.json"):
            if (path / name).exists():
                strategy.validate_rollout(read(path / name), task, harness,
                    study_sha256=study_sha256, fixture=fixture, arm="adaptive", run_id=run_id, results=results,
                    request_policy=request_policy)
        if (path / "halt.json").exists():
            halt = read(path / "halt.json")
            strategy._require(halt.get("kind") == "phase3a-execution-halt-v1"
                and halt.get("study_sha256") == study_sha256 and halt.get("run_id") == run_id,
                "saved execution halt has foreign identity")
    return checked


@strategy.scoped
def _stage_proof(native_result: dict, editor: dict, task: dict, run_root: Path,
                 tag: str, fixture: bool, study_sha256: str, results: dict) -> tuple[list, bool]:
    modules = _modules()
    namespace = modules["schedule"].Namespace(BENCHMARK, SUBSTRATE, "seq", 2, None, tag)
    work = namespace.task_dir(run_root / "native", task["id"])
    mode = native_result.get("modes", {}).get("seq", {})
    seed_hash = read_json(run_root / "identity.json")["seed"]["effective_strategy_sha256"]
    dispositions = []
    all_backed = True
    sessions = editor.get("sessions", {}) if isinstance(editor, dict) else {}
    for stage in mode.get("stages", []):
        label = stage.get("label")
        strategy._integrity(label in STAGES, "undeclared native stage")
        harness = strategy.validate_harness(work / "harnesses" / label)
        input_hash = None
        proofs = []
        eligible_proofs = []
        terminal_used = False
        for shape in (1, 2):
            key = f"{label}.a{shape}"
            proof = sessions.get(key)
            if not isinstance(proof, dict):
                continue
            slots = proof.get("result_slots", [])
            if (proof.get("model_backed") is True and proof.get("status") == "valid"
                    and proof.get("harvest_raw_tree_sha256") == harness["raw_tree_sha256"]
                    and proof.get("effective_strategy_sha256") == harness["effective_strategy_sha256"]
                    and type(slots) is list and slots and all(slot in results for slot in slots)):
                from .editor import input_snapshot, session_eligibility

                captured = proof.get("input_snapshot", {})
                started = read_json(run_root / "editor-audit/phase3a-sessions" / (key + ".started.json"))
                strategy._integrity(captured == input_snapshot(captured.get("tree"))
                    and started.get("input_snapshot") == captured, "native session input snapshot differs")
                input_hash = captured["effective_strategy_sha256"]
                if shape == 1:
                    expected_input = (strategy.validate_harness(work / "harnesses/c1")["effective_strategy_sha256"]
                                      if label.endswith("2") else seed_hash)
                    strategy._integrity(input_hash == expected_input,
                                        "native round input did not preserve the current composed harness")
                terminal = proof.get("terminal_note_used")
                changed, eligible_session = session_eligibility(terminal is True, input_hash,
                    harness["effective_strategy_sha256"])
                strategy._integrity(type(terminal) is bool and proof.get("input_effective_strategy_sha256") == input_hash
                    and terminal == any(row.get("role_translation") is not None for row in proof.get("requests", []))
                    and proof.get("effective_changed_from_input") is changed
                    and proof.get("authentic_eligible") is eligible_session,
                    "editor terminal/input classification differs from native context")
                for slot in slots:
                    result = results[slot]
                    wire = result.get("response") or {}
                    metadata = [r for r in proof.get("requests", []) if r.get("slot_id") == slot]
                    strategy._integrity(result.get("role") == "editor" and result.get("status") == "response"
                        and result.get("study_sha256") == study_sha256 and result.get("fixture") is fixture
                        and re.fullmatch(r"claude-opus-5(?:-\d{8})?", wire.get("model", "")) is not None
                        and len(metadata) == 1 and metadata[0].get("result_sha256") == digest(result)
                        and metadata[0].get("effective_sha256") == result.get("request_sha256"),
                        "editor proof is not bound to this journal")
                proofs.append(key)
                terminal_used = terminal_used or terminal is True
                if proof["authentic_eligible"]:
                    eligible_proofs.append(key)
        accepted = not stage.get("fell_back") and bool(proofs)
        eligible = not stage.get("fell_back") and bool(eligible_proofs)
        all_backed = all_backed and eligible
        dispositions.append({**stage, "accepted_editor_sessions": proofs,
                             "authentic_eligible": eligible, "terminal_note_used": terminal_used,
                             "cap_limited_unchanged": accepted and terminal_used and input_hash is not None and not eligible,
                             "terminal_input_unvalidated": accepted and terminal_used and input_hash is None,
                             "input_effective_strategy_sha256": input_hash,
                             "effective_strategy_sha256": harness["effective_strategy_sha256"],
                             "effective_changed": harness["effective_strategy_sha256"] != seed_hash,
                             "raw_tree_sha256": harness["raw_tree_sha256"], "model_backed": accepted})
    authentic = (not fixture and len(dispositions) == 6 and {s["label"] for s in dispositions} == set(STAGES)
        and all_backed and editor.get("fixture") is False and editor.get("study_sha256") == study_sha256
        and editor.get("backend") == "opencode" and editor.get("model") == "claude-opus-5")
    return dispositions, authentic


def _artifacts(root: Path) -> dict[str, str]:
    """Hash public native artifacts; operational private names never reach metadata."""
    root = safe(root)
    files = {}
    pending = [root]
    while pending:
        directory = pending.pop()
        for name in sorted(os.listdir(directory)):
            if name.casefold() in PRIVATE or "stdout" in name.casefold() or "stderr" in name.casefold():
                continue
            target = safe(directory / name)
            info = target.lstat()
            if stat.S_ISDIR(info.st_mode):
                pending.append(target)
            else:
                strategy._require(stat.S_ISREG(info.st_mode), "native artifact is not an ordinary file")
                if target != root / "adaptation.json":
                    files[target.relative_to(root).as_posix()] = file_hash(target)
    return files


def _selector_normal(evidence: dict, selection: dict, results: dict) -> bool:
    session = evidence.get("sessions", {}).get("select.seq2", {})
    slots = session.get("result_slots", [])
    return bool(selection.get("ok") and not selection.get("fallback") and not selection.get("trivial")
        and selection.get("chosen_label") in {"c1", "c2"}
        and session.get("status") == "valid" and session.get("model_backed")
        and session.get("authentic_eligible") is True and not session.get("terminal_note_used")
        and 0 < len(slots) < editor.MAX_STEPS and all(slot in results
            and results[slot].get("role") == "native_selector"
            and results[slot].get("status") == "response" for slot in slots))


def run_adaptation(task: dict, harness_dir: Path, *, study_sha256: str, run_root: Path,
                   tag: str, dispatch: strategy.Dispatch, fixture: bool, prop: Any,
                   known_results: dict | None = None, result_snapshot: Any = None, halt: Any = None,
                   on_required_failure: Any = None, request_policy: dict | None = None) -> dict:
    with strategy.validation_scope():
        return _run_adaptation(task, harness_dir, study_sha256=study_sha256, run_root=run_root,
            tag=tag, dispatch=dispatch, fixture=fixture, prop=prop, known_results=known_results,
            result_snapshot=result_snapshot, halt=halt, on_required_failure=on_required_failure,
            request_policy=request_policy)

def _run_adaptation(task: dict, harness_dir: Path, *, study_sha256: str, run_root: Path,
                    tag: str, dispatch: strategy.Dispatch, fixture: bool, prop: Any,
                    known_results: dict | None = None, result_snapshot: Any = None, halt: Any = None,
                    on_required_failure: Any = None, request_policy: dict | None = None) -> dict:
    def read(path):
        return read_artifact(path, request_policy=request_policy)

    modules = _modules()
    strategy._integrity(isinstance(prop, modules["proposer"].Proposer), "actual native Proposer required")
    strategy._integrity(fixture or callable(halt), "live native execution requires durable global halt")
    channel = modules["spec"].ChannelSpec("opencode", "anthropic/claude-opus-5", effort="high",
                                         steps=editor.MAX_STEPS, timeout=NATIVE_TIMEOUT)
    strategy._integrity(prop.spec == channel, "native editor profile differs")
    strategy._integrity(prop.attempts == 1, "native selector outer retry is not disabled")
    def cell_dispatch(slot, role, request):
        terminal = getattr(prop, "_known_provider_terminal", None)
        if terminal is not None:
            raise editor.KnownProviderTerminalStop(terminal)
        return dispatch(slot, role, request)

    if request_policy is not None and getattr(prop, "_known_provider_terminal", None) is not None:
        raise editor.KnownProviderTerminalStop(prop._known_provider_terminal)
    run_root = strategy._path(run_root, existing=False)
    if (run_root / "adaptation.json").exists():
        if known_results is None:
            raise ContractError("resume requires authoritative results")
        return validate_adaptation(read(run_root / "adaptation.json"), task, harness_dir,
            study_sha256=study_sha256, run_root=run_root, tag=tag, fixture=fixture, results=known_results,
            request_policy=request_policy)
    adapter = PortfolioAdapter(task, harness_dir, study_sha256=study_sha256, run_root=run_root,
        tag=tag, dispatch=cell_dispatch if request_policy is not None else dispatch,
        fixture=fixture, channel=channel, known_results=known_results, halt=halt,
        on_required_failure=on_required_failure, request_policy=request_policy)
    result = modules["schedule"].run_task(task["id"], 2, adapter=adapter, prop=prop,
        selector_prop=prop, runs_root=adapter.spec.runs_root, modes=("seq",), seed=None,
        tag=tag, library=None, libraries=None, pool_policy="finals")
    if request_policy is not None and getattr(prop, "_known_provider_terminal", None) is not None:
        raise editor.KnownProviderTerminalStop(prop._known_provider_terminal)
    if adapter.required_failure is not None:
        raise RequiredCheckpointStop("known mandatory checkpoint failure stopped further paid coverage")
    native_result = result.to_dict()
    editor_evidence = prop.phase3a_evidence() if hasattr(prop, "phase3a_evidence") else {}
    # The trusted boundary's settled editor results must be included in the authoritative snapshot.
    supplied = result_snapshot() if result_snapshot is not None else {}
    for slot, value in supplied.items():
        strategy._integrity(slot not in adapter.known_results or adapter.known_results[slot] == value,
                          "editor result conflicts with strategy journal")
        adapter.known_results[slot] = value
    dispositions, authentic = _stage_proof(native_result, editor_evidence, task, run_root, tag,
                                          fixture, study_sha256, adapter.known_results)
    selection = native_result.get("selections", {}).get("seq", {})
    strategy._integrity(prop.attempts == 1, "native selector outer retry is not disabled")
    strategy._integrity(not selection.get("ok") or not selection.get("trivial")
        and selection.get("chosen_label") in {"c1", "c2"}, "native seq2 selection changed")
    rollouts = {label: read(run_root / "rollouts" / label / "rollout.json")
                for label in LABELS if (run_root / "rollouts" / label / "rollout.json").exists()}
    # Both checkpoint portfolios are preserved; the selected final is an alias, not another judgment.
    checkpoints = {label: rollouts.get(label, {}).get("portfolio") for label in ("c1", "c2")}
    selected_checkpoint = selection.get("chosen_label") if selection.get("ok") else None
    portfolio = checkpoints.get(selected_checkpoint) if isinstance(selected_checkpoint, str) else None
    record = {"kind": "phase3b-native-adaptation-v1", "fixture": fixture, "arm": "adaptive",
        "study_sha256": study_sha256, "task_id": task["id"], "tag": tag,
        "native": native_result, "rollouts": rollouts, "editor_evidence": editor_evidence,
        "stage_dispositions": dispositions, "authentic": authentic and _selector_normal(editor_evidence, selection, adapter.known_results),
        "checkpoints": checkpoints, "selected_checkpoint": selected_checkpoint,
        "portfolio": portfolio, "status": "complete" if portfolio is not None else "missing",
        "artifact_hashes": _artifacts(run_root),
        "editor_profile_sha256": digest(editor.profile()),
        "editor_boundary_sha256": file_hash(Path(editor.__file__)),
        "native_entrypoint_sha256": file_hash(Path(__file__))}
    write_once(run_root / "adaptation.json", record)
    return record


def validate_adaptation(record: dict, task: dict, harness_dir: Path, *, study_sha256: str,
                        run_root: Path, tag: str, fixture: bool, results: dict,
                        request_policy: dict | None = None) -> dict:
    """Require the HI profile before the unchanged full native/report replay."""
    strategy._require(record.get("editor_profile_sha256") == digest(editor.profile())
        and record.get("editor_boundary_sha256") == file_hash(Path(editor.__file__))
        and record.get("native_entrypoint_sha256") == file_hash(Path(__file__)),
        "native HI editor profile/source differs")
    with strategy.validation_scope():
        return _validate_adaptation(record, task, harness_dir, study_sha256=study_sha256,
            run_root=run_root, tag=tag, fixture=fixture, results=results,
            request_policy=request_policy)


def _validate_adaptation(record: dict, task: dict, harness_dir: Path, *, study_sha256: str,
                        run_root: Path, tag: str, fixture: bool, results: dict,
                        request_policy: dict | None = None) -> dict:
    """Inspect native files and reconstruct saved portfolios without a Proposer or SDK."""
    def read(path):
        return read_artifact(path, request_policy=request_policy)

    run_root = strategy._path(run_root)
    strategy._require(record.get("kind") == "phase3b-native-adaptation-v1"
        and record.get("fixture") is fixture and record.get("study_sha256") == study_sha256
        and record.get("task_id") == task["id"] and record.get("tag") == tag,
        "native branch belongs to a different execution")
    strategy._require(record.get("artifact_hashes") == _artifacts(run_root), "native artifacts changed")
    validate_adaptive_partial(task, harness_dir, study_sha256=study_sha256, run_root=run_root,
                              tag=tag, fixture=fixture, results=results, request_policy=request_policy)
    ids = adaptive_run_ids(task["id"], tag)
    actual_rollouts = {label: read(run_root / "rollouts" / label / "rollout.json")
                       for label in LABELS if (run_root / "rollouts" / label / "rollout.json").exists()}
    strategy._require(record.get("rollouts") == actual_rollouts, "native rollout inventory differs")
    for label, run_id in ids.items():
        path = run_root / "rollouts" / label
        if path.exists():
            strategy.validate_partial(task, path / "harness", study_sha256=study_sha256,
                                      run_id=run_id, fixture=fixture, arm="adaptive", results=results,
                                      request_policy=request_policy)
        if label in record["rollouts"]:
            expected = strategy.validate_rollout(record["rollouts"][label], task, path / "harness",
                study_sha256=study_sha256, fixture=fixture, run_id=run_id, arm="adaptive", results=results,
                request_policy=request_policy)
            strategy._require(expected == read(path / "rollout.json"), "native rollout artifact differs")
    identity = read(run_root / "identity.json")
    strategy._require(identity["task"] == task and identity["seed"] == strategy.validate_harness(harness_dir)
                      and identity["study_sha256"] == study_sha256, "native seed identity differs")
    modules = _modules()
    namespace = modules["schedule"].Namespace(BENCHMARK, SUBSTRATE, "agg", 2, None, tag)
    work = namespace.task_dir(run_root / "native", task["id"])
    strategy._require(read(work / "summary.json") == record["native"], "native summary differs")
    dispositions, authentic = _stage_proof(record["native"], record["editor_evidence"], task,
        run_root, tag, fixture, study_sha256, results)
    strategy._require(record["stage_dispositions"] == dispositions and record["authentic"] is (authentic and _selector_normal(record["editor_evidence"], record["native"].get("selections", {}).get("seq", {}), results)),
                      "native stage/editor authenticity proof differs")
    selection = record["native"].get("selections", {}).get("seq", {})
    checkpoints = {label: record["rollouts"].get(label, {}).get("portfolio") for label in ("c1", "c2")}
    selected = selection.get("chosen_label") if selection.get("ok") else None
    portfolio = checkpoints.get(selected) if isinstance(selected, str) else None
    strategy._require(record.get("checkpoints") == checkpoints and record.get("selected_checkpoint") == selected,
                      "native checkpoint aliases differ from their exact rollouts")
    strategy._require((not selection.get("ok") or not selection.get("trivial")
        and selected in {"c1", "c2"} and not selection.get("fallback")
        and selection.get("chosen_run_id") == ids[selected]
        and selection.get("chosen_run_dir") == str(run_root / "rollouts" / selected))
        and record["portfolio"] == portfolio
        and record["status"] == ("complete" if portfolio is not None else "missing"),
        "native final is not its selected eligible composed checkpoint")
    return record
