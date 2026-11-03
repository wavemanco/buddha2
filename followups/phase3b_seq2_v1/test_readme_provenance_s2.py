"""One explicit document alias, unchanged closed source, and no stream widening."""
from __future__ import annotations

import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest

from . import support


class ReadmeProvenanceCases(unittest.TestCase):
    def test_actual_postrefresh_parent_and_current_documents(self):
        parent, manifest = support._parent_source()
        source = support.source_identity()
        self.assertEqual(parent["sha256"], support.PARENT_SOURCE_SHA)
        self.assertEqual(digest(parent["files"]), support.PARENT_SOURCE_SHA)
        self.assertEqual(parent["files"]["README.md"], support.LEGACY_README_SHA)
        self.assertEqual(source["files"]["README_LEGACY.md"], support.LEGACY_README_SHA)
        self.assertEqual(source["files"]["README.md"], support.file_hash(support.ROOT / "README.md"))
        self.assertNotEqual(source["files"]["README.md"], support.LEGACY_README_SHA)
        self.assertEqual(source["historical_document_alias"], {
            "README.md": {"retained_path": "README_LEGACY.md", "sha256": support.LEGACY_README_SHA}})
        for name in (".gitattributes", "docs/ATTRIBUTIONS.md", "docs/RESEARCH_METHOD.md", support.README_AUTHORITY,
            support.PARENT_STUDY, support.PARENT_HISTORY):
            self.assertEqual(source["files"][name], support.file_hash(support.ROOT / name))
        self.assertIn(support.PARENT_STUDY, manifest["member_sha256"])

    def test_actual_preservation_retains_all_previous_archive_checks(self):
        result = support.preserve()
        self.assertTrue(result["passed"])
        self.assertEqual(set(result["closed_ancestor_archives"]), {
            "evidence/phase3a-rc1-pilot-v1/offline-kit-v1.zip",
            "evidence/phase3a-rc1-pilot-v1/live-outcome-v1.zip",
            "evidence/phase3a-c1-completion-v4/live-outcome-v1.zip",
            "evidence/phase3a-readiness-recovery-v1/live-outcome-v1.zip"})
        self.assertFalse(result["protected_original_accessed"])
        self.assertFalse(result["private_worktree_accessed"])

    def test_legacy_and_other_current_parent_tampering_fail(self):
        original = support.file_hash
        for name in ("README_LEGACY.md", "followups/phase3a_readiness_recovery_v1/accounting.py"):
            def changed(path):
                return "0" * 64 if Path(path) == support.ROOT / name else original(path)
            with self.subTest(path=name), patch.object(support, "file_hash", side_effect=changed):
                with self.assertRaises(ContractError):
                    support.source_identity()

    def test_extra_document_alias_is_rejected(self):
        original = support.read
        def changed(path):
            value = original(path)
            if Path(path) == support.ROOT / support.README_AUTHORITY:
                value = copy.deepcopy(value)
                value["historical_document_alias"]["DECISIONS.md"] = {"retained_path": "other.md", "sha256": "0" * 64}
            return value
        with patch.object(support, "read", side_effect=changed), self.assertRaises(ContractError):
            support.source_identity()

    def test_new_document_fingerprint_is_bound_without_faking_parent(self):
        original = support.file_hash
        baseline = support.source_identity()
        def changed(path):
            return "0" * 64 if Path(path) == support.ROOT / "README.md" else original(path)
        with patch.object(support, "file_hash", side_effect=changed):
            altered = support.source_identity()
        self.assertNotEqual(altered["sha256"], baseline["sha256"])
        self.assertEqual(altered["parent_source_sha256"], support.PARENT_SOURCE_SHA)
        self.assertEqual(altered["files"]["README_LEGACY.md"], support.LEGACY_README_SHA)

    def test_exact_fourteen_classification_precedes_stream_metadata(self):
        parent, _ = support._parent_source()
        streams = support._offline_streams(parent["files"])
        self.assertEqual(len(streams), 14)
        for name in ("evidence/unclassified.stdout.log", "followups/__pycache__/probe.py", ".env"):
            with self.subTest(path=name), patch.object(Path, "lstat", side_effect=AssertionError("forbidden metadata")):
                with self.assertRaises(ContractError):
                    support._parent_file_hash(name, "0" * 64, streams)


if __name__ == "__main__":
    unittest.main()
