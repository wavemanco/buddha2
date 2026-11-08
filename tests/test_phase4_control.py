"""Cost-prefix, whole-pool and no-replacement boundaries, without model calls."""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError
from followups.phase3b_seq2_v1 import ledger_core, strategy
from followups.phase4_cm1_v1 import control
from tests.test_phase2_contracts import example


class Phase4ControlTests(unittest.TestCase):
    def run_control(self, prices, *, target=1000, failed=None, replay_total=None, unknown=False):
        portfolio = example(fixture=True)
        calls, total = [], [0]

        def dispatch(slot, role, request):
            calls.append((slot, role))
            if unknown:
                return {"status": "unknown", "spent_micro_usd": None}
            charge = 60 if role == "fixed_selector" else prices[len(calls) - 1]
            total[0] += charge
            return {"status": "response", "spent_micro_usd": charge,
                    "response": {"text": '{"candidate_id":"candidate-01"}', "stop_reason": "end_turn"}}

        def pool(task, harness, **kwargs):
            index = int(kwargs["run_id"][-2:])
            kwargs["dispatch"](f"pool.{index}", "plan", {})
            return {"run_id": kwargs["run_id"], "selected_run_id": kwargs["run_id"] + "/winner",
                    "status": "failed" if index == failed else "complete",
                    "portfolio": None if index == failed else portfolio}

        with patch.object(strategy, "fixed_best12", side_effect=pool), \
                patch.object(ledger_core, "validate_request"), \
                patch.object(strategy, "verified_response", side_effect=lambda result, **kw: result["response"]):
            record = control.run_fixed(portfolio["task"], Path("/unused-synthetic-seed"),
                study_sha256="a" * 64, run_id="synthetic-fixed", target_micro_usd=target,
                dispatch=dispatch, spent=lambda: total[0] if replay_total is None else replay_total,
                fixture=True, request_policy={"synthetic": True})
        return record, calls

    def test_exact_ninety_percent_stops_at_one_complete_pool_without_final_call(self):
        record, calls = self.run_control([900])
        self.assertEqual((record["status"], len(record["pools"]), record["spent_micro_usd"]),
                         ("complete", 1, 900))
        self.assertEqual([role for _, role in calls], ["plan"])
        self.assertIsNone(record["selection"])

    def test_final_selector_is_counted_and_saved_full_total_does_not_shorten_replay(self):
        record, calls = self.run_control([450, 450], replay_total=960)
        self.assertEqual(len(record["pools"]), 2)
        self.assertEqual(record["spent_micro_usd"], 960)
        self.assertEqual([role for _, role in calls], ["plan", "plan", "fixed_selector"])

    def test_eight_pool_ceiling_is_complete_but_not_padded_to_target(self):
        record, calls = self.run_control([50] * 8)
        self.assertTrue(record["pool_ceiling_reached"])
        self.assertEqual((len(record["pools"]), len(calls), record["spent_micro_usd"]), (8, 9, 460))
        self.assertEqual(record["status"], "complete")

    def test_failed_required_pool_does_not_select_previous_winner_or_generate_replacement(self):
        record, calls = self.run_control([400, 200], failed=2)
        self.assertEqual((record["status"], len(calls), record["spent_micro_usd"]),
                         ("incomplete", 2, 600))
        self.assertIsNone(record["portfolio"])
        self.assertIsNone(record["selection"])

    def test_unknown_delivery_and_unreachable_saved_cost_are_not_silent_results(self):
        with self.assertRaises(ledger_core.LiabilityStop):
            self.run_control([900], unknown=True)
        with self.assertRaisesRegex(ContractError, "unreachable"):
            self.run_control([900], replay_total=1000)

    def test_invalid_native_target_is_rejected_before_any_pool(self):
        for value in (0, -1, True, 1.2):
            with self.subTest(value=value), self.assertRaises(ContractError):
                self.run_control([900], target=value)
