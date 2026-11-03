"""Portfolio API substrate for the unchanged native Harness² task driver."""
from __future__ import annotations

import copy
import importlib
import json
import re
import threading
from pathlib import Path
from typing import Any

from buddha2.artifacts import (
    ContractError,
    digest,
    file_hash,
    read_json,
    write_bytes_once,
    write_once,
)
from buddha2.phase2_contracts import validate_portfolio
from buddha2.phase2_native import NativeAssessment

from . import strategy

BENCHMARK = "noveltybench-phase3a"
SUBSTRATE = "portfolio-api"
LABELS = ("base1", "inv1", "dom1", "agg1")
STAGES = ("inv1", "dom1", "agg1")


def _modules() -> dict:
    surface = strategy._surface()
    modules = {name: importlib.import_module("harness2.core." + name)
               for name in ("schedule", "spec", "tree", "runmark", "proposer")}
    for name, module in modules.items():
        expected = strategy.ROOT / ".upstream/harness2/harness2/core" / (name + ".py")
        strategy._integrity(Path(module.__file__ or "").resolve(strict=True) == expected.resolve(strict=True),
                          "native import is outside the pinned source")
    return {**modules, "surface": surface}


def adaptive_run_ids(task_id: str, tag: str) -> dict[str, str]:
    native = _modules()
    namespace = native["schedule"].Namespace(BENCHMARK, SUBSTRATE, "agg", 1, None, tag)
    return {label: namespace.run_id(task_id, label) for label in LABELS}


def _artifacts(root: Path) -> dict[str, str]:
    strategy._require(not any(p.is_symlink() for p in root.rglob("*")), "native artifacts contain a link")
    return {path.relative_to(root).as_posix(): file_hash(path) for path in sorted(root.rglob("*"))
            if path.is_file() and path != root / "adaptation.json" and path.name != ".writer.lock"}


def validate_adaptive_partial(task: dict, harness_dir: Path, *, study_sha256: str,
                              run_root: Path, tag: str, fixture: bool, results: dict) -> dict:
    """Verify all saved native inputs before any other missing arm may make a call."""
    run_root = strategy._path(run_root, existing=False)
    ids = adaptive_run_ids(task["id"], tag)
    root = run_root / "rollouts"
    strategy._require(not root.exists() or all(p.is_dir() and not p.is_symlink() and p.name in LABELS
                                              for p in root.iterdir()), "undeclared native rollout directory")
    identity_path = run_root / "identity.json"
    if identity_path.exists():
        identity = read_json(identity_path)
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
            run_id=run_id, fixture=fixture, arm="adaptive", results=results)
        for name in ("rollout.json", "failure.json"):
            if (path / name).exists():
                strategy.validate_rollout(read_json(path / name), task, harness,
                    study_sha256=study_sha256, fixture=fixture, arm="adaptive", run_id=run_id, results=results)
        if (path / "halt.json").exists():
            halt = read_json(path / "halt.json")
            strategy._require(halt.get("kind") == "phase3a-execution-halt-v1"
                and halt.get("study_sha256") == study_sha256 and halt.get("run_id") == run_id,
                "saved execution halt has foreign identity")
    return checked


class PortfolioSubstrate:
    """The solver is the declared API pipeline; OpenCode is only the authoring channel."""

    name = SUBSTRATE

    def surface(self):
        return strategy._surface()


