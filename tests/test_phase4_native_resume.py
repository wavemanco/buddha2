"""Native checkpoint-boundary regressions; no proposer or provider execution."""
from __future__ import annotations

import copy
import json
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
COMPLETED_AUTHORS = editor.completed_author_segments


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
        self.states: dict[Path, dict] = {}
        self.stack.enter_context(patch.object(accounting, "canonical_journal",
            side_effect=lambda child, fixture: self.journals[child]))
        self.dispatch = Mock(side_effect=AssertionError("dispatch forbidden"))
        self.paid = {"p4-01.adaptive.editor.inv1.a1.t01": {
            "study_sha256": STUDY, "pair": "p4-01", "role": "editor", "status": "response",
            "fixture": True, "spent_micro_usd": 1, "reserved_micro_usd": 0}}
        self.state = {"results": self.paid, "intents": {}, "reserved_micro_usd": 0,
            "active_unsettled_intents": [], "durable_unknown_results": 0,
            "transport_audit_summary": {"missing_or_invalid_slots": []}}
        self.stack.enter_context(patch.object(accounting, "replay",
            side_effect=lambda journal: copy.deepcopy(self.states[Path(journal)])))
        self.stack.enter_context(patch.object(accounting, "journal_reference", side_effect=self.reference))
        self.stack.enter_context(patch.object(accounting, "read_reference", side_effect=self.read_reference))
        self.stack.enter_context(patch.object(accounting, "_read_reference_cached", side_effect=self.read_reference))
        self.stack.enter_context(patch.object(editor, "completed_author_segments", side_effect=lambda *a, **k: []))

    def tearDown(self):
        self.assertTrue(all(mock.call_count == 0 for mock in self.blocked))
        self.dispatch.assert_not_called()

    def source(self, revision: str) -> dict:
        body = {"kind": "buddha2-effective-source-v2", "schema_version": 2, "files": {
            "fixture": revision, "followups/phase3b_seq2_v1/editor.py": file_hash(Path(editor.__file__))}}
        return body | {"sha256": digest(body)}

    def reference(self, journal: Path) -> dict:
        manifest = read_json(journal / "manifest.json")
        body = {"kind": "phase3b-journal-reference-v1",
            "execution_study_sha256": manifest["inputs"]["study_sha256"],
            "fixture": manifest["inputs"]["fixture"],
            "manifest_sha256": file_hash(journal / "manifest.json"),
            "events_sha256": file_hash(journal / "events.jsonl")}
        return body | {"sha256": digest(body)}

    def read_reference(self, reference: dict, *, _pins=None):
        # Keep real cryptographic pin/path and ancestry traversal checks; only
        # replace full accounting replay with the supplied synthetic snapshot.
        journal = accounting._reference_path(reference)
        return copy.deepcopy(self.states[journal]), read_json(journal / "manifest.json")

    def search(self, physical: str, source: dict, *, identity: bool = True) -> Path:
        search = self.root / physical / "mock/p4-01/adaptive/search"
        search.mkdir(parents=True)
        journal = self.root / (physical + "-journal")
        journal.mkdir()
        write_once(journal / "manifest.json", {"inputs": {"study_sha256": physical, "fixture": True,
            "bindings": {"source_sha256": source["sha256"]}, "slots": {},
            "policy": {"phase4_child": {"kind": "inference", "pair": "p4-01"}}}})
        (journal / "events.jsonl").write_bytes(b"")
        self.journals[physical] = journal
        self.states[journal] = copy.deepcopy(self.state)
        self.states[journal].update(study_sha256=physical, fixture=True)
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
        self.states[self.journals[physical]] = {**copy.deepcopy(self.state),
            "study_sha256": physical, "fixture": True}
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

    def ancestry_fixture(self):
        number = len(self.journals)
        old_id, new_id = digest([number, "old"]), digest([number, "new"])
        old_source, new_source = self.source(old_id), self.source(new_id)
        old, new = self.search(old_id, old_source), self.search(new_id, new_source)
        slot = "p4-01.adaptive.editor.select.seq2.t01"
        later = "p4-01.adaptive.editor.inv1.a1.t01"
        request = {"model": "synthetic", "messages": [{"role": "user", "content": "SYNTHETIC saved input"}]}
        intent = {"slot_id": slot, "study_sha256": STUDY, "request": request,
            "request_sha256": digest(request), "reservation": {"micro_usd": 1}}
        result = {"slot_id": slot, "study_sha256": STUDY, "fixture": True, "pair": "p4-01",
            "role": "native_selector", "status": "response", "request_sha256": digest(request),
            "spent_micro_usd": 1, "reserved_micro_usd": 0}
        slots = {slot: {"role": "native_selector", "pair": "p4-01", "cell": "p4-01:adaptive"},
            later: {"role": "editor", "pair": "p4-01", "cell": "p4-01:adaptive"}}
        for physical, paid in ((old_id, True), (new_id, False)):
            journal = self.journals[physical]
            manifest = read_json(journal / "manifest.json")
            manifest["inputs"]["slots"] = copy.deepcopy(slots)
            self.save(manifest, journal / "manifest.json")
            state = {**copy.deepcopy(self.state), **accounting.core._counter(), "study_sha256": physical,
                "fixture": True, "status": "ready", "results": {slot: copy.deepcopy(result)} if paid else {},
                "intents": {slot: copy.deepcopy(intent)} if paid else {},
                "cells": {"p4-01:adaptive": accounting.core._counter()}, "assessment": accounting.core._counter()}
            if paid:
                state.update(attempts=1, spent_micro_usd=1)
                state["cells"]["p4-01:adaptive"].update(attempts=1, spent_micro_usd=1)
            self.states[journal] = state
        snapshot: dict = {"kind": "phase3b-selector-input-v1", "files": {}, "effective_strategy_sha256": None}
        snapshot["sha256"] = digest(snapshot)
        binding = {"fixture": True, "study_sha256": STUDY, "pilot": "p4-01",
            "source_sha256": file_hash(Path(editor.__file__)), "editor_profile_sha256": digest(editor.profile())}
        session = {"fixture": True, "status": "empty", "terminal_note_used": False,
            "input_snapshot": snapshot, "input_effective_strategy_sha256": None,
            "result_slots": [slot], "requests": [{"slot_id": slot, "raw_sha256": digest(request),
                "effective_sha256": digest(request), "result_sha256": digest(result), "role_translation": None}]}
        for search in (old, new):
            proof = search / "editor-audit/phase3a-sessions"
            write_once(proof / "select.seq2.started.json", {"binding": binding,
                "label": "select.seq2", "input_snapshot": snapshot})
            settled = {"binding": binding, "label": "select.seq2", "session": session}
            write_once(proof / "select.seq2.settled.json", {**settled, "sha256": digest(settled)})
        self.bind_ancestor(new_id, old_id)
        return old, new, old_source, new_source, slot, later

    def save(self, value, path):
        path.write_text(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
                        encoding="utf-8")

    def bind_ancestor(self, successor, ancestor):
        journal = self.journals[successor]
        manifest = read_json(journal / "manifest.json")
        manifest["inputs"]["policy"]["phase4_child"]["continuation"] = accounting.continuation_binding(
            [self.reference(self.journals[ancestor])], logical_study_sha256=STUDY)
        self.save(manifest, journal / "manifest.json")

    def collect_real_authors(self, search, source, results):
        with patch.object(editor, "completed_author_segments", wraps=COMPLETED_AUTHORS) as collect:
            value = native.continuation_segments(search, known_results=results,
                request_policy=None, origin_source=source)
            return value, collect.call_args.kwargs

    def test_inherited_session_uses_original_intent_and_result_without_rewriting_proof(self):
        old, new, _, source, slot, _ = self.ancestry_fixture()
        original = self.states[self.journals[old.parents[3].name]]
        before = {p: p.read_bytes() for p in self.root.rglob("*.json")}
        found, passed = self.collect_real_authors(new, source, copy.deepcopy(original["results"]))
        self.assertEqual(passed["intents"], original["intents"])
        self.assertEqual(passed["results"], original["results"])
        self.assertEqual(found[0]["kind"], "native-author-quarantine-v1")
        self.assertEqual(found[0]["result_sha256"], {slot: digest(original["results"][slot])})
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*.json")})

    def test_older_search_excludes_later_segment_author_rows(self):
        old, new, source, _, _, later = self.ancestry_fixture()
        original = self.states[self.journals[old.parents[3].name]]
        later_result = copy.deepcopy(next(iter(original["results"].values())))
        later_result.update(slot_id=later, role="editor")
        self.states[self.journals[new.parents[3].name]]["results"][later] = later_result
        group = {**original["results"], later: later_result}
        _, passed = self.collect_real_authors(old, source, group)
        self.assertEqual(passed["results"], original["results"])
        self.assertNotIn(later, passed["results"])
        self.assertEqual(passed["intents"], original["intents"])

    def test_search_ancestry_missing_conflicting_foreign_and_tampered_evidence_fails_closed(self):
        for case in ("missing_intent", "changed_intent", "missing_result", "changed_result", "duplicate_slot",
                     "foreign_pair", "foreign_kind", "foreign_fixture", "foreign_worklist", "foreign_logical",
                     "unknown", "pending", "transport_gap",
                     "tampered_pin", "tampered_source"):
            with self.subTest(case=case):
                old, new, _, source, slot, _ = self.ancestry_fixture()
                old_id, new_id = old.parents[3].name, new.parents[3].name
                state, current = self.states[self.journals[old_id]], self.states[self.journals[new_id]]
                group = copy.deepcopy(state["results"])
                manifest = read_json(self.journals[old_id] / "manifest.json")
                if case == "missing_intent":
                    state["intents"].clear()
                elif case == "changed_intent":
                    state["intents"][slot]["request"]["model"] = "changed"
                elif case == "missing_result":
                    group.clear()
                elif case == "changed_result":
                    group[slot]["spent_micro_usd"] += 1
                elif case == "duplicate_slot":
                    current["results"], current["intents"] = copy.deepcopy(state["results"]), copy.deepcopy(state["intents"])
                elif case == "foreign_pair":
                    manifest["inputs"]["policy"]["phase4_child"]["pair"] = "p4-02"
                elif case == "foreign_kind":
                    manifest["inputs"]["policy"]["phase4_child"]["kind"] = "assessment"
                elif case == "foreign_fixture":
                    manifest["inputs"]["fixture"] = state["fixture"] = False
                elif case == "foreign_worklist":
                    manifest["inputs"]["slots"][slot]["role"] = "editor"
                elif case == "foreign_logical":
                    state["results"][slot]["study_sha256"] = "0" * 64
                    group = copy.deepcopy(state["results"])
                elif case == "unknown":
                    state["durable_unknown_results"] = 1
                    state["reserved_micro_usd"] = 1
                elif case == "pending":
                    state["active_unsettled_intents"] = [slot]
                elif case == "transport_gap":
                    state["transport_audit_summary"]["missing_or_invalid_slots"] = [slot]
                self.save(manifest, self.journals[old_id] / "manifest.json")
                self.bind_ancestor(new_id, old_id)
                if case == "tampered_pin":
                    (self.journals[old_id] / "events.jsonl").write_bytes(b"changed")
                elif case == "tampered_source":
                    source["files"]["fixture"] = "changed"
                with self.assertRaises(ContractError):
                    self.collect_real_authors(new, source, group)
                self.dispatch.assert_not_called()
