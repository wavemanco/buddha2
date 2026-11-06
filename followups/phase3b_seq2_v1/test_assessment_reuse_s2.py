"""Actual-parent assessment preparation is immutable, offline, and never live authority."""
from __future__ import annotations

import copy
import json
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError

from . import assessment_reuse as reuse
from . import support


@unittest.skipUnless(os.environ.get("BUDDHA2_ASSESSMENT_REUSE_STUDY"), "requires the approved saved parent")
class AssessmentReuseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.study = Path(os.environ["BUDDHA2_ASSESSMENT_REUSE_STUDY"])
        parent = support.ROOT / "runs/phase3b-seq2-v1"
        native = parent / "native" / reuse.PARENT_STUDY / "live"
        cls.parent_files = (
            cls.study,
            support.ROOT / "evidence/phase3b-seq2-v1/timing-continuation-live-outcome-v1.json",
            native / "seals/p3b-01.json",
            native / "branches/p3b-01-adaptive.json",
            native / "branches/p3b-01-fixed.json",
            parent / reuse.PARENT_STUDY / "live/journal/events.jsonl",
        )
        cls.before = {path: reuse.file_hash(path) for path in cls.parent_files}
        cls.summary = reuse.prepare(cls.study, cls.fresh_output())
        cls.packet_path = Path(cls.summary["packet_path"])
        cls.packet = json.loads(cls.packet_path.read_text(encoding="utf-8"))

    @staticmethod
    def fresh_output():
        return support.BASE / "assessment-reuse" / ("test-" + uuid.uuid4().hex)

    def tampered_packet(self, body):
        target = self.fresh_output() / "assessment-reuse.json"
        target.parent.mkdir(parents=True)
        sealed = support.seal({key: value for key, value in body.items() if key != "sha256"})
        target.write_text(json.dumps(sealed, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        return target

    def test_actual_prepare_and_verify_preserve_parent_and_classify_exact_25_plus_8(self):
        self.assertEqual(reuse.verify(self.packet_path), self.summary)
        self.assertEqual({key: self.summary[key] for key in (
            "reused_results", "pending_requests", "complete_cached_assessments", "provider_calls",
            "live_execution_allowed")}, {
                "reused_results": 25, "pending_requests": 8, "complete_cached_assessments": 2,
                "provider_calls": 0, "live_execution_allowed": False})
        self.assertEqual(len(self.packet["worklist"]), 33)
        pending = [row for row in self.packet["worklist"] if row["disposition"] == "pending"]
        self.assertEqual(len(pending), 8)
        self.assertTrue(all(row["target"] == "c2" and row["role"] == "quality" for row in pending))
        self.assertEqual(sorted(row["slot_id"].rsplit(".", 1)[1] for row in pending),
                         [f"{head:02}" for head in range(2, 10)])
        self.assertEqual({path: reuse.file_hash(path) for path in self.parent_files}, self.before)

    def test_resealed_missing_work_body_or_changed_cached_identity_cannot_verify(self):
        for change in ("missing_row", "missing_request", "cached_identity"):
            with self.subTest(change=change):
                body = copy.deepcopy(self.packet)
                pending = next(row for row in body["worklist"] if row["disposition"] == "pending")
                if change == "missing_row":
                    body["worklist"].remove(pending)
                elif change == "missing_request":
                    del pending["request"]
                else:
                    cached = next(row for row in body["worklist"] if row["disposition"] == "reuse")
                    cached["result_sha256"] = "0" * 64
                with self.assertRaises(ContractError):
                    reuse.verify(self.tampered_packet(body))

    def test_changed_parent_hash_is_rejected_without_altering_parent_bytes(self):
        parent = support.ROOT / "runs/phase3b-seq2-v1/native" / reuse.PARENT_STUDY / "live/seals/p3b-01.json"
        original = reuse.file_hash
        observed = []

        def changed(path):
            if Path(path) == parent:
                observed.append(path)
                return "0" * 64
            return original(path)

        with patch.object(reuse, "file_hash", side_effect=changed), self.assertRaises(ContractError):
            reuse.verify(self.packet_path)
        self.assertTrue(observed)
        self.assertEqual(original(parent), self.before[parent])

    def test_closed_generation_root_cannot_be_preparation_output(self):
        closed = support.ROOT / "runs/phase3b-seq2-v1/native" / reuse.PARENT_STUDY / "live"
        with patch.object(reuse, "_build", side_effect=AssertionError("parent opened before output rejection")), \
                self.assertRaises(ContractError):
            reuse.prepare(self.study, closed)

    def test_private_packet_paths_are_rejected_before_metadata_or_content(self):
        for private in (".env", "auth.json", "credential-binding.json"):
            with self.subTest(private=private), \
                    patch.object(reuse, "read", side_effect=AssertionError("private content read")), \
                    patch.object(reuse, "file_hash", side_effect=AssertionError("private file hashed")), \
                    patch.object(Path, "lstat", side_effect=AssertionError("private metadata read")), \
                    self.assertRaises(ContractError):
                reuse.verify(support.BASE / "assessment-reuse" / private / "assessment-reuse.json")

    def test_changed_source_binding_rejects_before_parent_rebuild(self):
        body = copy.deepcopy(self.packet)
        body["source_sha256"] = "0" * 64
        packet = self.tampered_packet(body)
        with patch.object(reuse, "_build", side_effect=AssertionError("stale packet reached parent rebuild")), \
                self.assertRaises(ContractError):
            reuse.verify(packet)


if __name__ == "__main__":
    unittest.main()
