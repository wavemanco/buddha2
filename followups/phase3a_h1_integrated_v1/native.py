"""HI channel-profile entrypoint; execute the actual pinned Harness2 scheduler."""
from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any

from buddha2.artifacts import ContractError, digest, file_hash, read_json, write_once
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


@strategy.scoped
def validate_adaptive_partial(task, harness_dir, *, run_root, **kwargs):
    strategy.precheck_harness(harness_dir)
    for label in LABELS:
        strategy.precheck_harness(run_root / "rollouts" / label / "harness")
    return frozen.validate_adaptive_partial(task, harness_dir, run_root=run_root, **kwargs)


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
