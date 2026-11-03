"""The provider gate requires exact passed checks and unchanged evidence files."""
import json
import tempfile
import unittest
from pathlib import Path

from followups.rank_format_v1 import support


class SupportTests(unittest.TestCase):
    def test_paths_cannot_escape_or_follow_links(self):
        with self.assertRaises(support.ContractError):
            support.checked_path("../escape", output=True)
        with self.assertRaises(support.ContractError):
            support.checked_path("/tmp/elsewhere", output=True)
        with tempfile.TemporaryDirectory(dir=support.RESULTS) as directory:
            path = Path(directory)
            (path / "file.json").write_text("{}", encoding="utf-8")
            (path / "link.json").symlink_to(path / "file.json")
            with self.assertRaises(support.ContractError):
                support.checked_path(path / "link.json")

    def test_readiness_requires_exact_booleans_binding_and_evidence(self):
        with tempfile.TemporaryDirectory(dir=support.RESULTS) as directory:
            path = Path(directory)
            study = {name: char * 64 for name, char in
                     (("study_sha256", "a"), ("source_sha256", "b"), ("policy_sha256", "c"))}
            (path / "study.json").write_text(json.dumps(study), encoding="utf-8")
            names = ("normalizer", "corpus_reuse", "sdk_mocks", "launcher", "static", "preservation")
            evidence = {}
            for name in names:
                file = path / (name + ".json")
                file.write_text(json.dumps({"kind": "p2bn-offline-check-v1", "group": name,
                                            "passed": True, **study}), encoding="utf-8")
                evidence[name] = {"path": str(file), "sha256": support.file_hash(file)}
            gate = {"kind": "p2bn-offline-readiness-v1", "passed": True, **study,
                    "checks": dict.fromkeys(names, True), "evidence": evidence}

            def save(value):
                (path / "readiness.json").write_text(json.dumps(value), encoding="utf-8")

            save(gate)
            support.validate_gate(path / "study.json", study)
            mutations: list[dict] = [{"passed": False}, {"source_sha256": "0" * 64},
                                     {"checks": dict.fromkeys(names, 1)}, {"evidence": {}}]
            for mutation in mutations:
                save(gate | mutation)
                with self.assertRaises(support.ContractError):
                    support.validate_gate(path / "study.json", study)
            save(gate)
            (path / "normalizer.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(support.ContractError):
                support.validate_gate(path / "study.json", study)

            # Even an updated hash cannot turn unrelated content into a pass.
            evidence["normalizer"]["sha256"] = support.file_hash(path / "normalizer.json")
            save(gate)
            with self.assertRaises(support.ContractError):
                support.validate_gate(path / "study.json", study)
