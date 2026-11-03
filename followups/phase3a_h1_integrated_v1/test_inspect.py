"""Offline public projection/visibility checks; fixtures never authorize provider activity."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from . import inspect_adapter
from . import snapshot as snapshot_module
from .inspect_adapter import host_export
from .snapshot import (
    ARMS,
    PILOTS,
    ROOT,
    CanonicalIntegrityError,
    ProjectionError,
    build_snapshot,
    canonical,
    output_path,
    publish_snapshot,
    read_snapshot,
    sha,
)


def fixture_records(mode: str, identity: str = "") -> tuple[dict, dict, dict]:
    if mode not in {"complete", "first-pair", "failed"}:
        raise ValueError("unknown fixture case")
    tasks = [{"pilot_id": pilot, "parent_task_id": f"synthetic-{pilot}",
              "prompt": f"SYNTHETIC fixture request {pilot}"} for pilot in PILOTS]
    study = {"study_sha256": hashlib.sha256((mode + identity).encode()).hexdigest(), "tasks": tasks,
             "assessment_plan": [{"id": f"fixture:{p}:{a}:primary", "pilot": p, "arm": a}
                                 for p in PILOTS for a in ARMS]}
    branches, assessments, rows = {}, {}, []
    for pilot in PILOTS:
        for arm in ARMS:
            reached = mode == "complete" or mode == "first-pair" and pilot == "p3a-01"
            portfolio = None
            aid = f"fixture:{pilot}:{arm}:primary"
            if reached:
                portfolio = {"fixture": True, "portfolio_id": f"portfolio-{pilot}-{arm}",
                             "responses": [{"id": f"{pilot}-{arm}-{i}", "text": f"SYNTHETIC {i}\nα"}
                                           for i in range(10)]}
                branches[pilot, arm] = {"study_sha256": study["study_sha256"], "pilot": pilot,
                                       "arm": arm, "fixture": True, "portfolio_sha256": sha(portfolio),
                                       "result": {"portfolio": portfolio, "status": "complete"}}
                assessments[aid] = {"fixture": True, "portfolio_sha256": sha(portfolio), "status": "scored",
                                    "failure": None, "metrics": {"utility": 0.0, "distinct": 1},
                                    "native": {"fields": {"generation_scores": [1] + [None] * 9}},
                                    "requests": [{"private_provider_blob": "must not be projected"}]}
            rows.append({"pilot": pilot, "parent_task_id": f"synthetic-{pilot}", "arm": arm,
                         "assessment_id": aid, "assessment_sha256": sha(assessments[aid]) if reached else None,
                         "final_sha256": sha(portfolio) if reached else None,
                         "status": "scored" if reached else "missing_final",
                         "branch_status": "complete" if reached else "not_attempted",
                         "metrics": {"utility": 0.0 if reached else None, "distinct": 1 if reached else None},
                         "authentic": False, "first_answer_quality": 1 if reached else None})
    summary = {"study_sha256": study["study_sha256"], "fixture": True,
               "complete_primary": mode == "complete", "scientific_complete": False,
               "status": "mock-complete" if mode == "complete" else "incomplete",
               "first_assessments_closed": mode != "failed", "engineering_review": {"approved": True},
               "spent_micro_usd": 0, "reserved_micro_usd": 0,
               "prior_real_phase3a_spent_micro_usd": 16_580_264,
               "prior_real_phase3a_reserved_micro_usd": 22_880_000}
    report = {"rows": rows, "summary": summary, "readiness": None if mode == "failed" else {"passed": True},
              "analysis": {"held_evidence_failure": None, "scientific_complete": False,
                           "mean_adaptive_minus_fixed": 0.0 if mode == "complete" else None},
              "coverage": {"fixture": True, "primary_scheduled": 8},
              "accounting": {"spent_micro_usd": 0, "reserved_micro_usd": 0,
                             "engineering_review": {"handle": "excluded"}, "unknown_cost_not_inferred_zero": True},
              "protocol": {"study_sha256": study["study_sha256"], "source_sha256": "b" * 64,
                           "runtime_sha256": "c" * 64, "runtime": {"image_id": "fixture-only"},
                           "requests": [{"slot_id": "synthetic.plan", "role": "plan",
                                         "requested_parameters": {"model": "claude-sonnet-5-5", "max_tokens": 4096},
                                         "spent_micro_usd": 0, "failure": None}]}}
    return study, report, {"branches": branches, "assessments": assessments}


class SnapshotChecks(unittest.TestCase):
    def setUp(self):
        output_root = Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", str(ROOT / "runs")))
        scratch = output_path(Path(os.environ.get("P3A_HI_TEST_OUTPUT", str(
            output_root / "phase3a-h1-integrated-v1/inspect-unit"))))
        scratch.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "repo"
        scope = self.root / "runs/phase3a-h1-integrated-v1"
        # Only tests remap the host's exact repository boundary; all source mounts stay read-only.
        for relative in ("followups/phase3a_h1_integrated_v1/inspect_adapter.py",
                         "followups/phase3a_h1_integrated_v1/snapshot.py",
                         "followups/inspect_visibility_i1/importer.py",
                         "followups/inspect_visibility_i1/paths.py"):
            source = (ROOT / relative).read_bytes()
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source)
            self.assertEqual(target.read_bytes(), source)
        self.enterContext(patch.multiple(snapshot_module, ROOT=self.root, SCOPES=(scope,)))
        self.enterContext(patch.multiple(inspect_adapter, ROOT=self.root,
                                       HERE=self.root / "followups/phase3a_h1_integrated_v1"))
        self.base = output_path(scope / "unit")
        self.base.mkdir(parents=True, exist_ok=True)

    def test_native_projection_is_pure_exact_and_excludes_controls(self):
        study, report, saved = fixture_records("complete")
        before = copy.deepcopy((study, report, saved))
        payload = build_snapshot(study, report, saved, "closure")
        self.assertEqual((study, report, saved), before)
        self.assertEqual(payload["rows"], report["rows"])
        self.assertNotIn("engineering_review", payload["summary"])
        self.assertNotIn("engineering_review", payload["accounting"])
        self.assertFalse(payload["summary"]["scientific_complete"])
        self.assertEqual(payload["rows"][0]["metrics"]["utility"], 0.0)
        self.assertNotIn("temperature", payload["requests"][0]["requested_parameters"])
        self.assertIsNone(payload["requests"][0]["failure"])
        self.assertTrue(all("requests" not in value for value in payload["native_assessments"].values()))
        self.assertEqual(payload["summary"]["prior_real_phase3a_reserved_micro_usd"], 22_880_000)

    def test_partial_failed_and_not_reached_remain_distinct(self):
        first = build_snapshot(*fixture_records("first-pair"), "first-pair")
        failed = build_snapshot(*fixture_records("failed"), "closure")
        self.assertEqual(sum(r["status"] == "scored" for r in first["rows"]), 2)
        self.assertEqual(first["checkpoint_dispositions"]["first-pair"], "reached")
        self.assertEqual(failed["checkpoint_dispositions"]["first-pair"], "not_reached")
        self.assertTrue(all(value["portfolio"] is None for value in failed["finals"]))
        self.assertIsNone(failed["rows"][0]["metrics"]["utility"])
        with self.assertRaises(ProjectionError):
            build_snapshot(*fixture_records("failed"), "first-pair")

    def test_retained_deadline_statuses_are_not_normalized(self):
        for status in ("unvalidated_known_deadline_stop", "unvalidated_unknown_deadline_hold"):
            study, report, saved = fixture_records("failed")
            for row in report["rows"]:
                row["status"] = row["branch_status"] = status
            payload = build_snapshot(study, report, saved, "closure")
            self.assertTrue(all(row["status"] == status for row in payload["rows"]))

    def _job(self, *, expired: bool = False):
        identity = self._testMethodName + str(time_nonce())
        payload = build_snapshot(*fixture_records("failed", identity), "closure")
        base = self.root / "runs/phase3a-h1-integrated-v1"
        directory = base / "native" / payload["study_sha256"] / "mock/visibility/closure"
        snapshot = directory / "snapshot"
        manifest = publish_snapshot(payload, snapshot)
        now = datetime.now(timezone.utc)
        started = now - timedelta(seconds=601) if expired else now
        request = {"kind": "p3a-hi-visibility-request-v1", "study_sha256": payload["study_sha256"],
                   "checkpoint": "closure", "snapshot_sha256": manifest["snapshot_sha256"],
                    "snapshot_dir": "/results/" + snapshot.relative_to(self.root / "runs").as_posix(),
                    "result_path": "/results/" + (directory / "result.json").relative_to(self.root / "runs").as_posix(),
                   "fixture": True, "timeout_seconds": 600, "cleanup_reserve_seconds": 15,
                   "started_at_utc": started.isoformat(), "deadline_at_utc": (started + timedelta(seconds=600)).isoformat()}
        (directory / "request.json").write_bytes(canonical(request) + b"\n")
        return snapshot, base / "visibility-exports/unit" / payload["study_sha256"], directory / "result.json", request

    def test_expired_job_never_constructs_docker_and_atomically_closes(self):
        snapshot, output, ack, _ = self._job(expired=True)
        with patch.object(inspect_adapter, "_host_command", side_effect=AssertionError("Docker called")):
            result = host_export(snapshot, output, ack=ack)
        self.assertEqual(result["visibility_status"], "timeout")
        self.assertTrue(result["exporter_stopped"])
        owner = json.loads((snapshot.parent / "ownership.json").read_bytes())
        self.assertEqual(owner["state"], "closed_without_export")
        self.assertFalse(owner["exporter_started"])
        self.assertEqual(json.loads(ack.read_bytes()), result)

    def test_core_wins_atomic_close_no_late_or_second_launch(self):
        snapshot, output, ack, request = self._job()
        owner = {"kind": "p3a-hi-visibility-owner-v1", "study_sha256": request["study_sha256"],
                 "checkpoint": "closure", "snapshot_sha256": request["snapshot_sha256"],
                 "deadline_at_utc": request["deadline_at_utc"], "state": "closed_without_export",
                 "exporter_started": False}
        original = canonical(owner) + b"\n"
        (snapshot.parent / "ownership.json").write_bytes(original)
        with patch.object(inspect_adapter, "_host_command", side_effect=AssertionError("Docker called")):
            result = host_export(snapshot, output, ack=ack)
        self.assertEqual(result["visibility_status"], "failed")
        self.assertFalse(ack.exists())
        self.assertEqual((snapshot.parent / "ownership.json").read_bytes(), original)

    def _fake_docker(self, snapshot, output, request, *, cleanup: int = 0, bad_mount: bool = False):
        commands, mounts = [], []

        def command(args, deadline, *, reserve=15):
            del deadline, reserve
            commands.append(args[1])
            owner = json.loads((snapshot.parent / "ownership.json").read_bytes())
            self.assertEqual(owner["state"], "claimed")
            if args[1] == "create":
                for i, value in enumerate(args):
                    if value == "--mount":
                        parts = dict(part.split("=", 1) for part in args[i + 1].split(",") if "=" in part)
                        mounts.append({"Destination": parts["target"], "Source": parts["source"],
                                       "RW": "readonly" not in args[i + 1].split(","), "Type": "bind"})
                return {"exit_code": 0, "stdout": "fixture-container", "stderr": ""}
            if args[1] == "inspect":
                if bad_mount:
                    next(m for m in mounts if m["Destination"] == "/out")["Source"] = str(snapshot.parent.parent)
                detail = {"Image": inspect_adapter.IMAGE, "Mounts": mounts,
                          "HostConfig": {"NetworkMode": "none", "ReadonlyRootfs": True},
                          "Config": {"Env": ["HOME=/tmp/empty-home", "PYTHONPATH=/code"]}}
                return {"exit_code": 0, "stdout": json.dumps([detail]), "stderr": ""}
            if args[1] == "start":
                return {"exit_code": 1, "stdout": "", "stderr": "synthetic export error"}
            self.assertEqual(args[1], "rm")
            return {"exit_code": cleanup, "stdout": "", "stderr": ""}

        return command, commands

    def test_cleanup_unknown_cannot_attest_stopped(self):
        snapshot, output, ack, request = self._job()
        fake, commands = self._fake_docker(snapshot, output, request, cleanup=1)
        with patch.object(inspect_adapter, "_host_command", side_effect=fake):
            result = host_export(snapshot, output, ack=ack)
        self.assertEqual(commands, ["create", "inspect", "start", "rm"])
        self.assertEqual(result["visibility_status"], "failed")
        self.assertFalse(result["exporter_stopped"])
        self.assertFalse(json.loads(ack.read_bytes())["exporter_stopped"])

    def test_actual_mount_substitution_rejected_before_start(self):
        snapshot, output, ack, request = self._job()
        fake, commands = self._fake_docker(snapshot, output, request, bad_mount=True)
        with patch.object(inspect_adapter, "_host_command", side_effect=fake):
            result = host_export(snapshot, output, ack=ack)
        self.assertEqual(commands, ["create", "inspect", "rm"])
        self.assertTrue(result["exporter_stopped"])
        self.assertEqual(result["visibility_status"], "failed")
        self.assertTrue(json.loads(ack.read_bytes())["exporter_stopped"])

    def test_canonical_mismatch_is_not_projection_failure(self):
        study, report, saved = fixture_records("complete")
        report["rows"][0]["final_sha256"] = "d" * 64
        with self.assertRaises(CanonicalIntegrityError):
            build_snapshot(study, report, saved, "closure")
        study, report, saved = fixture_records("complete")
        report["rows"][0]["metrics"]["utility"] = 9
        with self.assertRaises(CanonicalIntegrityError):
            build_snapshot(study, report, saved, "closure")

    def test_unsupported_mappings_fail_without_native_mutation(self):
        study, report, saved = fixture_records("complete")
        for target, key, value in [(report["rows"][0], "status", "unknown"),
                                   (report["protocol"]["requests"][0], "role", "unknown")]:
            original = target[key]
            target[key] = value
            with self.assertRaises(ProjectionError):
                build_snapshot(study, report, saved, "closure")
            target[key] = original

    def test_private_escape_foreign_before_metadata(self):
        for raw in [str(self.base / ".ENV"), str(self.base / ".." / "escaped"), "/outside/visibility"]:
            with self.subTest(raw=raw), patch.object(Path, "lstat", side_effect=AssertionError("metadata")):
                with self.assertRaises(ValueError):
                    output_path(Path(raw))
        with patch.object(Path, "lstat", side_effect=AssertionError("metadata")):
            with self.assertRaises(ProjectionError):
                read_snapshot(Path("/unmounted"))

    def test_host_cannot_write_canonical_tree_or_foreign_ack(self):
        native = self.root / "runs/phase3a-h1-integrated-v1/native" / ("a" * 64) / "mock"
        snapshot = native / "visibility/closure/snapshot"
        exports = self.root / "runs/phase3a-h1-integrated-v1/visibility-exports/test"
        with patch.object(Path, "lstat", side_effect=AssertionError("metadata")):
            for output, ack in [(native / "journal", None), (native / "owner", None),
                                (exports, native / "visibility/first-pair/result.json"),
                                (exports, native / "journal/result.json")]:
                with self.subTest(output=output, ack=ack), self.assertRaises(ProjectionError):
                    host_export(snapshot, output, ack=ack)

    def test_snapshot_roundtrip_tamper_and_link_rejection(self):
        payload = build_snapshot(*fixture_records("complete"), "closure")
        with tempfile.TemporaryDirectory(dir=self.base) as temp:
            directory = Path(temp) / "snapshot"
            manifest = publish_snapshot(payload, directory)
            restored, checked, raw = read_snapshot(directory)
            self.assertEqual(restored, payload)
            self.assertEqual(checked, manifest)
            self.assertEqual(raw["payload.json"], canonical(payload) + b"\n")
            self.assertEqual(manifest["payload_sha256"], manifest["snapshot_sha256"])
            with self.assertRaises(ProjectionError):
                publish_snapshot(payload, directory)
            (directory / "payload.json").write_bytes(b"{}")
            with self.assertRaises(ProjectionError):
                read_snapshot(directory)
        with tempfile.TemporaryDirectory(dir=self.base) as temp:
            directory = Path(temp) / "snapshot"
            publish_snapshot(payload, directory)
            (directory / "payload.json").rename(directory / "real.json")
            (directory / "payload.json").symlink_to(directory / "real.json")
            with self.assertRaises(ValueError):
                read_snapshot(directory)


def host_fixtures(output: Path) -> dict:
    """Run two independent actual Inspect exports of each synthetic disposition."""
    output = output_path(output)
    if output.exists():
        raise ValueError("fresh host fixture output required")
    output.mkdir(parents=True)
    results = {}
    for mode in ("complete", "first-pair", "failed"):
        payload = build_snapshot(*fixture_records(mode, str(output)), "first-pair" if mode == "first-pair" else "closure")
        directory = output / mode
        directory.mkdir()
        checkpoint = payload["checkpoint"]
        snapshot_dir = ROOT / "runs/phase3a-h1-integrated-v1/native" / payload["study_sha256"] / "mock" / "visibility" / checkpoint / "snapshot"
        manifest = publish_snapshot(payload, snapshot_dir)
        replays = []
        for number in (1, 2):
            target = directory / f"replay-{number}"
            ack = None
            if number == 1:
                now = datetime.now(timezone.utc)
                request = {"kind": "p3a-hi-visibility-request-v1", "study_sha256": payload["study_sha256"],
                           "checkpoint": checkpoint, "snapshot_sha256": manifest["snapshot_sha256"],
                           "snapshot_dir": "/results/" + snapshot_dir.relative_to(ROOT / "runs").as_posix(),
                           "result_path": "/results/" + (snapshot_dir.parent / "result.json").relative_to(ROOT / "runs").as_posix(),
                           "fixture": True, "timeout_seconds": 600, "cleanup_reserve_seconds": 15,
                           "started_at_utc": now.isoformat(), "deadline_at_utc": (now + timedelta(seconds=600)).isoformat()}
                (snapshot_dir.parent / "request.json").write_bytes(canonical(request) + b"\n")
                ack = snapshot_dir.parent / "result.json"
            result = host_export(snapshot_dir, target, ack=ack)
            if result["visibility_status"] != "complete":
                raise AssertionError(f"actual passive export failed: {mode} {number}")
            replays.append(json.loads((target / "export/result.json").read_bytes()))
        if replays[0]["semantic_sha256"] != replays[1]["semantic_sha256"]:
            raise AssertionError("two actual Inspect exports differ semantically")
        results[mode] = {"snapshot_sha256": manifest["snapshot_sha256"], "replays": replays}
    record = {"passed": True, "provider_calls": 0, "api_spend": 0, "fixture": True, "cases": results}
    with (output / "result.json").open("xb") as stream:
        stream.write(canonical(record) + b"\n")
    return record


def time_nonce() -> int:
    import time
    return time.monotonic_ns()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--host-exports", type=Path)
    args = parser.parse_args()
    if args.host_exports:
        print(json.dumps(host_fixtures(args.host_exports), sort_keys=True))
    else:
        unittest.main(argv=[__file__], verbosity=2)
