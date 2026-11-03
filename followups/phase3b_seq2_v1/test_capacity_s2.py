"""Capacity trust boundaries and independent liabilities; full observed fixture is a gate command."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError

from . import capacity, ledger_core
from .mocks import _metadata_reads
from .support import BASE


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


if __name__ == "__main__":
    unittest.main()
