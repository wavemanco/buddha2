"""Fresh C-N conformance, restricted authoring and fail-closed request replay."""
import copy
import json
import os
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from typing import Any
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest
from buddha2.phase2 import render_request
from buddha2.phase2_contracts import validate_permutation
from followups.phase3a_v1 import strategy

TASK = {"id": "p3a-test", "prompt": "Suggest ten useful ways to welcome a visitor.",
        "domain": "development", "source_context": {"dataset": "NoveltyBench/curated",
        "revision": "64a23be6b18ec1dacc298830aab276061b6e143c", "source_sha256": "a" * 64,
        "source_task_id": "curated-test"}}
STUDY = "b" * 64


class FakeDispatch:
    """In-memory classified fixture results, never a provider transport."""
    def __init__(self, *, fixture=True):
        self.fixture = fixture
        self.results: dict = {}
        self.requests: dict = {}
        self.sent: list = []
        self.invalid_plan_suffix = ""
        self.invalid_selector = False
        self.wrapped_rank = True

    def __call__(self, slot, role, request):
        if slot in self.results:
            if self.results[slot]["request_sha256"] != digest(request):
                raise ContractError("fixture slot request changed")
            return copy.deepcopy(self.results[slot])
        self.sent.append((slot, role))
        self.requests[slot] = copy.deepcopy(request)
        payload: Any = None
        if role == "plan":
            payload = ({"wrong": []} if self.invalid_plan_suffix and slot.startswith(self.invalid_plan_suffix)
                       else {"angles": [{"id": f"angle-{i:02d}", "angle": f"Direction {i}"}
                                        for i in range(1, 11)]})
        elif role == "rank":
            body = json.loads(request["messages"][0]["content"])
            payload = {"order": [r["id"] for r in reversed(body["responses"])]}
        elif role == "fixed_selector":
            body = json.loads(request["messages"][0]["content"])
            payload = {"candidate_id": "absent" if self.invalid_selector else body["candidates"][0]["id"]}
        elif role == "group":
            payload = {"groups": [[i, i + 1] for i in range(0, 10, 2)]}
        elif role == "quality":
            payload = {"score": 8}
        text = json.dumps(payload) if payload is not None else "A useful fixture answer for " + slot
        if role == "rank" and self.wrapped_rank:
            text = "A visible explanation.\n" + text + "\nSame order:\n" + text
        value = {"slot_id": slot, "role": role, "study_sha256": STUDY, "fixture": self.fixture,
                 "status": "response", "request_sha256": digest(request),
                 "dispatch_id": "fixture:" + slot, "spent_micro_usd": 1, "reserved_micro_usd": 0,
                 "response": {"model": request["model"], "text": text,
                    "stop_reason": "stop" if role == "group" else "end_turn",
                    "usage": {"input_tokens": 100, "output_tokens": 40,
                              "service_tier": "default" if role == "group" else "standard"}}}
        self.results[slot] = value
        return copy.deepcopy(value)


class StrategyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", str(strategy.ROOT / "runs"))))
        self.root = Path(self.temp.name)
        self.harness = self.root / "seed"
        strategy.materialize_seed(self.harness)

    def tearDown(self):
        self.temp.cleanup()

    def test_original_seed_wire_payloads_and_every_consumed_field(self):
        fields = strategy.validate_harness(self.harness)["strategy"]
        angle = {"id": "angle-01", "angle": "A supplied angle"}
        responses = [{"id": f"response-{i}", "text": f"Answer {i}"} for i in range(10)]
        for role, name in (("answer", "answer_system"), ("plan", "plan_system"), ("rank", "rank_system")):
            kwargs = {"angle": angle} if role == "answer" else {"responses": responses} if role == "rank" else {}
            expected = render_request(role, TASK, templates=strategy.seed_templates(), **kwargs)
            actual = strategy.render_strategy_request(role, TASK, fields, **kwargs)
            self.assertEqual(actual, expected)
            changed = fields | {name: fields[name] + "\nA real permitted instruction."}
            different = strategy.render_strategy_request(role, TASK, changed, **kwargs)
            self.assertEqual({k: v for k, v in actual.items() if k != "system"},
                             {k: v for k, v in different.items() if k != "system"})
            self.assertNotEqual(actual["system"], different["system"])

    def test_strict_surface_and_raw_compatibility_inventory(self):
        seed = strategy.seed_tree()["systemprompt.md"]
        value = json.loads(seed)
        for raw in (json.dumps(value | {"extra": "bad"}), json.dumps(value | {"plan_system": " "}),
                    '{"answer_system":"a","plan_system":"p","rank_system":"r","rank_system":"x"}',
                    json.dumps(value | {"answer_system": 2}), "[" + seed + "]", "x" * 24_001):
            with self.subTest(raw=raw[:60]), self.assertRaises(ContractError):
                strategy.parse_strategy(raw)
        checked = strategy.validate_harness(self.harness)
        (self.harness / "systemprompt.md").write_text(json.dumps(value), encoding="utf-8")
        whitespace = strategy.validate_harness(self.harness)
        self.assertEqual(checked["effective_strategy_sha256"], whitespace["effective_strategy_sha256"])
        self.assertNotEqual(checked["raw_tree_sha256"], whitespace["raw_tree_sha256"])
        readme = self.harness / "skills/README.md"
        original = readme.read_bytes()
        readme.write_bytes(original + b"changed")
        with self.assertRaises(ContractError):
            strategy.validate_harness(self.harness)
        readme.write_bytes(original)
        (self.harness / "unconsumed").mkdir()
        with self.assertRaises(ContractError):
            strategy.validate_harness(self.harness)
        (self.harness / "unconsumed").rmdir()
        (self.harness / "scripts/forbidden.py").write_text("pass", encoding="utf-8")
        with self.assertRaises(ContractError):
            strategy.validate_harness(self.harness)

    def test_twelve_fresh_requests_normalized_rank_and_exact_replay(self):
        dispatch = FakeDispatch()
        record = strategy.execute_cn(TASK, self.harness, study_sha256=STUDY,
                                     run_id="fresh", dispatch=dispatch, fixture=True)
        self.assertEqual(Counter(role for _, role in dispatch.sent), {"plan": 1, "answer": 10, "rank": 1})
        self.assertEqual(record["status"], "complete")
        self.assertEqual(len(record["normalization"]["candidates"]), 2)
        validate_permutation(record["parent_B"], record["portfolio"])
        self.assertEqual(strategy.validate_rollout(record, TASK, self.harness,
            study_sha256=STUDY, fixture=True, results=dispatch.results), record)
        before = len(dispatch.sent)
        self.assertEqual(strategy.execute_cn(TASK, self.harness, study_sha256=STUDY,
                         run_id="fresh", dispatch=dispatch, fixture=True), record)
        self.assertEqual(len(dispatch.sent), before)
        tampered = copy.deepcopy(record)
        tampered["portfolio"]["responses"][0]["text"] = "changed"
        with self.assertRaises(ContractError):
            strategy.validate_rollout(tampered, TASK, self.harness,
                study_sha256=STUDY, fixture=True, results=dispatch.results)

    def test_known_plan_failure_is_not_unknown_and_has_no_dependent_calls(self):
        dispatch = FakeDispatch()
        dispatch.invalid_plan_suffix = strategy.slot_prefix("bad")
        with self.assertRaises(strategy.KnownOutcomeError) as error:
            strategy.execute_cn(TASK, self.harness, study_sha256=STUDY,
                                run_id="bad", dispatch=dispatch, fixture=True)
        self.assertEqual(error.exception.evidence["reason"], "invalid_plan")
        self.assertEqual(len(dispatch.sent), 1)
        self.assertEqual(strategy.validate_rollout(error.exception.evidence, TASK, self.harness,
            study_sha256=STUDY, fixture=True, results=dispatch.results), error.exception.evidence)
        unknown = FakeDispatch()
        slot = strategy.slot_ids("unknown")["plan"]
        request = strategy.render_strategy_request("plan", TASK, strategy.validate_harness(self.harness)["strategy"])
        result = unknown(slot, "plan", request)
        unknown.results[slot] = result | {"status": "unknown", "reserved_micro_usd": 1}
        with self.assertRaises(ContractError) as failure:
            strategy.fixed_best6(TASK, self.harness, study_sha256=STUDY,
                run_id="control", dispatch=lambda *args: unknown.results[slot], fixture=True)
        self.assertNotIsInstance(failure.exception, strategy.KnownOutcomeError)

    def test_fixed_six_candidate_failures_are_retained_no_replacements_or_selector_repair(self):
        dispatch = FakeDispatch()
        dispatch.invalid_plan_suffix = strategy.slot_prefix("fixed/candidate-01")
        record = strategy.fixed_best6(TASK, self.harness, study_sha256=STUDY,
                                     run_id="fixed", dispatch=dispatch, fixture=True)
        self.assertEqual(len(record["candidates"]), 6)
        self.assertEqual([r["status"] for r in record["candidates"]], ["failed"] + ["complete"] * 5)
        self.assertEqual(Counter(role for _, role in dispatch.sent),
                         {"plan": 6, "answer": 50, "rank": 5, "fixed_selector": 1})
        self.assertEqual(strategy.validate_fixed(record, TASK, self.harness,
            study_sha256=STUDY, run_id="fixed", fixture=True, results=dispatch.results), record)
        request = record["selection"]["request"]
        packet = json.loads(request["messages"][0]["content"])
        self.assertEqual(set(packet), {"task", "candidates"})
        self.assertTrue(all(set(c) == {"id", "answers"} and len(c["answers"]) == 10
                            for c in packet["candidates"]))
        bad = FakeDispatch()
        bad.invalid_selector = True
        missing = strategy.fixed_best6(TASK, self.harness, study_sha256=STUDY,
                                      run_id="missing", dispatch=bad, fixture=True)
        self.assertIsNone(missing["portfolio"])
        self.assertEqual(sum(role == "fixed_selector" for _, role in bad.sent), 1)

    def test_later_partial_foreign_request_blocks_before_earlier_missing_candidate_dispatch(self):
        old = FakeDispatch()
        run_id = "resume/candidate-06"
        strategy.execute_cn(TASK, self.harness, study_sha256=STUDY,
                            run_id=run_id, dispatch=old, fixture=True)
        slot = strategy.slot_ids(run_id)["plan"]
        partial = {slot: old.results[slot] | {"request_sha256": "0" * 64}}
        fresh = FakeDispatch()
        with self.assertRaises(ContractError):
            strategy.fixed_best6(TASK, self.harness, study_sha256=STUDY, run_id="resume",
                                 dispatch=fresh, fixture=True, known_results=partial)
        self.assertEqual(fresh.sent, [])

    def test_partial_unknown_is_reportable_but_blocks_every_new_call(self):
        from followups.phase3a_v1.accounting import LiabilityStop

        dispatch = FakeDispatch()
        run_id = "unknown/candidate-06"
        slot = strategy.slot_ids(run_id)["plan"]
        request = strategy.render_strategy_request("plan", TASK, strategy.validate_harness(self.harness)["strategy"])
        result = dispatch(slot, "plan", request)
        results = {slot: result | {"status": "unknown", "reserved_micro_usd": 1}}
        checked = strategy.validate_partial(TASK, self.harness, study_sha256=STUDY,
            run_id=run_id, fixture=True, arm="fixed", results=results)
        self.assertEqual(checked["status"], "unresolved")
        fresh = FakeDispatch()
        with self.assertRaises(LiabilityStop):
            strategy.fixed_best6(TASK, self.harness, study_sha256=STUDY, run_id="unknown",
                dispatch=fresh, fixture=True, known_results=results)
        self.assertEqual(fresh.sent, [])

    def test_budget_stop_preserves_partial_candidate_and_unattempted_suffix(self):
        from followups.phase3a_v1.accounting import CellBudgetStop

        dispatch = FakeDispatch()

        def limited(slot, role, request):
            if slot not in dispatch.results and len(dispatch.sent) >= 16:
                raise CellBudgetStop("fixture allowance exhausted")
            return dispatch(slot, role, request)

        record = strategy.fixed_best6(TASK, self.harness, study_sha256=STUDY,
                                     run_id="bounded", dispatch=limited, fixture=True)
        self.assertEqual(record["status"], "budget_stop")
        self.assertIsNone(record["portfolio"])
        self.assertEqual([r["status"] for r in record["candidates"]],
                         ["complete", "budget_stop"] + ["not_attempted"] * 4)
        self.assertEqual(len(record["candidates"][1]["requests"]), 4)
        self.assertEqual(strategy.validate_fixed(record, TASK, self.harness,
            study_sha256=STUDY, run_id="bounded", fixture=True, results=dispatch.results, stopped=True), record)
        with self.assertRaises(ContractError):
            strategy.validate_fixed(record, TASK, self.harness, study_sha256=STUDY,
                run_id="bounded", fixture=True, results=dispatch.results)

    def test_oversized_requests_fail_locally_without_dispatch_or_truncation(self):
        value = strategy.validate_harness(self.harness)["strategy"]
        value["plan_system"] = "x" * 6000
        (self.harness / "systemprompt.md").write_text(json.dumps(value), encoding="utf-8")
        dispatch = FakeDispatch()
        with self.assertRaises(strategy.KnownOutcomeError) as failure:
            strategy.execute_cn(TASK, self.harness, study_sha256=STUDY,
                                run_id="too-large", dispatch=dispatch, fixture=True)
        self.assertEqual(failure.exception.evidence["reason"], "payload_limit")
        self.assertEqual(dispatch.sent, [])
        (self.harness / "systemprompt.md").write_text(strategy.seed_tree()["systemprompt.md"], encoding="utf-8")
        with patch("followups.phase3a_v1.accounting._wire", return_value=b"x" * 1_048_577):
            record = strategy.fixed_best6(TASK, self.harness, study_sha256=STUDY,
                                         run_id="too-large-packet", dispatch=dispatch, fixture=True)
        self.assertEqual(record["reason"], "selector_payload_limit")
        self.assertIsNone(record["portfolio"])
        self.assertEqual(len(dispatch.sent), 72)
        self.assertFalse(any(role == "fixed_selector" for _, role in dispatch.sent))

    def test_validation_scope_rechecks_source_at_exit_and_next_operation(self):
        from followups.phase3a_v1.accounting import IntegrityStop

        original = strategy.file_hash
        changed = False

        def observed(path):
            if changed and ".upstream" in Path(path).parts:
                return "0" * 64
            return original(path)

        with patch.object(strategy, "file_hash", side_effect=observed):
            for readonly in (False, True):
                with self.subTest(readonly=readonly), self.assertRaises(IntegrityStop):
                    with strategy.validation_scope(readonly=readonly):
                        strategy.validate_harness(self.harness)
                        changed = True
                with self.assertRaises(IntegrityStop):
                    strategy.validate_harness(self.harness)
                changed = False
                strategy.validate_harness(self.harness)

    def test_readonly_snapshot_reuses_successful_inputs_and_returns_independent_copies(self):
        checked = strategy.validate_harness(self.harness)
        templates = strategy.seed_templates()
        with patch.object(strategy, "_validate_harness_uncached", wraps=strategy._validate_harness_uncached) as harness_read:
            with patch.object(strategy, "_read_seed_templates", wraps=strategy._read_seed_templates) as template_read:
                with strategy.validation_scope(readonly=True):
                    first = strategy.validate_harness(self.harness)
                    first["strategy"]["answer_system"] = "caller mutation"
                    first["raw_files_sha256"].clear()
                    current_templates = strategy.seed_templates()
                    current_templates["answer_system"] = "caller mutation"
                    with strategy.validation_scope(readonly=True):
                        self.assertEqual(strategy.validate_harness(self.harness), checked)
                        self.assertEqual(strategy.seed_templates(), templates)
                    self.assertEqual((harness_read.call_count, template_read.call_count), (1, 1))
                self.assertEqual((harness_read.call_count, template_read.call_count), (2, 2))
                with strategy.validation_scope(readonly=True):
                    self.assertEqual(strategy.validate_harness(self.harness), checked)
                    self.assertEqual(strategy.seed_templates(), templates)
                self.assertEqual((harness_read.call_count, template_read.call_count), (4, 4))

    def test_readonly_snapshot_detects_harness_mutation_at_exit_and_resets_for_next_operation(self):
        path = self.harness / "systemprompt.md"
        original = path.read_bytes()
        changed = json.loads(original)
        changed["answer_system"] += "\nA permitted changed instruction."
        checked = strategy.validate_harness(self.harness)
        with self.assertRaises(ContractError):
            with strategy.validation_scope(readonly=True):
                self.assertEqual(strategy.validate_harness(self.harness), checked)
                path.write_text(json.dumps(changed), encoding="utf-8")
                self.assertEqual(strategy.validate_harness(self.harness), checked)
        with strategy.validation_scope(readonly=True):
            self.assertNotEqual(strategy.validate_harness(self.harness), checked)
        path.write_bytes(original)
        with self.assertRaises(ContractError):
            with strategy.validation_scope(readonly=True):
                strategy.validate_harness(self.harness)
                (self.harness / "skills/README.md").write_text("forbidden changed stub", encoding="utf-8")
        with self.assertRaises(ContractError):
            strategy.validate_harness(self.harness)

    def test_readonly_snapshot_rechecks_template_hash_and_does_not_cache_invalid_inputs(self):
        original = strategy.file_hash
        changed = False

        def observed(path):
            if changed and Path(path) == strategy.ROOT / "strategies/fixed/phase2.json":
                return "0" * 64
            return original(path)

        templates = strategy.seed_templates()
        with patch.object(strategy, "file_hash", side_effect=observed):
            with self.assertRaises(ContractError):
                with strategy.validation_scope(readonly=True):
                    self.assertEqual(strategy.seed_templates(), templates)
                    changed = True
                    self.assertEqual(strategy.seed_templates(), templates)
            with self.assertRaises(ContractError):
                strategy.seed_templates()
            changed = False
            with strategy.validation_scope(readonly=True):
                self.assertEqual(strategy.seed_templates(), templates)
                (self.harness / "systemprompt.md").write_text("{}", encoding="utf-8")
                with self.assertRaises(ContractError):
                    strategy.validate_harness(self.harness)
                (self.harness / "systemprompt.md").write_text(strategy.seed_tree()["systemprompt.md"], encoding="utf-8")
                strategy.validate_harness(self.harness)

    def test_default_scope_keeps_mutable_execution_uncached(self):
        with patch.object(strategy, "_validate_harness_uncached", wraps=strategy._validate_harness_uncached) as harness_read:
            with strategy.validation_scope():
                first = strategy.validate_harness(self.harness)
                changed = first["strategy"] | {"plan_system": "A newly edited plan instruction."}
                (self.harness / "systemprompt.md").write_text(json.dumps(changed), encoding="utf-8")
                self.assertNotEqual(strategy.validate_harness(self.harness), first)
            self.assertEqual(harness_read.call_count, 2)

    def test_same_family_dated_generator_change_is_global_integrity_stop(self):
        from followups.phase3a_v1.accounting import IntegrityStop

        dispatch = FakeDispatch()

        def changed(slot, role, request):
            result = dispatch(slot, role, request)
            if role == "plan":
                result["response"]["model"] += "-20261028"
            return result

        with self.assertRaises(IntegrityStop):
            strategy.execute_cn(TASK, self.harness, study_sha256=STUDY,
                                run_id="dated", dispatch=changed, fixture=True)
        self.assertEqual([role for _, role in dispatch.sent], ["plan", "answer"])


if __name__ == "__main__":
    unittest.main()
