"""R3 channel-profile entrypoint; execute the actual pinned Harness2 scheduler."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from buddha2.artifacts import ContractError, digest, file_hash, read_json, write_once
from followups.phase3a_v1 import native as frozen
from followups.phase3a_v1 import strategy

from . import editor

PortfolioAdapter = frozen.PortfolioAdapter
Phase3NativeAssessment = frozen.Phase3NativeAssessment
adaptive_run_ids = frozen.adaptive_run_ids
validate_adaptive_partial = frozen.validate_adaptive_partial
_modules, _stage_proof, _artifacts = frozen._modules, frozen._stage_proof, frozen._artifacts
LABELS = frozen.LABELS


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
    """Require the R3 profile before the unchanged full native/report replay."""
    strategy._require(record.get("editor_profile_sha256") == digest(editor.profile())
        and record.get("editor_boundary_sha256") == file_hash(Path(editor.__file__))
        and record.get("native_entrypoint_sha256") == file_hash(Path(__file__)),
        "native R3 editor profile/source differs")
    return frozen.validate_adaptation(record, task, harness_dir, study_sha256=study_sha256,
        run_root=run_root, tag=tag, fixture=fixture, results=results)
