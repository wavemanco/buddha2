"""Offline preparation, mock execution, review and replay; live calls require the host launcher."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from buddha2.artifacts import digest, write_once
from buddha2.phase2_am1_controls import BILLING_PROFILE, CONTROL_SHA256

from . import accounting, workflow
from .support import authorization, checked_path


def grant(study_path: Path, output: Path, *, fixture: bool) -> dict:
    study = workflow.load_study(study_path)
    original = authorization()
    authority = {"study_sha256": study["study_sha256"],
        "authorization_id": original["authorization_id"] + (":fixture" if fixture else ":live"),
        "authorized": True, "cap_micro_usd": accounting.POLICY["phase_micro_usd"],
        "canary_cap_micro_usd": accounting.POLICY["first_micro_usd"],
        "expansion_authorized": False, "control_policy_sha256": CONTROL_SHA256,
        "billing_profile": BILLING_PROFILE}
    value = {"kind": "phase3a-grant-v1", "fixture": fixture,
             **{key: study[key] for key in ("study_sha256", "source_sha256", "policy_sha256", "launcher_sha256")},
             "authority": authority}
    value["grant_sha256"] = digest(value)
    write_once(checked_path(output), value)
    return {"grant_sha256": value["grant_sha256"], "fixture": fixture, "provider_calls": 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "grant", "inspect", "report", "review", "mock"))
    parser.add_argument("--study", type=Path)
    parser.add_argument("--grant", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--stage", choices=("first", "remaining"), default="first")
    parser.add_argument("--cutoff")
    args = parser.parse_args(argv)
    if args.command == "prepare":
        if args.output is None:
            parser.error("prepare requires --output")
        result = workflow.prepare(args.output)
    elif args.command == "grant":
        if args.study is None or args.output is None:
            parser.error("grant requires --study and --output")
        result = grant(args.study, args.output, fixture=args.fixture)
    else:
        if args.study is None or args.grant is None:
            parser.error("this command requires --study and --grant")
        if args.command == "mock":
            from .editor import proposer_factory
            from .mocks import SDKMock
            with SDKMock() as mock:
                result = workflow.run(args.study, args.grant, stage=args.stage, transport=mock.transport,
                                      proposer_factory=proposer_factory, cutoff=args.cutoff)
                result = {**result, "new_mock_http_calls": mock.http_calls}
        elif args.command == "review":
            result = workflow.review_first(args.study, args.grant, args.fixture)
        elif args.command == "report":
            if args.output is None:
                parser.error("report requires --output")
            result = workflow.report(args.study, args.grant, args.output, args.fixture, cutoff=args.cutoff)
        else:
            result = workflow.snapshot(args.study, args.grant, args.fixture, cutoff=args.cutoff)["summary"]
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
