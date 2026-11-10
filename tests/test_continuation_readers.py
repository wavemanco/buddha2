"""All continuation consumers accept the same allowed saved-result size."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest, read_json, write_once
from followups.phase3b_seq2_v1.support import BASE, seal
from followups.phase4_cm1_v1 import policy, release, workflow


class ContinuationReaderTests(unittest.TestCase):
    def test_allowed_saved_result_survives_all_continuation_consumers(self):
        parent = BASE / "continuation-reader-tests"
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as raw:
            root = Path(raw)
            execution = "a" * 64
            source = seal({"files": {}})
            task = {"id": "synthetic-reader-task"}
            result = {"status": "complete", "padding": "x" * 2_000_001}
            result_path, opened_path, closure_path = [root / name for name in
                                                       ("result.json", "open.json", "closure.json")]
            opened = seal({"child_sha256": execution, "task": task,
                           "allocation": {"child_kind": "assessment", "pair": "p4-01"}})
            closure = seal({"child_sha256": execution, "open_sha256": opened["sha256"],
                            "result_sha256": digest(result)})
            for target, value in ((result_path, result), (opened_path, opened), (closure_path, closure)):
                write_once(target, value)
            self.assertLess(result_path.stat().st_size, policy.artifact_limits()["saved_artifact_bytes"])
            with self.assertRaises(ContractError):
                read_json(result_path)
            reference = {"execution_study_sha256": execution}
            entry = {"kind": "assessment", "pair": "p4-01", "journal": reference,
                     "result": result_path, "open": opened_path, "closure": closure_path}
            state = {"spent_micro_usd": 100, "reserved_micro_usd": 0, "attempts": 1,
                     "intents": {}, "results": {}, "active_unsettled_intents": [],
                     "durable_unknown_results": 0,
                     "transport_audit_summary": {"missing_or_invalid_slots": []}}
            manifest = {"inputs": {"policy": {}}}
            study = {"method_sha256": "b" * 64, "source_sha256": source["sha256"],
                     "development": [], "continuation": {"children": [entry],
                         "fixture": True, "confirmation_manifest": None}}
            with patch.object(release, "_referenced", side_effect=lambda target: target), \
                    patch.object(workflow.accounting, "read_reference", return_value=(state, manifest)), \
                    patch.object(workflow, "worklist", return_value={}):
                release.validate_origin_entry(entry)
                scope = release.continuation_scope(study)
                self.assertEqual(scope["known_spent_micro_usd"], 100)
                book = workflow.Coordinator(study, root, SimpleNamespace(fixture=True))
                self.assertEqual(book.origin_results[("assessment", "p4-01")], result)
                book.continuation["compatibility"] = result_path
                self.assertEqual(book.compatibility(), result)

                controls = ("model_ids", "role_profiles", "author_selector", "upstream_commits",
                            "seed_procedure_sha256", "seed_tree_sha256", "editor_profile",
                            "reservation_policy_sha256", "adaptive", "fixed", "scoring")
                method = dict.fromkeys(controls, "synthetic")
                previous = {"method": method, "seed_tree": {}, "source": source,
                            "source_sha256": source["sha256"]}
                previous["study_sha256"] = digest(previous)
                previous_path = root / "study.json"
                write_once(previous_path, previous)
                with patch.object(release, "continuation_children", return_value=[entry]), \
                        patch.object(release, "source_identity", return_value=source), \
                        patch.object(release, "_records", return_value=(None, None)), \
                        patch.object(release, "_method", return_value=method), \
                        patch.object(workflow.strategy, "seed_tree", return_value={}), \
                        patch.object(workflow, "_origin_unit_state", return_value=state):
                    proof = workflow.compatibility(previous_path, root / "compatibility.json", fixture=True)
                self.assertTrue(proof["passed"])
                self.assertEqual(proof["provider_calls"], 0)
