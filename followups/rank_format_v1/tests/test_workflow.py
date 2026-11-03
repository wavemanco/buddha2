"""Bounded follow-up proofs through the retained SDKs, without external sockets."""
from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError, read_json, write_once
from buddha2.phase2_am1_controls import CONTROL_POLICY
from buddha2.phase2_am1_mock import SDKMock
from buddha2.phase2_dispatch import Dispatcher, replay_dispatch, writer_lock
from followups.rank_format_v1 import workflow

CUTOFF = "2026-10-28T15:00:00Z"


class NativeMock(SDKMock):
    """Change only synthetic output shape/usage inside real SDK MockTransports."""

    def __init__(self, *, heads=1, content_fault=None, expensive=False, fault=None):
        super().__init__(partition="distinct", fault=fault)
        self.heads, self.content_fault, self.expensive = heads, content_fault, expensive
        self.content_fault_used = False

    def _apply_fault(self, role, slot, response):
        if role == "group":
            groups = ([list(range(10))] if self.heads == 1 else
                      [[i, i + 1] for i in range(0, 10, 2)] if self.heads == 5 else
                      [[i] for i in range(10)])
            response["choices"][0]["message"]["content"] = json.dumps({"groups": groups})
        if role == "quality" and self.expensive:
            response["usage"].update(input_tokens=900000, output_tokens=16000)
        if self.content_fault and not self.content_fault_used and self.content_fault.startswith(role):
            self.content_fault_used = True
            if role == "group":
                if self.content_fault.endswith("refusal"):
                    response["choices"][0]["message"]["refusal"] = "synthetic refusal"
                else:
                    response["choices"][0]["message"]["content"] = "not a partition"
            elif self.content_fault.endswith("refusal"):
                response["stop_reason"] = "refusal"
            else:
                response["content"][0]["text"] = '{"score":"five"}'
        return super()._apply_fault(role, slot, response)


