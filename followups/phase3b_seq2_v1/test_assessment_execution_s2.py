"""Synthetic eight-head execution through the owned SDK transport; no live data."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest
from buddha2.phase2_contracts import make_portfolio
from tests.test_phase2_native import sample_portfolio

from . import assessment_execution as execution
from . import ledger_core as core
from . import native, support
from . import transport as bounded
from .deadline import Policy


def raw_quality(score=6, *, unknown_usage=False):
    return {"id": "synthetic-assessment", "type": "message", "role": "assistant",
        "model": "claude-opus-5", "content": [{"type": "text", "text": json.dumps({"score": score})}],
        "stop_reason": "end_turn", "stop_sequence": None,
        "usage": {"input_tokens": 80, "output_tokens": 24, "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0, "cache_creation": {
                "ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 0},
            "service_tier": "standard", "inference_geo": "unsupported" if unknown_usage else "global"}}


def synthetic_parent(*, fixture=True):
    """Construct new unit records, including the nonfixture branch; never relabel saved data."""
    evaluator = native.Phase3NativeAssessment(support.ROOT / ".upstream/novelty-bench")
    seed = sample_portfolio("A")
    provenance = seed["provenance"]
    model = provenance["model"] if fixture else {
        "requested": "claude-sonnet-5-5", "returned": "claude-sonnet-5-5"}
    portfolios, worklist, originals, missing, complete, targets = {}, [], {}, {}, {}, []
    for target in ("fixed", "c1", "c2"):
        responses = [{**row, "text": f"Synthetic {target} answer {i}"}
                     for i, row in enumerate(seed["responses"])]
        portfolio = make_portfolio(seed["task"], responses, method="A", repeat=1, model=model,
            settings_sha256=provenance["settings_sha256"], procedure_sha256=provenance["procedure_sha256"],
            request_ids=provenance["request_ids"], study_sha256=execution.reuse.PARENT_STUDY,
            fixture=fixture)
        portfolios[target] = portfolio
        assessment_id = f"synthetic-original:p3b-01:{target}:candidate"
        targets.append({"target": target, "assessment_id": assessment_id,
                        "portfolio_sha256": digest(portfolio)})
        prefix = evaluator.slot_prefix(assessment_id)
        requests = [(prefix + ".group", "group", evaluator.group_request(portfolio))]
        requests += [(f"{prefix}.quality.{i:02}", "quality", body)
                     for i, body in enumerate(evaluator.quality_requests(portfolio, list(range(10))))]
        manifest = {"inputs": {"study_sha256": execution.reuse.PARENT_STUDY, "fixture": fixture,
            "slots": {slot: {"role": role, "cell": "assessment", "pair": "p3b-01"}
                      for slot, role, _ in requests}}}
        manifest["run_id"] = digest(manifest["inputs"])
        all_results = []
        for index, (slot, role, body) in enumerate(requests, 1):
            raw = raw_quality()
            if role == "group":
                raw = {"id": "synthetic-group", "model": body["model"], "service_tier": "default",
                    "choices": [{"message": {"content": json.dumps({"groups": [[i] for i in range(10)]}),
                                               "refusal": None}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 40, "completion_tokens": 5, "total_tokens": 45,
                        "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0}}}
            intent = core._intent(manifest, slot, body, index)
            result = core._result(intent, bounded.normalize(role, raw, "synthetic-request", 0.0))
            if result["status"] != "response":
                raise AssertionError("synthetic usage must have complete accounting")
            all_results.append(result)
            pending = target == "c2" and role == "quality" and index >= 4
            row = {"slot_id": slot, "role": role, "target": target, "request_sha256": digest(body),
                   "disposition": "pending" if pending else "reuse"}
            if pending:
                row["request"] = body
                missing[slot] = result
            else:
                row["result_sha256"] = digest(result)
                originals[slot] = result
            worklist.append(row)
        if target != "c2":
            complete[target] = digest(evaluator.finalize(portfolio, all_results[0], all_results[1:],
                                                        assessment_id=assessment_id))
    packet = support.seal({"kind": execution.reuse.KIND, "targets": targets, "worklist": worklist,
        "complete_cached_assessments": complete, "selected_checkpoint": "c1"})
    return packet, originals, missing, portfolios, evaluator


class AssessmentExecutionTests(unittest.TestCase):
    def setUp(self):
        support.BASE.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="assessment-execution-unit-", dir=support.BASE)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.run_root, self.journal = self.root / "new-native", self.root / "new-journal"
        self.packet, self.originals, self.missing, self.portfolios, self.evaluator = synthetic_parent()
        body = {"kind": execution.KIND, "packet_path": "runs/synthetic-assessment-packet.json",
            "assessment_packet_sha256": self.packet["sha256"],
            "generation_study_sha256": execution.reuse.PARENT_STUDY, "source_sha256": "a" * 64,
            "runtime_sha256": "b" * 64, "policy_sha256": digest(execution.POLICY),
            "launcher_sha256": "c" * 64, "authority_sha256": digest(execution.AUTHORITY),
            "pending": [copy.deepcopy(row) for row in self.packet["worklist"]
                        if row["disposition"] == "pending"]}
        self.study = {**body, "study_sha256": digest(body)}
        self.grant = support.seal({"kind": execution.KIND + "-grant",
            "study_sha256": self.study["study_sha256"], "fixture": True, "authority": execution.AUTHORITY})
        self.study_path, self.grant_path = self.root / "study.json", self.root / "grant.json"
        self.study_path.write_text(json.dumps(self.study), encoding="utf-8")
        self.grant_path.write_text(json.dumps(self.grant), encoding="utf-8")
        self.load_patch = patch.object(execution, "_load", side_effect=lambda *_: (self.study, self.grant))
        self.load_patch.start()
        self.addCleanup(self.load_patch.stop)
        for value in (patch.object(execution, "_packet", return_value=self.packet),
                      patch.object(execution, "_saved", return_value=(self.originals, self.portfolios, self.evaluator)),
                      patch.object(execution, "_paths", return_value=(self.run_root, self.journal)),
                      patch.object(execution, "PACKET_SHA", self.packet["sha256"])):
            value.start()
            self.addCleanup(value.stop)
        self.http_calls = []

    def transport(self, *, unknown_usage=False):
        import httpx
        import httpx2

        def response(request):
            self.http_calls.append(json.loads(request.content))
            return httpx2.Response(200, json=raw_quality(unknown_usage=unknown_usage),
                                   headers={"request-id": "synthetic-assessment-request"})

        value = bounded.Transport(anthropic_api_key="fixture-not-a-secret", openai_api_key="fixture-not-a-secret",
            http_transports={"anthropic": httpx2.MockTransport(response),
                "openai": httpx.MockTransport(lambda _: (_ for _ in ()).throw(AssertionError("wrong provider")))},
            fixture_policy=Policy(completion=30, cleanup=5, editor_margin=.01, editor_minimum=.01))
        self.addCleanup(value.close)
        return value

    def test_eight_sdk_calls_replay_without_resend_and_audits_stay_in_fresh_namespace(self):
        old_audit_lookup = patch.object(bounded, "audit_path", side_effect=AssertionError("old audit namespace"))
        with old_audit_lookup:
            result = execution.run(self.study_path, self.grant_path, "all", self.transport())
            self.assertEqual((result["status"], result["new_attempts"], result["reserved_micro_usd"]),
                             ("mock-completed", 8, 0))
            self.assertEqual(len(self.http_calls), 8)
            self.assertTrue(all(body["model"] == "claude-opus-5" for body in self.http_calls))
            first = execution.report(self.study_path, self.grant_path)
            self.assertEqual(first["assessments"], {})
            self.assertEqual(first["provider_calls"], 0)
            self.assertFalse(first["four_prompt_comparison_complete"])
            journal_before = (self.journal / "events.jsonl").read_bytes()
            self.assertEqual(execution.run(self.study_path, self.grant_path, "all", self.transport()), result)
            self.assertEqual(execution.report(self.study_path, self.grant_path), first)
            self.assertEqual(len(self.http_calls), 8)
            self.assertEqual((self.journal / "events.jsonl").read_bytes(), journal_before)
        self.assertEqual(len(list((self.run_root / "transport-audit").glob("*.json"))), 8)
        audit = execution._audit_path(self.run_root, self.study["pending"][0]["slot_id"])
        original = audit.read_bytes()
        for field, changed in (("source_sha256", "f" * 64), ("role", "group")):
            with self.subTest(field=field):
                body = json.loads(original)
                body[field] = changed
                body = support.seal({key: value for key, value in body.items() if key != "sha256"})
                audit.write_text(json.dumps(body), encoding="utf-8")
                with self.assertRaises(ContractError):
                    execution.report(self.study_path, self.grant_path)
                audit.write_bytes(original)
        self.assertEqual(len(self.http_calls), 8)

    def test_resealed_changed_body_source_or_role_rejects_before_execution(self):
        self.load_patch.stop()
        frozen_body = {key: value for key, value in self.study.items() if key != "study_sha256"}
        for change in ("body", "source", "role"):
            altered = copy.deepcopy(self.study)
            if change == "body":
                altered["pending"][0]["request"]["messages"][0]["content"] = "changed synthetic request"
            elif change == "source":
                altered["source_sha256"] = "d" * 64
            else:
                altered["pending"][0]["role"] = "group"
            altered["study_sha256"] = digest({key: value for key, value in altered.items()
                                               if key != "study_sha256"})
            self.study_path.write_text(json.dumps(altered), encoding="utf-8")
            with self.subTest(change=change), patch.object(support, "runtime_guard"), \
                    patch.object(execution, "_body", return_value=frozen_body), \
                    self.assertRaisesRegex(ContractError, "execution source or saved requests changed"):
                execution._load(self.study_path, self.grant_path)
        self.assertFalse(self.journal.exists())
        self.assertEqual(self.http_calls, [])

    def test_preflight_supplies_the_existing_windows_provider_handshake_fields(self):
        value = execution.preflight(self.study_path, self.grant_path, "all", "preflight")
        for field in ("cap_micro_usd", "first_pair_cap_micro_usd", "readiness_included_micro_usd"):
            self.assertIs(type(value[field]), int)
        self.assertEqual(value["readiness_included_micro_usd"], 0)
        self.assertEqual(value["cap_micro_usd"], execution.POLICY["cap_micro_usd"])
        self.assertEqual(value["study_sha256"], self.study["study_sha256"])
        self.assertEqual(value["grant_sha256"], self.grant["sha256"])

    def test_unfinished_intent_holds_reservation_and_is_never_resent(self):
        manifest = execution._manifest(self.study, self.grant)
        core._publish(self.journal / "manifest.json", manifest)
        row = self.study["pending"][0]
        core._append_event(self.journal, "intent", core._intent(manifest, row["slot_id"], row["request"], 1), [])
        before = (self.journal / "events.jsonl").read_bytes()
        for _ in range(2):
            result = execution.run(self.study_path, self.grant_path, "all", self.transport())
            self.assertEqual((result["status"], result["new_attempts"], result["reserved_micro_usd"]),
                             ("incomplete", 1, 11_440_000))
        self.assertEqual(self.http_calls, [])
        self.assertEqual((self.journal / "events.jsonl").read_bytes(), before)

    def test_unknown_sdk_usage_holds_full_reservation_and_prevents_resend(self):
        result = execution.run(self.study_path, self.grant_path, "all", self.transport(unknown_usage=True))
        self.assertEqual((result["status"], result["new_attempts"], result["reserved_micro_usd"]),
                         ("incomplete", 1, 11_440_000))
        self.assertEqual(len(self.http_calls), 1)
        before = (self.journal / "events.jsonl").read_bytes()
        self.assertEqual(execution.run(self.study_path, self.grant_path, "all", self.transport()), result)
        self.assertEqual(len(self.http_calls), 1)
        self.assertEqual((self.journal / "events.jsonl").read_bytes(), before)

    def test_cap_stop_and_fixture_live_mismatch_never_send(self):
        policy = {**execution.POLICY, "cap_micro_usd": core._reservation("quality")["micro_usd"] - 1}
        with patch.object(execution, "POLICY", policy):
            result = execution.run(self.study_path, self.grant_path, "all", self.transport())
        self.assertEqual((result["status"], result["new_attempts"]), ("incomplete", 0))
        self.assertEqual(self.http_calls, [])
        self.grant = {**self.grant, "fixture": False}
        with self.assertRaises(ContractError):
            execution.run(self.study_path, self.grant_path, "all", self.transport())
        self.assertEqual(self.http_calls, [])

    def test_nonfixture_report_branch_folds_only_new_synthetic_unit_records(self):
        # This is a pure branch test: all dictionaries below are newly generated test data,
        # not mocked calls relabelled as live evidence or outputs eligible for publication.
        packet, saved, missing, portfolios, evaluator = synthetic_parent(fixture=False)
        grant = {**self.grant, "fixture": False}
        state = {"status": "ready", "attempts": 8, "spent_micro_usd": sum(
            row["spent_micro_usd"] for row in missing.values()), "reserved_micro_usd": 0,
            "results": missing}
        with patch.object(execution, "_load", return_value=(self.study, grant)), \
                patch.object(execution, "_replay", return_value=(state, [], {})), \
                patch.object(execution, "_saved", return_value=(saved, portfolios, evaluator)), \
                patch.object(execution, "_packet", return_value=packet):
            result = execution.report(self.study_path, self.grant_path)
        self.assertEqual(result["status"], "assessed")
        self.assertEqual(set(result["assessments"]), {"fixed", "c1", "c2"})
        self.assertTrue(all(value["status"] == "scored" for value in result["assessments"].values()))
        self.assertEqual({key: digest(result["assessments"][key]) for key in ("fixed", "c1")},
                         packet["complete_cached_assessments"])
        self.assertFalse(result["closed_parent_changed"])
        self.assertFalse(result["four_prompt_comparison_complete"])
        self.assertEqual(self.http_calls, [])


if __name__ == "__main__":
    unittest.main()
