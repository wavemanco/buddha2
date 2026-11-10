"""Known c2 failure preserves a real saved c1, without inventing a selected result."""
from __future__ import annotations

import copy
import unittest
import uuid
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch

from buddha2.artifacts import ContractError, digest, write_once
from followups.phase3a_v1.tests.test_strategy import FakeDispatch
from followups.phase3b_seq2_v1 import native, strategy
from followups.phase3b_seq2_v1.support import BASE, NATIVE
from followups.phase4_cm1_v1 import assessment, workflow
from tests.test_phase4_assessment import portfolio
from tests.test_phase4_policy import profile_for


class Phase4PartialTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.blocked = [self.stack.enter_context(patch(name, side_effect=AssertionError("external activity")))
            for name in ("anthropic.Anthropic", "anthropic.AsyncAnthropic", "openai.OpenAI",
                         "openai.AsyncOpenAI", "socket.create_connection", "socket.socket.connect",
                         "socket.socket.connect_ex", "subprocess.Popen", "subprocess.run")]
        self.child = digest(["synthetic-p4-partial", uuid.uuid4().hex])
        self.task, self.pair = portfolio()["task"], "p4-01"
        self.study = {"study_sha256": digest(["parent", self.child]),
            "execution_tag": "synthetic-partial-" + self.child[:16], "source_sha256": "a" * 64}
        self.tag = workflow._ids(self.study, self.pair)[1]
        self.root = BASE / "p4-partial-tests" / self.child
        self.seed = self.root / "seed"
        strategy.materialize_seed(self.seed)
        self.search = NATIVE / self.child / "mock" / self.pair / "adaptive" / "search"
        self.profile, _ = profile_for()
        self.ids = native.adaptive_run_ids(self.task["id"], self.tag)
        self.identity = {"task": self.task, "study_sha256": self.child, "fixture": True,
            "tag": self.tag, "run_ids": self.ids, "seed": strategy.validate_harness(self.seed)}
        write_once(self.search / "identity.json", self.identity)
        self.fake = FakeDispatch()
        self.fake.wrapped_rank = False
        self.fake.invalid_plan_suffix = strategy.slot_ids(self.ids["c2"])["plan"]
        for label in ("c1", "c2"):
            directory = self.search / "rollouts" / label
            strategy.materialize_seed(directory / "harness")
            try:
                record = strategy.execute_cn(self.task, directory / "harness", study_sha256=self.child,
                    run_id=self.ids[label], dispatch=self.dispatch, fixture=True, arm="adaptive",
                    request_policy=self.profile)
            except strategy.KnownOutcomeError as exc:
                record = exc.evidence
            write_once(directory / ("rollout.json" if record["status"] == "complete" else "failure.json"), record)
            setattr(self, label, record)
        self.state = {"study_sha256": self.child, "fixture": True, "results": self.fake.results,
            "reserved_micro_usd": 0,
            "cells": {self.pair + ":adaptive": {"spent_micro_usd": 13},
                      self.pair + ":fixed": {"spent_micro_usd": 0}}}

    def dispatch(self, slot, role, request):
        result = self.fake(slot, role, request)
        result["study_sha256"] = self.child
        result["intent_sha256"] = digest(["synthetic-intent", self.child, slot, digest(request)])
        self.fake.results[slot] = copy.deepcopy(result)
        return result

    def tearDown(self):
        self.assertTrue(all(mock.call_count == 0 for mock in self.blocked))

    def retained(self, search=None, state=None):
        return workflow._retained_native(self.task, self.seed, child_sha=self.child,
            search=self.search if search is None else search, tag=self.tag, fixture=True,
            profile=self.profile, state=self.state if state is None else state)

    def test_known_failure_keeps_valid_c1_and_assesses_it_without_selection_or_fixed(self):
        self.assertEqual(self.c1["status"], "complete")
        self.assertEqual(self.c2["status"], "failed")
        ledger = SimpleNamespace(manifest={"inputs": {"study_sha256": self.child}},
            state=lambda: copy.deepcopy(self.state), dispatch=self.dispatch, halt=Mock())
        book = SimpleNamespace(study=self.study,
            transport=SimpleNamespace(fixture=True, register_conversation=Mock()),
            open=Mock(return_value=(ledger, self.profile, self.root)), close=Mock())
        with patch.object(workflow, "CompatibleProposer"), \
                patch.object(native, "run_adaptation", side_effect=native.RequiredCheckpointStop("synthetic c2 failure")), \
                patch.object(workflow, "_fixed", side_effect=AssertionError("no fixed target after failure")):
            generation = workflow._generation(book, self.pair, self.task, self.seed)
        retained = generation["adaptive"]
        self.assertEqual(retained, self.retained())
        self.assertIsNone(generation["fixed"])
        self.assertEqual(generation["failure"], "RequiredCheckpointStop")
        self.assertFalse(retained["authentic"])
        self.assertIsNone(retained["selected_checkpoint"])
        self.assertIsNone(retained["portfolio"])
        self.assertEqual(retained["stage_dispositions"], [])
        self.assertEqual(retained["checkpoints"], {"c1": self.c1["portfolio"], "c2": None})
        self.assertEqual(set(retained["rollouts"]), {"c1"})
        before = len(self.fake.sent)
        # This unit tests routing/native folds; the separate actual journey covers ledger settlement.
        assessment_ledger = SimpleNamespace(manifest={"inputs": {"study_sha256": digest(["assessment", self.child])}},
                                          dispatch=self.dispatch)
        book.open.return_value = (assessment_ledger, self.profile, self.root / "assessment")
        row = workflow._assessment(book, generation)
        self.assertTrue(row["targets"]["c1"]["complete"])
        self.assertIsNone(row["targets"]["fixed"])
        self.assertIsNone(row["targets"]["c2"])
        self.assertIsNone(row["selected_checkpoint"])
        self.assertEqual(len(self.fake.sent) - before, 13)
        analysis = assessment.analyze_pairs([row])
        self.assertFalse(analysis["primary_complete"])
        self.assertEqual(analysis["contrasts"]["official"]["utility"]["n"], 0)

    def test_tampered_saved_checkpoint_is_rejected_before_any_assessment(self):
        target = self.root / "tampered-search"
        write_once(target / "identity.json", self.identity)
        for label, record in (("c1", self.c1), ("c2", self.c2)):
            directory = target / "rollouts" / label
            strategy.materialize_seed(directory / "harness")
            changed = copy.deepcopy(record)
            if label == "c1":
                changed["portfolio"]["responses"][0]["text"] += " Unrecorded modification."
            write_once(directory / ("rollout.json" if label == "c1" else "failure.json"), changed)
        before = len(self.fake.sent)
        with self.assertRaises(ContractError):
            self.retained(search=target)
        self.assertEqual(len(self.fake.sent), before)

    def test_foreign_accounting_origin_is_rejected_before_native_replay(self):
        with patch.object(native, "validate_adaptive_partial", side_effect=AssertionError("origin first")), \
                self.assertRaises(ContractError):
            self.retained(state={**self.state, "study_sha256": "f" * 64})
