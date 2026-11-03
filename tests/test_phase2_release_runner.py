"""Full-runner boundaries with actual SDK mocks and native assessment functions.

The release-definition validator is isolated here; root's public-command full
rehearsal verifies the frozen release/source/launcher identity end to end.
"""

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest, read_json, tree_hashes
from buddha2.phase2 import PROJECT
from buddha2.phase2_am1_controls import BILLING_PROFILE, CONTROL_POLICY, CONTROL_SHA256
from buddha2.phase2_am1_mock import SDKMock
from buddha2.phase2_contracts import slot_prefix
from buddha2.phase2_decisions import implementation_identity
from buddha2.phase2_dispatch import writer_lock
from buddha2.phase2_release_journal import (
    AuthorityError,
    grant_template,
    initialize_journal,
    make_first_review,
    publish_grant,
    publish_review,
    replay_journal,
)
from buddha2.phase2_release_runner import run_stage, snapshot


def runner_study():
    study = copy.deepcopy(read_json(PROJECT / "runs/phase2-r012/frozen-study/study.json"))
    study.pop("study_sha256")
    budget = {"revision": "p2r-cumulative-authority-v1", "first_stage_max_micro_usd": 20_000_000,
              "phase_max_micro_usd": 125_000_000, "first_slots_max": 55, "phase_slots_max": 1320}
    study.update({"admission": CONTROL_POLICY, "control_policy_sha256": CONTROL_SHA256,
                  "billing_profile": BILLING_PROFILE, "launcher_sha256": "a" * 64,
                  "budget_policy": budget, "budget_policy_sha256": digest(budget)})
    study["study_sha256"] = digest(study)
    return study


class ReleaseRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.study = runner_study()

    def setUp(self):
        root = Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", PROJECT / "runs"))
        temporary = tempfile.TemporaryDirectory(prefix="test-release-runner-", dir=root)
        self.addCleanup(temporary.cleanup)
        self.run = Path(temporary.name) / "phase"
        self.validated = patch("buddha2.phase2_release_runner._validate_release")
        self.validated.start()
        self.addCleanup(self.validated.stop)
        # Keep this imported test implementation fixed while other independent
        # agents edit files. End-to-end release tests enforce live source hashes.
        implementation = patch("buddha2.phase2_decisions.implementation_identity",
                               return_value=implementation_identity())
        implementation.start()
        self.addCleanup(implementation.stop)
        initialize_journal(self.run / "journal", self.study, fixture=True)
        self.grant()

    def grant(self, cap=20_000_000):
        grant = grant_template(self.study, fixture=True, stage="first", grant_id="runner-first",
                               cumulative_cap_micro_usd=cap)
        return publish_grant(self.run / "journal", self.study, grant)

    def execute(self, stage="first", **kwargs):
        with SDKMock(**kwargs) as mock:
            result = run_stage(self.study, self.run, stage=stage, transport=mock.transport)
            return result, copy.deepcopy(mock.records)

    def test_first_stop_native_report_and_stable_read_only_resume(self):
        first, records = self.execute()
        self.assertEqual(len(records), 55)
        self.assertEqual(first["attempts"], 55)
        self.assertEqual(first["orders"], 3)
        self.assertEqual(first["missing_assessments"], 69)
        self.assertTrue(first["first_block_ready_for_review"])
        self.assertEqual(first["decision_status"], "inconclusive")
        self.assertIsNone(first["selected_method"])
        before = tree_hashes(self.run)
        repeated, new = self.execute()
        self.assertEqual(new, [])
        self.assertEqual(repeated, first)
        self.assertEqual(tree_hashes(self.run), before)
        with patch("buddha2.phase2_release_runner.ReleaseDispatcher", side_effect=AssertionError("no dispatch")):
            replay = snapshot(self.study, self.run)
        self.assertEqual(replay["summary"], first)
        self.assertEqual(tree_hashes(self.run), before)
        self.assertEqual(replay["coverage"]["slot_status_counts"]["not_attempted"], 1265)

    def test_no_unreviewed_expansion_and_identical_first_authority_adds_no_credit(self):
        first, _ = self.execute()
        before = tree_hashes(self.run)
        with SDKMock() as mock:
            with self.assertRaises(AuthorityError):
                run_stage(self.study, self.run, stage="expansion", transport=mock.transport)
            self.assertEqual(mock.http_calls, 0)
        self.assertEqual(tree_hashes(self.run), before)
        old = replay_journal(self.run / "journal")
        self.grant()
        state = replay_journal(self.run / "journal")
        self.assertEqual(state["spent_micro_usd"], old["spent_micro_usd"])
        self.assertEqual(state["attempts"], first["attempts"])
        self.assertEqual(state["authorized_cap_micro_usd"], 20_000_000)

    def test_pairs_nonheads_and_malformed_plan_remain_native_outcomes(self):
        first, records = self.execute(partition="pairs")
        self.assertEqual(len(records), 40)
        self.assertTrue(first["first_block_ready_for_review"])
        coverage = snapshot(self.study, self.run)["coverage"]
        self.assertEqual(coverage["slot_status_counts"]["not_needed_nonhead"], 15)
        self.run = self.run.parent / "malformed"
        initialize_journal(self.run / "journal", self.study, fixture=True)
        self.grant()
        failed, records = self.execute(fault="malformed-plan")
        self.assertEqual(len(records), 22)
        self.assertEqual(failed["orders"], 1)
        self.assertFalse(failed["first_block_ready_for_review"])
        before = tree_hashes(self.run)
        repeated, records = self.execute()
        self.assertEqual(records, [])
        self.assertEqual(repeated, failed)
        self.assertEqual(tree_hashes(self.run), before)
        with self.assertRaises(ContractError):
            make_first_review(self.run / "journal", self.study, review_id="invalid-readiness",
                              cutoff="2026-10-27T08:00:00Z")

    def test_unknown_group_usage_halts_and_repeated_resume_has_no_new_attempt(self):
        failed, records = self.execute(fault="missing-write")
        self.assertEqual(len(records), 23)
        self.assertEqual(failed["reserved_micro_usd"], 1661880)
        self.assertEqual(failed["orders"], 0)
        before = tree_hashes(self.run)
        repeated, new = self.execute()
        self.assertEqual(new, [])
        self.assertEqual(repeated, failed)
        self.assertEqual(tree_hashes(self.run), before)

    def test_budget_exhaustion_stops_without_trying_cheaper_following_requests(self):
        self.run = self.run.parent / "small-budget"
        initialize_journal(self.run / "journal", self.study, fixture=True)
        self.grant(cap=5_000_000)
        failed, records = self.execute()
        # All generation/ranking and A grouping settle. The first quality
        # reservation cannot fit; B/C grouping must not spend afterward.
        self.assertEqual(len(records), 23)
        self.assertEqual([row["role"] for row in records].count("group"), 1)
        self.assertEqual(failed["reserved_micro_usd"], 0)
        self.assertFalse(failed["first_block_ready_for_review"])
        self.assertEqual(self.execute()[1], [])

    def test_budget_failures_retain_each_attempt_prefix_and_topup_authority(self):
        self.run = self.run.parent / "topups"
        initialize_journal(self.run / "journal", self.study, fixture=True)
        self.grant(cap=5_000_000)
        first, records = self.execute()
        self.assertEqual(len(records), 23)
        authorities = [replay_journal(self.run / "journal")["authority_sha256"]]
        for cap, expected_new in ((10_000_000, 0), (11_450_000, 1)):
            state = replay_journal(self.run / "journal")
            grant = grant_template(self.study, fixture=True, stage="first", grant_id=f"topup-{cap}",
                                   cumulative_cap_micro_usd=cap,
                                   previous_authority_sha256=state["authority_sha256"])
            publish_grant(self.run / "journal", self.study, grant)
            authorities.append(replay_journal(self.run / "journal")["authority_sha256"])
            last, records = self.execute()
            self.assertEqual(len(records), expected_new)
        failures = snapshot(self.study, self.run)["failures"]
        self.assertEqual(sorted(row["attempts"] for row in failures), [23, 23, 24])
        self.assertEqual({row["authority_sha256"] for row in failures}, set(authorities))
        self.assertEqual(len({row["error"] for row in failures}), 1)
        self.assertEqual(first["attempts"], 23)
        before = tree_hashes(self.run)
        repeated, records = self.execute()
        self.assertEqual(records, [])
        self.assertEqual(repeated, last)
        self.assertEqual(tree_hashes(self.run), before)

    def test_export_publication_crash_recovers_exactly_without_repeating_saved_answers(self):
        from buddha2.phase2_release_runner import write_once as real_write

        for boundary in ("portfolios", "identities"):
            with self.subTest(boundary=boundary):
                if boundary == "identities":
                    self.run = self.run.parent / "partial-export"
                    initialize_journal(self.run / "journal", self.study, fixture=True)
                    self.grant()

                def interrupt(path, value):
                    if ((boundary == "portfolios" and path.parent.name == "portfolios")
                            or boundary == "identities" and path.name == "identities.json"):
                        raise KeyboardInterrupt("fixture crash during artifact publication")
                    return real_write(path, value)

                target = ("buddha2.phase2_release_runner.write_once" if boundary == "portfolios"
                          else "buddha2.phase2_contracts.write_once")
                with SDKMock() as mock, patch(target, side_effect=interrupt):
                    with self.assertRaises(KeyboardInterrupt):
                        run_stage(self.study, self.run, stage="first", transport=mock.transport)
                    self.assertEqual(mock.http_calls, 10)
                inspected = snapshot(self.study, self.run)
                self.assertEqual(len(inspected["recoverable_exports"]), 1)
                finished, new = self.execute()
                self.assertEqual(len(new), 45)
                self.assertEqual(finished["attempts"], 55)
                self.assertTrue(finished["first_block_ready_for_review"])

    def test_invalid_stage_and_cutoff_reject_before_http_or_cutoff_publication(self):
        with SDKMock() as mock:
            for stage, cutoff in (([], None), ("unbounded", None),
                                   ("first", "2026-02-31T08:00:00Z")):
                with self.assertRaises(ContractError):
                    run_stage(self.study, self.run, stage=stage, transport=mock.transport, cutoff=cutoff)
                self.assertEqual(mock.http_calls, 0)
        self.assertFalse((self.run / "report-cutoffs").exists())

    def test_owner_foreign_native_and_saved_portfolio_tamper_reject_before_http(self):
        with SDKMock() as mock:
            with writer_lock(self.run / "owner"):
                with self.assertRaisesRegex(ContractError, "concurrent"):
                    run_stage(self.study, self.run, stage="first", transport=mock.transport)
            self.assertEqual(mock.http_calls, 0)
        foreign = self.run / "native/foreign-order"
        foreign.mkdir(parents=True)
        with SDKMock() as mock:
            with self.assertRaisesRegex(ContractError, "undeclared"):
                run_stage(self.study, self.run, stage="first", transport=mock.transport)
            self.assertEqual(mock.http_calls, 0)
        foreign.rmdir()
        result, _ = self.execute()
        report = Path(result["snapshot"]) / "analysis.json"
        original_report = report.read_bytes()
        report.write_text('{"tampered":"report"}', encoding="utf-8")
        with SDKMock() as mock:
            with self.assertRaisesRegex(ContractError, "published report"):
                run_stage(self.study, self.run, stage="first", transport=mock.transport)
            self.assertEqual(mock.http_calls, 0)
        report.write_bytes(original_report)
        task = self.study["tasks"][0]
        path = self.run / "portfolios" / f"{slot_prefix(task['id'], 'A', 1)}.json"
        data = read_json(path)
        data["responses"][0]["text"] = "tampered"
        path.write_text(json.dumps(data), encoding="utf-8")
        with SDKMock() as mock:
            with self.assertRaises(ContractError):
                run_stage(self.study, self.run, stage="first", transport=mock.transport)
            self.assertEqual(mock.http_calls, 0)

    def test_expansion_uses_same_full_worklist_and_cumulative_authority(self):
        self.execute()
        review = make_first_review(self.run / "journal", self.study, review_id="runner-ready",
                                   cutoff="2026-10-27T08:00:00Z")
        publish_review(self.run / "journal", self.study, review)
        state = replay_journal(self.run / "journal")
        grant = grant_template(self.study, fixture=True, stage="expansion", grant_id="runner-expansion",
                               cumulative_cap_micro_usd=125_000_000,
                               previous_authority_sha256=state["authority_sha256"],
                               review_sha256=state["review_sha256"])
        publish_grant(self.run / "journal", self.study, grant)
        # Stop on the first new request. This proves the remainder starts at
        # block2 with its proper expansion slot and retains the first55; root's
        # full public-command rehearsal covers all remaining1,265 requests.
        task = self.study["tasks"][0]
        next_plan = slot_prefix(task["id"], "B", 2) + ".plan"
        result, records = self.execute(stage="expansion", fault="timeout", fault_slot=next_plan)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["slot_id"], next_plan)
        self.assertEqual(result["attempts"], 56)
        self.assertEqual(result["orders"], 3)
        state = replay_journal(self.run / "journal")
        self.assertEqual(state["authorized_cap_micro_usd"], 125_000_000)
        self.assertGreater(state["spent_micro_usd"], 0)
        self.assertGreater(state["reserved_micro_usd"], 0)


if __name__ == "__main__":
    unittest.main()
