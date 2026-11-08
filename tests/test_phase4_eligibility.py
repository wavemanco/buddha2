"""Synthetic-only checks; no actual corpus, legacy paths, SDK or keys."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest
from followups.phase4_cm1_v1 import eligibility as e


class EligibilityTests(unittest.TestCase):
    def rows(self, n=40):
        return [{"id": f"task-{i:03}", "prompt": f"Synthetic distinct task {i}"} for i in range(n)]

    def build(self, rows, **changes):
        args = dict(source_sha256=e.SOURCE_SHA256, frozen_method_sha256="1" * 64,
            exposure_inventory_sha256="2" * 64, excluded_source_ids=[],
            excluded_prompt_hashes=[], exposure_coverage_complete=True)
        return e.build_manifest(rows, **(args | changes))

    def test_exact_rank_order_and_no_content_output(self):
        rows = self.rows()
        result = self.build(rows)
        expected = sorted((r["id"] for r in rows), key=lambda v: (hashlib.sha256(("P4-CM1-v1|" + v).encode()).hexdigest(), v))[:24]
        self.assertEqual([r["source_task_id"] for r in result["selected"]], expected)
        self.assertEqual(self.build(list(reversed(rows))), result)
        self.assertNotIn("Synthetic distinct task", json.dumps(result))

    def test_known_ids_hashes_and_normalized_duplicates_cannot_evade_exclusion(self):
        rows = self.rows()
        rows += [{"id": "a-duplicate", "prompt": "  SYNTHETIC\tDISTINCT task 0  "}]
        result = self.build(rows, excluded_source_ids=["task-000"],
            excluded_prompt_hashes=[digest(e.normalize(rows[1]["prompt"]))])
        self.assertEqual(result["duplicate_rows_collapsed"], 1)
        self.assertEqual(result["excluded_prompt_units"], 2)
        self.assertFalse({"task-000", "a-duplicate", "task-001"} & {r["source_task_id"] for r in result["selected"]})

    def test_nfkc_duplicates_use_lexical_id_and_shortfall_selects_nothing(self):
        rows = [{"id": "z", "prompt": "ＦＯＯ"}, {"id": "a", "prompt": "foo"}]
        result = self.build(rows)
        self.assertEqual(result["inventory"][0]["source_task_id"], "a")
        self.assertEqual(result["inventory"][0]["duplicate_source_ids"], ["z"])
        self.assertEqual(result["eligible_prompt_units"], 1)
        self.assertEqual(result["selected"], [])
        self.assertFalse(result["eligibility_passed"])

    def test_invalid_identity_coverage_or_rows_fail(self):
        for changes in ({"exposure_coverage_complete": False}, {"source_sha256": "0" * 64},
                        {"frozen_method_sha256": None}, {"excluded_source_ids": "task-0"},
                        {"excluded_prompt_hashes": ["bad"]}):
            with self.subTest(changes=changes), self.assertRaises(ContractError):
                self.build(self.rows(), **changes)
        for rows in ([], [{"id": "x", "prompt": "a"}, {"id": "x", "prompt": "b"}],
                     [{"id": "x", "prompt": ""}], [{"id": "x\x00", "prompt": "a"}]):
            with self.subTest(rows=rows), self.assertRaises(ContractError):
                self.build(rows)

    def test_intake_checks_freeze_proof_and_exposure_before_source_open(self):
        with patch.object(Path, "read_bytes", side_effect=AssertionError("must not read any source")):
            with self.assertRaises(ContractError):
                e.intake(e.SOURCE_PATH, freeze={}, exposure_audit_path=Path("absent"), eligibility_proof={})
            freeze = {"accepted": True, "method_sha256": "1" * 64, "source_sha256": e.SOURCE_SHA256,
                      "eligibility_proof_sha256": "0" * 64}
            with self.assertRaises(ContractError):
                e.intake(e.SOURCE_PATH, freeze=freeze, exposure_audit_path=Path("absent"), eligibility_proof={"passed": True})

    def test_actual_wrapper_on_synthetic_files_and_changed_bytes_reject(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            source, audit_path = base / "synthetic.jsonl", base / "audit.json"
            source.write_text("".join(json.dumps(r) + "\n" for r in self.rows()), encoding="utf-8")
            def alias(i):
                return {"source_task_id": f"excluded-{i}", "normalized_prompt_sha256": digest(str(i))}
            audit = {"kind": "phase4-cm1-exposure-audit-v1", "known_exclusions": {
                "historical_wildchat": {"aliases": [alias(i) for i in range(263)]},
                "curated": {"aliases": [alias(i + 263) for i in range(100)]},
                "prior_synthetic_and_muce": {"aliases": [digest(str(i)) for i in range(50)]}}}
            audit_path.write_text(json.dumps(audit), encoding="utf-8")
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            audit_hash = hashlib.sha256(audit_path.read_bytes()).hexdigest()
            proof = {"passed": True, "exposure_inventory_sha256": audit_hash}
            freeze = {"accepted": True, "method_sha256": "1" * 64, "source_sha256": source_hash,
                      "exposure_inventory_sha256": audit_hash, "eligibility_proof_sha256": digest(proof)}
            with patch.object(e, "SOURCE_PATH", source), patch.object(e, "SOURCE_SHA256", source_hash), patch.object(e, "SOURCE_ROWS", 40):
                result = e.intake(source, freeze=freeze, exposure_audit_path=audit_path, eligibility_proof=proof)
                self.assertEqual(result["selected_count"], 24)
                original_read = Path.read_bytes

                def metadata_only(path):
                    if path == source:
                        raise AssertionError("invalid exposure must fail before corpus access")
                    return original_read(path)

                with patch.object(Path, "read_bytes", metadata_only):
                    with self.assertRaises(ContractError):
                        e.intake(source, freeze=freeze | {"exposure_inventory_sha256": "0" * 64},
                                 exposure_audit_path=audit_path, eligibility_proof=proof)
                    audit["known_exclusions"]["historical_wildchat"]["aliases"][0] = alias(1)
                    audit_path.write_text(json.dumps(audit), encoding="utf-8")
                    bad_hash = hashlib.sha256(original_read(audit_path)).hexdigest()
                    bad_proof = proof | {"exposure_inventory_sha256": bad_hash}
                    bad_freeze = freeze | {"exposure_inventory_sha256": bad_hash,
                                           "eligibility_proof_sha256": digest(bad_proof)}
                    with self.assertRaises(ContractError):
                        e.intake(source, freeze=bad_freeze, exposure_audit_path=audit_path,
                                 eligibility_proof=bad_proof)
                audit["known_exclusions"]["historical_wildchat"]["aliases"][0] = alias(0)
                audit_path.write_text(json.dumps(audit), encoding="utf-8")
                source.write_text("changed", encoding="utf-8")
                with self.assertRaises(ContractError):
                    e.intake(source, freeze=freeze, exposure_audit_path=audit_path, eligibility_proof=proof)


if __name__ == "__main__":
    unittest.main()
