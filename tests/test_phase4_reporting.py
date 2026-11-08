"""Saved-report trust boundaries with synthetic journals and zero provider dispatch."""
from __future__ import annotations

import copy
import json
import os
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, patch

from buddha2.artifacts import ContractError, digest, file_hash, write_once
from buddha2.phase2_dispatch import build_request
from followups.phase3b_seq2_v1 import ledger_core as core
from followups.phase3b_seq2_v1 import native
from followups.phase3b_seq2_v1 import transport as bounded
from followups.phase3b_seq2_v1.support import ROOT, seal
from followups.phase4_cm1_v1 import assessment, release, workflow
from tests.test_phase4_assessment import SavedDispatcher, portfolio
from tests.test_phase4_release import synthetic_release


def rewrite_fixture(path, value):
    """Intentional corruption is confined to a fresh synthetic test output."""
    path.write_text(json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def incomplete_fixed(book, ledger, profile, pair, task, target):
    return {"kind": "phase4-cm1-hierarchical-fixed-v1", "status": "incomplete",
        "study_sha256": ledger.manifest["inputs"]["study_sha256"], "task_id": task["id"],
        "run_id": workflow._ids(book.study, pair)[0], "fixture": True,
        "target_micro_usd": target, "request_policy_sha256": digest(profile),
        "pools": [], "spent_micro_usd": 0, "portfolio": None, "selected_run_id": None,
        "selection": None, "reason": "synthetic-unattempted", "pool_ceiling_reached": False}


@contextmanager
def saved_parent(kind="closed"):
    with synthetic_release() as (_, study_path, study):
        grant_path = study_path.parent / "mock-grant.json"
        write_once(grant_path, release.make_grant(study_path, True))
        run, _ = release.paths(study, True)
        core._publish(run / "started.json", {"study_sha256": study["study_sha256"],
            "started_at": "2026-11-08T00:00:00+00:00", "confirmation_manifest_sha256": None})
        # No SDK constructor: zero-call ledger initialization only.
        transport = object.__new__(bounded.Transport)
        transport.fixture = True
        if kind == "unavailable":
            transport = SimpleNamespace(fixture=True)
        book = workflow.Coordinator(study, run, transport)
        row = study["development"][0]
        ledger = profile = folder = None
        try:
            ledger, profile, folder = book.open("dev", row["pilot_id"], row["task"])
        except ContractError:
            if kind != "unavailable":
                raise
        if kind == "closed":
            result = incomplete_fixed(book, ledger, profile, row["pilot_id"], row["task"], row["target_micro_usd"])
            book.close(ledger, result)
            core._publish(run / "qualification.json", workflow._qualification([result]))
        elif kind == "pending":
            slot = next(name for name, meta in ledger.manifest["inputs"]["slots"].items() if meta["role"] == "plan")
            body = build_request("plan", messages=[{"role": "user", "content": "Synthetic pending request"}])
            core._append_event(ledger.journal, "intent", core._intent(ledger.manifest, slot, body, 1), [])
        outcome = seal({"kind": "phase4-cm1-outcome-v1", "study_sha256": study["study_sha256"],
            "fixture": True, "status": "qualification-change-required" if kind == "closed" else "paused-integrity-or-liability",
            "error_type": None if kind == "closed" else "SyntheticInterruption", "closed_children": book.closed,
            "active_child": book.active[2] if book.active else None, **book.accounting_view(),
            "provider_calls": 0, "historical_held_micro_usd": 22_880_000,
            "closed_at": "2026-11-08T00:01:00+00:00", "automatic_repeat": False})
        core._publish(run / "outcome.json", outcome)
        yield study_path, grant_path, run, ledger, folder, outcome


@unittest.skipUnless(os.getenv("BUDDHA2_NB_UPSTREAM"), "requires the pinned offline image")
class Phase4ReportingTests(unittest.TestCase):
    def test_partial_native_reuses_checkpoint_validator_without_selection_or_fixed_target(self):
        study = {"study_sha256": "a" * 64, "execution_tag": "synthetic-partial-report"}
        pair, child = "p4-01", "b" * 64
        task, profile = {"id": "synthetic-partial"}, {"synthetic_profile": True}
        state = {"fixture": True, "results": {}, "intents": {}, "cells": {
            pair + ":adaptive": {"spent_micro_usd": 100}, pair + ":fixed": {"spent_micro_usd": 0}}}
        partial = {"kind": "phase4-cm1-partial-native-v1", "status": "incomplete",
            "authentic": False, "selected_checkpoint": None, "portfolio": None,
            "checkpoints": {"c1": {"synthetic_checkpoint": True}, "c2": None}}
        value = {"kind": "phase4-cm1-generation-v1", "task": task, "pair": pair,
            "generation_study_sha256": child, "native_micro_usd": 100, "fixed_micro_usd": 0,
            "adaptive": partial, "fixed": None}
        seed = ROOT / "synthetic-unused-seed"
        with patch.object(workflow, "_retained_native", return_value=copy.deepcopy(partial)) as retained, \
                patch.object(native, "validate_adaptation", side_effect=AssertionError("full validator on partial")):
            workflow._report_generation(study, pair, task, child, profile, state, value, seed)
            retained.assert_called_once()
            changed = copy.deepcopy(value)
            changed["adaptive"]["checkpoints"]["c1"]["synthetic_checkpoint"] = False
            with self.assertRaisesRegex(ContractError, "do not replay"):
                workflow._report_generation(study, pair, task, child, profile, state, changed, seed)
            changed = {**value, "fixed": {"synthetic_unauthorized_target": True}}
            with self.assertRaisesRegex(ContractError, "cannot supply"):
                workflow._report_generation(study, pair, task, child, profile, state, changed, seed)

    def test_live_saved_report_uses_start_bound_manifest_without_opening_corpus(self):
        with synthetic_release() as (_, study_path, study):
            grant = study_path.parent / "live-grant.json"
            write_once(grant, release.make_grant(study_path, False))
            manifest = study_path.parent / "confirmation-manifest.json"
            write_once(manifest, {"kind": "synthetic-already-bound-manifest"})
            run, _ = release.paths(study, False)
            core._publish(run / "started.json", {"study_sha256": study["study_sha256"],
                "confirmation_manifest_sha256": file_hash(manifest)})
            zero = {key: 0 for key in workflow.policy.ALLOCATIONS}
            outcome = seal({"kind": "phase4-cm1-outcome-v1", "study_sha256": study["study_sha256"],
                "fixture": False, "automatic_repeat": False, "closed_children": [], "active_child": None,
                "spent_micro_usd": 0, "reserved_micro_usd": 0, "attempts": 0,
                "spent_by_allocation_micro_usd": zero, "reserved_by_allocation_micro_usd": zero,
                "active_child_accounting": None, "provider_calls": 0, "historical_held_micro_usd": 22_880_000,
                "status": "paused-integrity-or-liability"})
            core._publish(run / "outcome.json", outcome)
            corpus = SimpleNamespace(read_bytes=Mock(side_effect=AssertionError("saved report opened corpus")))
            with patch.object(workflow.eligibility, "SOURCE_PATH", corpus), \
                    patch.object(workflow, "_manifest", return_value={"selected": []}) as saved_manifest:
                self.assertEqual(workflow.report(study_path, grant), outcome)
                saved_manifest.assert_called_once_with(study_path, study, verify_derivation=False)
                corpus.read_bytes.assert_not_called()

    def test_saved_partial_report_preserves_journal_and_never_creates_analysis(self):
        with saved_parent() as (study, grant, run, ledger, _, outcome):
            before = {name: file_hash(ledger.journal / name) if (ledger.journal / name).exists() else None
                      for name in ("manifest.json", "events.jsonl")}
            self.assertEqual(workflow.report(study, grant), outcome)
            self.assertEqual(before, {name: file_hash(ledger.journal / name) if (ledger.journal / name).exists() else None
                                     for name in before})
            self.assertFalse((run / "analysis.json").exists())

    def test_resealed_foreign_parent_mode_and_counter_tampering_are_rejected(self):
        with saved_parent() as (study, grant, run, _, _, outcome):
            for key, value in (("study_sha256", "0" * 64), ("fixture", False), ("spent_micro_usd", 1)):
                changed = {k: v for k, v in outcome.items() if k != "sha256"}
                changed[key] = value
                rewrite_fixture(run / "outcome.json", seal(changed))
                with self.subTest(key=key), self.assertRaises(ContractError):
                    workflow.report(study, grant)

    def test_resealed_allocation_and_journal_swap_cannot_replace_a_child(self):
        with saved_parent() as (study, grant, _, _, folder, _):
            opened = json.loads((folder / "open.json").read_text(encoding="utf-8"))
            raw = (folder / "open.json").read_bytes()
            changed = copy.deepcopy(opened)
            allocation = {k: v for k, v in changed["allocation"].items() if k != "sha256"}
            allocation["remaining_total_micro_usd"] += 1
            changed["allocation"] = seal(allocation)
            rewrite_fixture(folder / "open.json", seal({k: v for k, v in changed.items() if k != "sha256"}))
            with self.assertRaisesRegex(ContractError, "allocation"):
                workflow.report(study, grant)
            (folder / "open.json").write_bytes(raw)
            closure = json.loads((folder / "closure.json").read_text(encoding="utf-8"))
            closure["journal"] = "/results/unrelated/journal"
            rewrite_fixture(folder / "closure.json", seal({k: v for k, v in closure.items() if k != "sha256"}))
            with self.assertRaisesRegex(ContractError, "closed child"):
                workflow.report(study, grant)

    def test_pending_active_child_keeps_exact_hold_and_is_zero_resend(self):
        with saved_parent("pending") as (study, grant, _, ledger, _, outcome):
            before = (ledger.journal / "events.jsonl").read_bytes()
            self.assertEqual(outcome["reserved_micro_usd"], 2_540_960)
            self.assertEqual(workflow.report(study, grant), outcome)
            self.assertEqual((ledger.journal / "events.jsonl").read_bytes(), before)
            self.assertEqual(outcome["active_child_accounting"]["attempts"], 1)

    def test_unavailable_active_ledger_retains_conservative_child_allocation(self):
        with saved_parent("unavailable") as (study, grant, _, _, _, outcome):
            self.assertFalse(outcome["active_child_accounting"]["known"])
            self.assertEqual(outcome["reserved_micro_usd"], 75_000_000)
            self.assertEqual(outcome["spent_micro_usd"], 0)
            self.assertEqual(workflow.report(study, grant), outcome)

    def test_saved_native_bundle_is_rebuilt_from_exact_journal_requests(self):
        original = portfolio()
        study = {"study_sha256": "a" * 64, "execution_tag": "synthetic-report"}
        pair = "p4-01"
        identity = workflow._ids(study, pair)[2]["fixed"]
        evaluator = native.Phase3NativeAssessment(ROOT / ".upstream/novelty-bench")
        dispatch = SavedDispatcher(evaluator, identity)
        intents = {}

        def remember(slot, role, request):
            intents[slot] = {"role": role, "request": copy.deepcopy(request)}
            return dispatch(slot, role, request)

        bundle = assessment.assess_target(evaluator, original, identity, remember)
        row = {"prompt_id": original["task"]["id"], "pair": pair, "targets": {"fixed": bundle, "c1": None, "c2": None},
            "selected_checkpoint": None, "stage_dispositions": [], "native_micro_usd": 0,
            "fixed_micro_usd": 0, "failure": None}
        generation = {"fixed": {"portfolio": original}, "adaptive": None,
                      "native_micro_usd": 0, "fixed_micro_usd": 0}
        state = {"results": dispatch.saved, "intents": intents}
        before = copy.deepcopy(row)
        workflow._report_assessment(study, pair, original["task"], state, row, generation)
        self.assertEqual(row, before)
        self.assertEqual(len(dispatch.calls), 13)
        changed = copy.deepcopy(row)
        changed["targets"]["fixed"]["quality_scores"][0] = 9
        changed["targets"]["fixed"]["sha256"] = digest({k: v for k, v in changed["targets"]["fixed"].items() if k != "sha256"})
        with self.assertRaisesRegex(ContractError, "does not replay"):
            workflow._report_assessment(study, pair, original["task"], state, changed, generation)
