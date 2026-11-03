"""Resource, retry, liability and authority checks using credential-free responses."""
from __future__ import annotations

import copy
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from buddha2 import phase2_am1_controls as am1
from buddha2.artifacts import ContractError, digest, read_json
from buddha2.phase2_dispatch import build_request, writer_lock
from followups.phase3a_v1 import accounting as a
from followups.phase3a_v1.mocks import SDKMock

STUDY = "1" * 64
BINDINGS = {"source_sha256": "2" * 64, "policy_sha256": "3" * 64, "launcher_sha256": "4" * 64}
AUTHORITY = {"study_sha256": STUDY, "authorization_id": "phase3a-fixture", "authorized": False,
             "cap_micro_usd": a.POLICY["phase_micro_usd"], "canary_cap_micro_usd": a.POLICY["first_micro_usd"], "expansion_authorized": False,
             "control_policy_sha256": am1.CONTROL_SHA256, "billing_profile": am1.BILLING_PROFILE}


def slots():
    result: dict[str, dict] = {}
    for pair in a.PAIRS:
        for arm, counts in (("adaptive", {"answer": 40, "plan": 4, "rank": 4}),
                            ("fixed", {"answer": 60, "plan": 6, "rank": 6, "fixed_selector": 1})):
            for role, count in counts.items():
                for i in range(count):
                    result[f"{pair}.{arm}.{role}.{i:02}"] = {"role": role, "pair": pair, "cell": pair + ":" + arm}
        for stage in ("inv1", "dom1", "agg1"):
            for shape in (1, 2):
                conversation = pair + f":adaptive:{stage}.a{shape}"
                for turn in range(1, a.POLICY["editor_turns"] + 1):
                    result[f"{pair}.adaptive.editor.{stage}.a{shape}.t{turn:02}"] = {
                        "role": "editor", "pair": pair, "cell": pair + ":adaptive", "conversation": conversation, "turn": turn}
        for i in range(3 if pair == a.PAIRS[0] else 2):
            prefix = f"{pair}.assessment.{i:02}"
            result[prefix + ".group"] = {"role": "group", "cell": "assessment", "pair": pair}
            for head in range(10):
                result[prefix + f".quality.{head:02}"] = {"role": "quality", "cell": "assessment", "pair": pair}
    return result


def request(role="plan"):
    if role in {"editor", "fixed_selector"}:
        return {"model": "claude-opus-5", "max_tokens": 16000, "thinking": {"type": "adaptive"},
                "output_config": {"effort": "high"}, "service_tier": "standard_only", "inference_geo": "global",
                "messages": [{"role": "user", "content": "Synthetic request"}]}
    return build_request(role, messages=[{"role": "user", "content": "Synthetic request"}])


def saved_editor_history():
    path = Path(__file__).resolve().parents[3] / "evidence/phase3a-v1/caller-regression-v1/candidate-direct-caller.json"
    saved = read_json(path)
    body = copy.deepcopy(saved["requests"][1])
    tools = {tool["name"]: copy.deepcopy(tool) for tool in body["tools"]}
    return saved, body, tools


def history_tool(body):
    return next(block for message in body["messages"]
                for block in (message["content"] if isinstance(message["content"], list) else [])
                if isinstance(block, dict) and block.get("type") == "tool_use")


class Transport:
    fixture = True

    def __init__(self, *, fault=None, input_tokens=80, output_tokens=24):
        self.fault, self.input_tokens, self.output_tokens = fault, input_tokens, output_tokens
        self.calls = []
        self.inflight = self.maximum_inflight = 0

    def create(self, role, body):
        self.calls.append((role, copy.deepcopy(body)))
        self.inflight += 1
        self.maximum_inflight = max(self.inflight, self.maximum_inflight)
        if self.fault == "slow":
            time.sleep(.03)
        usage = {"input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
                 "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
                 "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 0},
                 "service_tier": "standard", "inference_geo": "global"}
        response = {"model": body["model"], "text": "Synthetic response", "usage": usage,
                    "stop_reason": "end_turn", "content": [{"type": "text", "text": "Synthetic response"}]}
        if self.fault == "unknown":
            usage["unsupported_usage"] = 1
        elif self.fault == "server_tool":
            usage["server_tool_use"] = {"web_search_requests": 1}
        elif self.fault == "wrong-model":
            response["model"] = "different-model"
        elif self.fault == "timeout":
            raise TimeoutError("scripted timeout")
        self.inflight -= 1
        return response


