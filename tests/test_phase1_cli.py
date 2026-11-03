"""The usable workflow must preserve its readiness and held-out boundaries."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError, read_json, write_once
from buddha2.phase1 import (
    fixture_population,
    freeze_audit,
    judge,
    record_readiness,
    report_stage,
    stage_population,
)


class Phase1WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.prepared, self.run = self.root / "prepared", self.root / "run"
        self.rubric = self.root / "rubric.md"
        self.rubric.write_text("Compare creative ideas. Return choice and reason JSON.")
        fixture_population(self.prepared)
        stage_population(self.prepared, self.run, self.rubric, "sha256:" + "a" * 64)

    def judge(self, stage):
        return judge(self.run, stage, 5_000_000, fixture=True)

    def test_full_fixture_is_replayable_and_cannot_be_read_as_live_evidence(self):
        first = self.judge("calibration")
        self.assertEqual(first["finalized_presentations"], 2)
        self.assertEqual(self.judge("calibration")["attempts"], 2)
        record_readiness(self.run, "Synthetic readiness review only.")
        self.assertEqual(self.judge("calibration")["finalized_presentations"], 24)
        report_stage(self.prepared, self.run, "calibration")
        freeze_audit(self.run, self.rubric, "Keep the fixture rubric.")
        self.assertEqual(self.judge("audit")["finalized_presentations"], 48)
        audit = report_stage(self.prepared, self.run, "audit")
        self.assertEqual(audit["human_agreement"]["successes"], 12)
        self.assertTrue(audit["fixture"])
        self.assertEqual(audit["execution"]["provider_calls"], 0)
        self.assertEqual(report_stage(self.prepared, self.run, "audit"), audit)
        calibration = read_json(self.run / "assessments" / "calibration.json")
        self.assertEqual(report_stage(self.prepared, self.run, "calibration"), calibration)
        self.assertEqual(self.judge("audit")["attempts"], 48)

    def test_audit_gate_fails_before_any_transport_construction(self):
        with patch("buddha2.phase1.DirectAnthropicTransport") as client:
            with self.assertRaisesRegex(ContractError, "audit.*freeze"):
                judge(self.run, "audit", 5_000_000, fixture=False)
            client.assert_not_called()
        with self.assertRaisesRegex(ContractError, "readiness"):
            record_readiness(self.run, "Too soon.")
        with self.assertRaisesRegex(ContractError, "calibration"):
            freeze_audit(self.run, self.rubric, "Too soon.")

    def test_invalid_budget_refuses_before_credential_or_transport_access(self):
        with patch("buddha2.phase1.DirectAnthropicTransport") as client:
            for cap in (0, -1, True, 5_000_001):
                with self.assertRaisesRegex(ContractError, "authorization"):
                    judge(self.run, "calibration", cap, fixture=False)
            client.assert_not_called()

    def test_no_audit_label_open_until_all_predictions_are_committed(self):
        from buddha2 import phase1
        real_reader = phase1.read_json
        opened = []

        def tracked(path):
            opened.append(path.name)
            return real_reader(path)

        with patch("buddha2.phase1.read_json", side_effect=tracked):
            with self.assertRaisesRegex(ContractError, "complete"):
                report_stage(self.prepared, self.run, "audit")
        self.assertNotIn("labels.audit.json", opened)
        self.assertFalse((self.run / "controls" / "audit-predictions.json").exists())

    def test_staging_refuses_corrupted_population_and_label_files_are_not_copied(self):
        names = {p.name for p in self.run.iterdir()}
        self.assertFalse(any("label" in name or "private" in name for name in names))
        self.assertEqual(names, {"bundle.json", "plan.json", "preparation.json", "initial-rubric.md"})
        value = read_json(self.prepared / "pairs.json")
        value[0]["responses"][0]["text"] = "Corrupted answer"
        (self.prepared / "pairs.json").write_text(json.dumps(value))
        with self.assertRaisesRegex(ContractError, "identity|hash"):
            stage_population(self.prepared, self.root / "other", self.rubric, "sha256:" + "a" * 64)

    def test_staging_refuses_prompt_leakage_across_stages(self):
        # The structural gate is independently checked even when hashes match.
        from buddha2.phase1 import validate_worklists
        pairs = read_json(self.prepared / "pairs.json")
        work = read_json(self.prepared / "worklists.json")
        corrupt = copy.deepcopy(work)
        corrupt["audit"]["pair_ids"][0] = corrupt["calibration"]["pair_ids"][0]
        with self.assertRaises(ContractError):
            validate_worklists(pairs, corrupt)

    def test_staging_rejects_unknown_profile_before_dispatch(self):
        value = read_json(self.run / "plan.json")
        value["profile"]["model"] = "unreviewed-model"
        (self.run / "plan.json").unlink()
        write_once(self.run / "plan.json", value)
        with self.assertRaisesRegex(ContractError, "identity|profile"):
            self.judge("calibration")

    def test_changed_freeze_refuses_before_transport_construction_or_label_access(self):
        self.judge("calibration")
        record_readiness(self.run, "Synthetic review.")
        self.judge("calibration")
        report_stage(self.prepared, self.run, "calibration")
        freeze_audit(self.run, self.rubric, "Keep rubric.")
        path = self.run / "controls" / "audit-freeze.json"
        original = read_json(path)
        for field in ("rubric", "rubric_sha256", "calibration_sha256", "calibration_judgments_sha256"):
            corrupted = {**original, field: "changed"}
            path.write_text(json.dumps(corrupted))
            with patch("buddha2.phase1.DirectAnthropicTransport") as client:
                with self.assertRaisesRegex(ContractError, "freeze"):
                    judge(self.run, "audit", 5_000_000, fixture=False)
                client.assert_not_called()
        path.write_text(json.dumps(original))
        self.judge("audit")
        corrupted = {**original, "rubric": "Another self-consistent rubric."}
        corrupted["rubric_sha256"] = __import__("hashlib").sha256(corrupted["rubric"].encode()).hexdigest()
        path.write_text(json.dumps(corrupted))
        with self.assertRaisesRegex(ContractError, "executed rubric"):
            report_stage(self.prepared, self.run, "audit")
        self.assertFalse((self.run / "controls" / "audit-predictions.json").exists())


if __name__ == "__main__":
    unittest.main()
