"""First-block bounds, partial native decisions, resume and source preservation."""

import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest, read_json, tree_hashes
from buddha2.phase2 import PROJECT
from buddha2.phase2_am1 import (
    _definition,
    cost_sheet,
    first_block,
    mock_grant,
    preflight,
    validate_candidate,
)
from buddha2.phase2_am1_mock import SDKMock
from buddha2.phase2_contracts import slot_prefix
from buddha2.phase2_dispatch import replay_dispatch, writer_lock


class FirstBlockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.study = _definition()

    def setUp(self):
        root = Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", PROJECT / "runs"))
        temporary = tempfile.TemporaryDirectory(prefix="test-am1-", dir=root)
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name) / "first-block"

    def run_mock(self, **kwargs):
        with SDKMock(**kwargs) as mock:
            result = first_block(self.study, self.output, mock.transport,
                                 authorization=mock_grant(self.study))
            return result, copy.deepcopy(mock.records)

    def test_preflight_never_constructs_transport_and_freezes_unchanged_science(self):
        with patch("buddha2.phase2_dispatch.DirectSDKTransport", side_effect=AssertionError("no SDK")):
            result = preflight(self.study)
        self.assertEqual(result["provider_calls"], 0)
        self.assertFalse(result["credential_access"])
        self.assertFalse(result["live_ready"])
        self.assertEqual(len(self.study["tasks"]), 12)
        self.assertEqual(len(self.study["worklist"]["slots"]), 1320)
        self.assertEqual(cost_sheet(self.study)["first_block_sum_max_micro_usd"], 404086760)
        self.assertEqual(cost_sheet(self.study)["full_worklist_sum_max_micro_usd"], 9698082240)

    def test_all_heads_first_block_replays_with_no_new_http_and_no_selected_seed(self):
        result, records = self.run_mock()
        self.assertEqual(result["attempts"], 55)
        self.assertEqual(len(records), 55)
        self.assertEqual(result["orders"], 3)
        self.assertEqual(result["missing_assessments"], 69)
        self.assertEqual(result["decision_status"], "inconclusive")
        self.assertIsNone(result["selected_method"])
        self.assertEqual(result["provider_calls"], 0)
        self.assertEqual(result["experiment_api_spend_micro_usd"], 0)
        self.assertEqual(result["reserved_micro_usd"], 0)
        before = tree_hashes(self.output)
        replay, new_records = self.run_mock()
        self.assertEqual(new_records, [])
        self.assertEqual(replay, result)
        self.assertEqual(before, tree_hashes(self.output))
        coverage = read_json(Path(result["snapshot"]) / "coverage.json")
        self.assertEqual(coverage["slot_status_counts"]["not_attempted"], 1265)
        decision = read_json(Path(result["snapshot"]) / "decision.json")
        self.assertEqual(decision["human_status"], "not-required")

    def test_nonheads_are_not_called_and_remain_accounted(self):
        result, records = self.run_mock(partition="pairs")
        self.assertEqual(len(records), 40)
        self.assertEqual(result["orders"], 3)
        coverage = read_json(Path(result["snapshot"]) / "coverage.json")
        self.assertEqual(coverage["slot_status_counts"]["not_needed_nonhead"], 15)
        self.assertEqual(coverage["slot_status_counts"]["not_attempted"], 1265)
        self.assertEqual(self.run_mock(partition="pairs")[1], [])

    def test_unknown_group_usage_retains_liability_and_resume_preserves_artifacts(self):
        result, records = self.run_mock(fault="missing-write")
        self.assertEqual(len(records), 23)
        self.assertEqual(result["orders"], 0)
        self.assertEqual(result["reserved_micro_usd"], 1661880)
        self.assertEqual(replay_dispatch(self.output / "journal")["status"], "blocked-unknown")
        before = tree_hashes(self.output)
        repeated, new_records = self.run_mock()
        self.assertEqual(new_records, [])
        self.assertEqual(repeated, result)
        self.assertEqual(before, tree_hashes(self.output))

    def test_malformed_plan_is_paid_preserved_and_never_replaced(self):
        result, records = self.run_mock(fault="malformed-plan")
        self.assertEqual(len(records), 22)  # A10 + bad plan1 + A group/head11.
        self.assertEqual(result["orders"], 1)
        self.assertEqual(result["reserved_micro_usd"], 0)
        state = replay_dispatch(self.output / "journal")
        self.assertGreater(state["spent_micro_usd"], 0)
        self.assertEqual(len([row for row in records if row["role"] == "plan"]), 1)
        self.assertEqual(self.run_mock()[1], [])

    def test_grant_expansion_concurrency_and_changed_candidate_reject_before_http(self):
        with SDKMock() as mock:
            for key, value in (("study_sha256", "0" * 64),
                               ("control_policy_sha256", "0" * 64),
                               ("billing_profile", "private-contract"),
                               ("expansion_authorized", True),
                               ("cap_micro_usd", 1)):
                grant = mock_grant(self.study)
                grant[key] = value
                with self.assertRaises(ContractError):
                    first_block(self.study, self.output, mock.transport, authorization=grant)
                self.assertEqual(mock.http_calls, 0)
            # A separate run avoids the intentionally immutable rejected grant.
            self.output = self.output.parent / "owner-check"
            with writer_lock(self.output / "owner"):
                with self.assertRaisesRegex(ContractError, "concurrent"):
                    first_block(self.study, self.output, mock.transport,
                                authorization=mock_grant(self.study))
            changed = copy.deepcopy(self.study)
            changed["tasks"][0]["prompt"] += " changed"
            changed["study_sha256"] = digest({key: value for key, value in changed.items()
                                             if key != "study_sha256"})
            with self.assertRaisesRegex(ContractError, "candidate differs"):
                validate_candidate(changed)
            self.assertEqual(mock.http_calls, 0)

    def test_saved_portfolio_tampering_is_rejected_before_resume_calls(self):
        self.run_mock()
        task = self.study["tasks"][0]
        path = self.output / "portfolios" / f"{slot_prefix(task['id'], 'A', 1)}.json"
        portfolio = read_json(path)
        portfolio["responses"][0]["text"] = "tampered"
        import json

        path.write_text(json.dumps(portfolio), encoding="utf-8")
        with SDKMock() as mock:
            with self.assertRaises(ContractError):
                first_block(self.study, self.output, mock.transport,
                            authorization=mock_grant(self.study))
            self.assertEqual(mock.http_calls, 0)


if __name__ == "__main__":
    unittest.main()
