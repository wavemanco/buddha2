"""Offline preparation, mock execution and report replay for the bounded P2B-N block."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from buddha2.__main__ import _offline
from buddha2.phase2_am1_controls import runtime_guard

from .support import checked_path, read_json, require, write_once


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "grant", "mock", "snapshot", "report"))
    parser.add_argument("--study", type=Path)
    parser.add_argument("--grant", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--partition", choices=("pairs", "distinct"), default="distinct")
    args = parser.parse_args(argv)
    runtime_guard()
    _offline()
    from . import workflow

    if args.action == "prepare":
        require(args.output is not None, "prepare requires --output")
        result = workflow.prepare(checked_path(args.output, output=True))
    elif args.action == "grant":
        require(args.study is not None and args.output is not None,
                "grant requires --study and --output")
        # The retained whole-block user authority supplies the live grant, not
        # the existence of a preparation or a green mock run.
        authority = read_json(Path("/workspace/evidence/phase2b-rank-format-v1/authorization.json"))
        require(authority.get("implementation_authorized") is True
                and authority.get("additional_cap_micro_usd") == 30_000_000,
                "explicit whole-block authority is missing")
        result = workflow.grant_template(args.study, fixture=args.fixture, authorized=True)
        write_once(checked_path(args.output, output=True), result)
    else:
        require(args.study is not None and args.grant is not None,
                "execution/replay requires --study and --grant")
        if args.action == "mock":
            require(args.fixture, "mock requires an explicit fixture grant")
            from buddha2.phase2_am1_mock import SDKMock

            with SDKMock(partition=args.partition) as mock:
                result = workflow.run(args.study, args.grant, mock.transport)
                result = {**result, "new_mock_http_calls": mock.http_calls}
        elif args.action == "snapshot":
            result = workflow.snapshot(args.study, args.grant, args.fixture)
        else:
            require(args.output is not None, "report requires --output")
            result = workflow.report(args.study, args.grant, args.output, args.fixture)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
