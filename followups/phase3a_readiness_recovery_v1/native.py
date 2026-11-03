"""HI channel-profile entrypoint; execute the actual pinned Harness2 scheduler."""
from __future__ import annotations

import copy
import os
import stat
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
from followups.phase3a_v1 import native as frozen

from . import editor, strategy
from .support import PRIVATE, safe

Phase3NativeAssessment = frozen.Phase3NativeAssessment
adaptive_run_ids = strategy.scoped(frozen.adaptive_run_ids)
_modules = frozen._modules
LABELS = frozen.LABELS


class PortfolioSubstrate(frozen.PortfolioSubstrate):
    def surface(self):
        with strategy.validation_scope():
            return strategy._public_surface()


class PortfolioAdapter(frozen.PortfolioAdapter):
    def __init__(self, *args, **kwargs):
        with strategy.validation_scope():
            strategy.precheck_harness(Path(args[1]))
            root = kwargs["run_root"]
            for label in LABELS:
                strategy.precheck_harness(root / "rollouts" / label / "harness")
            super().__init__(*args, **kwargs)
        self.substrate = PortfolioSubstrate()

    def _validate_existing(self, known_results: dict | None) -> None:
        from .accounting import LiabilityStop

        root = self.run_root / "rollouts"
        strategy._require(known_results is not None or not root.exists() or not any(root.iterdir()),
                          "resume requires authoritative journal results")
        checked = validate_adaptive_partial(self.task, self.harness_dir, study_sha256=self.study_sha256,
            run_root=self.run_root, tag=self.tag, fixture=self.fixture, results=self.known_results)
        if any(row["status"] == "unresolved" for row in checked.values()):
            raise LiabilityStop("unresolved native request blocks further execution")


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
        record = read_json(path / "rollout.json")
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
                              run_root: Path, tag: str, fixture: bool, results: dict) -> dict:
    """Verify all saved native inputs before any other missing arm may make a call."""
    run_root = strategy._path(run_root, existing=False)
    ids = adaptive_run_ids(task["id"], tag)
    root = run_root / "rollouts"
    if root.exists():
        names = os.listdir(root)
        strategy._require(all(name in LABELS for name in names), "undeclared native rollout directory")
        strategy._require(all(safe(root / name).is_dir() for name in names), "nonordinary native rollout directory")
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


@strategy.scoped
def _stage_proof(native_result, editor_evidence, task, run_root, tag, fixture, study_sha256, results):
    modules = _modules()
    namespace = modules["schedule"].Namespace(frozen.BENCHMARK, frozen.SUBSTRATE, "agg", 1, None, tag)
    work = namespace.task_dir(run_root / "native", task["id"])
    for label in ("inv1", "dom1", "agg1"):
        strategy.precheck_harness(work / "harnesses" / label)
    return frozen._stage_proof(native_result, editor_evidence, task, run_root, tag, fixture, study_sha256, results)


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
                                         steps=editor.MAX_STEPS, timeout=600)
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
    editor_evidence = prop.phase3a_evidence() if hasattr(prop, "phase3a_evidence") else {}
    # The trusted boundary's settled editor results must be included in the authoritative snapshot.
    supplied = result_snapshot() if result_snapshot is not None else {}
    for slot, value in supplied.items():
        strategy._integrity(slot not in adapter.known_results or adapter.known_results[slot] == value,
                          "editor result conflicts with strategy journal")
        adapter.known_results[slot] = value
    dispositions, authentic = _stage_proof(native_result, editor_evidence, task, run_root, tag,
                                          fixture, study_sha256, adapter.known_results)
    selection = native_result.get("selections", {}).get("agg", {})
    strategy._integrity(not selection.get("ok") or selection.get("trivial") is True
        and selection.get("chosen_label") == "agg1", "native k1 final selection changed")
    rollouts = {label: read_json(run_root / "rollouts" / label / "rollout.json")
                for label in LABELS if (run_root / "rollouts" / label / "rollout.json").exists()}
    portfolio = rollouts.get("agg1", {}).get("portfolio") if selection.get("ok") else None
    record = {"kind": "phase3a-native-adaptation-v1", "fixture": fixture, "arm": "adaptive",
        "study_sha256": study_sha256, "task_id": task["id"], "tag": tag,
        "native": native_result, "rollouts": rollouts, "editor_evidence": editor_evidence,
        "stage_dispositions": dispositions, "authentic": authentic,
        "portfolio": portfolio, "status": "complete" if portfolio is not None else "missing",
        "artifact_hashes": _artifacts(run_root),
        "editor_profile_sha256": digest(editor.profile()),
        "editor_boundary_sha256": file_hash(Path(editor.__file__)),
        "native_entrypoint_sha256": file_hash(Path(__file__))}
    write_once(run_root / "adaptation.json", record)
    return record


def validate_adaptation(record: dict, task: dict, harness_dir: Path, *, study_sha256: str,
                        run_root: Path, tag: str, fixture: bool, results: dict) -> dict:
    """Require the HI profile before the unchanged full native/report replay."""
    strategy._require(record.get("editor_profile_sha256") == digest(editor.profile())
        and record.get("editor_boundary_sha256") == file_hash(Path(editor.__file__))
        and record.get("native_entrypoint_sha256") == file_hash(Path(__file__)),
        "native HI editor profile/source differs")
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
    namespace = modules["schedule"].Namespace(frozen.BENCHMARK, frozen.SUBSTRATE, "agg", 1, None, tag)
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