class PortfolioAdapter:
    def __init__(self, task: dict, harness_dir: Path, *, study_sha256: str, run_root: Path,
                 tag: str, dispatch: strategy.Dispatch, fixture: bool, channel: Any,
                 known_results: dict | None = None, halt: Any = None):
        strategy._task(task)
        self.task, self.harness_dir = copy.deepcopy(task), strategy._path(harness_dir)
        self.study_sha256, self.run_root, self.tag = study_sha256, strategy._path(run_root, existing=False), tag
        self.dispatch, self.fixture = dispatch, fixture
        self.halt = halt
        self.known_results = copy.deepcopy(known_results or {})
        self.ids = adaptive_run_ids(task["id"], tag)
        self.substrate = PortfolioSubstrate()
        native = _modules()
        self.spec = native["spec"].BenchSpec(
            name=BENCHMARK, runs_root=self.run_root / "native", install_mode="workspace_config",
            prompts=native["spec"].BenchPrompts(
                work="Produce ten useful, distinct answers that satisfy the supplied request.",
                inv_levers="Improve general instructions for planning, answering, or ordering the answers.",
                dom_levers="Improve the same instructions for this particular request and its constraints.",
                domain_guidance="This solver is a fixed portfolio API pipeline, not an OpenCode solver. "
                    "Only systemprompt.md is editable: one strict JSON object with exactly answer_system, "
                    "plan_system and rank_system, each a nonempty string. Those decoded strings replace "
                    "only the corresponding API system messages. All other request fields and the call "
                    "topology are fixed. Keep the three empty compatibility files and canonical README "
                    "stubs unchanged. No scripts, plugins, skills or subagents are available."),
            channels={"proposer": channel, "selector": channel}, allow_subagents=False,
            leak_globs=("assessment*.json", "scores.json", "partitions.json", "decision.json", "analysis.json"),
            proposer_deliverables="contents", state_deliverable=False, obs_trunc=50_000)
        identity = {"kind": "phase3a-native-input-v1", "task": task, "study_sha256": study_sha256,
                    "fixture": fixture, "tag": tag, "run_ids": self.ids,
                    "seed": strategy.validate_harness(self.harness_dir),
                    "native_sources": {name: file_hash(Path(module.__file__))
                                       for name, module in native.items() if name != "surface"}}
        write_once(self.run_root / "identity.json", identity)
        self._validate_existing(known_results)

    def _validate_existing(self, known_results: dict | None) -> None:
        from .accounting import LiabilityStop

        root = self.run_root / "rollouts"
        strategy._require(known_results is not None or not root.exists() or not any(root.iterdir()),
                          "resume requires authoritative journal results")
        checked = validate_adaptive_partial(self.task, self.harness_dir, study_sha256=self.study_sha256,
            run_root=self.run_root, tag=self.tag, fixture=self.fixture, results=self.known_results)
        if any(row["status"] == "unresolved" for row in checked.values()):
            raise LiabilityStop("unresolved native request blocks further execution")

    def tasks(self, split: str = "all") -> list[str]:
        return [self.task["id"]]

    def _task_id(self, task_id: str) -> None:
        strategy._require(task_id == self.task["id"], "unknown native task")

    def domain_of(self, task_id: str) -> str:
        self._task_id(task_id)
        return self.task["domain"]

    def task_prompt(self, task_id: str) -> str:
        self._task_id(task_id)
        return self.task["prompt"]

    def task_files(self, task_id: str) -> None:
        self._task_id(task_id)
        return None

    def base_harness(self) -> Path:
        return self.harness_dir

    def validate_tree(self, value: dict) -> None:
        strategy.validate_tree(value)

    def execute(self, task_id: str, harness_dir: Path | None, run_id: str,
                *, timeout: int | None = None) -> Path:
        from .accounting import IntegrityStop, LiabilityStop

        try:
            with strategy.validation_scope():
                return self._execute(task_id, harness_dir, run_id, timeout=timeout)
        except (IntegrityStop, LiabilityStop) as exc:
            if self.halt is not None:
                self.halt("native_execution_" + type(exc).__name__, evidence_sha256=digest({
                    "study_sha256": self.study_sha256, "run_id": run_id, "type": type(exc).__name__}))
            raise

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
            strategy.validate_rollout(read_json(path / "rollout.json"), self.task, path / "harness",
                study_sha256=self.study_sha256, fixture=self.fixture, run_id=run_id,
                arm="adaptive", results=self.known_results)
            return path

        def dispatch(slot: str, role: str, request: dict) -> dict:
            result = self.dispatch(slot, role, request)
            self.known_results[slot] = copy.deepcopy(result)
            return result

        try:
            record = strategy.execute_cn(self.task, path / "harness", study_sha256=self.study_sha256,
                run_id=run_id, dispatch=dispatch, fixture=self.fixture, arm="adaptive")
        except strategy.KnownOutcomeError as exc:
            write_once(path / "failure.json", exc.evidence)
            raise
        except ContractError as exc:
            write_once(path / "halt.json", {"kind": "phase3a-execution-halt-v1",
                "study_sha256": self.study_sha256, "run_id": run_id, "reason": str(exc)})
            raise
        write_once(path / "rollout.json", record)
        return path

    def delivered(self, run_dir: Path) -> bool:
        try:
            record = read_json(Path(run_dir) / "rollout.json")
            validate_portfolio(record["portfolio"])
            return record["status"] == "complete"
        except (ContractError, KeyError, OSError):
            return False

    def trajectory(self, run_dir: Path, *, obs_trunc: int) -> str:
        path = Path(run_dir)
        if not (path / "rollout.json").exists():
            return "[ERROR] This execution produced no completed portfolio."
        record = read_json(path / "rollout.json")
        blocks = []
        # Only model-visible requests/replies enter evidence; no costs, native scores or other arms.
        for result in record["requests"]:
            blocks.append("[ACTION] " + result["role"] + "\n[OBSERVATION] "
                          + result["response"]["text"])
        return "\n\n".join(blocks)

    def deliverable_text(self, run_dir: Path) -> str:
        record = read_json(Path(run_dir) / "rollout.json")
        validate_portfolio(record["portfolio"])
        return json.dumps([r["text"] for r in record["portfolio"]["responses"]], ensure_ascii=False)

    def deliverable_files(self, run_dir: Path) -> dict[str, str]:
        return {"answers.json": self.deliverable_text(run_dir)}

    def score(self, run_dir: Path, task_id: str) -> None:
        raise ContractError("external assessment is unavailable inside native adaptation")


