"""Capacity trust boundaries and independent liabilities; full observed fixture is a gate command."""
from __future__ import annotations

import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from buddha2 import phase2_am1_controls as am1
from buddha2 import phase2_contracts as portfolio_contract
from buddha2.artifacts import ContractError, digest
from buddha2.phase2_native import NativeAssessment
from tests.test_phase2_native import sample_portfolio

from . import capacity, ledger_core, workflow
from .mocks import _metadata_reads
from .support import BASE, READINESS_BINDINGS


def request() -> dict:
    return {"model": "claude-opus-5", "max_tokens": 16000, "thinking": {"type": "adaptive"},
        "output_config": {"effort": "high"}, "service_tier": "standard_only", "inference_geo": "global",
        "system": "Synthetic byte admission fixture only.", "messages": [{"role": "user", "content": "input"}]}


class CapacityS2Tests(unittest.TestCase):
    def test_large_metadata_pages_cover_every_unchanged_line(self):
        BASE.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="capacity-metadata-", dir=BASE))
        target = root / "context/C1_MANIFEST.json"
        target.parent.mkdir(parents=True)
        lines = [f"synthetic bounded metadata line {number}" for number in range(2317)]
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        calls = _metadata_reads(root, "C1_MANIFEST.json", "metadata")
        numbers = [number for _, name, row in calls for number in range(row["offset"], row["offset"] + row["limit"])]
        self.assertEqual(numbers, list(range(1, len(lines) + 1)))
        self.assertTrue(all(row["limit"] <= 128 for _, name, row in calls))
        self.assertTrue(all(name == "read" for _, name, row in calls))
        self.assertEqual(target.read_text(encoding="utf-8"), "\n".join(lines) + "\n")

    def test_actual_boundary_rejects_all_three_roles_before_sdk_or_intent(self):
        sdk = capacity.CapacitySDK("0" * 64)
        for role in ("editor", "native_selector", "fixed_selector"):
            proof = capacity._boundary(request(), role, sdk)
            self.assertEqual(proof["exact_bytes"], 2_097_152)
            self.assertEqual(proof["oversize_bytes"], 2_097_153)
            self.assertTrue(proof["rejected_before_intent"])
        self.assertEqual(sdk.sdk_calls, 0)
        self.assertEqual(sdk.intents, {})
        self.assertEqual(sdk.rejects, 3)

    def test_source_scope_rejects_reports_and_unexposed_pilot_before_metadata(self):
        sources = [capacity.PARENT_LIVE / "reports/final/grades.json",
                   capacity.PARENT_LIVE / "search/p3a-05/adaptive/identity.json",
                   capacity.PARENT_LIVE / "search/p3a-01/adaptive/grades.json"]
        for source in sources:
            with patch.object(Path, "lstat", side_effect=AssertionError("forbidden source metadata")):
                with self.assertRaises(ContractError):
                    capacity._copy(source, Path("/unwritten"), {})

    def test_model_liability_is_not_the_serialized_byte_bound(self):
        self.assertEqual(ledger_core.POLICY["editor_payload_bytes"], 2_097_152)
        for role in ("editor", "native_selector", "fixed_selector"):
            reserve = ledger_core._reservation(role)
            self.assertEqual(reserve["input"], 1_000_000)
            self.assertEqual(reserve["output"], 16_000)
            self.assertEqual(reserve["micro_usd"], 11_440_000)


