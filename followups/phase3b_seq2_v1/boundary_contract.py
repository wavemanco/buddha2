"""Generation-free expected negative and strict host contract regression.

The empty boundary-only study must be rejected before an export request while
its canonical reports remain honest. Pure prepared-unit negatives are separate.
Real positive first-pair and closure handshakes are required from fresh S13.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from .snapshot import VISIBILITY_OWNER_KIND, VISIBILITY_REQUEST_KIND
from .support import path, publish, read, require

CHECKPOINTS = ("first-pair", "closure")


def _hash(target: Path) -> str:
    return hashlib.sha256(path(target).read_bytes()).hexdigest()


def prepare(output: Path) -> dict:
    """Freeze actual source/runtime/authority and an empty supervised fixture."""
    from . import workflow

    output = path(output)
    require(not output.exists(), "boundary preparation requires a fresh root")
    study = workflow.prepare(output / "release", supervised_fixture=True, boundary_fixture=True)
    study_path = output / "release/study.json"
    grant_path = output / "release/mock-grant.json"
    publish(grant_path, workflow.make_grant(study_path, True))
    run, journal = workflow.paths(study, True)
    require(not run.exists() and not journal.exists(), "boundary execution namespace is not fresh")
    result = {"kind": "p3b-s2-boundary-prepared-v1", "study_path": str(study_path),
        "grant_path": str(grant_path), "run": str(run), "journal": str(journal),
        "study_sha256": study["study_sha256"], "source_sha256": study["source_sha256"],
        "fixture": True, "provider_calls": 0, "generations": 0,
        "fixture_supervision_rehearsal": True, "fixture_boundary_contract": True,
        "checkpoints": list(CHECKPOINTS)}
    publish(output / "prepared.json", result)
    return result


def core(output: Path) -> dict:
    """Expected negative: an empty fixture cannot claim first-pair readiness."""
    from . import workflow

    prepared = read(path(output / "prepared.json"))
    study_path, grant_path = Path(prepared["study_path"]), Path(prepared["grant_path"])
    study = workflow.load_study(study_path)
    require(study["fixture_supervision_rehearsal"] is True
            and study["fixture_boundary_contract"] is True, "boundary-only study required")
    workflow.grant_for(study, grant_path, True)
    run, journal = workflow.paths(study, True)
    require(str(run) == prepared["run"] and str(journal) == prepared["journal"]
            and not journal.exists(), "boundary fixture has generated activity")
    status = workflow._visibility_checkpoint(study_path, study, grant_path, True, "first-pair")
    directory = path(run / "visibility/first-pair")
    summary = status["canonical_summary"]
    require(status.get("canonical_status") == "complete" and status.get("worker_stopped") is True
            and status.get("reports_published") is True and status.get("report_status") == "complete"
            and status.get("visibility_status") == "failed" and status.get("snapshot_sha256") is None
            and status.get("projection_error_type") == "ProjectionError"
            and summary.get("first_assessments_closed") is False
            and not summary.get("engineering_review") and summary.get("attempts") == 0,
            "empty fixture bypassed the actual first-pair projection contract")
    require(not journal.exists() and not any((directory / name).exists()
            for name in ("request.json", "result.json", "ownership.json", "snapshot")),
            "empty fixture created request/export/generation activity")
    result = {"kind": "p3b-s2-boundary-empty-negative-v1", "passed": True,
        "expected_negative": True, "study_sha256": study["study_sha256"],
        "source_sha256": study["source_sha256"], "fixture": True,
        "provider_calls": 0, "generations": 0, "I1_exports": 0,
        "status_sha256": _hash(directory / "status.json"),
        "positive_proof_required_from": "fresh actual S13 first-pair and closure"}
    publish(path(output / "core-result.json"), result)
    return result


def host(output: Path) -> dict:
    """Service both real requests with unchanged SDK-free ACK-bound I1 export."""
    from .host_checks import from_container
    from .host_checks import read as host_read
    from .inspect_adapter import host_export
    from .snapshot import ROOT, lexical

    lexical(str(output))
    prepared = host_read(output / "prepared.json")
    require(prepared.get("kind") == "p3b-s2-boundary-prepared-v1"
            and prepared.get("fixture_supervision_rehearsal") is True
            and prepared.get("fixture_boundary_contract") is True
            and prepared.get("provider_calls") == prepared.get("generations") == 0,
            "foreign boundary preparation")
    run = from_container(prepared["run"], missing=True)
    outcomes = []
    for checkpoint in CHECKPOINTS:
        directory = run / "visibility" / checkpoint
        request_raw = prepared["run"] + "/visibility/" + checkpoint + "/request.json"
        request_path = from_container(request_raw, missing=True)
        # Waiting does not renew the request's own original 600-second window.
        wait_deadline = time.monotonic() + 650
        while not from_container(request_raw, missing=True).exists() and time.monotonic() < wait_deadline:
            time.sleep(0.25)
        request = host_read(request_path)
        before = hashlib.sha256(request_path.read_bytes()).hexdigest()
        target = (ROOT / "runs/phase3b-seq2-v1/visibility-exports" /
                  prepared["study_sha256"] / "mock" / checkpoint / "boundary-contract")
        result = host_export(directory / "snapshot", target, ack=directory / "result.json")
        require(result.get("visibility_status") == "complete"
                and result.get("exporter_stopped") is True and result.get("cleanup_verified") is True
                and host_read(directory / "result.json") == result
                and hashlib.sha256(request_path.read_bytes()).hexdigest() == before,
                "actual host export/ACK failed or changed its request")
        outcomes.append({"checkpoint": checkpoint, "output": str(target),
            "request_sha256": before, "snapshot_sha256": request["snapshot_sha256"],
            "result_sha256": hashlib.sha256((target / "visibility-result.json").read_bytes()).hexdigest()})
    # Host output is a separate immutable ordinary evidence file, never an ACK.
    result = {"kind": "p3b-s2-boundary-host-v1", "passed": True,
        "study_sha256": prepared["study_sha256"], "fixture": True,
        "provider_calls": 0, "generations": 0, "outcomes": outcomes}
    from .verify import save
    save(output / "host-result.json", result)
    return result


def negative(output: Path) -> dict:
    """Actual strict host validation/atomic claims; every Docker command denied."""
    from datetime import datetime, timedelta, timezone
    from unittest.mock import patch

    from . import inspect_adapter
    from .host_checks import read as host_read
    from .snapshot import (
        ROOT,
        ProjectionError,
        build_snapshot,
        canonical,
        output_path,
        publish_snapshot,
    )
    from .test_inspect_s2 import fixture_records
    from .verify import save

    output = output_path(output)
    require(not output.exists(), "negative evidence root must be fresh")
    output.mkdir(parents=True)
    cases = ("legacy-request", "wrong-study", "wrong-checkpoint", "wrong-snapshot",
             "invalid-deadline", "expired", "late", "tombstone")
    outcomes = []
    for checkpoint in CHECKPOINTS:
        for case in cases:
            identity = hashlib.sha256(canonical({"output": str(output), "checkpoint": checkpoint, "case": case})).hexdigest()

            def replace(value):
                if isinstance(value, str):
                    return value.replace("a" * 64, identity)
                if isinstance(value, list):
                    return [replace(item) for item in value]
                if isinstance(value, dict):
                    return {key: replace(item) for key, item in value.items()}
                return value

            study, report, saved = (replace(value) for value in fixture_records(no_calls=True))
            directory = output_path(ROOT / "runs/phase3b-seq2-v1/native" / identity / "mock/visibility" / checkpoint)
            manifest = publish_snapshot(build_snapshot(study, report, saved, checkpoint), directory / "snapshot")
            now = datetime.now(timezone.utc)
            started, deadline = now, now + timedelta(seconds=600)
            if case == "invalid-deadline":
                deadline += timedelta(seconds=1)
            elif case == "expired":
                started, deadline = now - timedelta(seconds=601), now - timedelta(seconds=1)
            elif case == "late":
                started, deadline = now - timedelta(seconds=590), now + timedelta(seconds=10)
            request = {"kind": VISIBILITY_REQUEST_KIND, "study_sha256": identity,
                "checkpoint": checkpoint, "snapshot_sha256": manifest["snapshot_sha256"],
                "snapshot_dir": "/results/" + (directory / "snapshot").relative_to(ROOT / "runs").as_posix(),
                "result_path": "/results/" + (directory / "result.json").relative_to(ROOT / "runs").as_posix(),
                "fixture": True, "timeout_seconds": 600, "cleanup_reserve_seconds": 15,
                "started_at_utc": started.isoformat(), "deadline_at_utc": deadline.isoformat()}
            if case == "legacy-request":
                request["kind"] = "p3b-rp2-visibility-request-v1"
            elif case == "wrong-study":
                request["study_sha256"] = "0" * 64
            elif case == "wrong-checkpoint":
                request["checkpoint"] = "closure" if checkpoint == "first-pair" else "first-pair"
            elif case == "wrong-snapshot":
                request["snapshot_sha256"] = "0" * 64
            inspect_adapter._write(directory / "request.json", request)
            request_bytes = (directory / "request.json").read_bytes()
            owner = {"kind": VISIBILITY_OWNER_KIND, **{key: request[key] for key in
                ("study_sha256", "checkpoint", "snapshot_sha256", "deadline_at_utc")},
                "exporter_started": False, "state": "closed_without_export"}
            if case == "tombstone":
                inspect_adapter._claim_owner(directory / "ownership.json", owner)
                owner_bytes = (directory / "ownership.json").read_bytes()
            target = output_path(ROOT / "runs/phase3b-seq2-v1/visibility-exports" / identity /
                                 "mock" / checkpoint / "boundary-negative")
            commands = []

            def forbidden(*args, **kwargs):
                commands.append("attempted")
                raise AssertionError("negative host case attempted a Docker command")

            rejected = False
            result = None
            with patch.object(inspect_adapter, "_host_command", side_effect=forbidden):
                try:
                    result = inspect_adapter.host_export(directory / "snapshot", target,
                                                         ack=directory / "result.json")
                except ProjectionError:
                    rejected = True
            require(not commands and (directory / "request.json").read_bytes() == request_bytes,
                    "negative dispatched or changed request")
            if case in {"legacy-request", "wrong-study", "wrong-checkpoint", "wrong-snapshot", "invalid-deadline"}:
                require(rejected and not target.exists() and not (directory / "result.json").exists(),
                        "invalid request was not rejected before output/ACK")
            elif case in {"expired", "late"}:
                require(not rejected and isinstance(result, dict) and result["visibility_status"] == "timeout"
                        and result["exporter_stopped"] is True
                        and host_read(directory / "ownership.json") == owner
                        and host_read(directory / "result.json") == result,
                        "expired/late request did not close without exporter")
            else:
                require(not rejected and isinstance(result, dict)
                        and result.get("failure_type") == "visibility_ownership_already_claimed"
                        and result.get("exporter_stopped") is False
                        and not (directory / "result.json").exists()
                        and (directory / "ownership.json").read_bytes() == owner_bytes,
                        "late host bypassed the existing atomic tombstone")
            outcomes.append({"checkpoint": checkpoint, "case": case, "study_sha256": identity,
                "passed": True, "host_command_attempts": len(commands),
                "request_sha256": hashlib.sha256(request_bytes).hexdigest(),
                "rejected_before_output": rejected})
    result = {"kind": "p3b-s2-boundary-negative-v1", "passed": True, "fixture": True,
              "provider_calls": 0, "host_command_attempts": 0, "outcomes": outcomes}
    save(output / "negative-result.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("mode", choices=("prepare", "core", "host", "negative"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps({"prepare": prepare, "core": core, "host": host, "negative": negative}[args.mode](args.output), sort_keys=True))


if __name__ == "__main__":
    main()