def _stage_proof(native_result: dict, editor: dict, task: dict, run_root: Path,
                 tag: str, fixture: bool, study_sha256: str, results: dict) -> tuple[list, bool]:
    modules = _modules()
    namespace = modules["schedule"].Namespace(BENCHMARK, SUBSTRATE, "agg", 1, None, tag)
    work = namespace.task_dir(run_root / "native", task["id"])
    mode = native_result.get("modes", {}).get("agg", {})
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
    authentic = (not fixture and len(dispositions) == 3 and {s["label"] for s in dispositions} == set(STAGES)
        and all_backed and editor.get("fixture") is False and editor.get("study_sha256") == study_sha256
        and editor.get("backend") == "opencode" and editor.get("model") == "claude-opus-5")
    return dispositions, authentic


def run_adaptation(task: dict, harness_dir: Path, *, study_sha256: str, run_root: Path,
                   tag: str, dispatch: strategy.Dispatch, fixture: bool, prop: Any,
                   known_results: dict | None = None, result_snapshot: Any = None, halt: Any = None) -> dict:
    with strategy.validation_scope():
        return _run_adaptation(task, harness_dir, study_sha256=study_sha256, run_root=run_root,
            tag=tag, dispatch=dispatch, fixture=fixture, prop=prop, known_results=known_results,
            result_snapshot=result_snapshot, halt=halt)


