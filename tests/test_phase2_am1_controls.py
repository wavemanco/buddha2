"""AM-1 financial/payload invariants, without any provider client or network."""

import copy
import os
import tempfile
import unittest
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError, read_json
from buddha2.phase2_am1_controls import (
    BILLING_PROFILE,
    CONTROL_POLICY,
    CONTROL_SHA256,
    FIRST_BLOCK_MAX_MICRO_USD,
    FULL_STUDY_MAX_MICRO_USD,
    account,
    admission,
    admitted,
    canonical_live_journal,
    normalize_group_usage,
    reservation,
)
from buddha2.phase2_dispatch import (
    FROZEN_PROFILES,
    Dispatcher,
    build_request,
    input_bound,
    replay_dispatch,
)

STUDY = "b" * 64


def auth(**changes):
    return {"study_sha256": STUDY, "authorization_id": "am1-offline-fixture-only",
            "authorized": False, "cap_micro_usd": FULL_STUDY_MAX_MICRO_USD,
            "canary_cap_micro_usd": FIRST_BLOCK_MAX_MICRO_USD, "expansion_authorized": False,
            "control_policy_sha256": CONTROL_SHA256, "billing_profile": BILLING_PROFILE, **changes}


def request(role="answer", text="A response."):
    return build_request(role, messages=[{"role": "user", "content": text}])


def response(role="answer", **usage):
    return {"model": FROZEN_PROFILES[role]["model"], "text": "An output.", "stop_reason": "end_turn",
            "usage": {"input_tokens": 80, "output_tokens": 20, "cache_creation_input_tokens": 0,
                      "cache_read_input_tokens": 0, "service_tier": "standard", **usage}}


class Fixture:
    fixture = True

    def __init__(self, outcome=None):
        self.calls = 0
        self.outcome = outcome

    def create(self, role, value):
        self.calls += 1
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return response(role) if self.outcome is None else self.outcome


