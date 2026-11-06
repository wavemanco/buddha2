"""Source-checkout entry point to the existing native comparison and saved evidence."""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

from .artifacts import ContractError, digest, public_path_parts

ROOT = Path(__file__).resolve().parents[2]


def _backend(name: str):
    # The native integration is a source-checkout package alongside src/.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    module = importlib.import_module("followups.phase3b_seq2_v1." + name)
    expected = ROOT / "followups/phase3b_seq2_v1" / (name + ".py")
    origin = getattr(module, "__file__", None)
    if (not isinstance(origin, str) or Path(origin) != expected
            or Path(origin).resolve() != expected):
        raise ContractError("native integration resolved outside this checkout")
    return module


def inspect_study(target: Path) -> dict:
    """Show sealed metadata without opening retained source or dispatching work."""
    target = Path(target).absolute()
    if target.name != "study.json":
        raise ContractError("inspect requires an ordinary study descriptor")
    relative = target.relative_to(ROOT) if target.is_relative_to(ROOT) else target
    public_path_parts(relative.parts)
    support = _backend("support")
    study = support.read(support.path(target))
    identity = study.get("study_sha256")
    if identity != digest({key: value for key, value in study.items() if key != "study_sha256"}):
        raise ContractError("study descriptor seal differs")
    tasks = study.get("tasks")
    if not isinstance(tasks, list) or any(not isinstance(task, dict) for task in tasks):
        raise ContractError("study task metadata is malformed")
    source = study.get("source")
    if not isinstance(source, dict) or any(
        not isinstance(task.get("parent_task_id"), str)
        or not 0 < len(task["parent_task_id"]) <= 256 for task in tasks
    ):
        raise ContractError("study source or task identities are malformed")
    current = source.get("kind") == support.SOURCE_KIND
    matches = (current and source == support.source_identity()
               and study.get("source_sha256") == source.get("sha256"))
    return {
        "study_sha256": identity,
        "kind": study.get("kind"),
        "source_sha256": study.get("source_sha256"),
        "source_matches_current": matches,
        "historical_profile": not current,
        "task_count": len(tasks),
        "task_ids": [task.get("parent_task_id") for task in tasks],
        "provider_calls": 0,
        "inspection_is_launch_approval": False,
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if args and args[0] in {"prepare", "grant", "report"}:
            return _backend("workflow").main(args)
        if args and args[0] == "launch":
            return _backend("launch").main(args[1:])
        parser = argparse.ArgumentParser(description=__doc__)
        commands = parser.add_subparsers(dest="command", required=True)
        commands.add_parser("prepare", help="freeze a new comparison in the contained runtime")
        commands.add_parser("grant", help="write an explicit fixture or approved live grant")
        commands.add_parser("report", help="reconstruct a report from saved accounted evidence")
        commands.add_parser("launch", help="use the existing inspected, source-bound launcher")
        view = commands.add_parser("inspect", help="read sealed study metadata without model calls")
        view.add_argument("--study", type=Path, required=True)
        timing = commands.add_parser("timing", help="continue or stop a pending timing review without model calls")
        timing.add_argument("--request", type=Path, required=True)
        timing.add_argument("--decision", choices=("continue", "stop"), required=True)
        parsed = parser.parse_args(args)
        result = (_backend("deadline").decide(parsed.request, parsed.decision)
                  if parsed.command == "timing" else inspect_study(parsed.study))
        print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))
        return 0
    except (ContractError, ValueError, OSError, ImportError, KeyError, TypeError):
        print(json.dumps({"error": "experiment_command_failed", "provider_calls": 0}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