def _run_adaptation(task: dict, harness_dir: Path, *, study_sha256: str, run_root: Path,
                    tag: str, dispatch: strategy.Dispatch, fixture: bool, prop: Any,
                    known_results: dict | None = None, result_snapshot: Any = None, halt: Any = None) -> dict:
    modules = _modules()
    strategy._integrity(isinstance(prop, modules["proposer"].Proposer), "actual native Proposer required")
    strategy._integrity(fixture or callable(halt), "live native execution requires durable global halt")
    channel = modules["spec"].ChannelSpec("opencode", "anthropic/claude-opus-5", effort="high",
                                         steps=8, timeout=600)
    strategy._integrity(prop.spec == channel, "native editor profile differs")
    run_root = strategy._path(run_root, existing=False)
    if (run_root / "adaptation.json").exists():
        if known_results is None:
            raise ContractError("resume requires authoritative results")
        return validate_adaptation(read_json(run_root / "adaptation.json"), task, harness_dir,
            study_sha256=study_sha256, run_root=run_root, tag=tag, fixture=fixture, results=known_results)
    adapter = PortfolioAdapter(task, harness_dir, study_sha256=study_sha256, run_root=run_root,
        tag=tag, dispatch=dispatch, fixture=fixture, channel=channel, known_results=known_results, halt=halt)
    result = modules["schedule"].run_task(task["id"], 1, adapter=adapter, prop=prop,
        selector_prop=prop, runs_root=adapter.spec.runs_root, modes=("agg",), seed=None,
        tag=tag, library=None, libraries=None, pool_policy="finals")
    native_result = result.to_dict()
    editor = prop.phase3a_evidence() if hasattr(prop, "phase3a_evidence") else {}
    # The trusted boundary's settled editor results must be included in the authoritative snapshot.
    supplied = result_snapshot() if result_snapshot is not None else {}
    for slot, value in supplied.items():
        strategy._integrity(slot not in adapter.known_results or adapter.known_results[slot] == value,
                          "editor result conflicts with strategy journal")
        adapter.known_results[slot] = value
    dispositions, authentic = _stage_proof(native_result, editor, task, run_root, tag,
                                          fixture, study_sha256, adapter.known_results)
    selection = native_result.get("selections", {}).get("agg", {})
    strategy._integrity(not selection.get("ok") or selection.get("trivial") is True
        and selection.get("chosen_label") == "agg1", "native k1 final selection changed")
    rollouts = {label: read_json(run_root / "rollouts" / label / "rollout.json")
                for label in LABELS if (run_root / "rollouts" / label / "rollout.json").exists()}
    portfolio = rollouts.get("agg1", {}).get("portfolio") if selection.get("ok") else None
    record = {"kind": "phase3a-native-adaptation-v1", "fixture": fixture, "arm": "adaptive",
        "study_sha256": study_sha256, "task_id": task["id"], "tag": tag,
        "native": native_result, "rollouts": rollouts, "editor_evidence": editor,
        "stage_dispositions": dispositions, "authentic": authentic,
        "portfolio": portfolio, "status": "complete" if portfolio is not None else "missing",
        "artifact_hashes": _artifacts(run_root)}
    write_once(run_root / "adaptation.json", record)
    return record


def validate_adaptation(record: dict, task: dict, harness_dir: Path, *, study_sha256: str,
                        run_root: Path, tag: str, fixture: bool, results: dict) -> dict:
    with strategy.validation_scope():
        return _validate_adaptation(record, task, harness_dir, study_sha256=study_sha256,
                                    run_root=run_root, tag=tag, fixture=fixture, results=results)