class WorkflowTests(unittest.TestCase):
    preparation: tempfile.TemporaryDirectory
    prepared: Path
    study_path: Path
    study: dict
    grant: dict
    grant_path: Path

    @classmethod
    def setUpClass(cls):
        cls.preparation = tempfile.TemporaryDirectory(prefix="p2bn-preparation-", dir=workflow.RESULTS)
        cls.prepared = Path(cls.preparation.name)
        workflow.prepare(cls.prepared)
        cls.study_path = cls.prepared / "study.json"
        cls.study = read_json(cls.study_path)
        cls.grant = workflow.grant_template(cls.study_path, fixture=True, authorized=True)
        cls.grant_path = cls.prepared / "grant.json"
        write_once(cls.grant_path, cls.grant)

    @classmethod
    def tearDownClass(cls):
        cls.preparation.cleanup()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="p2bn-workflow-", dir=workflow.RESULTS)
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.run_path = self.directory / "run"
        self.journal = self.run_path / "journal"
        # The full source/parent reconstruction was exercised in setUpClass;
        # isolated scenario runs share that immutable expected definition.
        self.addCleanup(patch.stopall)
        patch.object(workflow, "_definition", return_value=copy.deepcopy(self.study)).start()
        patch.object(workflow, "_location", return_value=(self.run_path, self.journal)).start()

    def run_mock(self, mock):
        return workflow.run(self.study_path, self.grant_path, mock.transport, cutoff=CUTOFF)

    def test_frozen_corpus_reuse_derivation_and_no_call_initial_report(self):
        study = workflow.load_preparation(self.study_path)
        self.assertEqual(len(study["normalizations"]), 24)
        self.assertEqual(sum(r["reuse_original_C"] for r in study["normalizations"]), 20)
        self.assertEqual(len(study["reuse"]), 68)
        self.assertEqual(len(study["derived_orders"]), 4)
        self.assertEqual(len(study["slots"]), 44)
        self.assertEqual(study["candidate_costs"], {"A": 635220, "B": 1320486, "C-N": 1621512})
        self.assertFalse(self.grant["authorization"]["authorized"])
        saved = workflow.snapshot(self.study_path, self.grant_path, True, CUTOFF)
        self.assertEqual(saved["summary"]["attempts"], 0)
        self.assertEqual(saved["summary"]["reused_assessments"], 68)
        self.assertEqual(saved["decision"]["status"], "inconclusive")
        for row in study["derived_orders"]:
            child = workflow._derived(study, row, fixture=False)
            self.assertEqual(child["provenance"]["study_sha256"], study["study_sha256"])
            self.assertNotEqual(child["provenance"]["study_sha256"], workflow.PARENT_STUDY)
            workflow.validate_derivation(study, row, child, fixture=False)

    def test_actual_sdk_one_five_ten_heads_and_zero_call_resume(self):
        for heads, expected in ((1, 8), (5, 24), (10, 44)):
            with self.subTest(heads=heads):
                path = self.directory / str(heads)
                with patch.object(workflow, "_location", return_value=(path, path / "journal")), NativeMock(heads=heads) as mock:
                    summary = self.run_mock(mock)
                    self.assertEqual(mock.http_calls, expected)
                    self.assertEqual(summary["attempts"], expected)
                    self.assertEqual(summary["status"], "mock-complete")
                    self.assertEqual(summary["scored_new_assessments"], 4)
                    self.assertEqual(summary["reserved_micro_usd"], 0)
                    saved = workflow.snapshot(self.study_path, self.grant_path, True)
                    self.assertEqual(len(saved["rows"]), 72)
                    self.assertTrue(saved["decision"]["native_complete"])
                    self.assertIsNone(saved["decision"]["selected_method"])
                    self.assertIsNone(saved["decision"]["selected_procedure_sha256"])
                    self.assertIsNotNone(saved["decision"]["synthetic_selected_method"])
                    self.run_mock(mock)
                    self.assertEqual(mock.http_calls, expected)
                    for name in ("first", "replay"):
                        workflow.report(self.study_path, self.grant_path, path / name, True)
                    protocol = read_json(path / "first/protocol.json")
                    self.assertEqual(len(protocol["request_index"]), expected)
                    self.assertEqual(len(protocol["reuse"]), 68)
                    self.assertEqual(protocol["native_score_config"]["patience"], 0.8)
                    self.assertEqual(protocol["profiles"]["quality"]["output_config"]["effort"], "high")
                    self.assertEqual({r["role"] for r in protocol["request_index"]}, {"group", "quality"})
                    for artifact in (path / "first").iterdir():
                        self.assertEqual(artifact.read_bytes(), (path / "replay" / artifact.name).read_bytes())
                    self.assertEqual(mock.http_calls, expected)

    def test_known_invalid_or_refused_native_results_are_preserved_and_continue(self):
        for fault, status, calls in (("group-malformed", "invalid_group", 7),
                                     ("group-refusal", "group_refused", 7),
                                     ("quality-malformed", "invalid_quality", 8),
                                     ("quality-refusal", "quality_refused", 8)):
            with self.subTest(fault=fault):
                path = self.directory / fault
                with patch.object(workflow, "_location", return_value=(path, path / "journal")), NativeMock(content_fault=fault) as mock:
                    summary = self.run_mock(mock)
                    self.assertEqual(mock.http_calls, calls)
                    self.assertEqual(summary["scored_new_assessments"], 3)
                    self.assertEqual(summary["decision_status"], "inconclusive")
                    self.assertEqual(summary["reserved_micro_usd"], 0)
                    saved = workflow.snapshot(self.study_path, self.grant_path, True)
                    self.assertIn(status, [r["status"] for r in saved["rows"]])
                    self.assertTrue(all(value is None for value in saved["decision"]["mean_utility"].values()))
                    self.run_mock(mock)
                    self.assertEqual(mock.http_calls, calls)

    def test_unknown_usage_keeps_liability_and_blocks_all_new_calls(self):
        with NativeMock(fault="missing-write") as mock:
            summary = self.run_mock(mock)
            self.assertEqual(mock.http_calls, 1)
            self.assertEqual(summary["reserved_micro_usd"], 1661880)
            self.assertEqual(summary["scored_new_assessments"], 0)
            with self.assertRaises(ContractError):
                self.run_mock(mock)
            self.assertEqual(mock.http_calls, 1)
            saved = workflow.snapshot(self.study_path, self.grant_path, True)
            self.assertEqual(saved["coverage"]["slots"][mock.records[0]["slot_id"]], "unknown_liability")
            self.assertEqual(saved["summary"]["reserved_micro_usd"], 1661880)
            workflow.report(self.study_path, self.grant_path, self.directory / "unknown-report", True, CUTOFF)
            protocol = read_json(self.directory / "unknown-report/protocol.json")
            self.assertEqual(protocol["request_index"][0]["reserved_micro_usd"], 1661880)
            self.assertEqual(protocol["request_index"][0]["outcome"], "unknown_liability")

    def test_reservation_stop_does_not_reset_spend_or_skip_to_cheaper_order(self):
        with NativeMock(heads=10, expensive=True) as mock:
            summary = self.run_mock(mock)
            self.assertEqual(mock.http_calls, 5)
            self.assertGreater(summary["new_spent_micro_usd"], 18560000)
            self.assertLess(summary["new_spent_micro_usd"], 30000000)
            self.assertEqual(summary["reserved_micro_usd"], 0)
            self.assertEqual(summary["new_assessments"], 0)
            self.run_mock(mock)
            self.assertEqual(mock.http_calls, 5)
            self.assertEqual(replay_dispatch(self.journal)["spent_micro_usd"], summary["new_spent_micro_usd"])

    def test_interrupt_leaves_durable_intent_without_retry(self):
        with NativeMock() as mock, patch.object(mock.transport, "create", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.run_mock(mock)
            state = replay_dispatch(self.journal)
            self.assertEqual(state["attempts"], 1)
            self.assertEqual(state["reserved_micro_usd"], 1661880)
            with self.assertRaises(ContractError):
                self.run_mock(mock)
            self.assertEqual(mock.http_calls, 0)

    def test_concurrent_owner_rejects_before_http(self):
        with writer_lock(self.run_path / "owner"), NativeMock() as mock:
            with self.assertRaises(ContractError):
                self.run_mock(mock)
            self.assertEqual(mock.http_calls, 0)

    def test_partial_journal_foreign_request_rejected_before_earlier_missing_order(self):
        native = workflow._native()
        first = workflow._derived(self.study, self.study["derived_orders"][0], fixture=True)
        later = self.study["derived_orders"][-1]["order_id"] + ".group"
        with NativeMock() as mock:
            dispatcher = Dispatcher(self.journal, study_sha256=self.study["study_sha256"],
                slots=self.study["slots"], authorization=self.grant["authorization"],
                transport=mock.transport, control_policy=CONTROL_POLICY)
            mock.select("group", later)
            dispatcher.dispatch(later, "group", native.group_request(first))
            self.assertEqual(mock.http_calls, 1)
            with self.assertRaisesRegex(ContractError, "request identity"):
                self.run_mock(mock)
            self.assertEqual(mock.http_calls, 1)

    def test_derived_text_tamper_and_numeric_alias_preparation_reject(self):
        row = self.study["derived_orders"][0]
        child = workflow._derived(self.study, row, fixture=True)
        child["responses"][0]["text"] += " changed"
        with self.assertRaises(ContractError):
            workflow.validate_derivation(self.study, row, child, fixture=True)
        alternate = self.directory / "preparation"
        shutil.copytree(self.prepared, alternate)
        altered = read_json(alternate / "study.json")
        altered["policy"]["max_utf8_bytes"] = 65536.0
        (alternate / "study.json").write_bytes(workflow._canonical(altered))
        with self.assertRaisesRegex(ContractError, "immutable artifact"):
            workflow.load_preparation(alternate / "study.json")

    def test_parent_native_semantically_equal_byte_tamper_rejects(self):
        parent = self.directory / "parent"
        shutil.copytree(workflow.PARENT, parent)
        relative = self.study["reuse"][0]["portfolio_path"].replace("portfolios/", "native/").removesuffix(".json")
        path = parent / relative / "generations.jsonl"
        path.write_bytes(b" " + path.read_bytes())
        self.assertEqual(workflow._native().load_export(path.parent), read_json(parent / self.study["reuse"][0]["portfolio_path"]))
        manifest = read_json(parent / "manifest.json")
        with patch.object(workflow, "PARENT", parent), self.assertRaisesRegex(ContractError, "parent evidence"):
            workflow._parent_file(str(path.relative_to(parent)), manifest)

    def test_wrong_grant_and_invalid_cutoff_fail_before_http(self):
        altered = copy.deepcopy(self.grant)
        altered["authorization"]["cap_micro_usd"] = 31000000
        altered["grant_sha256"] = workflow.digest({k: v for k, v in altered.items() if k != "grant_sha256"})
        path = self.directory / "wrong-grant.json"
        write_once(path, altered)
        with NativeMock() as mock:
            with self.assertRaises(ContractError):
                workflow.run(self.study_path, path, mock.transport)
            with self.assertRaises(ValueError):
                workflow.run(self.study_path, self.grant_path, mock.transport, "not-UTC")
            self.assertEqual(mock.http_calls, 0)


if __name__ == "__main__":
    unittest.main()
