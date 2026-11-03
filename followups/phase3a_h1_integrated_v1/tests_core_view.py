"""Bound canonical reads, start/IPC/cleanup and report/projection separation."""
from __future__ import annotations

import tempfile
import time
import unittest
import uuid
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from . import core_view, report, snapshot, workflow
from .support import BASE


class StartStall:
    pid = None
    def __init__(self, **kwargs):
        pass
    def start(self):
        time.sleep(2)
    def is_alive(self):
        return False


class WorkerTests(unittest.TestCase):
    def spec(self):
        return {"bindings": dict.fromkeys(core_view.BINDINGS, "a" * 64),
                "checkpoint": "closure", "fixture": True}

    def collect(self, mode, **kwargs):
        started = time.monotonic()
        result = core_view.collect(self.spec(), deadline=started + 3, cleanup=.7, behavior=mode, **kwargs)
        self.assertLess(time.monotonic() - started, 3.5)
        return result

    def test_actual_spawn_large_bounded_frame_is_received_and_worker_stops(self):
        result = self.collect("large")
        self.assertEqual(result["canonical_status"], "complete")
        self.assertTrue(result["worker_stopped"])
        self.assertEqual(len(result["summary"]["payload"]), core_view.MAX_FRAME // 2)

    def test_actual_canonical_hang_and_partial_or_oversized_frame_stop_before_admission(self):
        for mode in ("hang", "partial", "oversized"):
            with self.subTest(mode=mode):
                result = self.collect(mode)
                self.assertEqual(result["canonical_status"], "failed")
                self.assertTrue(result["worker_stopped"])
                self.assertIsNone(result["summary"])

    def test_projection_hang_after_validated_reports_is_visibility_only(self):
        result = self.collect("projection-hang")
        self.assertEqual(result["canonical_status"], "complete")
        self.assertEqual(result["visibility_status"], "timeout")
        self.assertTrue(result["worker_stopped"])

    def test_start_stall_and_unproved_cleanup_never_claim_canonical_release(self):
        result = self.collect("small", process_factory=StartStall)
        self.assertEqual(result["canonical_status"], "failed")
        self.assertFalse(result["worker_stopped"])
        def unproved(state, deadline):
            core_view.Transport._stop(state, deadline)
            return False
        result = self.collect("small", stop_worker=unproved)
        self.assertEqual(result["canonical_status"], "failed")
        self.assertFalse(result["worker_stopped"])

    def test_worker_provider_and_socket_attempts_are_canonical_failures(self):
        for mode in ("constructor", "network", "subprocess"):
            with self.subTest(mode=mode):
                result = self.collect(mode)
                self.assertEqual(result["canonical_status"], "failed")
                self.assertEqual(result["canonical_error_type"], "ForbiddenActivity")
                self.assertTrue(result["worker_stopped"])


class ReuseTests(unittest.TestCase):
    def test_one_validated_view_feeds_report_and_projection_even_if_projection_fails(self):
        root = BASE / "core-view-tests"
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as directory_text:
            directory = Path(directory_text)
            spec: dict = {"bindings": dict.fromkeys(core_view.BINDINGS, "a" * 64), "study_path": "/synthetic/study.json",
                    "fixture": True, "checkpoint": "closure", "reports_path": str(directory / "final"),
                    "reports_staging_path": str(directory / "staging"), "reports_held_staging_path": str(directory / "held-staging"), "snapshot_path": str(directory / "snapshot")}
            study, state, records = dict(spec["bindings"]), {"status": "ready"}, {"synthetic": True}
            data = {"summary": {"fixture": True, "status": "mock-complete"}}
            notifications: list[dict] = []
            def reports(value, output):
                self.assertIs(value, data)
                output.mkdir()
                for name in report.NAMES:
                    (output / (name + ".json")).write_text("{}", encoding="utf-8")
                (output / "PHASE3A_REPORT.md").write_text("SYNTHETIC", encoding="utf-8")
                return {"fixture": True}
            def projection(actual_study, actual_data, actual_records, checkpoint):
                self.assertIs(actual_study, study)
                self.assertIs(actual_data, data)
                self.assertIs(actual_records, records)
                raise snapshot.ProjectionError("SYNTHETIC DISPLAY FAILURE")
            with ExitStack() as stack:
                load = stack.enter_context(patch.object(workflow, "load_study", return_value=study))
                financial = stack.enter_context(patch.object(workflow, "_state", return_value=state))
                saved = stack.enter_context(patch.object(workflow, "_snapshot_records", return_value=records))
                folded = stack.enter_context(patch.object(workflow, "_fold_view", return_value=data))
                stack.enter_context(patch.object(report, "write_report", side_effect=reports))
                stack.enter_context(patch.object(snapshot, "build_snapshot", side_effect=projection))
                result = core_view._perform(spec, notifications.append)
            for call in (load, financial, saved, folded):
                call.assert_called_once()
            self.assertEqual(result["canonical_status"], "complete")
            self.assertEqual(result["visibility_status"], "failed")
            self.assertEqual(result["report_status"], "complete")
            self.assertFalse((directory / "final").exists())
            self.assertEqual(len(list((directory / "staging").iterdir())), 8)
            result["worker_stopped"] = False
            self.assertFalse(core_view.publish_reports(spec, result))
            self.assertFalse((directory / "final").exists())
            result["worker_stopped"] = True
            self.assertTrue(core_view.publish_reports(spec, result))
            self.assertEqual(len(list((directory / "final").iterdir())), 8)
            self.assertEqual(notifications[0]["phase"], "canonical_ready")

    def test_partial_report_write_stays_staged_and_never_publishes_final(self):
        root = BASE / "core-view-tests"
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as directory_text:
            directory = Path(directory_text)
            spec: dict = {"bindings": dict.fromkeys(core_view.BINDINGS, "a" * 64), "study_path": "/synthetic/study.json",
                    "fixture": True, "checkpoint": "closure", "reports_path": str(directory / "final"),
                    "reports_staging_path": str(directory / "staging"), "reports_held_staging_path": str(directory / "held-staging"), "snapshot_path": str(directory / "snapshot")}
            def partial(data, output):
                output.mkdir()
                (output / "rows.json").write_text("{}", encoding="utf-8")
                raise OSError("SYNTHETIC PARTIAL WRITE")
            with patch.object(workflow, "load_study", return_value=dict(spec["bindings"])), \
                    patch.object(workflow, "_state", return_value={"status": "ready"}), \
                    patch.object(workflow, "_snapshot_records", return_value={}), \
                    patch.object(workflow, "_fold_view", return_value={"summary": {"fixture": True}}), \
                    patch.object(report, "write_report", side_effect=partial), \
                    patch.object(snapshot, "build_snapshot", side_effect=AssertionError("projection after invalid report")):
                result = core_view._perform(spec)
            self.assertEqual(result["canonical_status"], "failed")
            self.assertFalse((directory / "final").exists())
            self.assertTrue((directory / "staging/rows.json").is_file())

    def test_canonical_failure_after_ready_publishes_only_held_reports_after_stop(self):
        root = BASE / "core-view-tests"
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as directory_text:
            directory = Path(directory_text)
            spec: dict = {"bindings": dict.fromkeys(core_view.BINDINGS, "a" * 64), "study_path": "/synthetic/study.json",
                "fixture": True, "checkpoint": "closure", "reports_path": str(directory / "final"),
                "reports_staging_path": str(directory / "staging"), "reports_held_staging_path": str(directory / "held-staging"),
                "snapshot_path": str(directory / "snapshot")}
            complete = {"summary": {"scientific_complete": True}}
            held = {"summary": {"scientific_complete": False}}
            notifications: list[dict] = []
            def reports(value, output):
                output.mkdir()
                for name in report.NAMES:
                    (output / (name + ".json")).write_text(str(value["summary"]["scientific_complete"]), encoding="utf-8")
                (output / "PHASE3A_REPORT.md").write_text("SYNTHETIC", encoding="utf-8")
                return {"fixture": True}
            with patch.object(workflow, "load_study", return_value=dict(spec["bindings"])), \
                    patch.object(workflow, "_state", return_value={"status": "ready"}) as financial, \
                    patch.object(workflow, "_snapshot_records", return_value={}) as saved, \
                    patch.object(workflow, "_fold_view", side_effect=[complete, held]), \
                    patch.object(report, "write_report", side_effect=reports), \
                    patch.object(snapshot, "build_snapshot", side_effect=snapshot.CanonicalIntegrityError("SYNTHETIC CONTRADICTION")):
                result = core_view._perform(spec, notifications.append)
            financial.assert_called_once()
            saved.assert_called_once()
            self.assertEqual(notifications[0]["phase"], "canonical_ready")
            self.assertEqual(result["canonical_status"], "failed")
            self.assertEqual(result["report_variant"], "held")
            self.assertFalse((directory / "final").exists())
            result["worker_stopped"] = False
            self.assertFalse(core_view.publish_reports(spec, result))
            self.assertFalse((directory / "final").exists())
            result["worker_stopped"] = True
            self.assertTrue(core_view.publish_reports(spec, result))
            self.assertEqual((directory / "final/summary.json").read_text(encoding="utf-8"), "False")
            self.assertEqual((directory / "staging/summary.json").read_text(encoding="utf-8"), "True")


class HostOwnershipTests(unittest.TestCase):
    def test_only_stopped_exporter_allows_staged_complete_reports_to_publish(self):
        for stopped in (False, True):
            study = {key: 'a' * 64 for key in core_view.BINDINGS}
            study['study_sha256'] = uuid.uuid4().hex * 2
            run, _ = workflow.paths(study, True)
            try:
                def collect(spec, **kwargs):
                    stage = Path(spec['reports_staging_path'])
                    stage.mkdir(parents=True)
                    for name in report.NAMES:
                        (stage / (name + '.json')).write_text('SYNTHETIC COMPLETE', encoding='utf-8')
                    (stage / 'PHASE3A_REPORT.md').write_text('SYNTHETIC', encoding='utf-8')
                    directory = Path(spec['snapshot_path']).parent
                    start = workflow.checked(workflow.read(directory / 'core-started.json'))
                    workflow.publish(directory / 'ownership.json', {'kind': 'p3a-hi-visibility-owner-v1',
                        'study_sha256': study['study_sha256'], 'checkpoint': 'closure', 'snapshot_sha256': 'b' * 64,
                        'deadline_at_utc': start['deadline_at_utc'], 'state': 'claimed', 'exporter_started': True})
                    return {'canonical_status': 'complete', 'report_status': 'complete', 'report_variant': 'validated',
                        'financial_state_validated': True, 'worker_stopped': True, 'visibility_status': 'prepared',
                        'snapshot_sha256': 'b' * 64, 'summary': {'study_sha256': study['study_sha256'],
                            'fixture': True, 'scientific_complete': True}}
                def ack(request):
                    return {'kind': 'p3a-hi-visibility-result-v1', **{key: request[key] for key in
                        ('study_sha256', 'checkpoint', 'snapshot_sha256')}, 'visibility_status': 'failed',
                        'provider_calls': 0, 'exporter_stopped': stopped}
                with patch.object(core_view, 'collect', side_effect=collect):
                    if stopped:
                        result = workflow._visibility_checkpoint(None, study, None, True, 'closure', fixture_ack=ack)
                        self.assertTrue(result['reports_published'])
                        self.assertTrue((run / 'reports/final/summary.json').is_file())
                    else:
                        with self.assertRaises(Exception):
                            workflow._visibility_checkpoint(None, study, None, True, 'closure', fixture_ack=ack)
                        self.assertFalse((run / 'reports/final').exists())
                        self.assertTrue((run / 'visibility/closure/reports-staging/summary.json').is_file())
                        self.assertTrue((run / 'canonical-stop.json').is_file())
            finally:
                import shutil
                self.assertEqual(run.parent.parent, workflow.NATIVE)
                shutil.rmtree(run.parent)
