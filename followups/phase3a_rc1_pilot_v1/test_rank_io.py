"""RC1 fixed/native execution and exact replay through actual in-memory SDK HTTP."""
from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from harness2.core.proposer import Proposer, Reply
from harness2.core.spec import ChannelSpec

from buddha2.artifacts import ContractError, digest
from buddha2.phase2_contracts import validate_permutation
from followups.phase3a_v1.mocks import SDKMock
from followups.phase3a_v1.tests.test_strategy import STUDY, TASK

from . import editor, native, rank_io, strategy
from .support import BASE


class Dispatch:
    def __init__(self, mock):
        self.mock = mock
        self.results: dict = {}
        self.requests: dict = {}

    def __call__(self, slot, role, request):
        if slot in self.results:
            if self.results[slot]["request_sha256"] != digest(request):
                raise ContractError("fixture request changed during replay")
            return copy.deepcopy(self.results[slot])
        self.mock.select(role, slot)
        response = self.mock.transport.create(role, request)
        self.requests[slot] = copy.deepcopy(request)
        value = {"slot_id": slot, "role": role, "study_sha256": STUDY, "fixture": True,
            "status": "response", "request_sha256": digest(request), "dispatch_id": "fixture:" + slot,
            "spent_micro_usd": 1, "reserved_micro_usd": 0, "intent_sha256": digest({"slot": slot, "request": request}),
            "response": response}
        self.results[slot] = value
        return copy.deepcopy(value)


class RankIOTests(unittest.TestCase):
    def setUp(self):
        root = BASE / "rank-io-tests"
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.root = Path(self.temp.name)
        self.seed = self.root / "seed"
        strategy.materialize_seed(self.seed)

    def tearDown(self):
        self.temp.cleanup()

    def check_rank(self, record, dispatch):
        derived = record["rank_io"]
        self.assertTrue(derived["fixture"])
        self.assertFalse(derived["eligible_live_result"])
        rank = record["requests"][-1]
        body = json.loads(dispatch.requests[rank["slot_id"]]["messages"][0]["content"])
        self.assertEqual([r["id"] for r in body["responses"]], list(rank_io.LABELS))
        self.assertEqual(derived["raw_reply_sha256"], __import__("hashlib").sha256(rank["response"]["text"].encode()).hexdigest())
        self.assertEqual(derived["result_sha256"], digest(rank))
        validate_permutation(record["parent_B"], record["portfolio"])
        self.assertEqual(record["parent_B"]["provenance"]["settings_sha256"], record["portfolio"]["provenance"]["settings_sha256"])

    def test_fixed_six_actual_sdk_shared_codec_and_zero_call_replay(self):
        with SDKMock() as mock:
            dispatch = Dispatch(mock)
            record = strategy.fixed_best6(TASK, self.seed, study_sha256=STUDY, run_id="rp1-fixed", dispatch=dispatch, fixture=True)
            self.assertEqual(record["status"], "complete")
            self.assertEqual(Counter(r["role"] for r in mock.records), {"plan": 6, "answer": 60, "rank": 6, "fixed_selector": 1})
            for candidate in record["candidates"]:
                self.check_rank(candidate, dispatch)
            before = len(mock.records)
            self.assertEqual(strategy.validate_fixed(record, TASK, self.seed, study_sha256=STUDY,
                run_id="rp1-fixed", fixture=True, results=dispatch.results), record)
            self.assertEqual(len(mock.records), before)

    def test_stale_valid_aliases_and_actual_raw_response_ownership(self):
        with SDKMock() as mock:
            dispatch = Dispatch(mock)
            record = strategy.execute_cn(TASK, self.seed, study_sha256=STUDY, run_id="rp1-ownership", dispatch=dispatch, fixture=True)
            self.check_rank(record, dispatch)
            parent = record["parent_B"]
            consumed = strategy.validate_harness(self.seed)["strategy"]
            result = record["requests"][-1]
            context = {"study_sha256": STUDY, "run_id": record["run_id"], "slot_id": result["slot_id"], "arm": "fixed", "fixture": True}
            prepared = rank_io.prepare(parent, TASK, consumed, context)
            self.assertEqual(rank_io.derive(parent, TASK, consumed, context, prepared, result), record["rank_io"])
            for changed in (context | {"run_id": "other"}, context | {"arm": "adaptive"}):
                with self.subTest(context=changed), self.assertRaises(ContractError):
                    rank_io.derive(parent, TASK, consumed, changed, prepared, result)
            for field, value in (("request_sha256", "f" * 64), ("slot_id", "wrong-rank"), ("fixture", False)):
                with self.subTest(field=field), self.assertRaises(ContractError):
                    rank_io.derive(parent, TASK, consumed, context, prepared, result | {field: value})

    def test_real_native_four_rollouts_same_codec_and_saved_replay(self):
        owner = self
        class FixtureProposer(Proposer):
            def call(self, mission, context_dir=None, label="", **kwargs):
                context = Path(context_dir)
                harvest = owner.root / "fixture-proposals" / label
                shutil.copytree(context / "harness", harvest)
                value = strategy.validate_harness(harvest)["strategy"]
                value["rank_system"] += "\nSynthetic semantic preference for this contained check."
                (harvest / "systemprompt.md").write_text(json.dumps(value), encoding="utf-8")
                reply = Reply(label=label, text="<notes>Synthetic fixture only.</notes>", ok=True, attempts=1, workspace=harvest)
                self._calls.append(reply)
                return reply
            def phase3a_evidence(self):
                return {"fixture": True, "study_sha256": STUDY, "backend": "synthetic-test", "model": "no-model", "sessions": {}}
        prop = FixtureProposer(ChannelSpec("opencode", "anthropic/claude-opus-5", effort="high", steps=editor.MAX_STEPS, timeout=600),
            audit_dir=self.root / "fixture-audit")
        with SDKMock() as mock:
            dispatch = Dispatch(mock)
            record = native.run_adaptation(TASK, self.seed, study_sha256=STUDY, run_root=self.root / "native-run", tag="rp1-test",
                dispatch=dispatch, fixture=True, prop=prop, known_results={}, result_snapshot=lambda: dispatch.results)
            self.assertEqual(record["status"], "complete")
            self.assertEqual(set(record["rollouts"]), set(native.LABELS))
            self.assertEqual(len(mock.records), 48)
            self.assertEqual(record["native"]["modes"]["agg"]["ledger"]["R"], 4)
            self.assertEqual(record["native"]["modes"]["agg"]["ledger"]["P"], 3)
            for rollout in record["rollouts"].values():
                self.check_rank(rollout, dispatch)
            before = len(mock.records)
            self.assertEqual(native.validate_adaptation(record, TASK, self.seed, study_sha256=STUDY,
                run_root=self.root / "native-run", tag="rp1-test", fixture=True, results=dispatch.results), record)
            self.assertEqual(len(mock.records), before)