def _validate_adaptation(record: dict, task: dict, harness_dir: Path, *, study_sha256: str,
                        run_root: Path, tag: str, fixture: bool, results: dict) -> dict:
    """Inspect native files and reconstruct saved portfolios without a Proposer or SDK."""
    run_root = strategy._path(run_root)
    strategy._require(record.get("kind") == "phase3a-native-adaptation-v1"
        and record.get("fixture") is fixture and record.get("study_sha256") == study_sha256
        and record.get("task_id") == task["id"] and record.get("tag") == tag,
        "native branch belongs to a different execution")
    strategy._require(record.get("artifact_hashes") == _artifacts(run_root), "native artifacts changed")
    validate_adaptive_partial(task, harness_dir, study_sha256=study_sha256, run_root=run_root,
                              tag=tag, fixture=fixture, results=results)
    ids = adaptive_run_ids(task["id"], tag)
    actual_rollouts = {label: read_json(run_root / "rollouts" / label / "rollout.json")
                       for label in LABELS if (run_root / "rollouts" / label / "rollout.json").exists()}
    strategy._require(record.get("rollouts") == actual_rollouts, "native rollout inventory differs")
    for label, run_id in ids.items():
        path = run_root / "rollouts" / label
        if path.exists():
            strategy.validate_partial(task, path / "harness", study_sha256=study_sha256,
                                      run_id=run_id, fixture=fixture, arm="adaptive", results=results)
        if label in record["rollouts"]:
            expected = strategy.validate_rollout(record["rollouts"][label], task, path / "harness",
                study_sha256=study_sha256, fixture=fixture, run_id=run_id, arm="adaptive", results=results)
            strategy._require(expected == read_json(path / "rollout.json"), "native rollout artifact differs")
    identity = read_json(run_root / "identity.json")
    strategy._require(identity["task"] == task and identity["seed"] == strategy.validate_harness(harness_dir)
                      and identity["study_sha256"] == study_sha256, "native seed identity differs")
    modules = _modules()
    namespace = modules["schedule"].Namespace(BENCHMARK, SUBSTRATE, "agg", 1, None, tag)
    work = namespace.task_dir(run_root / "native", task["id"])
    strategy._require(read_json(work / "summary.json") == record["native"], "native summary differs")
    dispositions, authentic = _stage_proof(record["native"], record["editor_evidence"], task,
        run_root, tag, fixture, study_sha256, results)
    strategy._require(record["stage_dispositions"] == dispositions and record["authentic"] is authentic,
                      "native stage/editor authenticity proof differs")
    selection = record["native"].get("selections", {}).get("agg", {})
    portfolio = record["rollouts"].get("agg1", {}).get("portfolio") if selection.get("ok") else None
    strategy._require((not selection.get("ok") or selection.get("trivial") is True
        and selection.get("chosen_label") == "agg1" and selection.get("chosen_run_id") == ids["agg1"]
        and selection.get("chosen_run_dir") == str(run_root / "rollouts/agg1")) and record["portfolio"] == portfolio
        and record["status"] == ("complete" if portfolio is not None else "missing"),
        "native final is not its sole eligible composed output")
    return record


class Phase3NativeAssessment(NativeAssessment):
    """Unchanged native evaluator with an explicit, separate assessment-slot namespace."""

    def __init__(self, upstream: Path):
        super().__init__(upstream)
        self._assessment_id: str | None = None
        self._assessment_lock = threading.RLock()

    @staticmethod
    def slot_prefix(assessment_id: str) -> str:
        strategy.slot_prefix(assessment_id)
        return "p3a-assessment-" + digest(assessment_id)[:24]

    def _prefix(self, portfolio: dict) -> str:
        strategy._require(self._assessment_id is not None, "an explicit assessment identity is required")
        return self.slot_prefix(self._assessment_id or "")

    def assess(self, portfolio: dict, dispatch, *, assessment_id: str, checkpoint: str = "canary") -> dict:
        with self._assessment_lock:
            self._assessment_id = assessment_id
            try:
                def bound(slot, role, request, **kwargs):
                    return dispatch(slot, role, request)
                return super().assess(portfolio, bound, checkpoint=checkpoint)
            finally:
                self._assessment_id = None

    def fold_group(self, portfolio: dict, result: dict, *, assessment_id: str | None = None) -> dict:
        with self._assessment_lock:
            previous = self._assessment_id
            if assessment_id is not None:
                self._assessment_id = assessment_id
            try:
                return super().fold_group(portfolio, result)
            finally:
                self._assessment_id = previous

    def finalize(self, portfolio: dict, group_result: dict, quality_results: list[dict],
                 *, assessment_id: str | None = None) -> dict:
        with self._assessment_lock:
            previous = self._assessment_id
            if assessment_id is not None:
                self._assessment_id = assessment_id
            try:
                strategy._require(self._assessment_id is not None, "assessment identity required for replay")
                return super().finalize(portfolio, group_result, quality_results)
            finally:
                self._assessment_id = previous
