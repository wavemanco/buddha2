"""Packet boundary checks independent of the native pilot's synthetic outcomes."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from .support import BASE, ROOT

spec = importlib.util.spec_from_file_location("hi_public_packet", ROOT / "evidence/phase3a-h1-integrated-v1/package_public.py")
assert spec is not None and spec.loader is not None
packet = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packet)


def fixture_release(root):
    evidence = root / "evidence" / packet.PREFIX
    release = root / "runs" / packet.PREFIX / "verification/release"
    evidence.mkdir(parents=True)
    release.mkdir(parents=True)
    code = root / "code.py"
    code.write_bytes(b"frozen source\n")
    source = {"files": {"code.py": packet.digest(code.read_bytes())}}
    study = {"source": source, "source_sha256": packet.digest(packet.canonical(source["files"])),
             "runtime_sha256": "a" * 64, "policy_sha256": "b" * 64, "launcher_sha256": "c" * 64}
    study["study_sha256"] = packet.digest(packet.canonical(study))
    bindings = {k: study[k] for k in ("study_sha256", "source_sha256", "runtime_sha256", "policy_sha256", "launcher_sha256")}
    gate = {**bindings, "passed": True, "checks": {}}
    groups = ("static", "matrix", "replay", "tests", "windows-tests", "launcher", "inspect", "preservation", "regression", "native-fixtures")
    for name in groups:
        target = release.parent / (name + ".json")
        target.write_text(json.dumps({**bindings, "passed": True}), encoding="utf-8")
        gate["checks"][name] = {"path": f"/results/{packet.PREFIX}/verification/{name}.json",
                                "sha256": packet.digest(target.read_bytes())}
    (release / "study.json").write_text(json.dumps(study), encoding="utf-8")
    (release / "offline-gate.json").write_text(json.dumps(gate), encoding="utf-8")
    acceptance = {**bindings, "passed": True,
                  "offline_gate_file_sha256": packet.digest((release / "offline-gate.json").read_bytes())}
    (evidence / "independent-acceptance.json").write_text(json.dumps(acceptance), encoding="utf-8")
    return evidence, release, code, study, bindings


class PacketTests(unittest.TestCase):
    def test_only_exact_receipt_authenticated_offline_names_can_cross_stream_filter(self):
        allowed = packet.authenticated_offline_streams()
        self.assertEqual(len(allowed), 14)
        self.assertEqual(set(allowed), packet.OFFLINE_NAMES)
        for name in allowed:
            self.assertFalse(packet.public(name))
            self.assertTrue(packet.public(name, allowed))
            for altered in (name + ".extra", name.replace("phase2-release-r018", "phase3a-h1-integrated-v1")):
                with patch.object(Path, "lstat", side_effect=AssertionError("stream metadata read")):
                    with self.assertRaises(ValueError):
                        packet.safe(altered, offline_streams=allowed)
        with patch.object(Path, "read_bytes", return_value=b"{}"), self.assertRaisesRegex(ValueError, "receipt changed"):
            packet.authenticated_offline_streams()

    def test_gate_group_cannot_override_frozen_source_bindings(self):
        from .verify import BINDINGS, record

        study = {name: str(index) * 64 for index, name in enumerate(BINDINGS)}
        BASE.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="record-bindings-", dir=BASE) as directory:
            target = Path(directory)
            record(target, "test", study, {"passed": True, "source_sha256": "foreign"})
            value = json.loads((target / "test.json").read_bytes())
            self.assertEqual({name: value[name] for name in BINDINGS}, study)

    def test_private_stream_and_traversal_names_are_rejected_before_metadata(self):
        for name in ("a/Credential-Binding.JSON/x", "a/.writer.lock", "a/.env/x", "a/Auth.JSON", "a/Credentials.Json",
                     "a/provider.stdout.log", "a/STDERR", "../a", "/a", "a\\b", "a/./b", "a//b", "C:/a"):
            with self.subTest(name=name), patch.object(Path, "lstat", side_effect=AssertionError("metadata read")):
                with self.assertRaises(ValueError):
                    packet.safe(name, missing=True)

    def test_existing_link_ancestor_rejected_even_when_descendant_is_missing(self):
        BASE.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="packet-link-", dir=BASE) as directory:
            root = Path(directory)
            (root / "real").mkdir()
            (root / "link").symlink_to(root / "real", target_is_directory=True)
            with patch.object(packet, "ROOT", root), self.assertRaises(ValueError):
                packet.safe("link/missing/file.json", missing=True)

    def test_tampered_frozen_source_cannot_be_packaged_or_overwrite_existing_packet(self):
        BASE.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="packet-source-", dir=BASE) as directory:
            root = Path(directory)
            evidence, release, code, _, _ = fixture_release(root)
            code.write_bytes(b"tampered source\n")
            with patch.object(packet, "ROOT", root), self.assertRaisesRegex(ValueError, "source drift"):
                packet.package(release.parent)
            self.assertFalse((evidence / "offline-kit-v1.zip").exists())
            retained = evidence / "offline-kit-v1.zip"
            retained.write_bytes(b"retained prior artifact")
            with patch.object(packet, "ROOT", root), self.assertRaisesRegex(ValueError, "already exists"):
                packet.package(release.parent)
            self.assertEqual(retained.read_bytes(), b"retained prior artifact")

    def test_closed_mock_packet_preserves_failure_and_excludes_private_stream_names(self):
        BASE.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="packet-close-", dir=BASE) as directory:
            root = Path(directory)
            evidence, release, _, study, bindings = fixture_release(root)
            run = root / "runs" / packet.PREFIX / "native" / study["study_sha256"] / "mock"
            reports = run / "reports/final"
            reports.mkdir(parents=True)
            names = [name + ".json" for name in ("rows", "coverage", "analysis", "summary", "accounting", "protocol", "readiness")]
            names.append("PHASE3A_REPORT.md")
            for name in names:
                value = {"fixture": True, "study_sha256": study["study_sha256"], "scientific_complete": False, "status": "incomplete"}
                (reports / name).write_text(json.dumps(value), encoding="utf-8")
            journal = root / "runs" / packet.PREFIX / study["study_sha256"] / "mock/journal"
            journal.mkdir(parents=True)
            for name in ("manifest.json", "events.jsonl"):
                (journal / name).write_text("{}\n", encoding="utf-8")
            # These inaccessible descendants must be skipped before classification.
            for name in ("Credential-Binding.JSON", "provider.stdout.log", "stderr-folder"):
                (run / name).symlink_to(root / "missing", target_is_directory=True)
            outcome = {**bindings, "kind": "phase3a-hi-outcome-v1", "closed": True, "fixture": True,
                       "scientific_complete": False, "run": run.relative_to(root).as_posix(),
                       "journal": journal.relative_to(root).as_posix(),
                       "report_sha256": {name: packet.digest((reports / name).read_bytes()) for name in names}}
            outcome_path, review_path = evidence / "mock-outcome.json", evidence / "mock-review.json"
            outcome_path.write_text(json.dumps(outcome), encoding="utf-8")
            review = {**bindings, "passed": True, "fixture": True,
                      "outcome_file_sha256": packet.digest(outcome_path.read_bytes())}
            review_path.write_text(json.dumps(review), encoding="utf-8")
            with patch.object(packet, "ROOT", root):
                result = packet.package(release.parent, mode="mock-closure", outcome=outcome_path, review=review_path)
            with zipfile.ZipFile(root / result["archive"]) as zipped:
                self.assertTrue(all(packet.public(name) for name in zipped.namelist()))
                saved = json.loads(zipped.read(outcome_path.relative_to(root).as_posix()))
                self.assertFalse(saved["scientific_complete"])
                self.assertIsNone(zipped.testzip())
