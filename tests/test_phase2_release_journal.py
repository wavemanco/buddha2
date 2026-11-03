"""Cumulative staged authority, durable unknown liability and exact replay."""

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path

from buddha2.artifacts import ContractError, digest, read_json, write_once
from buddha2.phase2 import PROJECT, generate_order, rank_order
from buddha2.phase2_am1_controls import BILLING_PROFILE, CONTROL_POLICY, CONTROL_SHA256, reservation
from buddha2.phase2_contracts import slot_prefix
from buddha2.phase2_dispatch import build_request, writer_lock
from buddha2.phase2_native import NativeAssessment
from buddha2.phase2_release_journal import (
    AuthorityError,
    BudgetStopError,
    LiabilityError,
    ReleaseDispatcher,
    grant_template,
    initialize_journal,
    journal_identity,
    make_first_review,
    publish_grant,
    publish_review,
    replay_journal,
    validate_grant,
)


def study():
    value = copy.deepcopy(read_json(PROJECT / "runs/phase2-r012/frozen-study/study.json"))
    value.pop("study_sha256")
    value.update({"admission": CONTROL_POLICY, "control_policy_sha256": CONTROL_SHA256,
                  "billing_profile": BILLING_PROFILE, "launcher_sha256": "e" * 64,
                  "budget_policy": {"revision": "p2r-cumulative-authority-v1",
                                    "first_stage_max_micro_usd": 20000000,
                                    "phase_max_micro_usd": 125000000,
                                    "first_slots_max": 55, "phase_slots_max": 1320}})
    value["budget_policy_sha256"] = digest(value["budget_policy"])
    value["study_sha256"] = digest(value)
    return value


class Fixture:
    fixture = True

    def __init__(self, *, failure=None, maximum=False, pairs=False):
        self.calls, self.slot, self.failure, self.maximum, self.pairs = 0, "", failure, maximum, pairs

    def create(self, role, request):
        self.calls += 1
        if isinstance(self.failure, BaseException):
            raise self.failure
        usage = {"input_tokens": 80, "output_tokens": 20,
                 "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
                 "service_tier": "default" if role == "group" else "standard"}
        if role == "plan":
            text = {"angles": [{"id": f"angle-{i:02}", "angle": f"Synthetic angle {i}"} for i in range(1, 11)]}
        elif role == "rank":
            text = {"order": [row["id"] for row in reversed(json.loads(request["messages"][0]["content"])["responses"])]}
        elif role == "group":
            text = {"groups": [[i, i + 1] for i in range(0, 10, 2)] if self.pairs else [[i] for i in range(10)]}
            usage["input_tokens_details"] = {"cached_tokens": 0, "cache_write_tokens": 0}
        elif role == "quality":
            text = {"score": 5}
        else:
            text = "Synthetic answer " + self.slot
        if self.maximum:
            usage.update({"input_tokens": 0, "output_tokens": 4096,
                          "cache_creation_input_tokens": 1000000,
                          "cache_creation": {"ephemeral_5m_input_tokens": 1000000}})
        if self.failure == "usage":
            usage.pop("cache_read_input_tokens")
        return {"model": request["model"], "text": text if isinstance(text, str) else json.dumps(text),
                "stop_reason": "stop" if role == "group" else "end_turn", "usage": usage,
                "latency_seconds": .001, "request_id": "fixture-" + self.slot}


class ReleaseJournalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.study = study()
        block = cls.study["worklist"]["blocks"][0]
        cls.first_task = next(row for row in cls.study["tasks"] if row["id"] == block["task_id"])
        cls.first_answer = slot_prefix(block["task_id"], "A", 1) + ".answer.00"
        cls.second_answer = slot_prefix(block["task_id"], "A", 1) + ".answer.01"

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="test-release-journal-",
                                               dir=os.environ.get("BUDDHA2_OUTPUT_ROOT", "/results"))
        self.addCleanup(temporary.cleanup)
        self.phase = Path(temporary.name)
        self.run = self.phase / "journal"
        self.transport = Fixture()
        self.dispatcher = ReleaseDispatcher(self.run, study=self.study, transport=self.transport)

    def grant(self, *, cap=20000000, grant_id="fixture-first", previous=None, stage="first", review=None):
        return grant_template(self.study, fixture=True, stage=stage, grant_id=grant_id,
                              cumulative_cap_micro_usd=cap, previous_authority_sha256=previous,
                              review_sha256=review)

    def first(self, **kwargs):
        return publish_grant(self.run, self.study, self.grant(**kwargs))

    def call(self, slot=None):
        slot = slot or self.first_answer
        self.transport.slot = slot
        return self.dispatcher.dispatch(slot, "answer", build_request(
            "answer", messages=[{"role": "user", "content": "Synthetic task"}]))

    def test_manifest_has_full_worklist_and_no_actual_grant_or_cap(self):
        manifest = read_json(self.run / "manifest.json")
        self.assertEqual(len(manifest["inputs"]["slots"]), 1320)
        self.assertNotIn("authorization", manifest["inputs"])
        self.assertNotIn("cumulative_cap_micro_usd", manifest["inputs"])
        self.assertEqual(manifest["run_id"], journal_identity(self.study, True))
        with self.assertRaises(AuthorityError):
            self.dispatcher.require_stage("first")
        with self.assertRaises(AuthorityError):
            self.call()
        self.assertEqual(self.transport.calls, 0)

    def test_grant_is_idempotent_and_does_not_reset_spent_or_rewrite_identity(self):
        before = (self.run / "manifest.json").read_bytes()
        record = self.first()
        outcome = self.call()
        self.assertEqual(self.first(), record)
        self.assertEqual(validate_grant(self.run, self.study, self.grant()), record)
        state = replay_journal(self.run)
        self.assertEqual(state["spent_micro_usd"], outcome["spent_micro_usd"])
        self.assertEqual(state["attempts"], 1)
        self.assertEqual(len(list((self.run / "authority").glob("*.json"))), 1)
        self.assertEqual((self.run / "manifest.json").read_bytes(), before)
        self.assertEqual(self.call(), outcome)
        self.assertEqual(self.transport.calls, 1)

    def test_mismatched_private_unapproved_and_out_of_order_authority_reject(self):
        for key, value in (("study_sha256", "0" * 64), ("control_policy_sha256", "0" * 64),
                           ("source_sha256", "0" * 64), ("launcher_sha256", "0" * 64),
                           ("billing_profile", "private-contract"), ("authorized", True)):
            grant = self.grant()
            grant[key] = value
            grant["grant_sha256"] = digest({k: v for k, v in grant.items() if k != "grant_sha256"})
            with self.assertRaises(AuthorityError):
                publish_grant(self.run, self.study, grant)
        record = self.first()
        for grant in (self.grant(grant_id="duplicate-credit", previous=record["authority_sha256"]),
                      self.grant(grant_id="missing-parent", cap=20000001),
                      self.grant(stage="expansion", grant_id="unreviewed", cap=125000000,
                                 previous=record["authority_sha256"], review="0" * 64)):
            with self.assertRaises(AuthorityError):
                publish_grant(self.run, self.study, grant)
        self.assertEqual(self.transport.calls, 0)

    def test_too_small_grant_stops_before_intent_and_without_transport(self):
        self.first(cap=reservation("answer") - 1)
        with self.assertRaises(BudgetStopError):
            self.call()
        self.assertFalse((self.run / "events.jsonl").exists())
        self.assertEqual(self.transport.calls, 0)
        self.assertEqual(replay_journal(self.run)["attempts"], 0)

    def test_explicit_within_policy_topup_is_cumulative_and_prefix_bound(self):
        self.transport.maximum = True
        first = self.first(cap=3000000)
        self.call()
        with self.assertRaises(BudgetStopError):
            self.call(self.second_answer)
        next_grant = self.grant(grant_id="explicit-topup", cap=6000000,
                                previous=first["authority_sha256"])
        publish_grant(self.run, self.study, next_grant)
        self.call(self.second_answer)
        state = replay_journal(self.run)
        self.assertEqual(state["spent_micro_usd"], 2 * reservation("answer"))
        self.assertEqual(state["authorized_cap_micro_usd"], 6000000)
        self.assertEqual(state["first_stage_cap_micro_usd"], 6000000)
        self.assertEqual(self.transport.calls, 2)

    def test_unknown_usage_keeps_reservation_and_blocks_new_slots_and_grants(self):
        record = self.first()
        self.transport.failure = "usage"
        outcome = self.call()
        self.assertEqual(outcome["status"], "unknown")
        state = replay_journal(self.run)
        self.assertEqual(state["reserved_micro_usd"], reservation("answer"))
        self.assertEqual(state["spent_micro_usd"], 0)
        self.assertEqual(self.call(), outcome)
        with self.assertRaises(LiabilityError):
            self.call(self.second_answer)
        with self.assertRaises(LiabilityError):
            self.dispatcher.require_stage("first")
        with self.assertRaises(LiabilityError):
            publish_grant(self.run, self.study, self.grant(
                cap=20000000, grant_id="cannot-release", previous=record["authority_sha256"]))
        self.assertEqual(self.transport.calls, 1)

    def test_interrupted_intent_and_truncated_result_tail_are_never_free_retries(self):
        self.first()
        self.transport.failure = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.call()
        self.assertEqual(replay_journal(self.run)["reserved_micro_usd"], reservation("answer"))
        path = self.run / "events.jsonl"
        with path.open("ab") as stream:
            stream.write(b'{"kind":"result",')
        before = path.read_bytes()
        self.assertEqual(replay_journal(self.run)["journal_integrity"], "truncated-result-tail")
        with self.assertRaises(LiabilityError):
            self.call(self.second_answer)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.transport.calls, 1)

    def test_event_tampering_and_concurrent_owner_are_rejected(self):
        self.first()
        self.call()
        path = self.run / "events.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        rows[-1]["record"]["spent_micro_usd"] = 0
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        with self.assertRaises(ContractError):
            replay_journal(self.run)
        with writer_lock(self.run):
            with self.assertRaisesRegex(ContractError, "concurrent"):
                publish_grant(self.run, self.study, self.grant())
        self.assertEqual(self.transport.calls, 1)

    def test_missing_native_first_block_cannot_be_approved_by_flags(self):
        self.first()
        with self.assertRaises(AuthorityError):
            make_first_review(self.run, self.study, review_id="fake", cutoff="2026-10-27T07:00:00Z")
        self.assertFalse((self.run / "reviews/first.json").exists())

    def complete_first(self):
        self.first()
        self.transport.pairs = True
        def dispatch(slot, role, request, **kwargs):
            self.transport.slot = slot
            return self.dispatcher.dispatch(slot, role, request, **kwargs)
        saved = {method: generate_order(self.study, self.first_task, 1, method, dispatch,
                                        checkpoint="canary", fixture=True) for method in ("A", "B")}
        saved["C"] = rank_order(self.study, saved["B"], dispatch, checkpoint="canary")
        native = NativeAssessment(PROJECT / ".upstream/novelty-bench")
        for method in ("A", "B", "C"):
            prefix = slot_prefix(self.first_task["id"], method, 1)
            write_once(self.phase / "portfolios" / f"{prefix}.json", saved[method])
            write_once(self.phase / "assessments" / f"{prefix}.json", native.assess(saved[method], dispatch))

    def test_verified_first_review_unlocks_remaining_slots_without_replacing_first_ledger(self):
        before = (self.run / "manifest.json").read_bytes()
        self.complete_first()
        first_state = replay_journal(self.run)
        self.assertEqual(first_state["attempts"], 40)
        review = make_first_review(self.run, self.study, review_id="operator-check",
                                   cutoff="2026-10-27T07:00:00Z")
        publish_review(self.run, self.study, review)
        self.assertEqual(publish_review(self.run, self.study, review), review)
        with self.assertRaises(AuthorityError):
            self.dispatcher.require_stage("expansion")
        record = publish_grant(self.run, self.study, self.grant(
            stage="expansion", grant_id="fixture-expansion", cap=125000000,
            previous=first_state["authority_sha256"], review=review["review_sha256"]))
        self.dispatcher.require_stage("expansion")
        next_block = self.study["worklist"]["blocks"][1]
        slot = slot_prefix(next_block["task_id"], "A", next_block["repeat"]) + ".answer.00"
        self.transport.slot = slot
        self.dispatcher.dispatch(slot, "answer", build_request("answer", messages=[{
            "role": "user", "content": "Synthetic expansion"}]), checkpoint="expansion")
        state = replay_journal(self.run)
        self.assertEqual(state["attempts"], 41)
        self.assertGreater(state["spent_micro_usd"], first_state["spent_micro_usd"])
        self.assertEqual(state["authority_sha256"], record["authority_sha256"])
        self.assertEqual(state["authorized_cap_micro_usd"], 125000000)
        self.assertEqual((self.run / "manifest.json").read_bytes(), before)
        self.assertEqual(publish_review(self.run, self.study, review), review)
        self.assertEqual(replay_journal(self.run)["authority_sha256"], record["authority_sha256"])
        unused_nonhead = slot_prefix(self.first_task["id"], "A", 1) + ".quality.01"
        with self.assertRaises(AuthorityError):
            self.dispatcher.dispatch(unused_nonhead, "quality", build_request("quality", messages=[{
                "role": "user", "content": "Must not add a first-block attempt"}]))
        self.assertEqual(self.transport.calls, 41)
        portfolio_path = self.phase / "portfolios" / f"{slot_prefix(self.first_task['id'], 'A', 1)}.json"
        with portfolio_path.open("ab") as stream:
            stream.write(b"\n")
        with self.assertRaises(AuthorityError):
            replay_journal(self.run)
        self.assertEqual(self.transport.calls, 41)

    def test_live_path_cannot_be_rebound_to_another_journal(self):
        with self.assertRaisesRegex(ContractError, "single canonical phase journal"):
            initialize_journal(self.phase / "another-journal", self.study, fixture=False)


if __name__ == "__main__":
    unittest.main()
