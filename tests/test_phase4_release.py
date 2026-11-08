"""Metadata/credential gates; synthetic freezes never supply real acceptance evidence."""
from __future__ import annotations

import copy
import tempfile
import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import Mock, patch

from buddha2.artifacts import ContractError, digest, read_json, write_once
from followups.phase3b_seq2_v1 import workflow as old_workflow
from followups.phase4_cm1_v1 import release


@contextmanager
def synthetic_release(*, isolate_claim=False):
    parent = release.BASE / "phase4-release-unit"
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=parent) as raw, ExitStack() as stack:
        directory = Path(raw)
        if isolate_claim:
            stack.enter_context(patch.object(release, "BASE", directory))
        stack.enter_context(patch.object(release, "runtime_guard"))
        stack.enter_context(patch.object(release, "runtime_identity", return_value={"synthetic_runtime": True}))
        source = {"kind": "buddha2-effective-source-v2", "schema_version": 2, "files": {}}
        source["sha256"] = digest(source)
        stack.enter_context(patch.object(release, "source_identity", return_value=source))
        development = [{"pilot_id": name, "source_pilot_id": original, "target_micro_usd": target,
            "task": {"id": "synthetic-" + name, "domain": "synthetic", "prompt": "Synthetic fixture task",
                     "source_context": {}}} for name, original, target in
            (("dev02", "p3b-02", 6_016_759), ("dev04", "p3b-04", 5_402_521))]
        stack.enter_context(patch.object(release, "_development", return_value=development))
        output = directory / "release"
        study = release.prepare(output)
        yield directory, output / "study.json", study


class Phase4ReleaseTests(unittest.TestCase):
    def test_only_two_exposed_development_tasks_preserve_exact_old_objects(self):
        original = {row["pilot_id"]: row for row in old_workflow.frozen_tasks()}
        rows = release._development()
        self.assertEqual([row["pilot_id"] for row in rows], ["dev02", "dev04"])
        self.assertEqual([row["target_micro_usd"] for row in rows], [6_016_759, 5_402_521])
        for row in rows:
            self.assertEqual(row["task"], old_workflow._task(original[row["source_pilot_id"]]))

    def test_source_freeze_includes_finite_p4_code_records_but_no_generated_results(self):
        value = release.source_identity()
        files = value["files"]
        self.assertIn("followups/phase4_cm1_v1/release.py", files)
        self.assertIn("tests/test_phase4_release.py", files)
        self.assertTrue(set(release.RECORDS.values()) <= set(files))
        self.assertIn(release.DEFINITION, files)
        self.assertIn(release.DEVELOPMENT, files)
        self.assertFalse(any(name.startswith(("runs/", ".archify/")) for name in files))
        self.assertNotIn("evidence/phase4-cm1-v1/offline-acceptance-v1.json", files)
        self.assertEqual(value["sha256"], digest({key: item for key, item in value.items() if key != "sha256"}))

    def test_parent_metadata_grants_and_resealed_source_tamper(self):
        with synthetic_release() as (_, study_path, study):
            self.assertEqual(release.load_study(study_path), study)
            self.assertFalse(study["confirmation_tasks_opened"])
            self.assertEqual(study["method_sha256"], digest(study["method"]))
            for fixture in (False, True):
                grant = release.make_grant(study_path, fixture)
                self.assertIs(grant["authority"]["authorized"], not fixture)
                self.assertEqual(grant["authority"]["cap_micro_usd"], 1_200_000_000)
            changed = copy.deepcopy(study)
            changed["runtime_sha256"] = "0" * 64
            changed["study_sha256"] = digest({key: item for key, item in changed.items() if key != "study_sha256"})
            with patch.object(release, "read_json", side_effect=lambda p: changed if p == study_path else read_json(p)), \
                    self.assertRaisesRegex(ContractError, "current method/source/runtime/authority"):
                release.load_study(study_path)

    def test_provider_requires_current_gate_while_configuration_remains_keyless(self):
        with synthetic_release() as (_, study_path, _):
            grant_path = study_path.parent / "live-grant.json"
            write_once(grant_path, release.make_grant(study_path, False))
            gate = Mock(side_effect=ContractError("synthetic missing acceptance"))
            with patch.object(release, "offline_readiness", gate):
                checked = release.preflight(study_path, grant_path, "all", "provider-config")
                self.assertTrue(checked["configuration_only"])
                self.assertEqual(checked["readiness_included_micro_usd"], 0)
                self.assertFalse(checked["credentials_read"])
                gate.assert_not_called()
                with self.assertRaisesRegex(ContractError, "missing acceptance"):
                    release.preflight(study_path, grant_path, "all", "provider", supervisor_agent="/root/p4_release")
                gate.assert_called_once()

    def test_claim_is_immutable_separate_and_cannot_authorize_a_closed_parent(self):
        with synthetic_release(isolate_claim=True) as (directory, study_path, _):
            grant_path = study_path.parent / "live-grant.json"
            write_once(grant_path, release.make_grant(study_path, False))
            old = directory / "live-study-remaining-pairs-v1.json"
            old.write_bytes(b'{"synthetic_closed_parent":true}\n')
            with patch.object(release, "offline_readiness", return_value={"synthetic_gate": True}):
                checked = release.preflight(study_path, grant_path, "all", "provider", supervisor_agent="/root/p4_release")
                record = release.claim(checked)
                self.assertEqual(release.claim(checked), record)
                self.assertEqual(old.read_bytes(), b'{"synthetic_closed_parent":true}\n')
                changed = {**checked, "cap_micro_usd": 1_200_000_001}
                with self.assertRaises(ContractError):
                    release.claim(changed)
            closed = directory / "closed-run"
            closed.mkdir()
            write_once(closed / "outcome.json", {"kind": "synthetic-closed-parent"})
            with patch.object(release, "paths", return_value=(closed, directory / "unused-journal")), \
                    self.assertRaisesRegex(ContractError, "closed P4 parent"):
                release.preflight(study_path, grant_path, "all", "provider-config")

    def test_started_parent_rejects_provider_and_mock_before_acceptance_or_keys(self):
        with synthetic_release() as (directory, study_path, _):
            started = directory / "started-run"
            started.mkdir()
            write_once(started / "started.json", {"kind": "synthetic-started-parent"})
            with patch.object(release, "paths", return_value=(started, directory / "unused-journal")), \
                    patch.object(release, "offline_readiness", side_effect=AssertionError("gate after already-started rejection")):
                for mode, fixture in (("provider", False), ("mock", True)):
                    grant_path = study_path.parent / (mode + "-grant.json")
                    write_once(grant_path, release.make_grant(study_path, fixture))
                    with self.subTest(mode=mode), self.assertRaisesRegex(ContractError, "started P4 parent"):
                        release.preflight(study_path, grant_path, "all", mode, supervisor_agent="/root/p4_release")