class AM1ControlsTests(unittest.TestCase):
    def test_live_journal_root_cannot_be_rebound_and_sdk_versions_are_checked(self):
        with patch.dict(os.environ, {"BUDDHA2_OUTPUT_ROOT": "/tmp/second-ledger"}):
            with self.assertRaisesRegex(ContractError, "fixed /workspace and /results"):
                canonical_live_journal(STUDY)
        with patch("buddha2.phase2_am1_controls.version", return_value="changed-sdk"):
            with self.assertRaisesRegex(ContractError, "pinned Linux image"):
                canonical_live_journal(STUDY)
        live = Fixture()
        live.fixture = False
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ContractError, "single canonical study journal"):
                Dispatcher(Path(temporary), study_sha256=STUDY,
                           slots={"a": {"role": "answer", "checkpoint": "canary"}},
                           authorization=auth(authorized=True), transport=live,
                           control_policy=CONTROL_POLICY)
            self.assertEqual(live.calls, 0)

    def test_independent_decimal_worst_cases_and_worklist_totals(self):
        cases = {"answer": (1000000, "2.50", 4096, "10"),
                 "plan": (1000000, "2.50", 4096, "10"),
                 "rank": (1000000, "2.50", 4096, "10"),
                 "group": (1050000, "1.10", 128000, "3.96"),
                 "quality": (1000000, "11", 16000, "27.5")}
        for role, (inputs, input_rate, outputs, output_rate) in cases.items():
            oracle = int((Decimal(inputs) * Decimal(input_rate) + Decimal(outputs) * Decimal(output_rate))
                         .to_integral_value(rounding=ROUND_CEILING))
            self.assertEqual(reservation(role), oracle)
        first = {"answer": 20, "plan": 1, "rank": 1, "group": 3, "quality": 30}
        full = {"answer": 480, "plan": 24, "rank": 24, "group": 72, "quality": 720}
        self.assertEqual(sum(first.values()), 55)
        self.assertEqual(sum(full.values()), 1320)
        self.assertEqual(sum(reservation(role) * n for role, n in first.items()), FIRST_BLOCK_MAX_MICRO_USD)
        self.assertEqual(sum(reservation(role) * n for role, n in full.items()), FULL_STUDY_MAX_MICRO_USD)

    def test_unchanged_payload_acceptance_at_every_role_boundary_with_unicode(self):
        for role in FROZEN_PROFILES:
            original = request(role, "Ω🙂")
            remaining = CONTROL_POLICY["payload_utf8_bytes"][role] - admission(role, original)["serialized_utf8_bytes"]
            for delta in (-1, 0, 1):
                value = copy.deepcopy(original)
                value["messages"][0]["content"] += "x" * (remaining + delta)
                self.assertEqual(admitted(role, value), delta <= 0)
                self.assertEqual(admitted(role, value),
                                 input_bound(value)["candidate_tokens"] <= FROZEN_PROFILES[role]["input_limit"])
                self.assertIsNone(admission(role, value)["provider_token_estimate"])
        with self.assertRaises(ContractError):
            admission("answer", request(text="\ud800"))

    def test_schema_system_and_dynamic_inputs_count_toward_payload(self):
        basic = request("group")
        schema = copy.deepcopy(basic) | {"response_format": {"type": "json_schema", "schema": {"description": "Ω🙂"}}}
        self.assertGreater(admission("group", schema)["serialized_utf8_bytes"],
                           admission("group", basic)["serialized_utf8_bytes"])
        value = request("rank", "saved-plan-and-answers" * 4000)
        self.assertFalse(admitted("rank", value))

    def test_group_write_read_normalization_is_exact_and_not_charged_twice(self):
        raw = {"prompt_tokens": 120, "completion_tokens": 24, "total_tokens": 144,
               "prompt_tokens_details": {"cached_tokens": 16, "cache_write_tokens": 32},
               "completion_tokens_details": {"reasoning_tokens": 4}}
        usage = normalize_group_usage(raw, "default")
        self.assertEqual(usage["input_tokens"], 72)
        self.assertEqual(usage["cache_creation_input_tokens"], 32)
        self.assertEqual(usage["cache_read_input_tokens"], 16)
        result = {"model": "gpt-5.6-luna", "usage": usage}
        expected = int(((Decimal(72) * Decimal(".2") + Decimal(32) * Decimal(".25")
                         + Decimal(16) * Decimal(".02") + Decimal(24) * Decimal("1.2")) * Decimal("1.1"))
                       .to_integral_value(rounding=ROUND_CEILING))
        self.assertEqual(account("group", result), (expected, True))
        self.assertEqual(expected, 57)
        for bad in (raw | {"total_tokens": 143}, raw | {"prompt_tokens_details": {"cached_tokens": 16}},
                    raw | {"prompt_tokens_details": {"cached_tokens": 90, "cache_write_tokens": 32}},
                    raw | {"prompt_tokens_details": {"cached_tokens": False, "cache_write_tokens": 32}},
                    raw | {"new_billable_category": 0}):
            self.assertEqual(normalize_group_usage(bad, "default"), {"unsupported_usage": True})

    def test_long_context_threshold_tier_and_fractional_rate_arithmetic(self):
        for prompt in (272000, 272001):
            for tier, multiplier in (("default", Decimal(1)), ("flex", Decimal(".5")), ("priority", Decimal(2))):
                raw = {"prompt_tokens": prompt, "completion_tokens": 17, "total_tokens": prompt + 17,
                       "prompt_tokens_details": {"cached_tokens": 3, "cache_write_tokens": 5}}
                value = {"model": "gpt-5.6-luna", "usage": normalize_group_usage(raw, tier)}
                inputs = Decimal(prompt - 8) * Decimal(".2") + Decimal(5) * Decimal(".25") + Decimal(3) * Decimal(".02")
                outputs = Decimal(17) * Decimal("1.2")
                if prompt > 272000:
                    inputs *= 2
                    outputs *= Decimal("1.5")
                oracle = int(((inputs + outputs) * multiplier * Decimal("1.1")).to_integral_value(rounding=ROUND_CEILING))
                self.assertEqual(account("group", value), (oracle, True))

    def test_group_text_details_are_bounded_breakdowns_and_images_remain_unsupported(self):
        raw = {"prompt_tokens": 120, "completion_tokens": 24, "total_tokens": 144,
               "prompt_tokens_details": {"cached_tokens": 16, "cache_write_tokens": 32,
                                          "text_tokens": 120, "image_tokens": 0, "audio_tokens": 0},
               "completion_tokens_details": {"reasoning_tokens": 4, "text_tokens": 20,
                                              "image_tokens": 0, "audio_tokens": 0}}
        self.assertEqual(account("group", {"model": "gpt-5.6-luna",
                                          "usage": normalize_group_usage(raw, "default")}), (57, True))
        for section, field, value in (("prompt_tokens_details", "image_tokens", 1),
                                      ("completion_tokens_details", "image_tokens", 1),
                                      ("prompt_tokens_details", "text_tokens", 121),
                                      ("completion_tokens_details", "text_tokens", 25),
                                      ("prompt_tokens_details", "text_tokens", True)):
            bad = copy.deepcopy(raw)
            bad[section][field] = value
            self.assertEqual(normalize_group_usage(bad, "default"), {"unsupported_usage": True})

    def test_missing_anthropic_cache_categories_retain_the_full_liability(self):
        for key in ("cache_creation_input_tokens", "cache_read_input_tokens"):
            outcome = response()
            del outcome["usage"][key]
            self.assertEqual(account("answer", outcome), (None, False))
            with tempfile.TemporaryDirectory() as temporary:
                transport = Fixture(outcome)
                root = Path(temporary)
                runner = Dispatcher(root, study_sha256=STUDY,
                                    slots={"a": {"role": "answer", "checkpoint": "canary"}},
                                    authorization=auth(), transport=transport, control_policy=CONTROL_POLICY)
                self.assertEqual(runner.dispatch("a", "answer", request())["status"], "unknown")
                self.assertEqual(replay_dispatch(root)["reserved_micro_usd"], reservation("answer"))
                with self.assertRaises(ContractError):
                    runner.dispatch("a", "answer", request())
                self.assertEqual(transport.calls, 1)

    def test_entire_input_can_be_cached_at_the_maximum_applicable_rate(self):
        for role, write_field in (("answer", "ephemeral_5m_input_tokens"), ("quality", "ephemeral_1h_input_tokens")):
            usage = {"input_tokens": 0, "output_tokens": CONTROL_POLICY["reserved_total_output"][role],
                     "cache_creation_input_tokens": 1000000, "cache_creation": {write_field: 1000000}}
            self.assertEqual(account(role, response(role, **usage)), (reservation(role), True))
            usage["cache_creation_input_tokens"] += 1
            self.assertEqual(account(role, response(role, **usage)), (None, False))
        raw = {"prompt_tokens": 1050000, "completion_tokens": 128000, "total_tokens": 1178000,
               "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 1050000}}
        self.assertEqual(account("group", {"model": "gpt-5.6-luna", "usage": normalize_group_usage(raw, "priority")}),
                         (reservation("group"), True))
        self.assertEqual(account("answer", response(cache_creation_input_tokens=2,
                         cache_creation={"ephemeral_1h_input_tokens": 2})), (None, False))

    def test_unproved_policy_private_profile_and_mismatched_grant_never_dispatch(self):
        for changes in ({"control_policy_sha256": "0" * 64}, {"billing_profile": "private-negotiated"}):
            with tempfile.TemporaryDirectory() as temporary:
                transport = Fixture()
                with self.assertRaises(ContractError):
                    Dispatcher(Path(temporary), study_sha256=STUDY, slots={"a": {"role": "answer", "checkpoint": "canary"}},
                               authorization=auth(**changes), transport=transport, control_policy=CONTROL_POLICY)
                self.assertEqual(transport.calls, 0)
        policy = copy.deepcopy(CONTROL_POLICY)
        policy["maximum_billable_input"]["quality"] = 0
        with tempfile.TemporaryDirectory() as temporary, self.assertRaises(ContractError):
            Dispatcher(Path(temporary), study_sha256=STUDY, slots={"a": {"role": "answer", "checkpoint": "canary"}},
                       authorization=auth(), transport=Fixture(), control_policy=policy)

    def test_reservation_before_dispatch_unknown_liability_and_resume(self):
        for outcome in (response(cache_creation_input_tokens=16), KeyboardInterrupt()):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                transport = Fixture(outcome)
                runner = Dispatcher(root, study_sha256=STUDY,
                                    slots={"a": {"role": "answer", "checkpoint": "canary"}},
                                    authorization=auth(), transport=transport, control_policy=CONTROL_POLICY)
                if isinstance(outcome, KeyboardInterrupt):
                    with self.assertRaises(KeyboardInterrupt):
                        runner.dispatch("a", "answer", request())
                else:
                    self.assertEqual(runner.dispatch("a", "answer", request())["status"], "unknown")
                state = replay_dispatch(root)
                self.assertEqual(state["reserved_micro_usd"], reservation("answer"))
                self.assertEqual(state["status"], "blocked-unknown")
                self.assertEqual(state["provider_calls"], 0)
                with self.assertRaises(ContractError):
                    runner.dispatch("a", "answer", request())
                self.assertEqual(transport.calls, 1)
                intent = read_json(root / "attempts/0001.intent.json")
                self.assertEqual(intent["admission"]["control_policy_sha256"], CONTROL_SHA256)

    def test_too_small_cap_and_expansion_reject_without_intent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            transport = Fixture()
            runner = Dispatcher(root, study_sha256=STUDY, slots={"a": {"role": "answer", "checkpoint": "canary"},
                                "b": {"role": "answer", "checkpoint": "expansion"}},
                                authorization=auth(canary_cap_micro_usd=reservation("answer") - 1),
                                transport=transport, control_policy=CONTROL_POLICY)
            with self.assertRaises(ContractError):
                runner.dispatch("a", "answer", request())
            with self.assertRaises(ContractError):
                runner.dispatch("b", "answer", request(), checkpoint="expansion")
            self.assertEqual(transport.calls, 0)
            self.assertEqual(replay_dispatch(root)["attempts"], 0)

    def test_successful_new_control_resume_is_exact_and_has_conservative_cost_label(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            transport = Fixture()
            runner = Dispatcher(root, study_sha256=STUDY, slots={"a": {"role": "answer", "checkpoint": "canary"}},
                                authorization=auth(), transport=transport, control_policy=CONTROL_POLICY)
            first = runner.dispatch("a", "answer", request())
            self.assertEqual(runner.dispatch("a", "answer", request()), first)
            self.assertEqual(transport.calls, 1)
            self.assertEqual(first["spent_micro_usd"], 360)
            self.assertEqual(first["cost_basis"], CONTROL_POLICY["cost_basis"])
            self.assertEqual(replay_dispatch(root)["reserved_micro_usd"], 0)
