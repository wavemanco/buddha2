"""Offline accounting boundaries; none of these tests construct a live client."""

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from buddha2.artifacts import ContractError, digest, read_json
from buddha2.phase2_dispatch import (
    FROZEN_PROFILES,
    DirectSDKTransport,
    Dispatcher,
    build_request,
    input_bound,
    replay_dispatch,
    reservation,
    writer_lock,
)

STUDY = "a" * 64


def auth(**changes):
    return {"study_sha256": STUDY, "authorization_id": "offline-fixture-only",
            "authorized": False, "cap_micro_usd": 125_000_000,
            "canary_cap_micro_usd": 5_000_000, "expansion_authorized": False, **changes}


def request(role="answer", text="A useful response."):
    return build_request(role, messages=[{"role": "user", "content": text}])


class FixtureTransport:
    fixture = True

    def __init__(self, outcomes=()):
        self.calls = []
        self.outcomes = list(outcomes)

    def create(self, role, value):
        self.calls.append((role, copy.deepcopy(value)))
        outcome = self.outcomes.pop(0) if self.outcomes else None
        if isinstance(outcome, BaseException):
            raise outcome
        if outcome is not None:
            return outcome
        return {"model": FROZEN_PROFILES[role]["model"], "text": "A useful output.",
                "stop_reason": "stop" if role == "group" else "end_turn",
                "request_id": "fixture-request", "message_id": "fixture-message",
                "usage": {"input_tokens": 80, "output_tokens": 20,
                          "service_tier": "default" if role == "group" else "standard"}}


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.journal = Path(self.temp.name) / "run"
        self.slots = {"a": {"role": "answer", "checkpoint": "canary"},
                      "b": {"role": "answer", "checkpoint": "expansion"}}

    def runner(self, transport=None, **changes):
        return Dispatcher(self.journal, study_sha256=STUDY, slots=self.slots,
                          authorization=auth(**changes), transport=transport or FixtureTransport())

    def test_profiles_caps_and_omitted_group_controls(self):
        self.assertEqual(request()["max_tokens"], 4096)
        self.assertEqual(request()["output_config"], {"effort": "low"})
        quality = request("quality")
        self.assertEqual(quality["max_tokens"], 16000)
        self.assertEqual(quality["output_config"], {"effort": "high"})
        group = request("group")
        self.assertNotIn("max_tokens", group)
        self.assertNotIn("reasoning_effort", group)
        self.assertEqual(reservation("answer"), 60_960)
        self.assertEqual(reservation("rank"), 200_960)
        self.assertEqual(reservation("group"), 166_400)
        self.assertEqual(reservation("quality"), 440_000)

    def test_offline_bound_covers_system_roles_unicode_and_schema_but_is_not_proof(self):
        plain = input_bound(request())
        extended = input_bound(build_request("group", messages=[{"role": "system", "content": "Ω"},
                               {"role": "user", "content": "🙂"}], response_format={
                                   "type": "json_schema", "json_schema": {"name": "x", "schema": {
                                       "description": "extra schema words", "type": "object"}}}))
        self.assertGreater(extended["serialized_utf8_bytes"], plain["serialized_utf8_bytes"])
        self.assertFalse(extended["provider_verified"])
        self.assertGreaterEqual(extended["candidate_tokens"], extended["serialized_utf8_bytes"])

    def test_resume_and_exact_request_identity_no_rebilling(self):
        transport = FixtureTransport()
        runner = self.runner(transport)
        first = runner.dispatch("a", "answer", request())
        self.assertEqual(first["status"], "response")
        self.assertIs(first["fixture"], True)
        self.assertEqual(first["study_sha256"], STUDY)
        self.assertEqual(first["spent_micro_usd"], 360)
        self.assertEqual(runner.dispatch("a", "answer", request()), first)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(replay_dispatch(self.journal)["reserved_micro_usd"], 0)
        with self.assertRaises(ContractError):
            runner.dispatch("a", "answer", request(text="changed"))
        with self.assertRaises(ContractError):
            self.runner(study_sha256="b" * 64)

    def test_caller_mutation_during_transport_cannot_change_durable_identity(self):
        caller_request = request()
        original_hash = digest(caller_request)

        class MutatingTransport(FixtureTransport):
            def create(self, role, value):
                caller_request["messages"][0]["content"] = "changed by the caller"
                return super().create(role, value)

        self.runner(MutatingTransport()).dispatch("a", "answer", caller_request)
        result = replay_dispatch(self.journal)["results"]["a"]
        self.assertEqual(result["request_sha256"], original_hash)

    def test_overlimit_bad_profile_and_unknown_slot_never_dispatch(self):
        transport = FixtureTransport()
        runner = self.runner(transport)
        for slot, role, value in (("a", "answer", request(text="x" * 9000)),
                                  ("unknown", "answer", request()),
                                  ("a", "quality", request("quality")),
                                  ("a", "answer", request() | {"tools": []}),
                                  ("a", "answer", request() | {"max_tokens": 9999})):
            with self.assertRaises(ContractError):
                runner.dispatch(slot, role, value)
        self.assertEqual(transport.calls, [])
        self.assertEqual(replay_dispatch(self.journal)["attempts"], 0)

    def test_authorization_and_unverified_bound_fail_before_live_transport(self):
        for approved in (False, True):
            with self.subTest(approved=approved), tempfile.TemporaryDirectory() as temporary:
                transport = FixtureTransport()
                transport.fixture = False
                runner = Dispatcher(Path(temporary), study_sha256=STUDY, slots=self.slots,
                                    authorization=auth(authorized=approved), transport=transport)
                with self.assertRaises(ContractError):
                    runner.dispatch("a", "answer", request())
                self.assertEqual(transport.calls, [])

    def test_canary_cap_and_expansion_review_are_independent_guards(self):
        transport = FixtureTransport()
        runner = self.runner(transport, canary_cap_micro_usd=60_959)
        with self.assertRaises(ContractError):
            runner.dispatch("a", "answer", request())
        self.assertEqual(transport.calls, [])
        with self.assertRaises(ContractError):
            runner.dispatch("b", "answer", request(), checkpoint="expansion")

    def test_expansion_permission_can_be_appended_without_rebinding_canary(self):
        transport = FixtureTransport()
        first = self.runner(transport).dispatch("a", "answer", request())
        expanded = self.runner(transport, expansion_authorized=True)
        second = expanded.dispatch("b", "answer", request(), checkpoint="expansion")
        self.assertEqual(first["spent_micro_usd"], second["spent_micro_usd"])
        self.assertEqual(replay_dispatch(self.journal)["attempts"], 2)
        self.assertTrue((self.journal / "authorization" / "expansion.json").exists())

    def test_ambiguous_delivery_retains_reservation_and_blocks_every_later_slot(self):
        transport = FixtureTransport([TimeoutError("opaque and possibly billed")])
        runner = self.runner(transport)
        result = runner.dispatch("a", "answer", request())
        self.assertEqual(result["status"], "unknown")
        self.assertIsNone(result["spent_micro_usd"])
        state = replay_dispatch(self.journal)
        self.assertEqual(state["spent_micro_usd"], 0)
        self.assertEqual(state["reserved_micro_usd"], 60_960)
        with self.assertRaises(ContractError):
            runner.dispatch("b", "answer", request(), checkpoint="expansion")
        self.assertEqual(len(transport.calls), 1)

    def test_missing_usage_and_outofrange_usage_remain_liabilities_not_free(self):
        for usage in (None, {"input_tokens": 80, "output_tokens": 4097, "service_tier": "standard"},
                      {"input_tokens": 80, "output_tokens": 20, "service_tier": "priority"},
                      {"input_tokens": 80, "output_tokens": 20, "service_tier": "standard",
                       "cache_creation_input_tokens": 3, "cache_creation": {
                           "ephemeral_1h_input_tokens": 3, "ephemeral_5m_input_tokens": 0}}):
            with self.subTest(usage=usage), tempfile.TemporaryDirectory() as temporary:
                transport = FixtureTransport([{"model": "claude-sonnet-5-5", "text": "x",
                    "stop_reason": "end_turn", "usage": usage}])
                runner = Dispatcher(Path(temporary), study_sha256=STUDY, slots=self.slots,
                                    authorization=auth(), transport=transport)
                result = runner.dispatch("a", "answer", request())
                self.assertEqual(result["status"], "unknown")
                self.assertGreater(replay_dispatch(Path(temporary))["reserved_micro_usd"], 0)

    def test_cache_categories_and_fractional_prices_settle_exactly(self):
        transport = FixtureTransport([{"model": "claude-sonnet-5-5", "text": "x",
            "stop_reason": "end_turn", "usage": {"input_tokens": 80, "output_tokens": 20,
                "cache_creation_input_tokens": 3, "cache_read_input_tokens": 30,
                "cache_creation": {"ephemeral_5m_input_tokens": 3, "ephemeral_1h_input_tokens": 0},
                "service_tier": "standard"}}])
        result = self.runner(transport).dispatch("a", "answer", request())
        self.assertEqual(result["spent_micro_usd"], 371)  # ceil(160+200+7.5+3)

    def test_actual_anthropic_usage_schema_thinking_breakdown_is_not_charged_twice(self):
        from anthropic.types import Usage

        usage = Usage(input_tokens=80, output_tokens=20, service_tier="standard",
                      output_tokens_details={"thinking_tokens": 12}).model_dump(
                          mode="json", exclude_none=True)
        transport = FixtureTransport([{"model": "claude-sonnet-5-5", "text": "answer",
                                       "stop_reason": "end_turn", "usage": usage}])
        result = self.runner(transport).dispatch("a", "answer", request())
        self.assertEqual(result["status"], "response")
        self.assertEqual(result["spent_micro_usd"], 360)

    def test_crash_after_durable_intent_is_not_reissued(self):
        transport = FixtureTransport([KeyboardInterrupt()])
        runner = self.runner(transport)
        with self.assertRaises(KeyboardInterrupt):
            runner.dispatch("a", "answer", request())
        self.assertEqual(replay_dispatch(self.journal)["reserved_micro_usd"], reservation("answer"))
        with self.assertRaises(ContractError):
            runner.dispatch("a", "answer", request())
        self.assertEqual(len(transport.calls), 1)

    def test_pending_intent_is_an_unknown_liability_in_composed_coverage(self):
        from buddha2.phase2 import make_worklist
        from buddha2.phase2_contracts import slot_prefix
        from buddha2.phase2_coverage import slot_coverage

        tasks = [{"id": f"pending-intent-task-{i}"} for i in range(12)]
        worklist = make_worklist(tasks)
        study = {"study_sha256": STUDY, "tasks": tasks, "worklist": worklist}
        parent = slot_prefix(tasks[0]["id"], "B", 1)
        child = slot_prefix(tasks[0]["id"], "C", 1)
        transport = FixtureTransport([KeyboardInterrupt()])
        dispatcher = Dispatcher(self.journal, study_sha256=STUDY, slots=worklist["slots"],
                                authorization=auth(), transport=transport)
        with self.assertRaises(KeyboardInterrupt):
            dispatcher.dispatch(parent + ".plan", "plan", request("plan"))
        intent = self.journal / "attempts" / "0001.intent.json"
        original_intent = intent.read_bytes()
        state = replay_dispatch(self.journal)
        coverage = slot_coverage(study, state["results"], [], [])
        self.assertEqual(coverage["slots"][parent + ".plan"], "unknown_liability")
        self.assertEqual(coverage["orders"][parent], "unresolved_plan")
        self.assertEqual(coverage["orders"][child], "unresolved_plan")
        self.assertEqual(coverage["slots"][parent + ".answer.00"], "skipped_unknown_liability")
        self.assertEqual(state["reserved_micro_usd"], reservation("plan"))
        self.assertEqual(state["spent_micro_usd"], 0)
        self.assertFalse((self.journal / "attempts" / "0001.result.json").exists())
        self.assertEqual(intent.read_bytes(), original_intent)
        with self.assertRaises(ContractError):
            dispatcher.dispatch(parent + ".plan", "plan", request("plan"))
        self.assertEqual(len(transport.calls), 1)

    def test_result_without_intent_and_modified_usage_fail_replay(self):
        self.runner().dispatch("a", "answer", request())
        path = self.journal / "attempts" / "0001.result.json"
        value = read_json(path)
        value["spent_micro_usd"] = 0
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(ContractError):
            replay_dispatch(self.journal)

    def test_fixture_live_namespace_and_result_provenance_cannot_be_rebound(self):
        self.runner().dispatch("a", "answer", request())
        live = FixtureTransport()
        live.fixture = False
        with self.assertRaises(ContractError):
            self.runner(live, authorized=True)
        self.assertEqual(live.calls, [])
        path = self.journal / "attempts" / "0001.result.json"
        value = read_json(path)
        value["fixture"] = False
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(ContractError):
            replay_dispatch(self.journal)

    def test_phase_writer_lock_rejects_concurrent_owner(self):
        with writer_lock(self.journal), self.assertRaises(ContractError):
            with writer_lock(self.journal):
                self.fail("second owner acquired phase lock")

    def test_process_death_releases_lock_but_retains_durable_intent(self):
        program = """
import json, os, sys
from pathlib import Path
from buddha2.phase2_dispatch import Dispatcher
class DyingTransport:
    fixture = True
    def create(self, role, request):
        os._exit(9)
Dispatcher(Path(sys.argv[1]), study_sha256=sys.argv[2], slots=json.loads(sys.argv[3]),
           authorization=json.loads(sys.argv[4]), transport=DyingTransport()).dispatch(
               'a', 'answer', json.loads(sys.argv[5]))
"""
        result = subprocess.run([sys.executable, "-B", "-c", program, str(self.journal), STUDY,
                                 json.dumps(self.slots), json.dumps(auth()), json.dumps(request())],
                                check=False, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 9, result.stderr.decode())
        state = replay_dispatch(self.journal)
        self.assertEqual(state["reserved_micro_usd"], reservation("answer"))
        with writer_lock(self.journal):
            self.assertEqual(state["status"], "blocked-unknown")

    def test_manifest_hashes_bind_profiles_worklist_and_authority(self):
        self.runner().dispatch("a", "answer", request())
        manifest = read_json(self.journal / "manifest.json")
        self.assertEqual(manifest["run_id"], digest(manifest["inputs"]))
        self.assertEqual(manifest["inputs"]["profiles"], FROZEN_PROFILES)
        self.assertEqual(manifest["inputs"]["slots"], self.slots)
        self.assertFalse(manifest["inputs"]["authorization"]["authorized"])

    def test_sdk_seam_has_zero_retries_no_token_calls_and_preserves_native_group_omissions(self):
        # Replaces both SDK modules entirely: no actual client is constructed.
        anthropic, openai = Mock(), Mock()
        raw_usage = {"prompt_tokens": 81, "completion_tokens": 20, "total_tokens": 101,
                     "prompt_tokens_details": {"cached_tokens": 1},
                     "completion_tokens_details": {"reasoning_tokens": 4}}
        reply = SimpleNamespace(model="gpt-5.6-luna", service_tier="default", id="fixture",
                                usage=SimpleNamespace(model_dump=lambda **kw: raw_usage),
                                choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(
                                    content='{"matches":[]}', refusal=None))])
        openai.OpenAI.return_value.chat.completions.create.return_value = reply
        anthropic_reply = SimpleNamespace(
            model="claude-sonnet-5-5", id="fixture-message", _request_id="fixture-request",
            stop_reason="end_turn", content=[SimpleNamespace(type="text", text="answer")],
            usage=SimpleNamespace(model_dump=lambda **kw: {
                "input_tokens": 80, "output_tokens": 20, "service_tier": "standard"}))
        anthropic.Anthropic.return_value.messages.create.return_value = anthropic_reply
        with patch.dict("sys.modules", {"anthropic": anthropic, "openai": openai}), patch.dict(
            "os.environ", {}, clear=True
        ):
            transport = DirectSDKTransport(anthropic_api_key="fixture-not-a-secret",
                                           openai_api_key="fixture-not-a-secret")
            schema = {"type": "json_schema", "json_schema": {"name": "Partition", "strict": True,
                      "schema": {"type": "object", "properties": {}, "additionalProperties": False}}}
            group = build_request("group", messages=[{"role": "user", "content": "partition"}],
                                  response_format=schema)
            with patch("time.monotonic", side_effect=[10.0, 10.125, 20.0, 20.25]):
                response = transport.create("group", group)
                answer = transport.create("answer", request())
        self.assertEqual(anthropic.Anthropic.call_args.kwargs["max_retries"], 0)
        self.assertEqual(openai.OpenAI.call_args.kwargs["max_retries"], 0)
        openai.OpenAI.return_value.chat.completions.create.assert_called_once_with(**group)
        self.assertNotIn("max_tokens", group)
        self.assertNotIn("reasoning_effort", group)
        self.assertEqual(response["usage"]["input_tokens"], 80)
        self.assertEqual(response["provider_usage"], raw_usage)
        self.assertEqual(response["latency_seconds"], 0.125)
        self.assertEqual(answer["latency_seconds"], 0.25)
        self.assertEqual(answer["request_id"], "fixture-request")
        self.assertEqual(answer["message_id"], "fixture-message")
        self.assertEqual(answer["stop_reason"], "end_turn")
        anthropic.Anthropic.return_value.messages.count_tokens.assert_not_called()

    @unittest.skipUnless(os.getenv("BUDDHA2_NB_UPSTREAM"), "requires supported native environment")
    def test_actual_native_requests_pass_the_dispatch_boundary(self):
        from buddha2.phase2_contracts import slot_prefix
        from buddha2.phase2_native import NativeAssessment
        from tests.test_phase2_native import sample_portfolio

        native = NativeAssessment(Path(os.environ["BUDDHA2_NB_UPSTREAM"]))
        portfolio = sample_portfolio()
        prefix = slot_prefix(portfolio["task"]["id"], "B", 1)
        slots = {prefix + ".group": {"role": "group", "checkpoint": "canary"},
                 prefix + ".quality.00": {"role": "quality", "checkpoint": "canary"}}
        dispatcher = Dispatcher(self.journal, study_sha256=STUDY, slots=slots,
                                authorization=auth(), transport=FixtureTransport())
        group = native.group_request(portfolio)
        quality = native.quality_requests(portfolio, [0] * 10)[0]
        self.assertIn("format", quality["output_config"])
        self.assertEqual(dispatcher.dispatch(prefix + ".group", "group", group)["status"], "response")
        result = dispatcher.dispatch(prefix + ".quality.00", "quality", quality)
        self.assertEqual(result["status"], "response")
        stored = read_json(self.journal / "attempts" / "0002.intent.json")
        self.assertEqual(stored["request"], quality)


if __name__ == "__main__":
    unittest.main()