def review(state, *, closed):
    return {"review_id": "fixture-reviewed", "study_sha256": STUDY, "run_id": state["run_id"],
            "state_sha256": digest(state), "checks": dict.fromkeys(a.CHECKS, True),
            "evidence": {"fixture-evidence.json": "5" * 64}, "first_assessments_closed": closed}


class AccountingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="phase3a-accounting-")
        self.addCleanup(self.temporary.cleanup)
        self.journal = Path(self.temporary.name) / "journal"
        self.slots = slots()

    def ledger(self, transport=None, **kwargs):
        return a.Ledger(self.journal, study_sha256=STUDY, slots=self.slots, authority=AUTHORITY,
                        transport=transport or Transport(), bindings=BINDINGS, **kwargs)

    def test_scope_authority_and_manifest_bind_before_mutation(self):
        bad = AUTHORITY | {"cap_micro_usd": a.POLICY["phase_micro_usd"] + 1}
        with self.assertRaises(ContractError):
            a.validate_authority(STUDY, bad, fixture=True, bindings=BINDINGS)
        with self.assertRaises(ContractError):
            a.validate_authority(STUDY, AUTHORITY | {"cap_micro_usd": 220000000,
                "canary_cap_micro_usd": 65000000}, fixture=True, bindings=BINDINGS)
        self.assertFalse(self.journal.exists())
        self.ledger()
        self.assertEqual(len(a.replay(self.journal)["results"]), 0)
        with self.assertRaises(ContractError):
            a.Ledger(self.journal, study_sha256=STUDY, slots=self.slots, authority=AUTHORITY,
                     transport=Transport(), bindings=BINDINGS | {"source_sha256": "a" * 64})

    def test_known_settlement_replay_and_durable_intent_precedes_create(self):
        transport = Transport()
        ledger = self.ledger(transport)
        original = transport.create
        def inspect(role, body):
            state = a.replay(self.journal)
            self.assertEqual(state["status"], "blocked-unknown")
            self.assertEqual(state["reserved_micro_usd"], am1.reservation(role))
            return original(role, body)
        with patch.object(transport, "create", side_effect=inspect):
            result = ledger.dispatch("p3a-01.fixed.plan.00", "plan", request())
        self.assertEqual(result["status"], "response")
        self.assertEqual(result["spent_micro_usd"], 400)
        self.assertEqual(ledger.dispatch("p3a-01.fixed.plan.00", "plan", request()), result)
        self.assertEqual(len(transport.calls), 1)
        state = a.replay(self.journal)
        self.assertEqual(state["cells"]["p3a-01:fixed"]["input_tokens"], 80)
        self.assertEqual(state["first_pair"]["spent_micro_usd"], 400)
        self.assertEqual(state["reserved_input_tokens"], 0)

    def test_unknown_cost_model_server_tool_or_timeout_halts_globally(self):
        for fault in ("unknown", "wrong-model", "server_tool", "timeout"):
            with self.subTest(fault=fault):
                self.journal = Path(self.temporary.name) / fault
                transport = Transport(fault=fault)
                ledger = self.ledger(transport)
                result = ledger.dispatch("p3a-01.fixed.plan.00", "plan", request())
                self.assertEqual(result["status"], "unknown")
                with self.assertRaises(a.LiabilityStop):
                    ledger.dispatch("p3a-01.adaptive.plan.00", "plan", request())
                with self.assertRaises(a.LiabilityStop):
                    self.ledger(transport).dispatch("p3a-01.fixed.plan.00", "plan", request())
                self.assertEqual(len(transport.calls), 1)
                self.assertEqual(a.replay(self.journal)["reserved_input_tokens"], 1000000)

    def test_interrupt_preserves_unresolved_intent_no_resend(self):
        transport = Transport()
        ledger = self.ledger(transport)
        with patch.object(transport, "create", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            ledger.dispatch("p3a-01.fixed.plan.00", "plan", request())
        state = a.replay(self.journal)
        self.assertEqual(state["status"], "blocked-unknown")
        self.assertEqual(state["attempts"], 1)
        with self.assertRaises(a.LiabilityStop):
            ledger.dispatch("p3a-01.fixed.plan.00", "plan", request())

    def test_profile_or_changed_retry_permanently_halts(self):
        ledger = self.ledger()
        ledger.dispatch("p3a-01.fixed.plan.00", "plan", request())
        changed = request()
        changed["messages"][0]["content"] += " changed"
        with self.assertRaises(a.IntegrityStop):
            ledger.dispatch("p3a-01.fixed.plan.00", "plan", changed)
        self.assertEqual(a.replay(self.journal)["status"], "halted-integrity")
        with self.assertRaises(a.IntegrityStop):
            self.ledger().dispatch("p3a-01.adaptive.plan.00", "plan", request())

    def test_cell_dollars_are_not_reset_or_borrowed(self):
        transport = Transport(input_tokens=1000000, output_tokens=16000)
        ledger = self.ledger(transport)
        for turn in (1, 2):
            ledger.dispatch(f"p3a-01.adaptive.editor.inv1.a1.t{turn:02}", "editor", request("editor"))
        with self.assertRaises(a.CellBudgetStop):
            ledger.dispatch("p3a-01.adaptive.editor.inv1.a1.t03", "editor", request("editor"))
        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(a.replay(self.journal)["cells"]["p3a-01:adaptive"]["spent_micro_usd"], 11880000)
        transport.input_tokens, transport.output_tokens = 80, 24
        ledger.dispatch("p3a-01.fixed.plan.00", "plan", request())
        with self.assertRaises(a.CellBudgetStop):
            ledger.dispatch("p3a-01.adaptive.plan.00", "plan", request())
        self.assertEqual(len(transport.calls), 3)

    def test_input_reservations_and_output_overrun(self):
        transport = Transport(input_tokens=900000, output_tokens=0)
        ledger = self.ledger(transport)
        for index in range(4):
            ledger.dispatch(f"p3a-01.fixed.answer.{index:02}", "answer", request("answer"))
        with self.assertRaises(a.CellBudgetStop):
            ledger.dispatch("p3a-01.fixed.answer.04", "answer", request("answer"))
        self.assertEqual(a.replay(self.journal)["cells"]["p3a-01:fixed"]["input_tokens"], 3600000)
        self.journal = Path(self.temporary.name) / "output-overrun"
        ledger = self.ledger(Transport(output_tokens=4097))
        ledger.dispatch("p3a-01.fixed.plan.00", "plan", request())
        self.assertEqual(a.replay(self.journal)["status"], "blocked-unknown")

    def test_checkpoint_review_unlocks_only_original_slots_and_no_new_credit(self):
        transport = Transport(input_tokens=1000000, output_tokens=16000)
        ledger = self.ledger(transport)
        for index in range(3):
            ledger.dispatch(f"p3a-01.assessment.00.quality.{index:02}", "quality", request("quality"))
        with self.assertRaises(a.CheckpointStop):
            ledger.dispatch("p3a-01.assessment.00.quality.03", "quality", request("quality"))
        before = a.replay(self.journal)
        record = review(before, closed=False)
        calls = []
        a.publish_review(self.journal, record, validate_evidence=lambda state, evidence: calls.append(state["attempts"]))
        a.publish_review(self.journal, record, validate_evidence=lambda *_: self.fail("duplicate review adds no authority"))
        self.assertEqual(calls, [3])
        ledger.dispatch("p3a-01.assessment.00.quality.03", "quality", request("quality"))
        with self.assertRaises(a.AuthorityError):
            ledger.dispatch("p3a-02.assessment.00.quality.00", "quality", request("quality"))
        closed = review(a.replay(self.journal), closed=True)
        a.close_first_assessments(self.journal, closed, validate_evidence=lambda *_: None)
        ledger.dispatch("p3a-02.assessment.00.quality.00", "quality", request("quality"))
        self.assertEqual(a.replay(self.journal)["spent_micro_usd"], 29700000)
        with self.assertRaises(ContractError):
            a.publish_review(self.journal, record | {"review_id": "new-credit"}, validate_evidence=lambda *_: None)

    def test_overlapping_first_limit_stops_before_intent_then_same_slot_uses_same_pool(self):
        class CacheTransport(Transport):
            mode = "small"

            def create(self, role, body):
                response = super().create(role, body)
                usage = response["usage"]
                usage.update(input_tokens=0, output_tokens=4096 if self.mode == "small" else 16000,
                             cache_creation_input_tokens=0)
                if self.mode == "last-small":
                    usage["output_tokens"] = 4080
                elif self.mode in {"hour", "five"}:
                    usage["cache_creation_input_tokens"] = 1000000
                    usage["cache_creation"] = {"ephemeral_5m_input_tokens": 1000000 if self.mode == "five" else 0,
                                               "ephemeral_1h_input_tokens": 1000000 if self.mode == "hour" else 0}
                    usage["output_tokens"] = 4096 if self.mode == "five" else 16000
                elif self.mode == "tiny":
                    usage.update(input_tokens=80, output_tokens=24)
                return response

        transport = CacheTransport()
        ledger = self.ledger(transport)
        for arm in ("fixed", "adaptive"):
            for index in range(18):
                transport.mode = "last-small" if index == 17 else "small"
                ledger.dispatch(f"p3a-01.{arm}.answer.{index:02}", "answer", request("answer"))
            transport.mode = "hour"
            role = "editor" if arm == "adaptive" else "fixed_selector"
            slot = "p3a-01.adaptive.editor.inv1.a1.t01" if arm == "adaptive" else "p3a-01.fixed.fixed_selector.00"
            ledger.dispatch(slot, role, request(role))
            transport.mode = "five"
            for index in range(18, 21):
                ledger.dispatch(f"p3a-01.{arm}.answer.{index:02}", "answer", request("answer"))
        before = a.replay(self.journal)
        self.assertEqual(before["first_pair"]["spent_micro_usd"], 39600000)
        self.assertTrue(all(before["cells"]["p3a-01:" + arm]["spent_micro_usd"] == 19800000
                            for arm in ("fixed", "adaptive")))
        self.assertLess(11440000, a.POLICY["first_assessment_micro_usd"])
        self.assertGreater(39600000 + 11440000, a.POLICY["first_micro_usd"])
        target = "p3a-01.assessment.00.quality.00"
        with self.assertRaises(a.CheckpointStop):
            ledger.dispatch(target, "quality", request("quality"))
        self.assertNotIn(target, a.replay(self.journal)["intents"])
        calls = len(transport.calls)
        a.publish_review(self.journal, review(a.replay(self.journal), closed=False), validate_evidence=lambda *_: None)
        transport.mode = "tiny"
        ledger.dispatch(target, "quality", request("quality"))
        self.assertEqual(len(transport.calls), calls + 1)
        self.assertEqual(ledger.dispatch(target, "quality", request("quality"))["status"], "response")
        self.assertEqual(len(transport.calls), calls + 1)
        transport.mode = "hour"
        for index in range(1, 5):
            ledger.dispatch(f"p3a-01.assessment.00.quality.{index:02}", "quality", request("quality"))
        assessed = a.replay(self.journal)
        self.assertEqual(assessed["assessment"]["spent_micro_usd"], 45761100)
        self.assertGreater(assessed["assessment"]["spent_micro_usd"], a.POLICY["first_assessment_micro_usd"])
        with self.assertRaises(a.AssessmentBudgetStop):
            ledger.dispatch("p3a-01.assessment.00.quality.05", "quality", request("quality"))
        self.assertEqual(a.replay(self.journal)["assessment"]["spent_micro_usd"], 45761100)

    def test_eighth_editor_turn_is_bounded_and_ninth_never_creates_an_intent(self):
        transport = Transport()
        ledger = self.ledger(transport)
        for turn in range(1, 9):
            ledger.dispatch(f"p3a-01.adaptive.editor.inv1.a1.t{turn:02}", "editor", request("editor"))
        with self.assertRaises(a.IntegrityStop):
            ledger.dispatch("p3a-01.adaptive.editor.inv1.a1.t09", "editor", request("editor"))
        self.assertEqual(len(transport.calls), 8)
        self.assertEqual(a.replay(self.journal)["attempts"], 8)

    def test_output_pool_is_independent_of_larger_configured_per_request_maxima(self):
        self.ledger()
        state = a.replay(self.journal)
        self.assertGreater(48 * 4096 + 48 * 16000, a.POLICY["cell_output"])
        # Independent guard check: another resource can bind earlier at current prices.
        state["cells"]["p3a-01:adaptive"]["output_tokens"] = 786432 - 1
        with self.assertRaises(a.CellBudgetStop):
            a._admit(state, self.slots["p3a-01.adaptive.plan.00"], a._reservation("plan"))
        self.assertEqual(a.replay(self.journal)["attempts"], 0)

    def test_editor_turn_binding_and_frozen_tools(self):
        read = {"name": "read", "description": "Read confined text", "input_schema": {"type": "object"}}
        ledger = self.ledger(editor_tools={"read": read})
        body = request("editor") | {"tools": [read]}
        ledger.dispatch("p3a-01.adaptive.editor.inv1.a1.t01", "editor", body)
        continued = copy.deepcopy(body)
        continued["messages"] += [{"role": "assistant", "content": [{"type": "tool_use", "id": "tool-1", "name": "read", "input": {"path": "task.md"}}]},
                                  {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "tool-1", "content": "task"}]}]
        ledger.dispatch("p3a-01.adaptive.editor.inv1.a1.t02", "editor", continued)
        with self.assertRaises(a.IntegrityStop):
            ledger.dispatch("p3a-01.adaptive.editor.inv1.a1.t04", "editor", continued)
        with self.assertRaises(ContractError):
            self.ledger(editor_tools={"bash": read | {"name": "bash"}})

    def test_external_boundary_halt_is_durable_without_inventing_a_charge(self):
        transport = Transport()
        ledger = self.ledger(transport)
        ledger.dispatch("p3a-01.fixed.plan.00", "plan", request())
        state = ledger.halt("fixture isolation violation", "6" * 64)
        self.assertEqual(state["status"], "halted-integrity")
        self.assertEqual(state["spent_micro_usd"], 400)
        self.assertEqual(state["reserved_micro_usd"], 0)
        with self.assertRaises(a.IntegrityStop):
            self.ledger(transport).dispatch("p3a-01.adaptive.plan.00", "plan", request())
        self.assertEqual(len(transport.calls), 1)

    def test_stream_tamper_and_concurrent_ownership_fail(self):
        ledger = self.ledger()
        ledger.dispatch("p3a-01.fixed.plan.00", "plan", request())
        path = self.journal / "events.jsonl"
        original = path.read_bytes()
        path.write_bytes(b" " + original)
        with self.assertRaises(ContractError):
            a.replay(self.journal)
        path.write_bytes(original[:-1])
        interrupted = a.replay(self.journal)
        self.assertEqual(interrupted["status"], "blocked-unknown")
        self.assertEqual(interrupted["reserved_micro_usd"], am1.reservation("plan"))
        with self.assertRaises(a.LiabilityStop):
            ledger.dispatch("p3a-01.fixed.plan.00", "plan", request())
        path.write_bytes(original)
        with writer_lock(self.journal), self.assertRaises(ContractError):
            ledger.dispatch("p3a-01.fixed.plan.01", "plan", request())

    def test_threads_queue_with_one_request_inflight(self):
        transport = Transport(fault="slow")
        ledger = self.ledger(transport)
        errors = []
        def dispatch(index):
            try:
                ledger.dispatch(f"p3a-01.fixed.answer.{index:02}", "answer", request("answer"))
            except BaseException as exc:
                errors.append(exc)
        threads = [threading.Thread(target=dispatch, args=(i,)) for i in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(transport.maximum_inflight, 1)
        self.assertEqual(a.replay(self.journal)["attempts"], 4)

    def test_retained_real_sdk_serialization_uses_same_accounting(self):
        with SDKMock(partition="pairs") as mock:
            ledger = self.ledger(mock.transport)
            result = ledger.dispatch("p3a-01.fixed.plan.00", "plan", request())
            self.assertEqual(result["status"], "response")
            self.assertEqual(mock.http_calls, 1)
            self.assertEqual(mock.records[0]["request"], request())
            self.assertEqual(ledger.dispatch("p3a-01.fixed.plan.00", "plan", request()), result)
            self.assertEqual(mock.http_calls, 1)

    def test_actual_sdk_editor_continuation_preserves_client_cache_fields(self):
        tools = {name: {"name": name, "description": "Confined fixture " + name,
                       "input_schema": {"type": "object"}} for name in ("read", "write", "edit")}
        with SDKMock() as mock:
            ledger = self.ledger(mock.transport, editor_tools=tools)
            body = request("editor") | {"system": [{"type": "text", "text": "Working directory: /tmp/phase3a-fixture"}],
                                        "tools": list(tools.values())}
            first = ledger.dispatch("p3a-01.adaptive.editor.inv1.a1.t01", "editor", body)
            self.assertEqual(first["status"], "response")
            calls = copy.deepcopy(first["response"]["provider_response"]["content"])
            calls[-1]["cache_control"] = {"type": "ephemeral"}
            outputs: list[dict] = [{"type": "tool_result", "tool_use_id": call["id"], "content": "fixture text"}
                                  for call in calls if call["type"] == "tool_use"]
            outputs[-1]["cache_control"] = {"type": "ephemeral", "ttl": "5m"}
            continued = copy.deepcopy(body)
            continued["messages"] += [{"role": "assistant", "content": calls}, {"role": "user", "content": outputs}]
            second = ledger.dispatch("p3a-01.adaptive.editor.inv1.a1.t02", "editor", continued)
            self.assertEqual(second["status"], "response")
            self.assertEqual(mock.http_calls, 2)
            self.assertEqual(mock.records[1]["request"]["messages"], continued["messages"])
            invalid = copy.deepcopy(continued)
            invalid["messages"][-1]["content"][-1]["cache_control"] = {"type": "ephemeral", "ttl": "1h"}
            with self.assertRaises(a.IntegrityStop):
                ledger.dispatch("p3a-01.adaptive.editor.inv1.a1.t03", "editor", invalid)
            self.assertEqual(mock.http_calls, 2)

    def test_saved_direct_caller_history_reaches_actual_sdk_without_wire_mutation(self):
        _, body, tools = saved_editor_history()
        self.assertEqual(history_tool(body)["caller"], {"type": "direct"})
        before = a._wire(body)
        a.validate_request("editor", body, editor_tools=tools)
        self.assertEqual(a._wire(body), before)
        with SDKMock() as mock:
            ledger = self.ledger(mock.transport, editor_tools=tools)
            result = ledger.dispatch("p3a-01.adaptive.editor.inv1.a1.t01", "editor", body)
            self.assertEqual(result["status"], "response")
            self.assertEqual(mock.http_calls, 1)
            self.assertEqual(a._wire(mock.records[0]["request"]), before)
            self.assertEqual(history_tool(mock.records[0]["request"])["caller"], {"type": "direct"})
            self.assertEqual(a._wire(body), before)

    def test_saved_history_accepts_absent_caller_and_rejects_every_other_variant(self):
        _, saved, tools = saved_editor_history()
        absent = copy.deepcopy(saved)
        history_tool(absent).pop("caller")
        before = a._wire(absent)
        a.validate_request("editor", absent, editor_tools=tools)
        self.assertEqual(a._wire(absent), before)
        for caller in (None, {}, {"type": "server"},
                       {"type": "code_execution_20250825", "tool_id": "srvtoolu-fixture"},
                       {"type": "direct", "extra": True}):
            with self.subTest(caller=caller):
                invalid = copy.deepcopy(saved)
                history_tool(invalid)["caller"] = caller
                original = a._wire(invalid)
                with self.assertRaisesRegex(ContractError, "only direct client-tool caller"):
                    a.validate_request("editor", invalid, editor_tools=tools)
                self.assertEqual(a._wire(invalid), original)
        invalid = copy.deepcopy(saved)
        history_tool(invalid)["extra"] = True
        original = a._wire(invalid)
        with self.assertRaisesRegex(ContractError, "invalid client tool call"):
            a.validate_request("editor", invalid, editor_tools=tools)
        self.assertEqual(a._wire(invalid), original)

    def test_unsupported_history_caller_halts_before_a_second_sdk_request(self):
        saved, continued, tools = saved_editor_history()
        history_tool(continued)["caller"] = {"type": "code_execution_20250825", "tool_id": "srvtoolu-fixture"}
        with SDKMock() as mock:
            ledger = self.ledger(mock.transport, editor_tools=tools)
            first = ledger.dispatch("p3a-01.adaptive.editor.inv1.a1.t01", "editor", saved["requests"][0])
            self.assertEqual(first["status"], "response")
            with self.assertRaises(a.IntegrityStop):
                ledger.dispatch("p3a-01.adaptive.editor.inv1.a1.t02", "editor", continued)
            state = a.replay(self.journal)
            self.assertEqual((state["status"], state["attempts"], state["reserved_micro_usd"]), ("halted-integrity", 1, 0))
            with self.assertRaises(a.IntegrityStop):
                self.ledger(mock.transport, editor_tools=tools).dispatch(
                    "p3a-01.adaptive.editor.inv1.a1.t02", "editor", saved["requests"][1])
            self.assertEqual(mock.http_calls, 1)


if __name__ == "__main__":
    unittest.main()
