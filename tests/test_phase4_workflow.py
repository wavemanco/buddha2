"""Parent allocation and generation/judging separation; no providers or holdout access."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest, file_hash, write_once
from followups.phase3b_seq2_v1.support import BASE
from followups.phase4_cm1_v1 import policy, workflow
from tests.test_phase2_contracts import example


def study():
    return {"study_sha256": "a" * 64, "source_sha256": "b" * 64,
        "launcher_sha256": "c" * 64, "authorization_sha256": file_hash(policy.AUTHORITY),
        "execution_tag": "synthetic-p4-controller", "editor_tools": {}}


class FakeLedger:
    def __init__(self, journal, *, study_sha256, slots, authority, transport,
                 bindings, editor_tools, stage, admission_guard, profile):
        self.journal = journal
        self.manifest = {"inputs": {"study_sha256": study_sha256}}
        pair = profile["execution_pairs"][0]
        self.value = {"status": "ready", "spent_micro_usd": 0, "reserved_micro_usd": 0, "attempts": 0,
            "transport_audit_summary": {"missing_or_invalid_slots": []}, "active_unsettled_intents": [],
            "durable_unknown_results": 0,
            "cells": {pair + ":fixed": {"spent_micro_usd": 0}, pair + ":adaptive": {"spent_micro_usd": 0}}}
        self.profile, self.guard = profile, admission_guard
        admission_guard(self.value)

    def state(self):
        return copy.deepcopy(self.value)


class Phase4WorkflowTests(unittest.TestCase):
    def setUp(self):
        directory = BASE / "p4-controller-tests"
        directory.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=directory)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.study = study()
        self.task = example(fixture=True)["task"]
        source = patch.object(workflow.release, "source_identity", return_value={"sha256": self.study["source_sha256"]})
        source.start()
        self.addCleanup(source.stop)

    def test_source_change_blocks_an_open_child_before_the_next_intent(self):
        book = workflow.Coordinator(self.study, self.root, SimpleNamespace(fixture=True))
        with patch.object(workflow.accounting, "Ledger", FakeLedger):
            ledger, _, _ = book.open("dev", "dev02", self.task)
            with patch.object(workflow.release, "source_identity", return_value={"sha256": "f" * 64}), \
                    self.assertRaisesRegex(ContractError, "implementation changed"):
                ledger.guard(ledger.state())

    def test_real_worklists_have_only_declared_profiles_and_no_judges_during_generation(self):
        for kind, pair, size in (("dev", "dev02", 1161), ("inference", "p4-24", 1569), ("assessment", "p4-01", 39)):
            slots = workflow.worklist(self.study, kind, pair, self.task)
            self.assertEqual(len(slots), size)
            self.assertEqual(any(row["role"] in {"group", "quality"} for row in slots.values()), kind == "assessment")

    def test_serial_children_receive_only_remaining_allocation_and_never_a_copied_parent_cap(self):
        book = workflow.Coordinator(self.study, self.root, SimpleNamespace(fixture=True))
        with patch.object(workflow.accounting, "Ledger", FakeLedger):
            ledger, first, _ = book.open("dev", "dev02", self.task)
            self.assertEqual(first["phase_micro_usd"], 75_000_000)
            with self.assertRaises(ContractError):
                book.open("dev", "dev04", self.task)
            ledger.value.update(spent_micro_usd=70_000_000, attempts=20)
            book.close(ledger, {"synthetic": "first"})
            ledger, second, _ = book.open("dev", "dev04", self.task)
            self.assertEqual(second["phase_micro_usd"], 30_000_000)
            self.assertEqual(second["phase4_child"]["remaining_total_micro_usd"], 1_130_000_000)
            ledger.value.update(spent_micro_usd=2_000_000, attempts=3)
            book.close(ledger, {"synthetic": "second"})
            self.assertEqual(book.accounting_view()["spent_micro_usd"], 72_000_000)
            with self.assertRaises(ContractError):
                book.open("dev", "dev02", self.task)

    def test_qualification_and_all_generation_seals_are_mandatory_before_new_role(self):
        book = workflow.Coordinator(self.study, self.root, SimpleNamespace(fixture=True))
        with patch.object(workflow.accounting, "Ledger", side_effect=AssertionError("must not open a ledger")):
            with self.assertRaises(ContractError):
                book.open("inference", "p4-01", self.task)
            book.qualification = True
            with self.assertRaises(ContractError):
                book.open("assessment", "p4-01", self.task, generation_study_sha256="d" * 64)

    def test_interrupted_active_child_keeps_known_spend_and_unknown_liability(self):
        book = workflow.Coordinator(self.study, self.root, SimpleNamespace(fixture=True))
        with patch.object(workflow.accounting, "Ledger", FakeLedger):
            ledger, profile, _ = book.open("dev", "dev02", self.task)
            ledger.value.update(spent_micro_usd=1234, reserved_micro_usd=11_440_000, attempts=2)
            view = book.accounting_view()
            self.assertEqual((view["spent_micro_usd"], view["reserved_micro_usd"]), (1234, 11_440_000))
            self.assertEqual(view["spent_by_allocation_micro_usd"]["dev"], 1234)
            with patch.object(ledger, "state", side_effect=ContractError("unverifiable")):
                view = book.accounting_view()
            self.assertFalse(view["active_child_accounting"]["known"])
            self.assertEqual(view["reserved_micro_usd"], profile["phase_micro_usd"])

    def test_genuine_integrity_halt_and_closed_unknown_prevent_later_spending(self):
        for status, held in (("halted", 0), ("blocked-unknown", 11_440_000)):
            with self.subTest(status=status):
                book = workflow.Coordinator(self.study, self.root / status, SimpleNamespace(fixture=True))
                with patch.object(workflow.accounting, "Ledger", FakeLedger):
                    ledger, _, _ = book.open("dev", "dev02", self.task)
                    ledger.value.update(status=status, reserved_micro_usd=held, attempts=1)
                    with self.assertRaises(ContractError):
                        book.close(ledger, {"synthetic": status})
                    self.assertEqual(book.accounting_view()["reserved_micro_usd"], held)
                    with self.assertRaises(ContractError):
                        book.open("dev", "dev04", self.task)

    def test_fixture_tasks_never_open_the_real_frame_and_qualification_is_not_a_score_gate(self):
        with patch.object(workflow, "_manifest", side_effect=AssertionError("real frame accessed")):
            tasks = workflow._tasks(self.root / "study.json", self.study, fixture=True)
        self.assertEqual(len(tasks), 24)
        self.assertTrue(all(row["source_context"]["dataset"] == "synthetic" for row in tasks))
        rows = [{"status": "complete", "spent_micro_usd": 1000, "target_micro_usd": 1000}] * 2
        self.assertTrue(workflow._qualification(rows)["passed"])
        self.assertFalse(workflow._qualification([{**row, "spent_micro_usd": 1500} for row in rows])["passed"])

    def test_resealed_selection_tamper_is_rejected_against_frozen_derivation(self):
        body = {"frozen_method_sha256": "b" * 64, "source_sha256": "c" * 64,
                "exposure_inventory_sha256": "d" * 64, "eligibility_passed": True,
                "selected": [{"source_task_id": f"synthetic-{i}"} for i in range(24)]}
        original = body | {"manifest_sha256": digest(body)}
        changed = {**body, "selected": list(reversed(body["selected"]))}
        changed["manifest_sha256"] = digest(changed)
        write_once(self.root / "confirmation-manifest.json", changed)
        metadata = {"method_sha256": "b" * 64, "confirmation_source_sha256": "c" * 64,
            "exposure_inventory_sha256": "d" * 64, "eligibility_proof_sha256": "e" * 64,
            "eligibility_proof": {"synthetic": True}}
        with patch.object(workflow.eligibility, "intake", return_value=original), self.assertRaisesRegex(ContractError, "derivation"):
            workflow._manifest(self.root / "study.json", metadata)
        with patch.object(workflow.eligibility, "intake", side_effect=AssertionError("report reopened corpus")):
            self.assertEqual(workflow._manifest(self.root / "study.json", metadata, verify_derivation=False), changed)
