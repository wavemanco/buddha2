"""Native checkpoint-boundary regressions; no proposer or provider execution."""
from __future__ import annotations

import copy
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

from harness2.core.spec import ChannelSpec

from buddha2.artifacts import ContractError, digest, file_hash, read_json, write_once
from followups.phase3a_v1.tests.test_strategy import STUDY, TASK, FakeDispatch
from followups.phase3b_seq2_v1 import accounting, editor, native, strategy
from followups.phase3b_seq2_v1.support import NATIVE

RECOVERY = "required-plan-rank-once-v1"


class SettledTrace(FakeDispatch):
    def __call__(self, slot, role, request):
        result = super().__call__(slot, role, request)
        result["intent_sha256"] = digest([slot, digest(request)])
        self.results[slot] = copy.deepcopy(result)
        return result


class NativeResumeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.blocked = [self.stack.enter_context(patch(name, side_effect=AssertionError("external activity")))
            for name in ("anthropic.Anthropic", "anthropic.AsyncAnthropic", "openai.OpenAI",
                         "openai.AsyncOpenAI", "socket.create_connection", "socket.socket.connect",
                         "socket.socket.connect_ex", "subprocess.run", "subprocess.Popen")]
        NATIVE.mkdir(parents=True, exist_ok=True)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix="resume-boundary-", dir=NATIVE)))
        self.journals: dict[str, Path] = {}
        self.stack.enter_context(patch.object(accounting, "canonical_journal",
            side_effect=lambda child, fixture: self.journals[child]))
        self.dispatch = Mock(side_effect=AssertionError("dispatch forbidden"))
        self.paid = {"p4-01.adaptive.editor.inv1.a1.t01": {
            "study_sha256": STUDY, "pair": "p4-01", "role": "editor", "status": "response",
            "spent_micro_usd": 1, "reserved_micro_usd": 0}}
        self.state = {"results": self.paid, "intents": {}, "reserved_micro_usd": 0,
            "active_unsettled_intents": [], "durable_unknown_results": 0}
        self.stack.enter_context(patch.object(accounting, "replay", return_value=self.state))
        self.stack.enter_context(patch.object(editor, "completed_author_segments", side_effect=lambda *a, **k: []))

    def tearDown(self):
        self.assertTrue(all(mock.call_count == 0 for mock in self.blocked))
        self.dispatch.assert_not_called()

    def source(self, revision: str) -> dict:
        body = {"kind": "buddha2-effective-source-v2", "schema_version": 2, "files": {"fixture": revision}}
        return body | {"sha256": digest(body)}

    def search(self, physical: str, source: dict, *, identity: bool = True) -> Path:
        search = self.root / physical / "mock/p4-01/adaptive/search"
        search.mkdir(parents=True)
        journal = self.root / (physical + "-journal")
        journal.mkdir()
        write_once(journal / "manifest.json", {"inputs": {"bindings": {"source_sha256": source["sha256"]}}})
        self.journals[physical] = journal
        if identity:
            write_once(search / "identity.json", {"task": TASK, "study_sha256": STUDY,
                "fixture": True, "tag": "resume-boundary"})
        return search

    def certificate(self, old: dict, new: dict, segment: dict) -> dict:
        body = {"kind": "phase4-cm1-continuation-compatibility-v1", "passed": True,
            "provider_calls": 0, "previous_source_sha256": old["sha256"],
            "current_source_sha256": new["sha256"], "origin_source": old,
            "origin_sources": {old["sha256"]: old}, "validated_segments": [segment]}
        return body | {"sha256": digest(body)}

    def adapter(self, search: Path, origin: Path, certificate: dict, seed: Path):
        return native.PortfolioAdapter(TASK, seed, study_sha256=STUDY, run_root=search,
            tag="resume-boundary", dispatch=self.dispatch, fixture=True,
            channel=ChannelSpec("opencode", "anthropic/claude-opus-5", effort="high"),
            known_results=copy.deepcopy(self.paid), halt=Mock(), resume_from=origin,
            compatibility=certificate)

    def test_paid_author_prefix_without_proof_is_rejected_before_dispatch(self):
        source = self.source("original")
        origin = self.search("a" * 64, source)
        with patch.object(strategy, "execute_cn", side_effect=AssertionError("solver execution forbidden")) as execute:
            with self.assertRaisesRegex(ContractError, "paid author prefix"):
                native.continuation_segments(origin, known_results=self.paid,
                    request_policy=None, origin_source=source)
            execute.assert_not_called()

    def test_second_resume_preserves_adopted_author_before_scheduler(self):
        first_source, second_source, third_source = [self.source(name) for name in ("first", "second", "third")]
        origin = self.search("a" * 64, first_source)
        artifact = origin / "completed-author-proof.json"
        write_once(artifact, {"normal_author_fixture": True})
        body = {"kind": "native-author-stage-v1", "label": "inv1.a1", "origin_search": str(origin),
            "logical_study_sha256": STUDY, "source_sha256": first_source["sha256"],
            "files_sha256": {artifact.name: file_hash(artifact)},
            "result_sha256": {slot: digest(row) for slot, row in self.paid.items()}}
        segment = body | {"sha256": digest(body)}
        seed = self.root / "seed"
        strategy.materialize_seed(seed)
        intermediate = self.search("b" * 64, second_source, identity=False)
        final = self.search("c" * 64, third_source, identity=False)
        first_certificate = self.certificate(first_source, second_source, segment)
        second_certificate = self.certificate(second_source, third_source, segment)
        second_certificate["origin_sources"][first_source["sha256"]] = first_source
        second_certificate["sha256"] = digest({k: v for k, v in second_certificate.items() if k != "sha256"})
        schedule = native._modules()["schedule"]
        with patch.object(schedule, "run_task", side_effect=AssertionError("scheduler must not execute")) as run:
            with patch.object(native, "continuation_segments", return_value=[segment]):
                self.adapter(intermediate, origin, first_certificate, seed)
            adopted = read_json(intermediate / "origin-author-stages/inv1.a1.json")
            self.assertEqual(adopted["segment"], segment)
            found = native.continuation_segments(intermediate, known_results=self.paid,
                request_policy=None, origin_source=second_source)
            self.assertEqual(found, [segment])
            self.adapter(final, intermediate, second_certificate, seed)
            copied = read_json(final / "origin-author-stages/inv1.a1.json")
            self.assertEqual(copied["segment"], segment)
            self.assertEqual(copied["segment"]["source_sha256"], first_source["sha256"])
            run.assert_not_called()

    def saved_rollout(self, physical: str, *, recovery: str | None, fail: bool):
        source = self.source(physical)
        search = self.search(physical, source, identity=False)
        seed = self.root / (physical + "-seed")
        strategy.materialize_seed(seed)
        ids = native.adaptive_run_ids(TASK["id"], "resume-boundary")
        trace = SettledTrace()
        trace.wrapped_rank = False
        if fail:
            trace.invalid_plan_suffix = strategy.slot_prefix(ids["c1"])
        try:
            record = strategy.execute_cn(TASK, seed, study_sha256=STUDY, run_id=ids["c1"],
                dispatch=trace, fixture=True, arm="adaptive", recovery_policy=recovery)
        except strategy.KnownOutcomeError as exc:
            record = exc.evidence
        path = search / "rollouts/c1"
        strategy.materialize_seed(path / "harness")
        write_once(path / ("failure.json" if fail else "rollout.json"), record)
        identity = {"task": TASK, "study_sha256": STUDY, "fixture": True, "tag": "resume-boundary",
            "run_ids": ids, "seed": strategy.validate_harness(seed)}
        if recovery:
            identity["recovery_policy"] = recovery
        write_once(search / "identity.json", identity)
        self.state["results"] = trace.results
        adapter = object.__new__(native.PortfolioAdapter)
        adapter.task, adapter.harness_dir, adapter.run_root = copy.deepcopy(TASK), seed, search
        adapter.study_sha256, adapter.fixture, adapter.tag = STUDY, True, "resume-boundary"
        adapter.request_policy, adapter.recovery_policy = None, recovery
        adapter.known_results, adapter.ids = copy.deepcopy(trace.results), ids
        adapter.required_failure, adapter.on_required_failure = None, None
        adapter.dispatch = self.dispatch
        return adapter, record, trace, source

    def test_saved_exhausted_recovery_failure_replays_without_dispatch(self):
        for index, recovery in enumerate((None, RECOVERY)):
            with self.subTest(recovery=recovery):
                adapter, record, trace, source = self.saved_rollout(str(index + 1) * 64,
                    recovery=recovery, fail=True)
                self.assertEqual(len(trace.sent), 1 if recovery is None else 2)
                self.assertEqual("required_artifact_failures" in record, recovery is not None)
                checked = native.validate_adaptive_partial(TASK, adapter.harness_dir,
                    study_sha256=STUDY, run_root=adapter.run_root, tag=adapter.tag, fixture=True,
                    results=trace.results, recovery_policy=recovery)
                self.assertEqual(checked["c1"]["status"], "failed")
                with self.assertRaises(strategy.KnownOutcomeError) as caught:
                    adapter._execute(TASK["id"], adapter.harness_dir, adapter.ids["c1"])
                self.assertEqual(caught.exception.evidence, record)
                segments = native.continuation_segments(adapter.run_root,
                    known_results=trace.results, request_policy=None, origin_source=source)
                rollout = next(row for row in segments if row["label"] == "c1")
                self.assertEqual(rollout["status"], "failed")
                self.assertEqual(rollout.get("recovery_policy"), recovery)
                self.assertEqual(rollout["record_sha256"], digest(record))

    def test_completed_native_rollout_replays_unchanged_without_dispatch(self):
        adapter, record, trace, _ = self.saved_rollout("d" * 64, recovery=RECOVERY, fail=False)
        before = file_hash(adapter.run_root / "rollouts/c1/rollout.json")
        checked = native.validate_adaptive_partial(TASK, adapter.harness_dir, study_sha256=STUDY,
            run_root=adapter.run_root, tag=adapter.tag, fixture=True, results=trace.results,
            recovery_policy=RECOVERY)
        self.assertEqual(checked["c1"]["status"], "complete")
        self.assertEqual(adapter._execute(TASK["id"], adapter.harness_dir, adapter.ids["c1"]),
            adapter.run_root / "rollouts/c1")
        self.assertEqual(file_hash(adapter.run_root / "rollouts/c1/rollout.json"), before)
        self.assertEqual(read_json(adapter.run_root / "rollouts/c1/rollout.json"), record)
        self.assertEqual(len(trace.sent), 12)
