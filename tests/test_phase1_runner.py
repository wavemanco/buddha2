"""Offline failures and recovery on the actual sequential evaluator runner."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from buddha2.artifacts import ContractError, read_json
from buddha2.pairs import make_pair, make_presentation
from buddha2.phase1_runner import (
    PROFILE,
    AmbiguousDelivery,
    DirectAnthropicTransport,
    TransientRejected,
    replay_run,
    run_stage,
    writer_lock,
)


def plan(count=2):
    pairs, presentations = [], []
    for index in range(count):
        item = make_pair(prompt_id=f"p{index}", prompt=f"Useful unusual idea {index}",
                         family="fixture", fixture=True, responses=[
                             {"id": f"r{index}a", "text": "Put books on a rolling cart."},
                             {"id": f"r{index}b", "text": "Make a giant public book hammock."},
                         ])
        pairs.append(item)
        order = [response["id"] for response in item["responses"]]
        presentations.extend((make_presentation(item, order), make_presentation(item, order[::-1])))
    return {"pairs": pairs, "presentations": presentations,
            "stages": {"calibration": [p["presentation_id"] for p in presentations[:2]],
                       "audit": [p["presentation_id"] for p in presentations[2:]]},
            "profile": copy.deepcopy(PROFILE), "image_id": "sha256:" + "a" * 64}


class FakeTransport:
    fixture = True

    def __init__(self, outcomes=(), count=80):
        self.outcomes, self.count_value = list(outcomes), count
        self.count_calls, self.create_calls = [], []

    def count(self, request):
        self.count_calls.append(copy.deepcopy(request))
        return self.count_value

    def create(self, request):
        self.create_calls.append(copy.deepcopy(request))
        value = self.outcomes.pop(0) if self.outcomes else {}
        if isinstance(value, BaseException):
            raise value
        return {"model": "claude-sonnet-5-5", "stop_reason": "end_turn",
                "text": '{"choice":"A","reason":"An unusual useful idea."}',
                "usage": {"input_tokens": 80, "output_tokens": 20,
                          "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
                          "service_tier": "standard"}, **value}


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "run"
        self.plan = plan()

    def run_stage(self, transport, **kwargs):
        return run_stage(self.root, self.plan, stage=kwargs.pop("stage", "calibration"),
                         rubric=kwargs.pop("rubric", "Compare unusualness and task usefulness."),
                         transport=transport, authorization_micro_usd=kwargs.pop("cap", 5_000_000),
                         **kwargs)

    def test_saved_requests_are_independent_and_resume_does_not_dispatch(self):
        transport = FakeTransport()
        result = self.run_stage(transport)
        self.assertEqual(result["finalized_presentations"], 2)
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(result["spent_micro_usd"], 720)
        self.assertEqual(result["reserved_micro_usd"], 0)
        self.assertNotEqual(transport.create_calls[0], transport.create_calls[1])
        self.assertEqual(transport.create_calls[0]["max_tokens"], 2048)
        self.assertEqual(transport.create_calls[0]["thinking"], {"type": "adaptive"})
        self.assertEqual(transport.create_calls[0]["inference_geo"], "global")
        self.assertEqual(len(transport.create_calls[0]["messages"]), 1)
        self.assertEqual(self.run_stage(transport), result)
        self.assertEqual(len(transport.create_calls), 2)
        self.assertEqual(replay_run(self.root)["attempts"], 2)

    def test_stage_rubric_can_change_but_global_budget_remains_shared(self):
        self.run_stage(FakeTransport())
        result = self.run_stage(FakeTransport(), stage="audit", rubric="Final frozen rubric.")
        self.assertEqual(result["attempts"], 4)
        self.assertEqual(result["finalized_presentations"], 4)
        with self.assertRaisesRegex(ContractError, "immutable"):
            self.run_stage(FakeTransport(), stage="audit", rubric="Post-audit tuning.")

    def test_stale_plan_and_budget_cannot_silently_reuse_run(self):
        self.run_stage(FakeTransport())
        self.plan["image_id"] = "sha256:" + "b" * 64
        with self.assertRaises(ContractError):
            self.run_stage(FakeTransport())
        self.plan = plan()
        with self.assertRaises(ContractError):
            self.run_stage(FakeTransport(), cap=10_000_000)

    def test_token_count_limit_prevents_generation_and_logs_count(self):
        transport = FakeTransport(count=8001)
        with self.assertRaisesRegex(ContractError, "token"):
            self.run_stage(transport)
        self.assertEqual(transport.create_calls, [])
        self.assertEqual(len(list((self.root / "counts").glob("*.result.json"))), 1)

    def test_reservation_refuses_before_dispatch(self):
        transport = FakeTransport()
        with self.assertRaisesRegex(ContractError, "budget|reservation"):
            self.run_stage(transport, cap=36_479)
        self.assertEqual(transport.create_calls, [])

    def test_one_transient_retry_is_preserved_and_outcomes_never_retry(self):
        transport = FakeTransport([TransientRejected(429), {"text": "invalid JSON"}])
        result = self.run_stage(transport)
        self.assertEqual(result["attempts"], 3)
        self.assertEqual(result["retries"], 1)
        self.assertEqual([r["status"] for r in result["judgments"]], ["malformed", "ok"])
        self.assertEqual(len(transport.create_calls), 3)

    def test_unknown_delivery_keeps_reservation_and_blocks_resume(self):
        transport = FakeTransport([AmbiguousDelivery()])
        result = self.run_stage(transport)
        self.assertEqual(result["status"], "blocked-unknown")
        self.assertEqual(result["reserved_micro_usd"], 36_480)
        again = self.run_stage(transport)
        self.assertEqual(again, result)
        self.assertEqual(len(transport.create_calls), 1)

    def test_interrupt_after_intent_is_unknown_not_a_free_retry(self):
        with self.assertRaises(KeyboardInterrupt):
            self.run_stage(FakeTransport([KeyboardInterrupt()]))
        result = self.run_stage(FakeTransport())
        self.assertEqual(result["status"], "blocked-unknown")
        self.assertEqual(result["reserved_micro_usd"], 36_480)

    def test_unexpected_usage_stops_with_recorded_liability(self):
        transport = FakeTransport([{"usage": {"input_tokens": 8001, "output_tokens": 20,
                                             "service_tier": "standard"}}])
        result = self.run_stage(transport)
        self.assertEqual(result["status"], "blocked-usage")
        self.assertEqual(len(transport.create_calls), 1)
        self.assertGreater(result["spent_micro_usd"], 0)

    def test_zero_cache_metadata_is_valid_but_unknown_pricing_is_not_zero_cost(self):
        usage = {"input_tokens": 80, "output_tokens": 20, "service_tier": "standard",
                 "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
                 "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 0},
                 "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0}}
        result = self.run_stage(FakeTransport([{"usage": usage}]))
        self.assertEqual(result["status"], "ready")
        other = self.root / "other"
        usage["cache_creation_input_tokens"] = 40
        result = run_stage(other, self.plan, stage="calibration", rubric="Rubric",
                           transport=FakeTransport([{"usage": usage}]), authorization_micro_usd=5_000_000)
        self.assertEqual(result["status"], "blocked-usage")
        self.assertIsNone(result["judgments"][0]["cost_usd"])
        self.assertEqual(result["spent_micro_usd"], 0)
        self.assertEqual(result["reserved_micro_usd"], 36_480)

    def test_model_prefix_is_not_the_pinned_model_identity(self):
        result = self.run_stage(FakeTransport([{"model": "claude-sonnet-5-5-unreviewed-variant"}]))
        self.assertEqual(result["status"], "blocked-usage")
        self.assertIsNone(result["judgments"][0]["cost_usd"])

    def test_refusal_and_truncation_are_final_not_retries(self):
        transport = FakeTransport([{"stop_reason": "end_turn", "stop_details_type": "refusal"},
                                   {"stop_reason": "max_tokens"}])
        result = self.run_stage(transport)
        self.assertEqual([r["status"] for r in result["judgments"]], ["refused", "truncated"])
        self.assertEqual(result["retries"], 0)

    def test_corrupt_saved_result_is_not_treated_as_complete(self):
        self.run_stage(FakeTransport())
        path = sorted((self.root / "attempts").glob("*.result.json"))[0]
        value = read_json(path)
        value["request_sha256"] = "0" * 64
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(ContractError):
            replay_run(self.root)

    def test_missing_token_count_evidence_invalidates_saved_judgment(self):
        self.run_stage(FakeTransport())
        (self.root / "counts/0001.result.json").unlink()
        with self.assertRaises(ContractError):
            replay_run(self.root)

    def test_uncertain_error_does_not_echo_exception_secrets(self):
        result = self.run_stage(FakeTransport([RuntimeError("Authorization: secret-value")]))
        self.assertEqual(result["status"], "blocked-unknown")
        for path in self.root.rglob("*.json"):
            self.assertNotIn("secret-value", path.read_text(encoding="utf-8"))

    def test_concurrent_writer_refused(self):
        with writer_lock(self.root):
            with self.assertRaisesRegex(ContractError, "writer|concurrent"):
                self.run_stage(FakeTransport())
            code = ("import sys; from pathlib import Path; "
                    "from buddha2.phase1_runner import writer_lock; "
                    "lock=writer_lock(Path(sys.argv[1])); lock.__enter__()")
            child = subprocess.run([sys.executable, "-B", "-c", code, str(self.root)],
                                   capture_output=True, text=True, timeout=10, check=False)
            self.assertNotEqual(child.returncode, 0)
            self.assertIn("concurrent writer", child.stderr)

    def test_fixture_and_replay_never_construct_sdk_or_read_credentials(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "should-not-be-read"}), patch.dict(
            "sys.modules", {"anthropic": None}
        ):
            self.run_stage(FakeTransport())
            self.assertEqual(replay_run(self.root)["attempts"], 2)

    def test_live_transport_requires_explicit_key_and_rejects_ambient_redirectors(self):
        with self.assertRaises(ContractError):
            DirectAnthropicTransport(api_key="")
        with patch.dict("os.environ", {"ANTHROPIC_CUSTOM_HEADERS": "x-api-key: secret"}):
            with self.assertRaises(ContractError):
                DirectAnthropicTransport(api_key="explicit-not-real")

    def test_direct_sdk_transport_disables_hidden_retries_and_counts_exact_request(self):
        client = Mock()
        client.messages.count_tokens.return_value = SimpleNamespace(input_tokens=80)
        client.messages.create.return_value = SimpleNamespace(
            model="claude-sonnet-5-5", stop_reason="end_turn",
            id="msg-fixture", _request_id="req-fixture",
            content=[SimpleNamespace(type="text", text='{"choice":"tie","reason":"Equal."}')],
            usage=SimpleNamespace(model_dump=lambda **kwargs: {"input_tokens": 80, "output_tokens": 20}),
        )
        sdk = SimpleNamespace(Anthropic=Mock(return_value=client), DefaultHttpxClient=Mock(),
                              APIStatusError=type("APIStatusError", (Exception,), {}))
        with patch.dict("os.environ", {}, clear=True), patch.dict("sys.modules", {"anthropic": sdk}):
            transport = DirectAnthropicTransport(api_key="explicit-not-real")
            request = {"model": "claude-sonnet-5-5", "max_tokens": 2048,
                       "service_tier": "standard_only", "inference_geo": "global", "system": "Rubric",
                       "messages": [{"role": "user", "content": "Pair"}],
                       "thinking": {"type": "adaptive"}, "output_config": {"effort": "medium"}}
            self.assertEqual(transport.count(request), 80)
            transport.create(request)
        arguments = sdk.Anthropic.call_args.kwargs
        self.assertEqual(arguments["max_retries"], 0)
        self.assertEqual(arguments["base_url"], "https://api.anthropic.com")
        self.assertFalse(sdk.DefaultHttpxClient.call_args.kwargs["trust_env"])
        self.assertFalse(sdk.DefaultHttpxClient.call_args.kwargs["follow_redirects"])
        self.assertEqual(client.messages.count_tokens.call_args.kwargs,
                         {key: value for key, value in request.items()
                          if key not in {"max_tokens", "service_tier", "inference_geo"}})
        self.assertEqual(client.messages.create.call_args.kwargs, request)

    def test_live_http_rejection_has_unknown_billing_until_reconciled(self):
        class StatusError(Exception):
            def __init__(self, code):
                self.status_code = code
                self.request_id = "req-fixture"

        client = Mock()
        sdk = SimpleNamespace(Anthropic=Mock(return_value=client), DefaultHttpxClient=Mock(),
                              APIStatusError=StatusError)
        with patch.dict("os.environ", {}, clear=True), patch.dict("sys.modules", {"anthropic": sdk}):
            transport = DirectAnthropicTransport(api_key="explicit-not-real")
            for status in (429, 529):
                client.messages.create.side_effect = StatusError(status)
                with self.assertRaises(AmbiguousDelivery):
                    transport.create({})
        self.assertEqual(client.messages.create.call_count, 2)

    def test_global_retry_allowance_and_attempt_ceiling_span_all_presentations(self):
        self.plan = plan(24)
        ids = [item["presentation_id"] for item in self.plan["presentations"]]
        self.plan["stages"] = {"calibration": ids, "audit": []}
        # Four permitted retries. A fifth rejected request earns a failed outcome,
        # preserving its scheduled denominator instead of replacing the pair.
        outcomes = [value for _ in range(4) for value in (TransientRejected(429), {})]
        outcomes += [TransientRejected(429)]
        transport = FakeTransport(outcomes)
        result = self.run_stage(transport, max_presentations=48)
        self.assertEqual(result["attempts"], 52)
        self.assertEqual(result["retries"], 4)
        self.assertEqual(result["finalized_presentations"], 48)
        self.assertEqual(sum(row["status"] == "transport_error" for row in result["judgments"]), 1)
        self.assertEqual(len(transport.create_calls), 52)


if __name__ == "__main__":
    unittest.main()
