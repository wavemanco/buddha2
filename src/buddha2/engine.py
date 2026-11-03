"""External adapter for unchanged Harness² with an explicitly synthetic executor."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
from dataclasses import replace
from pathlib import Path

from harness2.core import schedule, tree
from harness2.core.proposer import Proposer, ProposerError, Reply
from harness2.core.spec import BenchPrompts, BenchSpec, ChannelSpec
from harness2.substrate.opencode import OpencodeSubstrate

FIXTURE_TASK = {
    "id": "phase0-reading-room",
    "prompt": "Give ten distinct ways to make a fictional public reading room welcoming without screens. Each answer should be a short actionable idea.",
    "domain": "creative-ideation",
    "fixture": True,
}
_EXPECTED_COMMIT = "1cfe254e8d25b15f37048c3730134686abe60335"
_CALLS = ["inv1.a1", "dom1.a1", "agg1.a1"]
_HELPER = "scripts/fixture_portfolio.py"
_REQUIRED_FILES = {
    "systemprompt.md", "guardrails.md", "LongTermMEMORY.md",
    "tool_descriptions/tool_guidance.md", "skills/planner/SKILL.md", _HELPER,
}
# shortcut: Phase 0 runs only this known helper; real executors require a later reviewed phase.
_HELPER_SHA256 = "cb7f347f9778b1c196c265f3c75d7600dd0d3676ca08151588c894d9cf9e2705"


class FixtureEngineError(RuntimeError):
    """The local fixture failed to complete its declared native execution path."""


def _digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _files(directory: Path) -> dict[str, str]:
    result = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Links are not supported in fixture files: {path}")
        if path.is_file():
            result[path.relative_to(directory).as_posix()] = _digest(path.read_bytes())
    return result


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _validate_task(task: object) -> None:
    if not isinstance(task, dict) or type(task) is not dict or task.get("fixture") is not True or task != FIXTURE_TASK:
        raise ValueError("Phase 0 accepts only the exact declared fixture task")


def _generations(path: Path) -> list[str]:
    artifact = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(artifact, dict):
        raise ValueError("The execution artifact must be a JSON object")
    _validate_task(artifact.get("task"))
    generations = artifact.get("generations")
    if artifact.get("fixture") is not True or artifact.get("provider_calls") != 0:
        raise ValueError("The execution artifact is not an offline fixture")
    if not isinstance(generations, list) or len(generations) != 10 or any(
        not isinstance(text, str) or not text.strip() for text in generations
    ):
        raise ValueError("The fixture must produce exactly ten nonempty responses")
    return generations


class _FixtureProposer(Proposer):
    def call(self, mission, context_dir, label, **kwargs) -> Reply:
        if label not in _CALLS:
            raise ProposerError(f"Unexpected fixture label: {label}")
        context = Path(context_dir)
        workspace = context / "harness"
        before = _files(workspace)
        if label == "inv1.a1":
            target = workspace / "guardrails.md"
            target.write_text(target.read_text(encoding="utf-8").replace(
                "<!-- fixture-angle-policy: repeated -->", "<!-- fixture-angle-policy: distinct -->"
            ), encoding="utf-8")
        elif label == "dom1.a1":
            target = workspace / "LongTermMEMORY.md"
            target.write_text(target.read_text(encoding="utf-8").replace(
                "<!-- fixture-domain-policy: general -->", "<!-- fixture-domain-policy: reading-room -->"
            ), encoding="utf-8")
        else:
            for candidate, name in (("inv1", "guardrails.md"), ("dom1", "LongTermMEMORY.md")):
                candidate_root = context / "pool" / candidate
                if not (candidate_root / "rollout.md").is_file() or not (candidate_root / "produced.md").is_file():
                    raise ProposerError("Composition requires native probe evidence")
                shutil.copyfile(candidate_root / "harness" / name, workspace / name)
        audit = Path(self.audit_dir) / label
        audit.mkdir(parents=True, exist_ok=True)
        (audit / "mission.txt").write_text(mission, encoding="utf-8")
        _write_json(audit / "edit.json", {
            "fixture": True, "label": label, "provider_calls": 0,
            "before_sha256": before, "after_sha256": _files(workspace),
        })
        reply = Reply(label=label, text="<notes>Synthetic fixture edit; no model reasoning occurred.</notes>",
                      ok=True, attempts=1, workspace=workspace)
        self._calls.append(reply)
        return reply


class _FixtureAdapter:
    def __init__(self, root: Path, strategy: Path, task: dict):
        self.root, self.strategy, self.task = root, strategy, task
        self.execution_count = 0
        self._lock = threading.Lock()
        self.substrate = OpencodeSubstrate(launcher=self._launch_fixture)
        channel = ChannelSpec("opencode", "local/deterministic")
        self.spec = BenchSpec(
            name="phase0-fixture", runs_root=root / "adapt", install_mode="workspace_config",
            prompts=BenchPrompts(work="Write ten short useful ideas for a welcoming public reading room"),
            channels={"proposer": channel, "selector": channel},
            leak_globs=("scores.json", "partitions.json", "assessment*.json"),
        )

    def tasks(self, split="all"):
        return [self.task["id"]]

    def domain_of(self, task_id):
        self._check_task_id(task_id)
        return self.task["domain"]

    def task_prompt(self, task_id):
        self._check_task_id(task_id)
        return self.task["prompt"]

    def task_files(self, task_id):
        self._check_task_id(task_id)
        return None

    def _check_task_id(self, task_id):
        if task_id != self.task["id"]:
            raise ValueError("Unknown fixture task ID")

    def base_harness(self):
        return self.root / "base-harness"

    def validate_tree(self, harness):
        if set(harness) != _REQUIRED_FILES:
            raise ValueError("Phase 0 accepts only the declared fixture harness files")
        if _digest(harness.get(_HELPER, "").encode("utf-8")) != _HELPER_SHA256:
            raise ValueError("Phase 0 runs only the known fixture helper")
        for name, choices in (
            ("guardrails.md", ("repeated", "distinct")),
            ("LongTermMEMORY.md", ("general", "reading-room")),
        ):
            prefix = "angle" if name == "guardrails.md" else "domain"
            count = sum(f"<!-- fixture-{prefix}-policy: {choice} -->" in harness[name] for choice in choices)
            if count != 1:
                raise ValueError(f"Exactly one fixture policy must be declared in {name}")

    def execute(self, task_id, harness_dir, run_id, *, timeout=None):
        self._check_task_id(task_id)
        source = harness_dir or self.base_harness()
        self.validate_tree(tree.read_tree(self.substrate.surface(), source))
        install = self.substrate.materialise(source, self.spec, {})
        try:
            return self.substrate.execute(task_id, install, [run_id], timeout or 10)[0]
        finally:
            shutil.rmtree(install.staging_dir)

    def _launch_fixture(self, request, install):
        self._check_task_id(request.task_ref)
        directories = []
        for run_id in request.run_ids:
            run_dir = (self.root / "executions" / run_id).resolve()
            if not run_dir.is_relative_to((self.root / "executions").resolve()):
                raise ValueError("Fixture run ID escapes execution storage")
            if run_dir.exists():
                if not self.artifacts_intact(run_dir):
                    raise FixtureEngineError("Existing execution artifacts changed; use a new destination")
                previous = json.loads((run_dir / "materialization.json").read_text(encoding="utf-8"))
                if previous["native_source_fingerprint"] != install.fingerprint or previous["materialized_sha256"] != _files(install.staging_dir):
                    raise FixtureEngineError("Existing execution belongs to a different effective harness")
                directories.append(run_dir)
                continue
            run_dir.mkdir(parents=True)
            retained = run_dir / "harness"
            shutil.copytree(install.staging_dir, retained)
            staged = replace(install, staging_dir=retained)
            task_path = run_dir / "task.json"
            _write_json(task_path, self.task)
            command = [sys.executable, "-I", "-B", str(staged.staging_dir / _HELPER),
                       str(staged.staging_dir), str(task_path)]
            completed = subprocess.run(
                command, check=True, capture_output=True, text=True, timeout=request.timeout,
                cwd=run_dir, env={"PATH": os.defpath, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
                                  "PYTHONDONTWRITEBYTECODE": "1"},
            )
            (run_dir / "portfolio.json").write_text(completed.stdout, encoding="utf-8")
            _generations(run_dir / "portfolio.json")
            (run_dir / "trajectory.md").write_text(
                "[ACTION] Run the known local fixture helper on the native materialized harness\n"
                "[OBSERVATION] Synthetic portfolio; model and provider calls: zero.\n" + completed.stdout,
                encoding="utf-8",
            )
            _write_json(run_dir / "materialization.json", {
                "fixture": True, "run_id": run_id, "command": command,
                "native_source_fingerprint": install.fingerprint,
                "materialized_sha256": _files(retained),
                "portfolio_sha256": _digest((run_dir / "portfolio.json").read_bytes()),
                "trajectory_sha256": _digest((run_dir / "trajectory.md").read_bytes()),
                "provider_calls": 0,
            })
            with self._lock:
                self.execution_count += 1
            directories.append(run_dir)
        return directories

    def delivered(self, run_dir):
        try:
            _generations(Path(run_dir) / "portfolio.json")
            return True
        except (OSError, ValueError, TypeError):
            return False

    def artifacts_intact(self, run_dir):
        run_dir = Path(run_dir)
        try:
            record = json.loads((run_dir / "materialization.json").read_text(encoding="utf-8"))
            return (
                self.delivered(run_dir)
                and record["materialized_sha256"] == _files(run_dir / "harness")
                and record["portfolio_sha256"] == _digest((run_dir / "portfolio.json").read_bytes())
                and record["trajectory_sha256"] == _digest((run_dir / "trajectory.md").read_bytes())
            )
        except (OSError, ValueError, KeyError, TypeError):
            return False

    def trajectory(self, run_dir, *, obs_trunc):
        return (Path(run_dir) / "trajectory.md").read_text(encoding="utf-8")

    def deliverable_text(self, run_dir):
        _generations(Path(run_dir) / "portfolio.json")
        return (Path(run_dir) / "portfolio.json").read_text(encoding="utf-8")

    def deliverable_files(self, run_dir):
        return {"portfolio.json": self.deliverable_text(run_dir)}

    def score(self, run_dir, task_id):
        raise FixtureEngineError("Live judging is unavailable; use independent offline fixture assessment")


def run_fixture(destination: Path, strategy_dir: Path, task: dict) -> dict:
    """Run actual upstream agg1 with a local fixture, never a provider-backed fallback."""
    _validate_task(task)
    destination, strategy_dir = Path(destination).resolve(), Path(strategy_dir).resolve(strict=True)
    if destination == strategy_dir or destination.is_relative_to(strategy_dir) or strategy_dir.is_relative_to(destination):
        raise ValueError("Execution storage and strategy source must be separate")
    source_files = _files(strategy_dir)
    for name in source_files:
        (strategy_dir / name).read_text(encoding="utf-8", errors="strict")
    adapter = _FixtureAdapter(destination, strategy_dir, dict(task))
    rejected: list[str] = []
    source_tree = tree.read_tree(adapter.substrate.surface(), strategy_dir, rejected=rejected)
    if rejected:
        raise ValueError(f"Files outside the native harness surface: {rejected}")
    tree.validate(adapter.substrate.surface(), source_tree, allow_subagents=False)
    adapter.validate_tree(source_tree)
    native_source = {
        "scheduler": str(Path(schedule.__file__).resolve()),
        "scheduler_sha256": _digest(Path(schedule.__file__).read_bytes()),
        "expected_commit": _EXPECTED_COMMIT,
    }
    identity = {"fixture": True, "policy": "phase0-agg1-v1", "task": task,
                "strategy_sha256": source_files, "native_source": native_source}
    identity_path = destination / "identity.json"
    if identity_path.exists() and json.loads(identity_path.read_text(encoding="utf-8")) != identity:
        raise ValueError("This destination belongs to different effective inputs; choose a new destination")
    if not identity_path.exists():
        _write_json(identity_path, identity)
    tree.write_tree(adapter.substrate.surface(), source_tree, adapter.base_harness(), stubs=False)
    proposer = _FixtureProposer(adapter.spec.channels["proposer"], audit_dir=destination / "proposer")
    result = schedule.run_task(
        task["id"], 1, adapter=adapter, prop=proposer, selector_prop=proposer,
        runs_root=adapter.spec.runs_root, modes=("agg",), library=None, pool_policy="finals",
    )
    mode = result.modes.get("agg", {})
    selection = result.selections.get("agg", {})
    if result.status not in ("ok", "skipped") or mode.get("fell_back") or not selection.get("ok") or not selection.get("trivial"):
        raise FixtureEngineError(f"Native fixture did not complete without fallback: {result.to_dict()}")
    calls = [reply.label for reply in proposer._calls]
    if calls and sorted(calls) != sorted(_CALLS):
        raise FixtureEngineError(f"Unexpected native fixture calls: {calls}")
    selected_run = Path(selection["chosen_run_dir"]).resolve()
    selected_label = selection["chosen_label"]
    selected_harness = destination / "adapt" / "phase0-fixture-oc-agg1" / task["id"] / "harnesses" / selected_label
    record = {
        "selected_run_dir": str(selected_run), "selected_harness_dir": str(selected_harness),
        "selected_label": selected_label, "generations": _generations(selected_run / "portfolio.json"),
        "execution_count": adapter.execution_count,
        "proposer_calls": [label for label in _CALLS if label in calls],
        "trace_paths": sorted(str(path.resolve()) for path in destination.rglob("*") if path.is_file()
                              and path.name in ("trajectory.md", "materialization.json", "summary.json", "selection.json", "edit.json")),
        "fixture": True, "provider_calls": 0, "native_source": native_source,
    }
    engine_record = destination / "engine.json"
    if not engine_record.exists():
        _write_json(engine_record, record)
    return record