@unittest.skipUnless(os.environ.get("BUDDHA2_NB_UPSTREAM"), "requires supported native environment")
class EvaluatorAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.native = NativeAssessment(Path(os.environ["BUDDHA2_NB_UPSTREAM"]))

    def test_quality_request_at_saved_failure_size_is_admitted(self):
        portfolio = sample_portfolio()
        request = self.native.quality_requests(portfolio, list(range(10)))[2]
        portfolio["responses"][2]["text"] += "x" * (6206 - len(ledger_core._wire(request)))
        portfolio["portfolio_id"] = "portfolio-" + digest(
            {k: v for k, v in portfolio.items() if k != "portfolio_id"})
        request = self.native.quality_requests(portfolio, list(range(10)))[2]
        self.assertEqual(len(ledger_core._wire(request)), 6206)
        self.assertFalse(am1.admitted("quality", request))
        ledger_core.validate_request("quality", request)

    def test_native_requests_cover_entire_allowed_portfolio_text_envelope(self):
        for character in ("x", "\U0001f600", "\x01", '"', "\\"):
            with self.subTest(character=repr(character)):
                portfolio = sample_portfolio()
                portfolio["task"]["prompt"] = character * portfolio_contract.MAX_PROMPT_CHARS
                for response in portfolio["responses"]:
                    response["text"] = character * portfolio_contract.MAX_RESPONSE_CHARS
                portfolio["portfolio_id"] = "portfolio-" + digest(
                    {k: v for k, v in portfolio.items() if k != "portfolio_id"})
                group = self.native.group_request(portfolio)
                ledger_core.validate_request("group", group)
                for request in self.native.quality_requests(portfolio, list(range(10))):
                    ledger_core.validate_request("quality", request)

    def test_evaluator_size_boundaries_and_frozen_profiles(self):
        portfolio = sample_portfolio()
        requests = {"group": self.native.group_request(portfolio),
                    "quality": self.native.quality_requests(portfolio, list(range(10)))[0]}
        for role, request in requests.items():
            with self.subTest(role=role):
                limit = ledger_core.POLICY["evaluator_payload_bytes"][role]
                request["messages"][-1]["content"] += "x" * (limit - len(ledger_core._wire(request)))
                self.assertEqual(len(ledger_core._wire(request)), limit)
                ledger_core.validate_request(role, request)
                request["messages"][-1]["content"] += "x"
                with self.assertRaisesRegex(ContractError, "payload"):
                    ledger_core.validate_request(role, request)
                changed = copy.deepcopy(requests[role])
                changed["model"] = "substituted-model"
                with self.assertRaisesRegex(ContractError, "frozen profile"):
                    ledger_core.validate_request(role, changed)
        quality = self.native.quality_requests(portfolio, list(range(10)))[0]
        quality["max_tokens"] *= 2
        with self.assertRaisesRegex(ContractError, "frozen profile"):
            ledger_core.validate_request("quality", quality)

    def test_evaluator_reservations_and_legacy_limits_are_unchanged(self):
        self.assertEqual(am1.CONTROL_POLICY["payload_utf8_bytes"],
                         {"answer": 5952, "plan": 5952, "rank": 61952,
                          "group": 61952, "quality": 5952})
        for role in ("group", "quality"):
            self.assertEqual(ledger_core._reservation(role)["micro_usd"], am1.reservation(role))
            self.assertEqual(ledger_core._reservation(role)["input"],
                             am1.CONTROL_POLICY["maximum_billable_input"][role])
            self.assertEqual(ledger_core._reservation(role)["output"],
                             am1.CONTROL_POLICY["reserved_total_output"][role])

    def test_preflight_rejects_changed_producer_limit_without_consumer_change(self):
        original = sample_portfolio()["task"]
        study = {"fixture_boundary_contract": False, "tasks": [{
            "parent_task_id": original["id"], "prompt": original["prompt"],
            "source_context": original["source_context"]}],
            **{key: "a" * 64 for key in READINESS_BINDINGS}}
        BASE.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="contract-preflight-", dir=BASE) as raw:
            root = Path(raw)
            with patch.object(workflow, "load_study", return_value=study), \
                    patch.object(workflow, "grant_for", return_value={}), \
                    patch.object(workflow, "paths", return_value=(root / "run", root / "journal")), \
                    patch.object(workflow, "offline_readiness") as gate, \
                    patch.object(workflow, "_state", side_effect=AssertionError("accounting reached")) as state:
                with self.assertRaisesRegex(AssertionError, "accounting reached"):
                    workflow.preflight(root / "study.json", root / "grant.json", False)
                gate.assert_called_once()
                ceilings = copy.deepcopy(ledger_core.POLICY["evaluator_payload_bytes"])
                changed_limits = {
                    "MAX_PROMPT_CHARS": max(portfolio_contract.MAX_PROMPT_CHARS + 1,
                                            ceilings["quality"] // 6 + 1),
                    "MAX_RESPONSE_CHARS": max(portfolio_contract.MAX_RESPONSE_CHARS + 1,
                        ceilings["group"] // (6 * len(sample_portfolio()["responses"])) + 1),
                }
                for field, value in changed_limits.items():
                    with self.subTest(field=field), patch.object(portfolio_contract, field, value):
                        state.reset_mock()
                        with self.assertRaisesRegex(ContractError, "payload admission"):
                            workflow.preflight(root / "study.json", root / "grant.json", False)
                        state.assert_not_called()
                        self.assertEqual(ledger_core.POLICY["evaluator_payload_bytes"], ceilings)


if __name__ == "__main__":
    unittest.main()
