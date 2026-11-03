"""R3 projections reuse scoring and preserve the inventory/admission distinction."""
from __future__ import annotations

import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError
from followups.phase3a_c1_completion_v3.tests.test_report import native_stub
from followups.phase3a_c1_completion_v3.tests.test_report import records as old_records
from followups.phase3a_c1_completion_v4 import report


def records(**kwargs):
    study, state, saved = old_records(**kwargs)
    for slot, row in list(study["slots"].items()):
        if row["role"] == "editor" and row["turn"] == 8:
            for turn in range(9, 17):
                study["slots"][slot.rsplit(".t", 1)[0] + f".t{turn:02}"] = row | {"turn": turn}
    study["policy"] = study["policy"] | {"editor_turns": 16}
    study["prior_live_episode"] = {"known_spent_micro_usd": 13101271, "reserved_micro_usd": 22880000,
        "provider_calls": 904, "known_requests": 902, "unknown_requests": 2}
    return study, state, saved


class ReportTests(unittest.TestCase):
    def setUp(self):
        patched = patch.object(report.parent, "_native", return_value=native_stub())
        patched.start()
        self.addCleanup(patched.stop)

    def test_same_scientific_fold_new_inventory_and_history_without_mutation(self):
        args = records()
        before = copy.deepcopy(args)
        study, state, saved = args
        data = report.build(study, state, saved, False)
        self.assertEqual(args, before)
        self.assertEqual(data["analysis"]["mean_adaptive_minus_fixed"], 1)
        self.assertEqual(data["coverage"]["scheduled_slots"], 967)
        self.assertEqual(data["summary"]["maximum_new_admitted_attempts"], 775)
        self.assertFalse(data["summary"]["inventory_is_authorization"])
        self.assertEqual(data["summary"]["cumulative_real_phase3a_spent_micro_usd"], 13101271 + 27)
        self.assertEqual(data["summary"]["cumulative_real_phase3a_reserved_micro_usd"], 22880000)
        self.assertEqual(data["summary"]["cumulative_real_phase3a_provider_calls"], 904 + 27)

    def test_missing_readiness_unknown_and_fixture_do_not_invent_real_success(self):
        for mode in ("readiness", "unknown", "fixture"):
            with self.subTest(mode=mode):
                study, state, saved = records(fixture=mode == "fixture")
                if mode == "readiness":
                    saved.pop("readiness")
                if mode == "unknown":
                    slot = next(iter(state["results"]))
                    state["results"][slot].update(status="unknown", response=None,
                        spent_micro_usd=None, reserved_micro_usd=2540960)
                    state.update(status="blocked-unknown", reserved_micro_usd=2540960,
                        durable_unknown_results=1, active_unsettled_intents=[])
                data = report.build(study, state, saved, mode == "fixture")
                self.assertFalse(data["summary"]["scientific_complete"])
                if mode != "fixture":
                    self.assertIsNone(data["analysis"]["mean_adaptive_minus_fixed"])
                else:
                    self.assertIsNone(data["summary"]["cumulative_real_phase3a_spent_micro_usd"])

    def test_old_inventory_extra_slot_or_over_admission_rejects(self):
        for kind in ("old", "extra", "admission"):
            with self.subTest(kind=kind):
                study, state, saved = old_records() if kind == "old" else records()
                if kind == "extra":
                    study["slots"]["foreign"] = {"cell": "p3a-01:adaptive"}
                if kind == "admission":
                    state["attempts"] = 776
                with self.assertRaises(ContractError):
                    report.build(study, state, saved, False)

    def test_writer_is_new_scope_immutable_eight_files(self):
        base = Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", str(report.ROOT / "runs"))) / "phase3a-c1-completion-v4/unit-report"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temporary:
            study, state, saved = records(fixture=True)
            data = report.build(study, state, saved, True)
            output = Path(temporary) / "report"
            report.write_report(data, output)
            first = {path.name: path.read_bytes() for path in output.iterdir()}
            report.write_report(data, output)
            self.assertEqual(first, {path.name: path.read_bytes() for path in output.iterdir()})
            self.assertEqual(len(first), 8)
            altered = copy.deepcopy(data)
            altered["summary"]["status"] = "different"
            with self.assertRaises(ContractError):
                report.write_report(altered, output)
            with self.assertRaises(ContractError):
                report.write_report(data, report.ROOT / "runs/phase3a-c1-completion-v3/forbidden")
